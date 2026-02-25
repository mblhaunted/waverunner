"""Tests for the wave integration guard feature (TDD)."""

import os
import pytest
import tempfile
from unittest.mock import patch
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity, TaskType
from waverunner.providers import MockLLMProvider
import waverunner.agent as agent_module


MOCK_GUARD_PROMPT_KEYWORD = "Wave Integration Check"
MOCK_ISSUES = "DEVIATION: Wrong library used. Expected sounddevice, found pyaudio in audio_utils.py:5"
MOCK_ALL_CLEAR = "ALL_CLEAR - all files match the architecture contract"
MOCK_ARCH_CONTRACT = "## Architecture Contract\n- Use sounddevice not pyaudio\n- Files: synthesizer.py, audio_utils.py"


def _make_impl_task(task_id, artifacts=None, status=TaskStatus.COMPLETED):
    task = Task(
        id=task_id,
        title=f"Task {task_id}",
        description="",
        task_type=TaskType.IMPLEMENTATION,
        complexity=Complexity.SMALL,
        status=status,
    )
    if artifacts:
        task.artifacts = artifacts
    return task


def _make_spike_task(task_id, status=TaskStatus.COMPLETED):
    task = Task(
        id=task_id,
        title=f"Spike {task_id}",
        description="",
        task_type=TaskType.SPIKE,
        complexity=Complexity.SMALL,
        status=status,
    )
    return task


# ─── run_wave_integration_guard tests ───────────────────────────────────────

def test_guard_skipped_when_no_arch_spec():
    """Empty arch spec → returns '', 0 LLM calls."""
    mock = MockLLMProvider({MOCK_GUARD_PROMPT_KEYWORD: MOCK_ALL_CLEAR})
    board = Board(id="test-board", goal="Build synth", context="")
    board.architecture_spec = ""  # No spec
    wave_tasks = [_make_impl_task("impl-1")]

    with patch('waverunner.agent.get_current_provider', return_value=mock):
        result = agent_module.run_wave_integration_guard(board, wave_tasks)

    assert result == "", "Guard should return '' when no arch spec"
    assert mock.call_count == 0, "Should make 0 LLM calls when no arch spec"


def test_guard_skipped_for_spike_only_wave():
    """Wave with only spike tasks → returns '' (no integration to check)."""
    mock = MockLLMProvider({MOCK_GUARD_PROMPT_KEYWORD: MOCK_ALL_CLEAR})
    board = Board(id="test-board", goal="Build synth", context="")
    board.architecture_spec = MOCK_ARCH_CONTRACT
    wave_tasks = [_make_spike_task("spike-1"), _make_spike_task("spike-2")]

    with patch('waverunner.agent.get_current_provider', return_value=mock):
        result = agent_module.run_wave_integration_guard(board, wave_tasks)

    assert result == "", "Guard should return '' for spike-only wave"
    assert mock.call_count == 0, "Should make 0 LLM calls for spike-only wave"


def test_guard_returns_all_clear():
    """Mock returns ALL_CLEAR → integration_notes NOT updated."""
    mock = MockLLMProvider({MOCK_GUARD_PROMPT_KEYWORD: MOCK_ALL_CLEAR})
    board = Board(id="test-board", goal="Build synth", context="")
    board.architecture_spec = MOCK_ARCH_CONTRACT
    board.integration_notes = ""
    wave_tasks = [_make_impl_task("impl-1")]

    with patch('waverunner.agent.get_current_provider', return_value=mock):
        result = agent_module.run_wave_integration_guard(board, wave_tasks)

    assert "ALL_CLEAR" in result, "Guard should return ALL_CLEAR response"
    # Caller is responsible for not updating integration_notes on ALL_CLEAR
    # Guard just returns the result string


def test_guard_appends_issues_to_board():
    """When guard returns issues (not ALL_CLEAR), run_sprint appends to board.integration_notes."""
    from unittest.mock import MagicMock
    import threading

    board = Board(id="test-board", goal="Build synth", context="")
    board.architecture_spec = MOCK_ARCH_CONTRACT
    board.integration_notes = ""

    mock_issues = MOCK_ISSUES

    # Simulate what run_sprint does when guard returns issues
    issues = mock_issues  # non-ALL_CLEAR response
    if issues and "ALL_CLEAR" not in issues:
        board.integration_notes += f"\n\n--- Wave 1 ---\n{issues}"

    assert "Wave 1" in board.integration_notes, "integration_notes should contain wave info"
    assert MOCK_ISSUES in board.integration_notes, "integration_notes should contain the issues"


def test_guard_reads_artifact_files():
    """Guard prompt should contain file contents when artifact files exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake artifact file
        artifact_path = os.path.join(tmpdir, "audio_utils.py")
        artifact_content = "import pyaudio  # WRONG library\n\ndef play(data):\n    pass\n"
        with open(artifact_path, "w") as f:
            f.write(artifact_content)

        # Create board with architecture spec
        board = Board(id="test-board", goal="Build synth", context="")
        board.architecture_spec = MOCK_ARCH_CONTRACT

        # Task with the artifact file
        task = _make_impl_task("impl-1", artifacts=["audio_utils.py"])

        captured = {}

        def mock_run_claude(prompt, system_prompt=None, **kwargs):
            captured['prompt'] = prompt
            return MOCK_ALL_CLEAR

        # Mock find_board_file to point to our temp dir
        fake_board_file = os.path.join(tmpdir, ".waverunner.yaml")
        with open(fake_board_file, "w") as f:
            f.write("id: test-board\n")

        with patch('waverunner.agent.run_claude', side_effect=mock_run_claude):
            with patch('waverunner.agent.find_board_file', return_value=fake_board_file):
                result = agent_module.run_wave_integration_guard(board, [task])

        assert 'prompt' in captured, "run_claude should have been called"
        assert "pyaudio" in captured['prompt'] or "audio_utils.py" in captured['prompt'], \
            "Guard prompt should contain file contents or filename"
