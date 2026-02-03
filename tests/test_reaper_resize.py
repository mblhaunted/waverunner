"""Test that team can resize tasks after Reaper timeout kills."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity
from waverunner.agent import run_sprint


def test_team_resizes_task_after_timeout_kill():
    """Test that when Reaper kills due to timeout, team discusses and resizes task."""

    # Create a board with a task estimated as TRIVIAL
    board = Board(
        id="test",
        goal="Test resize after timeout",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="underestimated-task",
                title="Task that takes longer than estimated",
                description="",
                complexity=Complexity.TRIVIAL,  # Wrong estimate
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "discussion": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] <= 2:
            # First 2 attempts: simulate timeout kill (non-silence triggers re-estimation after 2)
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: timeout exceeded for trivial task")
        else:
            # Third attempt with new complexity: success
            return (["output.txt"], Complexity.SMALL, "Completed with correct estimate")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        """Mock the re-estimation discussion."""
        call_count["discussion"] += 1

        # Return YAML indicating team agreed to resize from TRIVIAL to SMALL
        return """
```yaml
new_complexity: small
consensus: true
reasoning: "Team reviewed the timeout. Explorer found the task requires more API calls than expected. Senior Dev agrees this is SMALL not TRIVIAL. Tech Lead approves resize."
```
"""

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
            run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Verify task completed
    assert board.tasks[0].status == TaskStatus.COMPLETED

    # Verify task was resized from TRIVIAL to SMALL
    assert board.tasks[0].complexity == Complexity.SMALL

    # Verify discussion happened (team re-estimated)
    assert call_count["discussion"] >= 1, "Team should have discussed re-estimation"

    # Verify task was attempted at least 3 times (2 kills triggering re-estimation + 1 success)
    assert call_count["task"] >= 3


def test_team_rejects_resize_if_no_consensus():
    """Test that task keeps original estimate if team doesn't agree on resize."""

    board = Board(
        id="test",
        goal="Test no resize without consensus",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="task",
                title="Task",
                description="",
                complexity=Complexity.TRIVIAL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] == 1:
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: timeout exceeded for trivial task")
        else:
            return (["output.txt"], Complexity.TRIVIAL, "Completed")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        # Team doesn't reach consensus - keep original estimate
        return """
```yaml
new_complexity: trivial
consensus: false
reasoning: "Maverick says ship it and try again. Skeptic says we need more data. No consensus - keep TRIVIAL and retry."
```
"""

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
            run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Task completed but complexity unchanged
    assert board.tasks[0].status == TaskStatus.COMPLETED
    assert board.tasks[0].complexity == Complexity.TRIVIAL
