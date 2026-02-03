"""Tests for Board model and state management."""

import pytest
import tempfile
from pathlib import Path
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity, Priority


def test_board_creation():
    """Should create a board with default values."""
    board = Board(id="test-1", goal="Test goal", context="Test context")

    assert board.id == "test-1"
    assert board.goal == "Test goal"
    assert board.mode == Mode.SPRINT
    assert len(board.tasks) == 0
    assert board.status == "empty"


def test_board_add_task():
    """Should add tasks to board."""
    board = Board(id="test-1", goal="Test", context="")
    task = Task(id="task-1", title="Test", description="Test task", complexity=Complexity.SMALL)

    board.add_task(task)
    assert len(board.tasks) == 1
    assert board.get_task("task-1") == task


def test_board_next_task():
    """Should return next ready task based on dependencies."""
    board = Board(id="test-1", goal="Test", context="", mode=Mode.SPRINT)
    board.tasks = [
        Task(id="task-1", title="First", description="", complexity=Complexity.SMALL, status=TaskStatus.PLANNED),
        Task(id="task-2", title="Second", description="", complexity=Complexity.SMALL, status=TaskStatus.PLANNED, dependencies=["task-1"]),
    ]

    next_task = board.next_task()
    assert next_task.id == "task-1"

    # Complete task-1, task-2 should become next
    board.get_task("task-1").complete()
    next_task = board.next_task()
    assert next_task.id == "task-2"


def test_board_next_task_priority():
    """Should return highest priority ready task."""
    board = Board(id="test-1", goal="Test", context="", mode=Mode.SPRINT)
    board.tasks = [
        Task(id="low", title="Low", description="", complexity=Complexity.SMALL, status=TaskStatus.PLANNED, priority=Priority.LOW),
        Task(id="high", title="High", description="", complexity=Complexity.SMALL, status=TaskStatus.PLANNED, priority=Priority.HIGH),
        Task(id="critical", title="Critical", description="", complexity=Complexity.SMALL, status=TaskStatus.PLANNED, priority=Priority.CRITICAL),
    ]

    next_task = board.next_task()
    assert next_task.id == "critical"


def test_board_kanban_wip_limit():
    """Kanban mode should respect WIP limits."""
    board = Board(id="test-1", goal="Test", context="", mode=Mode.KANBAN)
    board.kanban_config.wip_limit = 2

    board.tasks = [
        Task(id="task-1", title="T1", description="", complexity=Complexity.SMALL, status=TaskStatus.IN_PROGRESS),
        Task(id="task-2", title="T2", description="", complexity=Complexity.SMALL, status=TaskStatus.IN_PROGRESS),
        Task(id="task-3", title="T3", description="", complexity=Complexity.SMALL, status=TaskStatus.BACKLOG),
    ]

    # At WIP limit, should return None
    next_task = board.next_task()
    assert next_task is None

    # Complete one task, should now return task-3
    board.get_task("task-1").complete()
    next_task = board.next_task()
    assert next_task.id == "task-3"


def test_board_progress_sprint():
    """Sprint mode progress should track committed tasks."""
    board = Board(id="test-1", goal="Test", context="", mode=Mode.SPRINT)
    board.tasks = [
        Task(id="t1", title="", description="", complexity=Complexity.SMALL, status=TaskStatus.PLANNED),
        Task(id="t2", title="", description="", complexity=Complexity.SMALL, status=TaskStatus.COMPLETED),
        Task(id="t3", title="", description="", complexity=Complexity.SMALL, status=TaskStatus.BACKLOG),
    ]

    progress = board.progress
    assert progress["total"] == 2  # Only planned/completed, not backlog
    assert progress["completed"] == 1
    assert progress["percent"] == 50


def test_board_progress_kanban():
    """Kanban mode progress should track flow metrics."""
    board = Board(id="test-1", goal="Test", context="", mode=Mode.KANBAN)
    board.kanban_config.wip_limit = 3
    board.tasks = [
        Task(id="done-1", title="", description="", complexity=Complexity.SMALL, status=TaskStatus.COMPLETED),
        Task(id="done-2", title="", description="", complexity=Complexity.SMALL, status=TaskStatus.COMPLETED),
        Task(id="wip-1", title="", description="", complexity=Complexity.SMALL, status=TaskStatus.IN_PROGRESS),
        Task(id="backlog-1", title="", description="", complexity=Complexity.SMALL, status=TaskStatus.BACKLOG),
    ]

    progress = board.progress
    assert progress["completed"] == 2
    assert progress["in_progress"] == 1
    assert progress["backlog"] == 1
    assert progress["wip_limit"] == 3
    assert progress["wip_available"] == 2


def test_board_serialization():
    """Should serialize and deserialize board to YAML."""
    board = Board(id="test-1", goal="Test goal", context="Some context", mode=Mode.SPRINT)
    task = Task(id="task-1", title="Test", description="Test task", complexity=Complexity.SMALL)
    board.add_task(task)
    board.risks = ["Risk 1"]
    board.assumptions = ["Assumption 1"]

    # Serialize
    yaml_str = board.to_yaml()
    assert "test-1" in yaml_str
    assert "Test goal" in yaml_str
    assert "task-1" in yaml_str

    # Deserialize
    board2 = Board.from_yaml(yaml_str)
    assert board2.id == board.id
    assert board2.goal == board.goal
    assert len(board2.tasks) == 1
    assert board2.risks == ["Risk 1"]


def test_board_save_load():
    """Should save and load board from file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "board.yaml"

        board = Board(id="test-1", goal="Test", context="")
        board.add_task(Task(id="task-1", title="Test", description="", complexity=Complexity.SMALL))

        board.save(str(file_path))
        assert file_path.exists()

        board2 = Board.load(str(file_path))
        assert board2.id == board.id
        assert len(board2.tasks) == 1


def test_task_lifecycle():
    """Should track task lifecycle transitions."""
    task = Task(id="task-1", title="Test", description="Test", complexity=Complexity.SMALL)

    assert task.status == TaskStatus.BACKLOG
    assert task.started_at is None
    assert task.completed_at is None

    # Start task
    task.start()
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.started_at is not None

    # Complete task
    task.complete(artifacts=["file.py"], actual_complexity=Complexity.SMALL)
    assert task.status == TaskStatus.COMPLETED
    assert task.completed_at is not None
    assert task.artifacts == ["file.py"]
    assert task.actual_complexity == Complexity.SMALL
    assert task.cycle_time_seconds is not None
    assert task.cycle_time_seconds >= 0


def test_task_block():
    """Should track blocked tasks with reason."""
    task = Task(id="task-1", title="Test", description="", complexity=Complexity.SMALL)

    task.block("Waiting for API access")
    assert task.status == TaskStatus.BLOCKED
    assert task.blocked_reason == "Waiting for API access"
