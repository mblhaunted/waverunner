"""
Tests for determine_validate_steps().

Planning auto-determines an ordered list of validation steps. Each step
is an independent shell command that proves a specific thing works.
"""

import pytest
from unittest.mock import patch
from waverunner.models import Board, Task, TaskType, Mode
from waverunner.agent import determine_validate_steps
from waverunner.providers import MockLLMProvider


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_board(goal: str = "Build something") -> Board:
    return Board(id="test-board", goal=goal, context="", mode=Mode.SPRINT)


def make_impl_task(title: str = "Implement feature", description: str = "") -> Task:
    return Task(id="task-1", title=title, description=description, task_type=TaskType.IMPLEMENTATION)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDetermineValidateStepsBasic:
    """Returns a list of steps, not a single command."""

    def test_returns_list_for_rust_project(self):
        board = make_board(goal="Build a CLI tool in Rust")
        board.tasks = [make_impl_task("Implement CLI")]

        yaml_response = "```yaml\n- cargo build\n- cargo test --lib\n```"
        provider = MockLLMProvider({"Validation Steps Determination": yaml_response})
        with patch("waverunner.agent.get_current_provider", return_value=provider):
            result = determine_validate_steps(board)

        assert isinstance(result, list)
        assert "cargo build" in result
        assert "cargo test --lib" in result

    def test_returns_multiple_steps(self):
        board = make_board(goal="Build a Tauri desktop app")
        board.tasks = [make_impl_task("Implement backend"), make_impl_task("Implement frontend")]

        yaml_response = "```yaml\n- cargo build\n- npm run typecheck\n- npm test -- --run\n```"
        provider = MockLLMProvider({"Validation Steps Determination": yaml_response})
        with patch("waverunner.agent.get_current_provider", return_value=provider):
            result = determine_validate_steps(board)

        assert len(result) == 3
        assert result[0] == "cargo build"
        assert result[1] == "npm run typecheck"
        assert result[2] == "npm test -- --run"

    def test_returns_empty_list_on_failure(self):
        board = make_board(goal="Build something")
        board.tasks = [make_impl_task()]

        provider = MockLLMProvider({"Validation Steps Determination": "not valid yaml {"})
        with patch("waverunner.agent.get_current_provider", return_value=provider):
            result = determine_validate_steps(board)

        assert result == []

    def test_returns_empty_list_on_exception(self):
        board = make_board(goal="Build something")
        board.tasks = [make_impl_task()]

        def failing_run(*args, **kwargs):
            raise RuntimeError("Provider failed")

        provider = MockLLMProvider({})
        provider.run = failing_run
        with patch("waverunner.agent.get_current_provider", return_value=provider):
            result = determine_validate_steps(board)

        assert result == []


class TestDetermineValidateStepsContext:
    """Prompt includes relevant context."""

    def test_prompt_includes_goal(self):
        board = make_board(goal="Build a Rust audio synthesizer")
        board.tasks = [make_impl_task("Implement synthesis engine")]

        captured = []

        def capturing_run(prompt, system_prompt, **kwargs):
            captured.append(prompt)
            return "```yaml\n- cargo build\n```"

        provider = MockLLMProvider({})
        provider.run = capturing_run
        with patch("waverunner.agent.get_current_provider", return_value=provider):
            determine_validate_steps(board)

        assert captured and "Rust audio synthesizer" in captured[0]

    def test_prompt_includes_task_list(self):
        board = make_board(goal="Build a CLI")
        board.tasks = [
            make_impl_task("Implement argument parser"),
            make_impl_task("Implement file processor"),
        ]

        captured = []

        def capturing_run(prompt, system_prompt, **kwargs):
            captured.append(prompt)
            return "```yaml\n- cargo build\n```"

        provider = MockLLMProvider({})
        provider.run = capturing_run
        with patch("waverunner.agent.get_current_provider", return_value=provider):
            determine_validate_steps(board)

        assert "Implement argument parser" in captured[0]
        assert "Implement file processor" in captured[0]

    def test_prompt_includes_architecture_spec(self):
        board = make_board(goal="Build an app")
        board.tasks = [make_impl_task()]
        board.architecture_spec = "## Stack\n- Rust backend\n- TypeScript frontend"

        captured = []

        def capturing_run(prompt, system_prompt, **kwargs):
            captured.append(prompt)
            return "```yaml\n- cargo build\n```"

        provider = MockLLMProvider({})
        provider.run = capturing_run
        with patch("waverunner.agent.get_current_provider", return_value=provider):
            determine_validate_steps(board)

        assert "architecture" in captured[0].lower() or "Architecture" in captured[0]


class TestRunValidateSteps:
    """_run_validate_steps runs each step and stops on first failure."""

    def test_all_pass_returns_true(self):
        from waverunner.agent import _run_validate_steps
        from unittest.mock import MagicMock
        pass_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=pass_result) as mock_run:
            passed, output = _run_validate_steps(["step1", "step2", "step3"])
        assert passed is True
        assert mock_run.call_count == 3

    def test_stops_at_first_failure(self):
        from waverunner.agent import _run_validate_steps
        from unittest.mock import MagicMock
        fail_result = MagicMock(returncode=1, stdout="error", stderr="")
        pass_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", side_effect=[pass_result, fail_result, pass_result]) as mock_run:
            passed, output = _run_validate_steps(["step1", "step2", "step3"])
        assert passed is False
        assert mock_run.call_count == 2  # stopped after step2 failed

    def test_failure_output_contains_step_name(self):
        from waverunner.agent import _run_validate_steps
        from unittest.mock import MagicMock
        fail_result = MagicMock(returncode=1, stdout="type error", stderr="")
        with patch("subprocess.run", return_value=fail_result):
            passed, output = _run_validate_steps(["npm run typecheck"])
        assert "npm run typecheck" in output
        assert "type error" in output
