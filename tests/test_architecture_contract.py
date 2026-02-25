"""Tests for the architecture contract generation feature (TDD)."""

import pytest
from unittest.mock import patch
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity, TaskType
from waverunner.providers import MockLLMProvider
import waverunner.agent as agent_module


MOCK_ARCH_CONTRACT = """# Architecture Contract

## File/Module Structure
- synthesizer.py: Core synthesis engine
- audio_utils.py: Audio utilities and playback

## Interface Contracts
- `Synthesizer.generate(frequency: float, duration: float) -> bytes`
- `play_audio(data: bytes, sample_rate: int = 44100) -> None`

## Package Choices
- sounddevice for audio output (NOT pyaudio)
- numpy for signal generation

## Integration Points
- synthesizer.py imports numpy
- audio_utils.py imports sounddevice
"""

MOCK_ARCH_PROMPT_KEYWORD = "Architecture Contract Generation"


def _make_board_with_tasks(task_types):
    """Helper: create a board with tasks of given types."""
    board = Board(id="test-board", goal="Build audio synthesizer", context="")
    for i, task_type in enumerate(task_types):
        board.tasks.append(Task(
            id=f"task-{i}",
            title=f"Task {i}",
            description="",
            task_type=task_type,
            complexity=Complexity.SMALL,
        ))
    return board


# ─── generate_architecture_contract tests ───────────────────────────────────

def test_contract_generated_for_multi_impl_tasks():
    """2+ implementation tasks → non-empty contract, exactly 1 LLM call."""
    mock = MockLLMProvider({MOCK_ARCH_PROMPT_KEYWORD: MOCK_ARCH_CONTRACT})
    board = _make_board_with_tasks([TaskType.IMPLEMENTATION, TaskType.IMPLEMENTATION])

    with patch('waverunner.agent.get_current_provider', return_value=mock):
        result = agent_module.generate_architecture_contract(board)

    assert result != "", "Contract should be non-empty for 2 impl tasks"
    assert mock.call_count == 1, "Should make exactly 1 LLM call"


def test_contract_skipped_for_spike_only_plan():
    """All spike tasks → returns '', 0 LLM calls."""
    mock = MockLLMProvider({MOCK_ARCH_PROMPT_KEYWORD: MOCK_ARCH_CONTRACT})
    board = _make_board_with_tasks([TaskType.SPIKE, TaskType.SPIKE, TaskType.SPIKE])

    with patch('waverunner.agent.get_current_provider', return_value=mock):
        result = agent_module.generate_architecture_contract(board)

    assert result == "", "Contract should be empty for spike-only plan"
    assert mock.call_count == 0, "Should make 0 LLM calls for spike-only plan"


def test_contract_skipped_for_single_impl_task():
    """1 implementation task → returns '', 0 LLM calls (no parallelism needed)."""
    mock = MockLLMProvider({MOCK_ARCH_PROMPT_KEYWORD: MOCK_ARCH_CONTRACT})
    board = _make_board_with_tasks([TaskType.IMPLEMENTATION])

    with patch('waverunner.agent.get_current_provider', return_value=mock):
        result = agent_module.generate_architecture_contract(board)

    assert result == "", "Contract should be empty for single impl task"
    assert mock.call_count == 0, "Should make 0 LLM calls for single impl task"


def test_contract_injected_into_task_system_prompt():
    """Board with arch spec → system prompt in execute_task contains 'BINDING ARCHITECTURE CONTRACT'."""
    board = Board(id="test-board", goal="Build synthesizer", context="")
    board.architecture_spec = MOCK_ARCH_CONTRACT
    board.tasks = [
        Task(id="impl-1", title="Implement synth", description="Build it",
             task_type=TaskType.IMPLEMENTATION, complexity=Complexity.SMALL)
    ]

    # Capture the system_prompt passed to run_claude
    captured = {}

    def mock_run_claude(prompt, system_prompt=None, **kwargs):
        captured['system_prompt'] = system_prompt or prompt
        return """```yaml
artifacts:
  - synthesizer.py
actual_complexity: small
notes: "Done"
```"""

    with patch('waverunner.agent.run_claude', side_effect=mock_run_claude):
        agent_module.execute_task(board, board.tasks[0])

    assert 'system_prompt' in captured, "run_claude should have been called"
    assert "BINDING ARCHITECTURE CONTRACT" in captured['system_prompt'], \
        "System prompt should contain BINDING ARCHITECTURE CONTRACT section"


def test_contract_stored_on_board_after_planning():
    """After generate_plan_collaborative runs, board.architecture_spec should be populated."""
    from waverunner.providers import MockLLMProvider

    # Mock LLM returns a minimal plan with 2 impl tasks
    plan_yaml = """```yaml
risks: []
assumptions: []
out_of_scope: []
definition_of_done:
  - Works
tasks:
  - id: "impl-1"
    title: "Build core"
    description: "Core impl"
    complexity: small
    task_type: implementation
    acceptance_criteria:
      - Works
    dependencies: []
  - id: "impl-2"
    title: "Build UI"
    description: "UI impl"
    complexity: small
    task_type: implementation
    acceptance_criteria:
      - Works
    dependencies: []
```"""

    arch_contract_response = MOCK_ARCH_CONTRACT

    call_count = [0]
    call_prompts = []

    def mock_run_claude(prompt, system_prompt=None, **kwargs):
        call_count[0] += 1
        call_prompts.append(prompt[:200])

        if MOCK_ARCH_PROMPT_KEYWORD in prompt:
            return arch_contract_response

        # Return plan YAML for any planning call
        return plan_yaml

    board = Board(id="test-board", goal="Build audio synthesizer", context="")

    with patch('waverunner.agent.run_claude', side_effect=mock_run_claude):
        with patch('waverunner.agent.run_multi_agent_discussion', return_value="Mock discussion"):
            with patch('waverunner.agent.assess_if_trivial', return_value=(False, "")):
                result = agent_module.generate_plan_collaborative(board, auto=True)

    # The board should have architecture_spec set
    assert result.architecture_spec != "", \
        "Board should have non-empty architecture_spec after planning with 2+ impl tasks"
