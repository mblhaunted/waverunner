"""
Live streaming dashboard for waverunner.

Shows all agents working in real-time with progress bars, live output, and metrics.
"""

import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.layout import Layout
from rich.console import Group
from rich.table import Table
from rich.text import Text
from rich import box

from .models import Task, TaskStatus
from . import ui


@dataclass
class TaskState:
    """State of a running task for the dashboard."""
    task: Task
    persona_name: str
    status: str  # 'running', 'complete', 'failed', 'queued'
    progress: int  # 0-100
    latest_output: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    error: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)


class LiveDashboard:
    """Real-time dashboard showing all agents working simultaneously."""

    def __init__(self, total_tasks: int, show_live: bool = True):
        self.tasks: Dict[str, TaskState] = {}
        self.total_tasks = total_tasks
        self.completed_count = 0
        self.failed_count = 0
        self.start_time = time.time()
        self.total_cost = 0.0
        self.total_tokens = 0
        self.cumulative_task_seconds = 0  # Track total task time for cost estimation
        self.show_live = show_live
        self.current_wave = 1
        self.lock = threading.RLock()  # RLock allows same thread to acquire multiple times
        self.live: Optional[Live] = None

    def _get_renderable(self):
        """Called by Rich on each refresh cycle to pull current state."""
        with self.lock:
            return self._render_locked()

    def start(self):
        """Start the live dashboard."""
        if not self.show_live:
            return

        self.live = Live(
            self._get_renderable(),
            refresh_per_second=4,
            screen=False,
            auto_refresh=True,
            get_renderable=self._get_renderable,
        )
        self.live.start()

    def stop(self):
        """Stop the live dashboard."""
        if self.live:
            self.live.stop()

    def add_task(self, task_id: str, task: Task, persona_name: str, status: str = 'queued'):
        """Add a task to the dashboard."""
        with self.lock:
            self.tasks[task_id] = TaskState(
                task=task,
                persona_name=persona_name,
                status=status,
                progress=0
            )
            self._refresh()

    def start_task(self, task_id: str):
        """Mark a task as started."""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id].status = 'running'
                self.tasks[task_id].start_time = time.time()
                self._refresh()

    def update_task(self, task_id: str, progress: Optional[int] = None, output: Optional[str] = None):
        """Update task progress and output."""
        with self.lock:
            if task_id not in self.tasks:
                return

            task_state = self.tasks[task_id]

            if progress is not None:
                task_state.progress = min(100, max(0, progress))

            if output:
                # Keep last line of output
                task_state.latest_output = output.strip().split('\n')[-1][:60]

            self._refresh()

    def complete_task(self, task_id: str, success: bool = True, artifacts: List[str] = None, error: Optional[str] = None):
        """Mark task as complete or failed."""
        with self.lock:
            if task_id not in self.tasks:
                return

            task_state = self.tasks[task_id]
            task_state.status = 'complete' if success else 'failed'
            task_state.progress = 100 if success else task_state.progress
            task_state.end_time = time.time()
            task_state.error = error

            # Track cumulative task time for cost estimation
            task_duration = task_state.end_time - task_state.start_time
            self.cumulative_task_seconds += task_duration

            if artifacts:
                task_state.artifacts = artifacts

            if success:
                self.completed_count += 1
            else:
                self.failed_count += 1

            self._refresh()

    def set_wave(self, wave_number: int):
        """Update current wave number."""
        with self.lock:
            self.current_wave = wave_number
            self._refresh()

    def add_metrics(self, cost: float = 0, tokens: int = 0):
        """Add to running metrics."""
        with self.lock:
            self.total_cost += cost
            self.total_tokens += tokens
            self._refresh()

    def _refresh(self):
        """Mark state as dirty — auto_refresh picks it up at 4Hz.
        Do NOT call live.update() from worker threads; parallel calls
        cause partial renders to commit and produce duplicate output lines."""
        pass  # auto_refresh=True handles redraw on its own schedule

    def _render_locked(self):
        """Render the current dashboard state. Must be called with lock held."""
        # Group running, queued, and completed tasks
        running = [t for t in self.tasks.values() if t.status == 'running']
        queued = [t for t in self.tasks.values() if t.status == 'queued']
        completed = [t for t in self.tasks.values() if t.status in ['complete', 'failed']]

        renderables = []

        # Header
        elapsed = int(time.time() - self.start_time)
        elapsed_str = f"{elapsed // 60}m {elapsed % 60}s" if elapsed >= 60 else f"{elapsed}s"

        header = Text()
        header.append("🌊 WAVE ", style="bright_magenta")
        header.append(f"{self.current_wave}", style="bright_cyan")
        header.append(f"  ┃  ", style=ui.DIM)

        if running:
            header.append(f"{len(running)} RUNNING", style="bright_cyan")
        else:
            header.append(f"{len(running)} RUNNING", style=ui.DIM)

        header.append(f"  ┃  ", style=ui.DIM)

        if self.completed_count:
            header.append(f"{self.completed_count} COMPLETE", style="bright_green")
        else:
            header.append(f"{self.completed_count} COMPLETE", style=ui.DIM)

        if self.failed_count:
            header.append(f"  ┃  ", style=ui.DIM)
            header.append(f"{self.failed_count} FAILED", style="bright_red")

        renderables.append(Panel(header, border_style="bright_magenta", box=box.HEAVY))

        # Running tasks
        if running:
            for task_state in running[:5]:  # Show up to 5 running
                renderables.append(self._render_task(task_state))

        # Queued tasks
        if queued:
            queued_text = Text()
            queued_text.append(f"\n🌊 WAVE {self.current_wave + 1} — ", style="bright_magenta")
            queued_text.append(f"{len(queued)} QUEUED\n", style="bright_yellow")
            for task_state in queued[:3]:  # Show first 3
                queued_text.append(f"  ⏸ {task_state.task.id}", style="yellow")
                if task_state.task.dependencies:
                    queued_text.append(f" (waiting on {', '.join(task_state.task.dependencies[:2])})", style=ui.DIM)
                queued_text.append("\n")
            if len(queued) > 3:
                queued_text.append(f"  ⋯ and {len(queued) - 3} more\n", style=ui.DIM)
            renderables.append(queued_text)

        # Recently completed (last 2)
        if completed:
            recent_complete = sorted(completed, key=lambda t: t.end_time or 0, reverse=True)[:2]
            for task_state in recent_complete:
                renderables.append(self._render_completed_task(task_state))

        # Metrics footer
        # Estimate tokens based on cumulative task time + currently running tasks
        # Rough estimate: ~1000 tokens per minute per task
        completed_task_tokens = int((self.cumulative_task_seconds / 60) * 1000)

        # Add estimate for currently running tasks
        running_task_tokens = 0
        for task_state in running:
            task_elapsed = time.time() - task_state.start_time
            running_task_tokens += int((task_elapsed / 60) * 1000)

        estimated_tokens = completed_task_tokens + running_task_tokens
        tokens_per_sec = estimated_tokens / max(1, elapsed)

        # Estimate cost based on tokens (Sonnet 4.5: $3/1M input, $15/1M output, assume 50/50 split = $9/1M avg)
        estimated_cost = (estimated_tokens / 1_000_000) * 9.0

        footer = Text()
        footer.append("💰 ", style="bright_yellow")
        footer.append(f"${estimated_cost:.2f}", style="bright_white")
        footer.append("  ┃  ", style=ui.DIM)
        footer.append("⚡ ", style="bright_cyan")
        footer.append(f"{tokens_per_sec:.1f} tok/s", style="bright_white")
        footer.append("  ┃  ", style=ui.DIM)
        footer.append("⏱ ", style="bright_magenta")
        footer.append(elapsed_str, style="bright_white")
        footer.append("  ┃  ", style=ui.DIM)

        # Progress indicator
        progress_pct = int((self.completed_count / max(1, self.total_tasks)) * 100)
        if self.completed_count == self.total_tasks:
            footer.append(f"✓ {self.completed_count}/{self.total_tasks} ({progress_pct}%)", style="bright_green")
        else:
            footer.append(f"{self.completed_count}/{self.total_tasks} ({progress_pct}%)", style="bright_cyan")

        renderables.append(Panel(footer, border_style="bright_magenta", box=box.HEAVY))

        return Group(*renderables)

    def _render_task(self, task_state: TaskState) -> Panel:
        """Render a single running task with progress bar."""
        # Progress bar with gradient colors
        filled = int(task_state.progress / 10)

        # Color gradient based on progress
        if task_state.progress < 25:
            bar_color = "magenta"
        elif task_state.progress < 50:
            bar_color = "bright_magenta"
        elif task_state.progress < 75:
            bar_color = "cyan"
        else:
            bar_color = "bright_cyan"

        bar_char = "▰"
        empty_char = "▱"

        # Elapsed time
        elapsed = int(time.time() - task_state.start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        elapsed_str = f"{mins}m{secs:02d}s" if mins > 0 else f"{secs}s"

        # Build content with styled progress bar
        content = Text()
        content.append(bar_char * filled, style=bar_color)
        content.append(empty_char * (10 - filled), style=ui.DIM)
        content.append(f" {task_state.progress}%", style=ui.WHITE)
        content.append(f"  ⏱ {elapsed_str}", style=ui.DIM)

        if task_state.latest_output:
            content.append(f"\n▸ {task_state.latest_output}", style=ui.DIM)

        # Title
        title = Text()
        title.append(task_state.task.id, style=ui.WHITE)
        title.append(f" — {task_state.persona_name}", style=bar_color)

        return Panel(
            content,
            title=title,
            border_style=bar_color,
            box=box.ROUNDED,
            padding=(0, 1)
        )

    def _render_completed_task(self, task_state: TaskState) -> Panel:
        """Render a completed task."""
        # Elapsed time
        if task_state.end_time:
            elapsed = int(task_state.end_time - task_state.start_time)
            mins = elapsed // 60
            secs = elapsed % 60
            elapsed_str = f"⏱ {mins}m{secs:02d}s" if mins > 0 else f"⏱ {secs}s"
        else:
            elapsed_str = ""

        # Build content
        content = Text()

        if task_state.status == 'complete':
            content.append("✓ COMPLETE", style="bright_green")
            content.append(f"                {elapsed_str}", style=ui.DIM)
            if task_state.artifacts:
                content.append(f"\n  ▸ {', '.join(task_state.artifacts[:3])}", style="bright_green")
                if len(task_state.artifacts) > 3:
                    content.append(f" +{len(task_state.artifacts) - 3} more", style=ui.DIM)
        else:
            content.append("✗ FAILED", style="bright_red")
            content.append(f"                    {elapsed_str}", style=ui.DIM)
            if task_state.error:
                content.append(f"\n  ▸ {task_state.error[:60]}", style="bright_red")

        # Title
        title = Text()
        title.append(task_state.task.id, style=ui.WHITE)
        title.append(f" — {task_state.persona_name}", style=ui.DIM)

        border_color = "bright_green" if task_state.status == 'complete' else "bright_red"

        return Panel(
            content,
            title=title,
            border_style=border_color,
            box=box.ROUNDED,
            padding=(0, 1)
        )
