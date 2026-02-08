"""Tests for board overwrite protection."""

import pytest
import tempfile
import os
from pathlib import Path
from waverunner.models import Board, Mode
from waverunner.cli import check_existing_board, BoardExistsError


def test_detects_existing_board():
    """Should detect when .waverunner.yaml already exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        board_file = Path(tmpdir) / ".waverunner.yaml"

        # Create existing board
        board = Board(
            id="existing-sprint",
            goal="Existing work",
            context="",
            mode=Mode.SPRINT,
            tasks=[],
        )
        board.save(str(board_file))

        # Should detect it exists
        assert check_existing_board(tmpdir) == board_file


def test_no_board_returns_none():
    """Should return None when no board exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        assert check_existing_board(tmpdir) is None


def test_board_exists_error_has_details():
    """BoardExistsError should include board details."""
    with tempfile.TemporaryDirectory() as tmpdir:
        board_file = Path(tmpdir) / ".waverunner.yaml"

        board = Board(
            id="existing-sprint",
            goal="Existing work with 5 completed tasks",
            context="",
            mode=Mode.SPRINT,
            tasks=[],
        )
        board.save(str(board_file))

        # Should raise error with details
        with pytest.raises(BoardExistsError) as exc_info:
            from waverunner.cli import require_no_existing_board
            require_no_existing_board(tmpdir)

        error = exc_info.value
        assert "Existing work" in str(error)
        assert board_file.name in str(error)


def test_force_flag_bypasses_check():
    """--force flag should allow overwriting existing board."""
    with tempfile.TemporaryDirectory() as tmpdir:
        board_file = Path(tmpdir) / ".waverunner.yaml"

        board = Board(
            id="existing-sprint",
            goal="Old work",
            context="",
            mode=Mode.SPRINT,
            tasks=[],
        )
        board.save(str(board_file))

        # Should NOT raise with force=True
        from waverunner.cli import require_no_existing_board
        require_no_existing_board(tmpdir, force=True)  # Should not raise


def test_continue_flag_loads_existing_board():
    """--continue flag should load and continue existing board."""
    with tempfile.TemporaryDirectory() as tmpdir:
        board_file = Path(tmpdir) / ".waverunner.yaml"

        board = Board(
            id="existing-sprint",
            goal="Work in progress",
            context="",
            mode=Mode.SPRINT,
            tasks=[],
        )
        board.save(str(board_file))

        # Should load existing board
        from waverunner.cli import load_or_create_board
        loaded = load_or_create_board(tmpdir, continue_existing=True)

        assert loaded.goal == "Work in progress"
        assert loaded.id == "existing-sprint"
