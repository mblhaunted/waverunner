# Waverunner TODO

## High Priority - Visualization Dashboard

### Real-Time Wave Visualization Dashboard
**Goal:** Make wave parallelism visible and shareable to capture tech enthusiast imagination.

**What it is:**
A local web UI (`:3000`) that visualizes waverunner execution in real-time.

**Features:**
- **Dependency Graph Visualization** (D3.js force-directed graph)
  - Nodes = tasks (colored by status: pending/running/completed/failed)
  - Edges = dependencies
  - Animated: watch waves cascade through the graph

- **Wave Timeline**
  - Visual representation of waves executing sequentially
  - Show parallelism: "Wave 1: 3 tasks running concurrently"
  - Highlight current wave, dim completed waves

- **Live Task Outputs**
  - Column layout showing terminal output from each running task
  - Color-coded by task status
  - Scrollable console for each task

- **Metrics Sidebar**
  - Total elapsed time vs estimated sequential time
  - Parallelism factor (e.g., "3.75x faster")
  - Reaper kills count
  - Re-estimations performed
  - Current wave / total waves

- **Reaper Visibility**
  - Tasks turn red when Reaper kills them
  - Show kill reason as tooltip
  - Display re-estimation discussions in real-time
  - Visual indicator when Reaper is analyzing a task

**CLI Integration:**
```bash
waverunner go "goal" --dashboard  # Opens browser at localhost:3000
```

**Why This Matters:**
- Visual proof of parallelism value
- Instantly shareable (screenshots/videos go viral)
- Educational - watching teaches parallel thinking
- Tech catnip - animated graphs + real-time execution
- Quantifiable value displayed (speedup metrics)

**Implementation Notes:**
- Backend: WebSocket server in waverunner (emit events on task status changes)
- Frontend: React/Vue + D3.js for graph visualization
- Real-time updates: WebSocket connection from browser to waverunner process
- Graph layout: Force-directed for dependency visualization
- Persistent across iterations (show iteration 1, 2, 3 timeline)

**Success Metric:**
Someone posts: "Watch waverunner execute 20 tasks in 5min that would take 30min sequentially" with animated graph - tech Twitter explodes.

---

## Medium Priority

### Distributed Wave Execution
Execute waves across multiple machines/cloud workers for even more parallelism.

### Agent Replay/Debugging
Pause execution mid-wave, inspect task state, modify and resume.

### Performance Profiling
Detailed analysis of where time is spent, bottleneck identification.
