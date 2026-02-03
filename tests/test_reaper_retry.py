"""Test that sprint continues after Reaper kills a task."""

import pytest
from unittest.mock import Mock, patch
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity
from waverunner.agent import run_sprint


def test_sprint_continues_after_reaper_kill():
    """Test that when Reaper kills a task, the sprint continues and retries it."""

    # Create a board with dependent tasks
    board = Board(
        id="test",
        goal="Test Reaper retry",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(id="spike", title="Spike", description="", complexity=Complexity.SMALL, dependencies=[]),
            Task(id="impl", title="Implement", description="", complexity=Complexity.SMALL, dependencies=["spike"]),
        ]
    )

    # Mock execute_task to simulate Reaper kill on first attempt, success on second
    call_count = {"spike": 0}

    def mock_execute(board, task, progress_callback=None):
        if task.id == "spike":
            call_count["spike"] += 1
            if call_count["spike"] == 1:
                # First attempt: simulate Reaper kill
                task.reaper_kill_count += 1
                raise RuntimeError("Task killed by Reaper: silence timeout")
            else:
                # Second attempt: success
                return (["spike_output.txt"], Complexity.SMALL, "Spike complete")
        elif task.id == "impl":
            return (["impl_output.txt"], Complexity.SMALL, "Implementation complete")
        return ([], Complexity.SMALL, "")

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        # Run the sprint with no dashboard
        run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Verify both tasks completed
    assert board.tasks[0].status == TaskStatus.COMPLETED, "Spike should be completed after retry"
    assert board.tasks[1].status == TaskStatus.COMPLETED, "Impl should be completed after spike retries"
    assert call_count["spike"] == 2, "Spike should have been called twice (kill + retry)"


def test_sprint_exits_after_10_reaper_kills():
    """Test that sprint exits after 10 Reaper kills on same task."""

    board = Board(
        id="test",
        goal="Test max kills",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(id="failing-task", title="Fails", description="", complexity=Complexity.SMALL, dependencies=[]),
        ]
    )

    call_count = {"failing-task": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["failing-task"] += 1
        # Always fail with Reaper kill
        task.reaper_kill_count += 1
        raise RuntimeError("Task killed by Reaper: silence timeout")

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # After 10 kills, task should be BLOCKED
    assert board.tasks[0].status == TaskStatus.BLOCKED, "Task should be blocked after 10 kills"
    assert board.tasks[0].reaper_kill_count >= 10, "Task should have been killed at least 10 times"
    assert "Reaper killed" in board.tasks[0].blocked_reason, "Blocked reason should mention Reaper"
