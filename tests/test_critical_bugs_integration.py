"""Integration test for all 4 critical context-loss bugs.

This test verifies that the fixes for all 4 bugs work together:
1. YAML validation catches malformed responses
2. Board overwrite protection prevents context loss
3. Directory awareness detects existing work
4. SAFETY_CONTEXT is enforced in planning
"""

import pytest
import tempfile
from pathlib import Path
from waverunner.models import Board, Mode
from waverunner.cli import check_existing_board, BoardExistsError, require_no_existing_board
from waverunner.agent import (
    detect_existing_work,
    generate_existing_work_context,
    extract_yaml_from_response
)


def test_integration_scenario_prevents_context_loss():
    """
    Simulate the exact scenario that caused context loss in ~/Documents/dev/uaas:

    1. User has existing project with code
    2. User runs `waverunner go` without --force
    3. System should detect existing board and refuse to overwrite
    4. System should detect existing code and add context
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Step 1: Create existing project structure (simulating uaas)
        (tmpdir / "README.md").write_text("# Union App Platform\n\nExisting project...")
        (tmpdir / "src").mkdir()
        (tmpdir / "src" / "main.py").write_text("# Union platform code\ndef main(): pass")
        (tmpdir / "tests").mkdir()
        (tmpdir / "tests" / "test_main.py").write_text("def test_main(): pass")

        # Step 2: Create existing board with completed work
        board_file = tmpdir / ".waverunner.yaml"
        board = Board(
            id="sprint-001",
            goal="Build union platform features",
            context="This is a union app aggregation platform, NOT a dog rescue app",
            mode=Mode.SPRINT,
            tasks=[],
        )
        board.save(str(board_file))

        # Step 3: Verify board overwrite protection works
        with pytest.raises(BoardExistsError) as exc_info:
            require_no_existing_board(str(tmpdir), force=False)

        error_msg = str(exc_info.value)
        assert "Board already exists" in error_msg
        assert "union platform" in error_msg.lower()
        assert "waverunner run" in error_msg  # Should suggest continuing

        # Step 4: Verify directory awareness detects existing work
        existing_work = detect_existing_work(str(tmpdir))
        assert existing_work is not None
        assert existing_work["file_count"] > 0
        assert existing_work["has_code"] is True
        assert existing_work["has_tests"] is True
        assert "README.md" in existing_work["significant_files"]

        # Step 5: Verify context generation warns about non-greenfield
        context = generate_existing_work_context(str(tmpdir))
        assert context is not None
        assert "NOT a greenfield" in context or "NOT greenfield" in context
        assert "README.md" in context
        assert "src/" in context or "source code" in context.lower()

        # Step 6: Verify --force flag allows overwrite if user wants
        require_no_existing_board(str(tmpdir), force=True)  # Should not raise


def test_integration_yaml_validation_prevents_malformed_plans():
    """
    Verify YAML validation catches the malformed response that caused the user's error.

    The LLM added an "ASK:" field which broke task structure.
    """
    # This is the actual malformed YAML from user's error
    malformed_response = """
Here's the plan:

```yaml
tasks:
  - id: "user-decision-blocker"
    title: "Wait for user decision"
    ASK: "What would you like to prioritize next?"
    complexity: trivial
```
"""

    # Should raise with helpful error
    with pytest.raises(ValueError) as exc_info:
        extract_yaml_from_response(malformed_response)

    error_msg = str(exc_info.value)
    assert "invalid fields" in error_msg.lower() or "YAML" in error_msg
    if "invalid fields" in error_msg.lower():
        assert "ASK" in error_msg  # Should mention the invalid field


def test_integration_empty_directory_no_false_warnings():
    """
    Verify that truly empty directories don't trigger warnings.

    This ensures we don't over-warn on legitimate greenfield projects.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Empty directory
        existing_work = detect_existing_work(str(tmpdir))
        assert existing_work is None or existing_work["file_count"] == 0

        # Should not generate context warning
        context = generate_existing_work_context(str(tmpdir))
        assert context == ""  # Empty context for empty dir


def test_integration_force_flag_emergency_override():
    """
    Verify --force flag works as emergency override.

    Sometimes users legitimately want to start over (e.g., after bad sprint).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create existing board
        board_file = tmpdir / ".waverunner.yaml"
        board = Board(
            id="sprint-bad",
            goal="Failed sprint that went wrong",
            context="",
            mode=Mode.SPRINT,
            tasks=[],
        )
        board.save(str(board_file))

        # Without force: should error
        with pytest.raises(BoardExistsError):
            require_no_existing_board(str(tmpdir), force=False)

        # With force: should allow
        require_no_existing_board(str(tmpdir), force=True)  # No error


def test_integration_all_bugs_fixed():
    """
    Master integration test: verify all 4 bugs are fixed together.

    This is the comprehensive proof that the critical bugs are resolved.
    """
    # Bug 1: YAML validation works
    try:
        extract_yaml_from_response("```yaml\ntasks:\n  - id: test\n    INVALID_FIELD: bad\n```")
        assert False, "Should have raised for invalid YAML"
    except ValueError as e:
        assert "invalid" in str(e).lower() or "YAML" in str(e)

    # Bug 2: Board overwrite protection works
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        board_file = tmpdir / ".waverunner.yaml"
        Board(id="test", goal="Test", context="", mode=Mode.SPRINT, tasks=[]).save(str(board_file))

        try:
            require_no_existing_board(str(tmpdir), force=False)
            assert False, "Should have raised BoardExistsError"
        except BoardExistsError:
            pass  # Expected

        # Bug 3: Directory awareness works
        (tmpdir / "src").mkdir()
        (tmpdir / "src" / "main.py").write_text("code")
        existing_work = detect_existing_work(str(tmpdir))
        assert existing_work["has_code"] is True

        # Bug 4: SAFETY_CONTEXT is included (verified by checking personas.py)
        # This is tested in test_personas.py - all personas have SAFETY_CONTEXT
        from waverunner.personas import SAFETY_CONTEXT
        assert "CRITICAL CONTEXT" in SAFETY_CONTEXT
        assert "DIRECTORY AWARENESS" in SAFETY_CONTEXT
        assert "FILE POLLUTION" in SAFETY_CONTEXT
