"""Tests for Reaper-Agent resurrection negotiation.

When a task is killed, the Reaper and assigned Agent must negotiate
an adjustment before retrying, not just blindly repeat the same approach.
"""

import pytest
from unittest.mock import Mock, patch
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity, ResurrectionRecord
from waverunner.agent import negotiate_resurrection


def test_negotiation_requires_reaper_and_agent():
    """Negotiation should involve both Reaper and assigned Agent."""
    board = Board(
        id="test",
        goal="Test",
        context="",
        mode=Mode.SPRINT,
        tasks=[]
    )

    task = Task(
        id="test-task",
        title="Test",
        description="Test task",
        assigned_to="Senior Dev",
        reaper_kill_count=1,
        resurrection_history=[
            ResurrectionRecord(
                attempt_number=1,
                persona="Senior Dev",
                kill_reason="Timeout after 300s",
                elapsed_seconds=300,
                partial_notes="Started implementation",
                killed_at="2026-02-08T12:00:00"
            )
        ]
    )

    with patch('waverunner.agent.run_claude') as mock_run:
        mock_run.side_effect = [
            "I'll try a simpler approach: reduce scope to core functionality",  # Agent
            "Approved. Focus on core only, skip edge cases for now."  # Reaper
        ]

        adjustment = negotiate_resurrection(board, task, "Timeout - no progress in 60s")

        # Should have called run_claude twice (Agent then Reaper)
        assert mock_run.call_count == 2

        # Should return an adjustment
        assert adjustment is not None
        assert "simpler" in adjustment.lower() or "core" in adjustment.lower()


def test_reaper_can_reject_agent_proposal():
    """Reaper should be able to reject inadequate adjustments."""
    board = Board(
        id="test",
        goal="Test",
        context="",
        mode=Mode.SPRINT,
        tasks=[]
    )

    task = Task(
        id="test-task",
        title="Test",
        description="Test task",
        assigned_to="Senior Dev",
        reaper_kill_count=2,
        resurrection_history=[]
    )

    with patch('waverunner.agent.run_claude') as mock_run:
        mock_run.side_effect = [
            "I'll try the same approach but with more time",  # Agent (bad)
            "REJECTED. That's the same approach. Try something fundamentally different.",  # Reaper
            "I'll break it into 3 smaller tasks instead",  # Agent (better)
            "Approved. Split and conquer."  # Reaper
        ]

        adjustment = negotiate_resurrection(board, task, "Complexity explosion")

        # Should have gone back and forth until approved
        assert mock_run.call_count == 4
        assert "smaller" in adjustment.lower() or "split" in adjustment.lower()


def test_adjustment_includes_kill_reason_context():
    """Agent should see WHY the task was killed."""
    board = Board(
        id="test",
        goal="Test",
        context="",
        mode=Mode.SPRINT,
        tasks=[]
    )

    task = Task(
        id="test-task",
        title="Test",
        description="Test task",
        assigned_to="Explorer",
        reaper_kill_count=1,
        resurrection_history=[]
    )

    kill_reason = "Infinite loop detected in file processing"

    with patch('waverunner.agent.run_claude') as mock_run:
        mock_run.side_effect = [
            "Add batch size limit to prevent infinite loops",
            "Approved."
        ]

        negotiate_resurrection(board, task, kill_reason)

        # Agent's prompt should contain the kill reason
        agent_call = mock_run.call_args_list[0]
        agent_prompt = agent_call[1]['prompt']
        assert "Infinite loop" in agent_prompt
        assert "file processing" in agent_prompt


def test_adjustment_considers_resurrection_history():
    """Agent should see what was tried before."""
    board = Board(
        id="test",
        goal="Test",
        context="",
        mode=Mode.SPRINT,
        tasks=[]
    )

    task = Task(
        id="test-task",
        title="Test",
        description="Test task",
        assigned_to="Senior Dev",
        reaper_kill_count=3,
        resurrection_history=[
            ResurrectionRecord(
                attempt_number=1,
                persona="Senior Dev",
                kill_reason="Timeout",
                elapsed_seconds=300,
                partial_notes="Tried recursive approach",
                killed_at="2026-02-08T12:00:00"
            ),
            ResurrectionRecord(
                attempt_number=2,
                persona="Senior Dev",
                kill_reason="Timeout",
                elapsed_seconds=300,
                partial_notes="Tried iterative approach",
                killed_at="2026-02-08T12:05:00"
            ),
            ResurrectionRecord(
                attempt_number=3,
                persona="Senior Dev",
                kill_reason="Infinite loop",
                elapsed_seconds=180,
                partial_notes="Tried streaming approach",
                killed_at="2026-02-08T12:10:00"
            )
        ]
    )

    with patch('waverunner.agent.run_claude') as mock_run:
        mock_run.side_effect = [
            "All previous approaches failed. Need to simplify the problem - maybe spike first?",
            "Approved. Create investigation spike."
        ]

        negotiate_resurrection(board, task, "Still hanging")

        # Agent should see history
        agent_call = mock_run.call_args_list[0]
        agent_prompt = agent_call[1]['prompt']
        assert "recursive" in agent_prompt or "Attempt #" in agent_prompt


def test_negotiation_returns_structured_adjustment():
    """Adjustment should be structured, not just raw text."""
    board = Board(
        id="test",
        goal="Test",
        context="",
        mode=Mode.SPRINT,
        tasks=[]
    )

    task = Task(
        id="test-task",
        title="Test",
        description="Test task",
        assigned_to="Senior Dev",
        reaper_kill_count=1,
        resurrection_history=[]
    )

    with patch('waverunner.agent.run_claude') as mock_run:
        mock_run.side_effect = [
            "Reduce scope: only implement core feature, skip validation",
            "Approved."
        ]

        adjustment = negotiate_resurrection(board, task, "Timeout")

        # Should be a string with clear guidance
        assert isinstance(adjustment, str)
        assert len(adjustment) > 10
        assert "core" in adjustment.lower() or "reduce" in adjustment.lower()


def test_max_negotiation_rounds_prevents_infinite_loop():
    """Should not negotiate forever if they can't agree."""
    board = Board(
        id="test",
        goal="Test",
        context="",
        mode=Mode.SPRINT,
        tasks=[]
    )

    task = Task(
        id="test-task",
        title="Test",
        description="Test task",
        assigned_to="Senior Dev",
        reaper_kill_count=1,
        resurrection_history=[]
    )

    with patch('waverunner.agent.run_claude') as mock_run:
        # Reaper keeps rejecting
        mock_run.side_effect = [
            "Try approach A", "REJECTED",
            "Try approach B", "REJECTED",
            "Try approach C", "REJECTED",
            "Try approach D", "REJECTED",
            "Try approach E", "REJECTED",
        ]

        # Should give up after max rounds (e.g., 3)
        with pytest.raises(Exception, match="Could not reach agreement|max.*rounds"):
            negotiate_resurrection(board, task, "Failed", max_rounds=3)
