"""Test re-estimation trigger conditions and visible progress."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity
from waverunner.agent import run_sprint


def test_reestimation_triggers_after_2_non_silence_kills():
    """Test that re-estimation triggers after 2 complexity timeout kills (non-silence)."""
    board = Board(
        id="test",
        goal="Test 2 non-silence kills",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="complex-task",
                title="Task that exceeds complexity timeout",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "discussion": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] <= 2:
            # First 2 attempts: killed for complexity timeout (NOT silence)
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: exceeded 30 minute timeout")
        # 3rd attempt: success
        return (["result.txt"], Complexity.MEDIUM, "Completed after resize")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        call_count["discussion"] += 1
        return """
```yaml
new_complexity: medium
consensus: true
reasoning: "Task exceeded SMALL timeout twice. Needs MEDIUM complexity."
```
"""

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
            run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Re-estimation should trigger after 2 non-silence kills
    assert call_count["discussion"] >= 1, "Re-estimation should trigger after 2 complexity timeouts"
    assert board.tasks[0].complexity == Complexity.MEDIUM, "Task should be resized to MEDIUM"
    assert board.tasks[0].status == TaskStatus.COMPLETED


def test_reestimation_triggers_after_3_silence_kills():
    """Test that re-estimation triggers after 3 silence timeout kills."""
    board = Board(
        id="test",
        goal="Test 3 silence kills",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="silent-task",
                title="Task that goes silent",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "discussion": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] <= 3:
            # First 3 attempts: killed for silence
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: 181 seconds of silence")
        # 4th attempt: success
        return (["result.txt"], Complexity.MEDIUM, "Completed after resize")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        call_count["discussion"] += 1
        return """
```yaml
new_complexity: medium
consensus: true
reasoning: "Task went silent 3 times. Needs more time - MEDIUM complexity."
```
"""

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
            run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Re-estimation should trigger after 3 silence kills
    assert call_count["discussion"] >= 1, "Re-estimation should trigger after 3 silence timeouts"
    assert board.tasks[0].complexity == Complexity.MEDIUM, "Task should be resized to MEDIUM"
    assert board.tasks[0].status == TaskStatus.COMPLETED


def test_no_reestimation_before_threshold():
    """Test that re-estimation does NOT trigger before thresholds are met."""
    board = Board(
        id="test",
        goal="Test no premature re-estimation",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="task-1",
                title="Task killed once for silence",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task-1": 0, "discussion": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task-1"] += 1
        if call_count["task-1"] == 1:
            # Killed once for silence (threshold is 3)
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: 181 seconds of silence")
        return (["result1.txt"], Complexity.SMALL, "Success after 1 retry")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        call_count["discussion"] += 1
        return """
```yaml
new_complexity: medium
consensus: true
reasoning: "Should not be called."
```
"""

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
            run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # No re-estimation should occur (only 1 silence kill, threshold is 3)
    assert call_count["discussion"] == 0, f"Re-estimation should NOT trigger with only 1 silence kill (got {call_count['discussion']} discussions)"
    assert board.tasks[0].complexity == Complexity.SMALL, "Task should keep SMALL complexity"
    assert call_count["task-1"] == 2, "Task should be attempted twice (1 kill + 1 success)"


def test_visible_progress_during_reestimation_with_dashboard():
    """Test that dashboard shows visible progress during re-estimation."""
    board = Board(
        id="test",
        goal="Test visible progress",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="task-x",
                title="Task with visible re-estimation",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "discussion": 0}
    dashboard_updates = []

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] <= 3:
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: 200 seconds of silence")
        return (["result.txt"], Complexity.MEDIUM, "Done")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        call_count["discussion"] += 1
        return """
```yaml
new_complexity: medium
consensus: true
reasoning: "Resize."
```
"""

    # Mock dashboard
    mock_dashboard = MagicMock()
    mock_dashboard.update_task = Mock(side_effect=lambda task_id, **kwargs: dashboard_updates.append({
        'task_id': task_id,
        **kwargs
    }))

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
            with patch('waverunner.dashboard.LiveDashboard', return_value=mock_dashboard):
                run_sprint(board, max_parallel=1, use_live_dashboard=True)

    # Verify dashboard was updated during re-estimation
    reestimation_updates = [
        u for u in dashboard_updates
        if u.get('task_id') == 'task-x' and 'output' in u and 're-estimation' in u['output'].lower()
    ]

    assert len(reestimation_updates) > 0, "Dashboard should show re-estimation progress"
    assert any('🔄' in u.get('output', '') or 'discussing' in u.get('output', '').lower()
               for u in reestimation_updates), "Dashboard should show discussion indicator"


def test_visible_progress_during_reestimation_terminal():
    """Test that terminal shows visible progress during re-estimation (no dashboard)."""
    board = Board(
        id="test",
        goal="Test terminal progress",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="task-y",
                title="Task with terminal re-estimation",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "discussion": 0}
    console_prints = []

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] <= 3:
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: 190 seconds of silence")
        return (["result.txt"], Complexity.MEDIUM, "Done")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        call_count["discussion"] += 1
        return """
```yaml
new_complexity: medium
consensus: true
reasoning: "Resize to MEDIUM."
```
"""

    # Mock console.print to capture output
    def mock_console_print(*args, **kwargs):
        console_prints.append(' '.join(str(a) for a in args))

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
            with patch('waverunner.ui.console.print', side_effect=mock_console_print):
                run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Verify console showed re-estimation progress
    reestimation_messages = [
        msg for msg in console_prints
        if 're-estimation' in msg.lower() or 'discussing' in msg.lower()
    ]

    assert len(reestimation_messages) > 0, "Console should show re-estimation messages"
    assert any('💬' in msg or '🔄' in msg for msg in reestimation_messages), \
        "Console should show discussion indicator"


def test_visible_result_after_reestimation():
    """Test that visible result is shown after re-estimation completes."""
    board = Board(
        id="test",
        goal="Test visible result",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="task-z",
                title="Task showing result",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "discussion": 0}
    console_prints = []

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] <= 3:
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: 200 seconds of silence")
        return (["result.txt"], Complexity.LARGE, "Done")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        call_count["discussion"] += 1
        return """
```yaml
new_complexity: large
consensus: true
reasoning: "Needs LARGE complexity."
```
"""

    def mock_console_print(*args, **kwargs):
        console_prints.append(' '.join(str(a) for a in args))

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
            with patch('waverunner.ui.console.print', side_effect=mock_console_print):
                run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Verify result message shown
    result_messages = [
        msg for msg in console_prints
        if ('resized' in msg.lower() or 'keeping' in msg.lower()) and 'task-z' in msg
    ]

    assert len(result_messages) > 0, "Console should show re-estimation result"

    # Check that it shows the complexity change (SMALL → LARGE or similar format)
    assert any(('small' in msg.lower() and 'large' in msg.lower()) or
               ('small→large' in msg.lower()) or
               ('resized task-z' in msg.lower() and 'large' in msg.lower())
               for msg in result_messages), \
        f"Result should show complexity change from SMALL to LARGE. Got: {result_messages}"
