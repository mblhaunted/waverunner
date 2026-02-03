/**
 * Waverunner Dashboard - Main logic
 *
 * Handles:
 * - WebSocket connection to event stream
 * - D3.js dependency graph visualization
 * - Task status cards
 * - Metrics display
 * - Wave progress
 */

class WaverunnerDashboard {
    constructor() {
        this.ws = null;
        this.graph = null;
        this.simulation = null;
        this.tasks = new Map();
        this.waves = [];
        this.currentWave = 0;
        this.totalTasks = 0;
        this.completedTasks = 0;
        this.startTime = null;
        this.reaperKills = 0;

        this.initWebSocket();
        this.initGraph();
        this.startMetricsUpdate();
    }

    initWebSocket() {
        const wsUrl = 'ws://localhost:3001';
        console.log('Connecting to', wsUrl);

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('Dashboard connected!');
            this.updateConnectionStatus(true);
        };

        this.ws.onclose = () => {
            console.log('Dashboard disconnected');
            this.updateConnectionStatus(false);
            // Attempt reconnect after 2 seconds
            setTimeout(() => this.initWebSocket(), 2000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus(false);
        };

        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleEvent(message);
            } catch (error) {
                console.error('Error parsing message:', error);
            }
        };
    }

    updateConnectionStatus(connected) {
        const status = document.getElementById('connection-status');
        status.className = connected ? 'connected' : 'disconnected';
    }

    handleEvent(message) {
        const { type, data } = message;
        console.log('Event:', type, data);

        switch(type) {
            case 'sprint_started':
                this.handleSprintStarted(data);
                break;
            case 'wave_plan_created':
                this.handleWavePlan(data);
                break;
            case 'wave_started':
                this.handleWaveStarted(data);
                break;
            case 'task_started':
                this.handleTaskStarted(data);
                break;
            case 'task_progress':
                this.handleTaskProgress(data);
                break;
            case 'task_completed':
                this.handleTaskCompleted(data);
                break;
            case 'task_failed':
                this.handleTaskFailed(data);
                break;
            case 'reaper_kill_triggered':
                this.handleReaperKill(data);
                break;
            case 'sprint_completed':
                this.handleSprintCompleted(data);
                break;
        }
    }

    handleSprintStarted(data) {
        this.startTime = Date.now();
        this.totalTasks = data.total_tasks || 0;
        this.completedTasks = 0;
        this.reaperKills = 0;

        // Initialize tasks
        if (data.tasks) {
            data.tasks.forEach(task => {
                this.tasks.set(task.id, {
                    ...task,
                    status: 'pending',
                    progress: 0
                });
            });
            this.updateGraph();
        }
    }

    handleWavePlan(data) {
        this.waves = data.waves || [];
        document.getElementById('total-waves').textContent = this.waves.length;
        this.updateWaveTimeline();
    }

    handleWaveStarted(data) {
        this.currentWave = data.wave_number || 0;
        document.getElementById('current-wave').textContent = this.currentWave;
        document.getElementById('wave-progress').textContent = `${this.currentWave}/${this.waves.length}`;
        this.updateWaveTimeline();
    }

    handleTaskStarted(data) {
        const task = this.tasks.get(data.task_id);
        if (task) {
            task.status = 'running';
            task.started_at = data.started_at;
            this.updateTaskCard(task);
            this.updateGraphNode(data.task_id, 'running');
        }
    }

    handleTaskProgress(data) {
        const task = this.tasks.get(data.task_id);
        if (task) {
            task.progress = data.progress_pct || 0;
            task.last_output = data.output_line;
            this.updateTaskCard(task);
        }
    }

    handleTaskCompleted(data) {
        const task = this.tasks.get(data.task_id);
        if (task) {
            task.status = 'completed';
            task.completed_at = data.completed_at;
            task.artifacts = data.artifacts;
            this.completedTasks++;

            this.updateTaskCard(task);
            this.updateGraphNode(data.task_id, 'completed');
            this.updateProgress();

            // Animate wave particle from this task to dependents
            this.animateTaskCompletion(data.task_id);
        }
    }

    handleTaskFailed(data) {
        const task = this.tasks.get(data.task_id);
        if (task) {
            task.status = 'failed';
            task.error = data.error;
            this.updateTaskCard(task);
            this.updateGraphNode(data.task_id, 'failed');
        }
    }

    handleReaperKill(data) {
        this.reaperKills++;
        document.getElementById('reaper-kills').textContent = this.reaperKills;

        // Flash the reaper metric
        const reaperMetric = document.getElementById('reaper-kills');
        reaperMetric.style.color = '#ff006e';
        setTimeout(() => {
            reaperMetric.style.color = '';
        }, 1000);
    }

    handleSprintCompleted(data) {
        // Show completion animation
        console.log('Sprint completed!', data);
    }

    // Graph Management
    initGraph() {
        const svg = d3.select('#dependency-graph');
        const container = document.getElementById('graph-container');
        const width = container.clientWidth;
        const height = container.clientHeight;

        svg.attr('width', width).attr('height', height);

        // Create force simulation
        this.simulation = d3.forceSimulation()
            .force('link', d3.forceLink().id(d => d.id).distance(150))
            .force('charge', d3.forceManyBody().strength(-400))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(50));

        // Create groups for links and nodes
        svg.append('g').attr('class', 'links');
        svg.append('g').attr('class', 'nodes');
    }

    updateGraph() {
        const tasks = Array.from(this.tasks.values());
        const links = [];

        // Build links from dependencies
        tasks.forEach(task => {
            if (task.dependencies) {
                task.dependencies.forEach(depId => {
                    links.push({
                        source: depId,
                        target: task.id
                    });
                });
            }
        });

        const svg = d3.select('#dependency-graph');

        // Update links
        const linkSelection = svg.select('.links')
            .selectAll('line')
            .data(links, d => `${d.source}-${d.target}`);

        linkSelection.enter()
            .append('line')
            .attr('class', 'link')
            .merge(linkSelection);

        linkSelection.exit().remove();

        // Update nodes
        const nodeSelection = svg.select('.nodes')
            .selectAll('g')
            .data(tasks, d => d.id);

        const nodeEnter = nodeSelection.enter()
            .append('g')
            .attr('class', d => `node ${d.status}`)
            .call(d3.drag()
                .on('start', (event, d) => this.dragStarted(event, d))
                .on('drag', (event, d) => this.dragging(event, d))
                .on('end', (event, d) => this.dragEnded(event, d)));

        nodeEnter.append('circle')
            .attr('r', 30);

        nodeEnter.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', 4)
            .text(d => d.title?.substring(0, 10) || d.id);

        nodeSelection.merge(nodeEnter)
            .attr('class', d => `node ${d.status}`);

        nodeSelection.exit().remove();

        // Update simulation
        this.simulation
            .nodes(tasks)
            .on('tick', () => this.ticked());

        this.simulation.force('link')
            .links(links);

        this.simulation.alpha(1).restart();
    }

    updateGraphNode(taskId, status) {
        const task = this.tasks.get(taskId);
        if (task) {
            task.status = status;
            d3.select('#dependency-graph')
                .selectAll('.node')
                .filter(d => d.id === taskId)
                .attr('class', `node ${status}`);
        }
    }

    ticked() {
        const svg = d3.select('#dependency-graph');

        svg.selectAll('.link')
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        svg.selectAll('.node')
            .attr('transform', d => `translate(${d.x},${d.y})`);
    }

    dragStarted(event, d) {
        if (!event.active) this.simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    dragging(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    dragEnded(event, d) {
        if (!event.active) this.simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    animateTaskCompletion(taskId) {
        // Find completed task position
        const node = this.simulation.nodes().find(n => n.id === taskId);
        if (!node) return;

        // Find dependent tasks
        const dependents = Array.from(this.tasks.values())
            .filter(t => t.dependencies && t.dependencies.includes(taskId));

        // Animate particles to each dependent
        dependents.forEach(dep => {
            const depNode = this.simulation.nodes().find(n => n.id === dep.id);
            if (depNode && window.waveParticles) {
                window.waveParticles.addWaveParticle(node.x, node.y, depNode.x, depNode.y);
            }
        });
    }

    // Task Cards
    updateTaskCard(task) {
        const container = document.getElementById('task-cards');
        let card = document.getElementById(`task-${task.id}`);

        if (!card && task.status === 'running') {
            card = document.createElement('div');
            card.id = `task-${task.id}`;
            card.className = `task-card ${task.status}`;
            container.appendChild(card);
        }

        if (card) {
            card.className = `task-card ${task.status}`;
            card.innerHTML = `
                <h4>${task.title || task.id}</h4>
                <div class="task-status">${task.status.toUpperCase()}</div>
                <div class="task-progress">${task.progress || 0}%</div>
                ${task.last_output ? `<div class="task-output">${task.last_output}</div>` : ''}
            `;

            // Remove completed/failed cards after animation
            if (task.status === 'completed' || task.status === 'failed') {
                setTimeout(() => {
                    card.style.opacity = '0';
                    setTimeout(() => card.remove(), 500);
                }, 2000);
            }
        }
    }

    // Wave Timeline
    updateWaveTimeline() {
        const timeline = document.getElementById('wave-timeline');
        timeline.innerHTML = this.waves.map((wave, idx) => {
            const active = idx + 1 === this.currentWave ? 'active' : '';
            const completed = idx + 1 < this.currentWave ? 'completed' : '';
            return `<span class="wave-badge ${active} ${completed}">Wave ${idx + 1}</span>`;
        }).join('');
    }

    // Progress & Metrics
    updateProgress() {
        const percent = this.totalTasks > 0 ? (this.completedTasks / this.totalTasks * 100) : 0;
        document.getElementById('progress-bar').style.width = `${percent}%`;
        document.getElementById('progress-text').textContent = `${Math.round(percent)}%`;
        document.getElementById('tasks-progress').textContent = `${this.completedTasks}/${this.totalTasks}`;
    }

    startMetricsUpdate() {
        setInterval(() => {
            if (this.startTime) {
                const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
                const minutes = Math.floor(elapsed / 60);
                const seconds = elapsed % 60;
                document.getElementById('elapsed').textContent =
                    `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }

            // Update parallel count
            const runningTasks = Array.from(this.tasks.values())
                .filter(t => t.status === 'running').length;
            document.getElementById('parallel-count').textContent = runningTasks;
        }, 1000);
    }
}

// Initialize dashboard on load
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new WaverunnerDashboard();
});
