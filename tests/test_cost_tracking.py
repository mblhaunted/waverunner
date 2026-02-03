"""
Tests for cost tracking and token usage estimation.
"""

import pytest
from waverunner.models import Board, Task, Mode, TaskStatus
from waverunner.cost_tracker import CostTracker, estimate_tokens


def test_estimate_tokens_basic():
    """Test basic token estimation (roughly 4 chars per token)."""
    text = "Hello world, this is a test prompt for token estimation."
    tokens = estimate_tokens(text)
    # Rough estimate: ~14 tokens for this text
    assert 10 <= tokens <= 20


def test_estimate_tokens_empty():
    """Empty string should be 0 tokens."""
    assert estimate_tokens("") == 0


def test_estimate_tokens_long_text():
    """Test with longer text."""
    text = "a" * 1000  # 1000 characters
    tokens = estimate_tokens(text)
    # Should be roughly 250 tokens (4 chars/token)
    assert 200 <= tokens <= 300


def test_cost_tracker_initialization():
    """CostTracker should initialize with zero costs."""
    tracker = CostTracker()
    assert tracker.total_input_tokens == 0
    assert tracker.total_output_tokens == 0
    assert tracker.total_cost == 0.0


def test_cost_tracker_add_task_cost():
    """Adding task usage should update totals."""
    tracker = CostTracker()

    # Simulate a task with prompt and response
    prompt = "Write a function to add two numbers"
    response = "def add(a, b):\n    return a + b"

    tracker.add_task_usage("task-1", prompt, response)

    assert tracker.total_input_tokens > 0
    assert tracker.total_output_tokens > 0
    assert tracker.total_cost > 0


def test_cost_tracker_multiple_tasks():
    """Multiple tasks should accumulate costs."""
    tracker = CostTracker()

    tracker.add_task_usage("task-1", "prompt 1" * 10, "response 1" * 10)
    first_cost = tracker.total_cost

    tracker.add_task_usage("task-2", "prompt 2" * 10, "response 2" * 10)
    second_cost = tracker.total_cost

    assert second_cost > first_cost
    assert len(tracker.task_costs) == 2


def test_cost_tracker_get_task_cost():
    """Should be able to retrieve individual task cost."""
    tracker = CostTracker()
    tracker.add_task_usage("task-1", "test prompt", "test response")

    task_cost = tracker.get_task_cost("task-1")
    assert task_cost > 0


def test_cost_tracker_format_summary():
    """Should format a readable cost summary."""
    tracker = CostTracker()
    tracker.add_task_usage("task-1", "prompt" * 100, "response" * 100)

    summary = tracker.format_summary()

    assert "Total cost" in summary
    assert "$" in summary
    assert "token" in summary.lower()


def test_cost_tracker_pricing():
    """Test Sonnet 4.5 pricing calculation (example rates)."""
    tracker = CostTracker()

    # Add exactly 1M input tokens and 1M output tokens
    # Sonnet 4.5: $3/M input, $15/M output = $18 total
    tracker.total_input_tokens = 1_000_000
    tracker.total_output_tokens = 1_000_000
    tracker._calculate_cost()

    # Should be roughly $18 (allowing for rounding)
    assert 17.5 <= tracker.total_cost <= 18.5


def test_board_stores_cost_tracker():
    """Board should have a cost_tracker field."""
    board = Board(
        id="test-board",
        goal="Test goal",
        context="",
        mode=Mode.SPRINT,
        tasks=[]
    )

    # Should be able to store cost tracking data
    assert hasattr(board, 'cost_data')


def test_cost_data_persists_in_board():
    """Cost data should be serializable in board YAML."""
    board = Board(
        id="test-board",
        goal="Test goal",
        context="",
        mode=Mode.SPRINT,
        tasks=[]
    )

    board.cost_data = {
        'total_input_tokens': 1000,
        'total_output_tokens': 2000,
        'total_cost': 0.05,
        'task_costs': {
            'task-1': {'input_tokens': 500, 'output_tokens': 1000, 'cost': 0.025}
        }
    }

    # Should be able to convert to dict for YAML serialization
    board_dict = board.to_dict()
    assert 'cost_data' in board_dict
    assert board_dict['cost_data']['total_cost'] == 0.05
