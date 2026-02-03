"""Test that sprint completes without freezing or deadlocking."""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity
from waverunner.agent import run_sprint


def test_sprint_completes_without_freeze_during_reestimation():
    """
    CRITICAL: Test that sprint completes within reasonable time even when
    re-estimation is triggered. This verifies the deadlock fix where re-estimation
    was happening inside board_lock.
    """
    board = Board(
        id="test",
        goal="Test no freeze during re-estimation",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(
                id="task-1",
                title="Task that triggers re-estimation",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
            Task(
                id="task-2",
                title="Parallel task",
                description="",
                complexity=Complexity.SMALL,
                dependencies=[]
            ),
        ]
    )

    call_count = {"task-1": 0, "task-2": 0, "discussion": 0}

    def mock_execute(board, task, progress_callback=None):
        """Simulate task execution with first task triggering re-estimation."""
        if task.id == "task-1":
            call_count["task-1"] += 1
            if call_count["task-1"] <= 3:
                # First 3 attempts: killed for silence (triggers re-estimation after 3)
                task.reaper_kill_count += 1
                raise RuntimeError("Task killed by Reaper: 181 seconds of silence")
            # 4th attempt: success
            return (["result.txt"], Complexity.MEDIUM, "Completed after resize")

        elif task.id == "task-2":
            call_count["task-2"] += 1
            # Simulate some delay to ensure tasks run in parallel
            time.sleep(0.1)
            return (["task2.txt"], Complexity.SMALL, "Task 2 complete")

        return ([], Complexity.SMALL, "")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        """Mock re-estimation discussion - simulates LLM delay."""
        call_count["discussion"] += 1
        # Simulate discussion delay (should NOT block other tasks)
        time.sleep(0.2)
        return """
```yaml
new_complexity: medium
consensus: true
reasoning: "Task keeps timing out. Team agrees resize to MEDIUM."
```
"""

    # Run sprint in a thread with timeout to detect freeze
    sprint_result = {"completed": False, "error": None}

    def run_sprint_thread():
        try:
            with patch('waverunner.agent.execute_task', side_effect=mock_execute):
                with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
                    run_sprint(board, max_parallel=2, use_live_dashboard=False)
            sprint_result["completed"] = True
        except Exception as e:
            sprint_result["error"] = str(e)

    thread = threading.Thread(target=run_sprint_thread)
    thread.start()

    # Wait maximum 30 seconds (should complete in <5 seconds)
    thread.join(timeout=30.0)

    # Verify sprint completed
    assert not thread.is_alive(), "Sprint FROZE and did not complete within 30 seconds - DEADLOCK DETECTED"
    assert sprint_result["completed"], f"Sprint did not complete: {sprint_result.get('error', 'unknown error')}"

    # Verify re-estimation happened
    assert call_count["discussion"] >= 1, "Re-estimation discussion should have occurred"

    # Verify both tasks completed
    assert board.tasks[0].status == TaskStatus.COMPLETED, "Task 1 should be completed"
    assert board.tasks[1].status == TaskStatus.COMPLETED, "Task 2 should be completed"

    # Verify task was resized
    assert board.tasks[0].complexity == Complexity.MEDIUM, "Task should be resized to MEDIUM"


def test_parallel_tasks_not_blocked_during_reestimation():
    """
    Test that parallel tasks continue executing while one task undergoes
    re-estimation. This ensures re-estimation doesn't hold board_lock.
    """
    board = Board(
        id="test",
        goal="Test parallel execution during re-estimation",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(id="reestimate-me", title="Gets resized", description="",
                 complexity=Complexity.SMALL, dependencies=[]),
            Task(id="fast-task-1", title="Quick task 1", description="",
                 complexity=Complexity.TRIVIAL, dependencies=[]),
            Task(id="fast-task-2", title="Quick task 2", description="",
                 complexity=Complexity.TRIVIAL, dependencies=[]),
            Task(id="fast-task-3", title="Quick task 3", description="",
                 complexity=Complexity.TRIVIAL, dependencies=[]),
        ]
    )

    execution_times = {}
    call_count = {"reestimate-me": 0, "discussion": 0}

    def mock_execute(board, task, progress_callback=None):
        start_time = time.time()

        if task.id == "reestimate-me":
            call_count["reestimate-me"] += 1
            if call_count["reestimate-me"] <= 3:
                task.reaper_kill_count += 1
                raise RuntimeError("Task killed by Reaper: 200 seconds of silence")
            time.sleep(0.05)
            result = (["result.txt"], Complexity.MEDIUM, "Resized and completed")
        else:
            # Fast tasks complete quickly
            time.sleep(0.05)
            result = ([f"{task.id}.txt"], Complexity.TRIVIAL, f"{task.id} complete")

        execution_times[task.id] = time.time() - start_time
        return result

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        call_count["discussion"] += 1
        # Simulate long discussion (1 second)
        time.sleep(1.0)
        return """
```yaml
new_complexity: medium
consensus: true
reasoning: "Resize to MEDIUM."
```
"""

    start_time = time.time()

    with patch('waverunner.agent.execute_task', side_effect=mock_execute):
        with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
            run_sprint(board, max_parallel=4, use_live_dashboard=False)

    total_time = time.time() - start_time

    # All tasks should complete
    assert all(t.status == TaskStatus.COMPLETED for t in board.tasks), "All tasks should complete"

    # Re-estimation should have happened
    assert call_count["discussion"] >= 1, "Re-estimation should occur"

    # Total time should be much less than if tasks ran sequentially
    # If re-estimation blocked everything: 3 kills + 1 success + 3 fast tasks = ~7 sequential ops = ~7+ seconds
    # With proper parallelism: Should complete in ~2-3 seconds (3 kills + discussion + parallel fast tasks)
    assert total_time < 5.0, f"Sprint took {total_time}s - tasks may have been blocked by re-estimation"


def test_multiple_concurrent_reestimations_no_freeze():
    """
    Test that multiple tasks can trigger re-estimation concurrently without
    deadlock or race conditions.
    """
    board = Board(
        id="test",
        goal="Test concurrent re-estimations",
        context="",
        mode=Mode.SPRINT,
        tasks=[
            Task(id=f"task-{i}", title=f"Task {i}", description="",
                 complexity=Complexity.SMALL, dependencies=[])
            for i in range(3)
        ]
    )

    call_count = {}
    discussion_count = {"total": 0}

    def mock_execute(board, task, progress_callback=None):
        task_id = task.id
        call_count[task_id] = call_count.get(task_id, 0) + 1

        if call_count[task_id] <= 3:
            # First 3 attempts: killed for silence
            task.reaper_kill_count += 1
            raise RuntimeError(f"Task killed by Reaper: {task_id} silence timeout")

        # 4th attempt: success
        return ([f"{task_id}.txt"], Complexity.MEDIUM, f"{task_id} complete")

    def mock_multi_agent(goal, context, mode, iteration=1, max_iterations=1, mcps=None, accountability=None):
        discussion_count["total"] += 1
        # Simulate discussion with slight delay
        time.sleep(0.2)
        return """
```yaml
new_complexity: medium
consensus: true
reasoning: "Resize needed."
```
"""

    # Run with timeout
    sprint_result = {"completed": False, "error": None}

    def run_sprint_thread():
        try:
            with patch('waverunner.agent.execute_task', side_effect=mock_execute):
                with patch('waverunner.agent.run_multi_agent_discussion', side_effect=mock_multi_agent):
                    run_sprint(board, max_parallel=3, use_live_dashboard=False)
            sprint_result["completed"] = True
        except Exception as e:
            sprint_result["error"] = str(e)

    thread = threading.Thread(target=run_sprint_thread)
    thread.start()
    thread.join(timeout=30.0)

    # Verify no freeze
    assert not thread.is_alive(), "Sprint FROZE with concurrent re-estimations - DEADLOCK"
    assert sprint_result["completed"], f"Sprint failed: {sprint_result.get('error')}"

    # All tasks should complete and be resized
    assert all(t.status == TaskStatus.COMPLETED for t in board.tasks), "All tasks should complete"
    assert all(t.complexity == Complexity.MEDIUM for t in board.tasks), "All tasks should be resized"

    # At least one re-estimation should have occurred per task
    assert discussion_count["total"] >= 3, "Each task should trigger re-estimation"
