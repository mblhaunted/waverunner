"""
Tests for the Ralph validation loop.

After each implementation task completes, waverunner runs a configurable
validation command (e.g. `cargo build`, `npm run typecheck`, `pytest`).
If it fails, the task is retried with the failure output injected as context.
Only mark DONE when validation passes.

This catches the class of bug that killed holophonor:
- Wrong model names (would fail at runtime, caught by build/typecheck)
- Broken IPC parameter names (caught by typecheck)
- Unrealistic timeouts (caught by integration test)
"""

import subprocess
import pytest
from unittest.mock import patch, MagicMock, call
from waverunner.models import Board, Task, TaskStatus, TaskType, Complexity, Mode
from waverunner.agent import run_ralph_validation


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_board(validate_cmd: str = "") -> Board:
    board = Board(id="test-board", goal="test goal", context="", mode=Mode.SPRINT)
    if validate_cmd:
        board.validate_steps = [validate_cmd]
    return board


def make_impl_task(title: str = "Implement feature") -> Task:
    task = Task(id="task-1", title=title, description="", task_type=TaskType.IMPLEMENTATION)
    task.status = TaskStatus.IN_PROGRESS
    return task


def make_spike_task() -> Task:
    task = Task(id="spike-1", title="Investigate options", description="", task_type=TaskType.SPIKE)
    task.status = TaskStatus.IN_PROGRESS
    return task


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRalphValidationSkip:
    """Validation is skipped in certain conditions."""

    def test_skipped_when_no_validate_cmd(self):
        """No validate_cmd → returns True immediately, no subprocess called."""
        board = make_board(validate_cmd="")
        task = make_impl_task()
        with patch("subprocess.run") as mock_run:
            result = run_ralph_validation(board, task, execute_task_fn=None)
        assert result is True
        mock_run.assert_not_called()

    def test_skipped_for_spike_tasks(self):
        """Spike tasks are skipped — validation only applies to implementation."""
        board = make_board(validate_cmd="npm run build")
        task = make_spike_task()
        with patch("subprocess.run") as mock_run:
            result = run_ralph_validation(board, task, execute_task_fn=None)
        assert result is True
        mock_run.assert_not_called()


class TestRalphValidationPass:
    """Validation succeeds on first attempt."""

    def test_passes_immediately_returns_true(self):
        """Validation exits 0 → returns True, no retry."""
        board = make_board(validate_cmd="cargo build")
        task = make_impl_task()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = run_ralph_validation(board, task, execute_task_fn=None)

        assert result is True
        assert mock_run.call_count == 1

    def test_passes_on_second_attempt(self):
        """Validation fails once, then passes → True, one retry."""
        board = make_board(validate_cmd="npm run typecheck")
        task = make_impl_task()

        fail_result = MagicMock(returncode=1, stdout="error TS2345", stderr="")
        pass_result = MagicMock(returncode=0, stdout="", stderr="")

        retry_artifacts = (["src/fix.ts"], Complexity.SMALL, "Fixed the type error")

        def fake_execute(b, t, **kwargs):
            return retry_artifacts

        with patch("subprocess.run", side_effect=[fail_result, pass_result]):
            result = run_ralph_validation(board, task, execute_task_fn=fake_execute)

        assert result is True

    def test_failure_context_injected_into_task_notes(self):
        """When validation fails, failure output is injected into task.notes before retry."""
        board = make_board(validate_cmd="cargo check")
        task = make_impl_task()
        task.notes = "Original notes"

        fail_result = MagicMock(returncode=1, stdout="error[E0308]: mismatched types", stderr="")
        pass_result = MagicMock(returncode=0, stdout="", stderr="")

        captured_notes = []

        def fake_execute(b, t, **kwargs):
            captured_notes.append(t.notes)
            return ([], Complexity.SMALL, "Retried")

        with patch("subprocess.run", side_effect=[fail_result, pass_result]):
            run_ralph_validation(board, task, execute_task_fn=fake_execute)

        assert len(captured_notes) == 1
        assert "Ralph validation failed" in captured_notes[0]
        assert "error[E0308]: mismatched types" in captured_notes[0]


class TestRalphValidationFailure:
    """Validation fails all attempts."""

    def test_returns_false_after_max_retries(self):
        """All 3 attempts fail → returns False."""
        board = make_board(validate_cmd="pytest")
        task = make_impl_task()

        fail_result = MagicMock(returncode=1, stdout="FAILED test_thing.py", stderr="")

        def fake_execute(b, t, **kwargs):
            return ([], Complexity.SMALL, "tried")

        with patch("subprocess.run", return_value=fail_result):
            result = run_ralph_validation(board, task, execute_task_fn=fake_execute)

        assert result is False

    def test_exactly_three_validation_attempts(self):
        """Runs validation exactly 3 times (initial + 2 retries)."""
        board = make_board(validate_cmd="make test")
        task = make_impl_task()

        fail_result = MagicMock(returncode=1, stdout="error", stderr="")
        run_calls = []

        def fake_run(*args, **kwargs):
            run_calls.append(args)
            return fail_result

        def fake_execute(b, t, **kwargs):
            return ([], Complexity.SMALL, "")

        with patch("subprocess.run", side_effect=fake_run):
            run_ralph_validation(board, task, execute_task_fn=fake_execute)

        # 3 validations: initial + 2 retries
        assert len(run_calls) == 3

    def test_execute_called_twice_on_two_failures(self):
        """execute_task called twice when first two validations fail but third also fails."""
        board = make_board(validate_cmd="npm test")
        task = make_impl_task()

        fail_result = MagicMock(returncode=1, stdout="fail", stderr="")
        execute_calls = []

        def fake_execute(b, t, **kwargs):
            execute_calls.append(True)
            return ([], Complexity.SMALL, "")

        with patch("subprocess.run", return_value=fail_result):
            run_ralph_validation(board, task, execute_task_fn=fake_execute)

        # execute_task called for attempt 1 retry and attempt 2 retry = 2 times
        assert len(execute_calls) == 2

    def test_failure_notes_accumulated(self):
        """After exhausting retries, task notes contain validation failure info."""
        board = make_board(validate_cmd="cargo test")
        task = make_impl_task()
        task.notes = ""

        fail_result = MagicMock(returncode=1, stdout="FAILED: test_audio_engine", stderr="")

        def fake_execute(b, t, **kwargs):
            return ([], Complexity.SMALL, "attempted fix")

        with patch("subprocess.run", return_value=fail_result):
            run_ralph_validation(board, task, execute_task_fn=fake_execute)

        assert "Ralph" in task.notes and "validation failed" in task.notes


class TestRalphBoardField:
    """validate_steps is stored on Board and serialized."""

    def test_board_has_validate_steps_field(self):
        board = Board(id="x", goal="y", context="", mode=Mode.SPRINT)
        assert hasattr(board, "validate_steps")
        assert board.validate_steps == []

    def test_validate_steps_serialized(self):
        board = Board(id="x", goal="y", context="", mode=Mode.SPRINT)
        board.validate_steps = ["npm run build", "npm test"]
        d = board.to_dict()
        assert d["validate_steps"] == ["npm run build", "npm test"]

    def test_validate_steps_deserialized(self):
        board = Board(id="x", goal="y", context="", mode=Mode.SPRINT)
        board.validate_steps = ["cargo check", "cargo test --lib"]
        board2 = Board.from_dict(board.to_dict())
        assert board2.validate_steps == ["cargo check", "cargo test --lib"]

    def test_validate_steps_defaults_to_empty(self):
        """Boards without validate_steps in YAML load cleanly."""
        data = {"id": "x", "goal": "y", "mode": "sprint"}
        board = Board.from_dict(data)
        assert board.validate_steps == []

    def test_legacy_validate_cmd_migrated_to_steps(self):
        """Old boards with validate_cmd but no validate_steps get migrated on load."""
        data = {"id": "x", "goal": "y", "mode": "sprint", "validate_cmd": "cargo build"}
        board = Board.from_dict(data)
        assert board.validate_steps == ["cargo build"]
