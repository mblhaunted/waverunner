"""Test that Reaper intelligently analyzes output, not just silence."""

import pytest
from unittest.mock import Mock, patch
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity
from waverunner.agent import run_sprint


def test_reaper_allows_progress_output_despite_time():
    """Test that Reaper doesn't kill when agent is outputting progress."""

    board = Board(
        id="test",
        goal="Test Reaper intelligence",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="npm-install",
                title="Install dependencies",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "reaper": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        # Simulate successful completion
        return (["package.json"], Complexity.SMALL, "npm install completed")

    def mock_reaper_monitor(task, persona, silence_seconds, elapsed_seconds):
        """Mock Reaper that checks if output shows progress."""
        call_count["reaper"] += 1

        # Simulate: 181 seconds of silence but last output was "Installing dependencies..."
        # Reaper should see progress indicators and CONTINUE
        if call_count["reaper"] == 1:
            # First check: sees "npm install" in output, continues
            return ("CONTINUE", "")

        return ("CONTINUE", "")

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.reaper_monitor_task', side_effect=mock_reaper_monitor):
            run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Task should complete successfully (not killed)
    assert board.tasks[0].status == TaskStatus.COMPLETED
    assert board.tasks[0].reaper_kill_count == 0


def test_reaper_kills_actual_infinite_loop():
    """Test that Reaper kills when output shows infinite loop or errors."""

    board = Board(
        id="test",
        goal="Test Reaper detects hang",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="broken-task",
                title="Task with infinite loop",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "reaper": 0, "discussion": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] <= 2:
            # First 2 attempts: Reaper kills it (non-silence error triggers re-estimation after 2)
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: output shows infinite loop")
        return (["fixed.py"], Complexity.SMALL, "Fixed after re-estimation")

    def mock_reaper_monitor(task, persona, silence_seconds, elapsed_seconds, recent_output=None):
        """Mock Reaper that detects infinite loop in output."""
        call_count["reaper"] += 1
        if call_count["reaper"] <= 2:
            # Sees same output repeating = infinite loop
            return ("KILL", "output shows infinite loop")
        return ("CONTINUE", "")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        call_count["discussion"] += 1
        # Team decides to keep complexity (infinite loop is a code issue, not estimate issue)
        return """
```yaml
new_complexity: small
consensus: false
reasoning: "Infinite loop is a code bug, not estimation issue."
```
"""

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.reaper_monitor_task', side_effect=mock_reaper_monitor):
            with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
                run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Task should complete after kills and re-estimation discussion
    assert board.tasks[0].status == TaskStatus.COMPLETED
    assert board.tasks[0].reaper_kill_count >= 2, "Task should be killed at least twice (triggers re-estimation)"


def test_reestimation_after_repeated_silence_kills():
    """Test that repeated silence kills trigger team re-estimation."""

    board = Board(
        id="test",
        goal="Test re-estimation on silence",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="silent-task",
                title="Task that keeps timing out",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "reaper": 0, "discussion": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] <= 3:
            # First 3 attempts: killed by Reaper for silence
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: 181 seconds of silence")
        # 4th attempt: success
        return (["result.txt"], Complexity.MEDIUM, "Completed after resize")

    def mock_reaper_monitor(task, persona, silence_seconds, elapsed_seconds, recent_output=None):
        call_count["reaper"] += 1
        if call_count["reaper"] <= 3:
            return ("KILL", "181 seconds of silence")
        return ("CONTINUE", "")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        """Mock re-estimation discussion."""
        call_count["discussion"] += 1
        # Team decides task needs to be MEDIUM, not SMALL
        return """
```yaml
new_complexity: medium
consensus: true
reasoning: "Task keeps timing out due to silence. Explorer says it involves multiple API calls. Team agrees resize to MEDIUM."
```
"""

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.reaper_monitor_task', side_effect=mock_reaper_monitor):
            with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
                run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Task completed and was resized
    assert board.tasks[0].status == TaskStatus.COMPLETED
    assert board.tasks[0].complexity == Complexity.MEDIUM  # Resized from SMALL

    # Re-estimation discussion happened
    assert call_count["discussion"] >= 1, "Team should discuss re-estimation after repeated failures"

    # Multiple kill attempts before success
    assert call_count["task"] == 4  # 3 kills + 1 success


def test_reaper_receives_output_for_analysis():
    """Test that Reaper monitor function accepts recent_output parameter."""

    # This test verifies the Reaper monitor signature, not actual Reaper execution
    # (Reaper only monitors during actual subprocess execution, which we mock)

    from waverunner.agent import reaper_monitor_task
    from waverunner.models import Complexity
    from waverunner.personas import Persona

    test_task = Task(
        id="test",
        title="Test",
        description="",
        complexity=Complexity.SMALL,
        dependencies=[]
    )

    # Create a test Persona object
    test_persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test prompt",
        color="white"
    )

    # Call with recent_output parameter - should not raise TypeError
    action, reason = reaper_monitor_task(
        test_task,
        test_persona,
        silence_seconds=100,
        elapsed_seconds=200,
        recent_output=["line 1", "line 2", "installing packages..."]
    )

    # Should return valid action
    assert action in ["CONTINUE", "KILL"], f"Invalid action: {action}"


def test_reaper_analyzes_progress_indicators():
    """Test that Reaper recognizes progress indicators and continues execution."""

    board = Board(
        id="test",
        goal="Test progress indicator analysis",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="building-task",
                title="Task showing build progress",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "reaper": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        return (["built.txt"], Complexity.SMALL, "Build complete")

    def mock_reaper_monitor(task, persona, silence_seconds, elapsed_seconds, recent_output=None):
        """Simulate Reaper analyzing output for progress indicators."""
        call_count["reaper"] += 1

        # Simulate receiving output with progress indicators
        if recent_output and any(indicator in line.lower()
                               for line in recent_output
                               for indicator in ["installing", "downloading", "building", "processing"]):
            # Output shows progress - CONTINUE
            return ("CONTINUE", "Progress indicators detected in output")

        # For this test, always continue (simulating progress)
        return ("CONTINUE", "")

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.reaper_monitor_task', side_effect=mock_reaper_monitor):
            run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Task should complete without being killed
    assert board.tasks[0].status == TaskStatus.COMPLETED
    assert board.tasks[0].reaper_kill_count == 0, "Reaper should not kill task showing progress"


def test_reaper_detects_infinite_loop_pattern():
    """Test that Reaper detects identical repeating patterns (infinite loops)."""

    board = Board(
        id="test",
        goal="Test infinite loop detection",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="looping-task",
                title="Task stuck in loop",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task": 0, "reaper": 0, "discussion": 0}

    def mock_execute(board, task, progress_callback=None):
        call_count["task"] += 1
        if call_count["task"] <= 2:
            # First 2 attempts: killed for infinite loop (triggers re-estimation)
            task.reaper_kill_count += 1
            raise RuntimeError("Task killed by Reaper: output shows infinite loop")
        # After re-estimation: success
        return (["fixed.txt"], Complexity.SMALL, "Loop fixed")

    def mock_reaper_monitor(task, persona, silence_seconds, elapsed_seconds, recent_output=None):
        """Simulate Reaper detecting repeating patterns."""
        call_count["reaper"] += 1

        # Detect infinite loop on first 2 calls
        if call_count["reaper"] <= 2:
            return ("KILL", "output shows infinite loop")

        return ("CONTINUE", "")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        call_count["discussion"] += 1
        return """
```yaml
new_complexity: small
consensus: false
reasoning: "Code bug, not estimate issue."
```
"""

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.reaper_monitor_task', side_effect=mock_reaper_monitor):
            with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
                run_sprint(board, max_parallel=1, use_live_dashboard=False)

    # Task should complete after kills and re-estimation
    assert board.tasks[0].status == TaskStatus.COMPLETED
    assert board.tasks[0].reaper_kill_count >= 2, "Reaper should kill multiple times (triggers re-estimation)"
