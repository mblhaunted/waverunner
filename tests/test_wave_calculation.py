"""Tests for wave calculation (dependency graph)."""

import pytest
from waverunner.models import Task, Complexity, Priority
from waverunner.agent import calculate_waves


def test_single_task_single_wave():
    """Single task with no dependencies should be wave 1."""
    tasks = [
        Task(id="task-1", title="Test", description="Test task", complexity=Complexity.SMALL),
    ]
    waves = calculate_waves(tasks)

    assert len(waves) == 1
    assert len(waves[0]) == 1
    assert waves[0][0].id == "task-1"


def test_parallel_tasks_single_wave():
    """Multiple tasks with no dependencies should all be in wave 1."""
    tasks = [
        Task(id="task-1", title="Test 1", description="Test", complexity=Complexity.SMALL),
        Task(id="task-2", title="Test 2", description="Test", complexity=Complexity.SMALL),
        Task(id="task-3", title="Test 3", description="Test", complexity=Complexity.SMALL),
    ]
    waves = calculate_waves(tasks)

    assert len(waves) == 1
    assert len(waves[0]) == 3
    assert {t.id for t in waves[0]} == {"task-1", "task-2", "task-3"}


def test_linear_dependencies():
    """Tasks with linear dependencies should form separate waves."""
    tasks = [
        Task(id="task-1", title="First", description="Test", complexity=Complexity.SMALL, dependencies=[]),
        Task(id="task-2", title="Second", description="Test", complexity=Complexity.SMALL, dependencies=["task-1"]),
        Task(id="task-3", title="Third", description="Test", complexity=Complexity.SMALL, dependencies=["task-2"]),
    ]
    waves = calculate_waves(tasks)

    assert len(waves) == 3
    assert waves[0][0].id == "task-1"
    assert waves[1][0].id == "task-2"
    assert waves[2][0].id == "task-3"


def test_diamond_dependency():
    """Diamond dependency pattern should create proper waves."""
    tasks = [
        Task(id="task-1", title="Root", description="Test", complexity=Complexity.SMALL, dependencies=[]),
        Task(id="task-2", title="Left", description="Test", complexity=Complexity.SMALL, dependencies=["task-1"]),
        Task(id="task-3", title="Right", description="Test", complexity=Complexity.SMALL, dependencies=["task-1"]),
        Task(id="task-4", title="Join", description="Test", complexity=Complexity.SMALL, dependencies=["task-2", "task-3"]),
    ]
    waves = calculate_waves(tasks)

    assert len(waves) == 3
    assert waves[0][0].id == "task-1"
    assert {t.id for t in waves[1]} == {"task-2", "task-3"}
    assert waves[2][0].id == "task-4"


def test_circular_dependency():
    """Circular dependencies should leave some tasks unscheduled."""
    tasks = [
        Task(id="task-1", title="A", description="Test", complexity=Complexity.SMALL, dependencies=["task-2"]),
        Task(id="task-2", title="B", description="Test", complexity=Complexity.SMALL, dependencies=["task-1"]),
    ]
    waves = calculate_waves(tasks)

    # Neither task can run due to circular dependency
    assert len(waves) == 0


def test_multiple_roots():
    """Multiple root tasks should all be in wave 1."""
    tasks = [
        Task(id="root-1", title="Root 1", description="Test", complexity=Complexity.SMALL, dependencies=[]),
        Task(id="root-2", title="Root 2", description="Test", complexity=Complexity.SMALL, dependencies=[]),
        Task(id="child-1", title="Child 1", description="Test", complexity=Complexity.SMALL, dependencies=["root-1"]),
        Task(id="child-2", title="Child 2", description="Test", complexity=Complexity.SMALL, dependencies=["root-2"]),
    ]
    waves = calculate_waves(tasks)

    assert len(waves) == 2
    assert {t.id for t in waves[0]} == {"root-1", "root-2"}
    assert {t.id for t in waves[1]} == {"child-1", "child-2"}
