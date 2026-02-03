"""
Tests for git auto-commit per wave functionality.
"""

import pytest
import os
import subprocess
from pathlib import Path
from waverunner.models import Board, Task, Mode, TaskStatus, Complexity
from waverunner.git_integration import GitIntegration, should_auto_commit


def test_git_integration_detects_repo(tmp_path):
    """GitIntegration should detect if directory is a git repo."""
    # Create a git repo
    os.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)

    git = GitIntegration(tmp_path)
    assert git.is_git_repo() is True


def test_git_integration_non_repo(tmp_path):
    """GitIntegration should detect non-git directories."""
    os.chdir(tmp_path)
    git = GitIntegration(tmp_path)
    assert git.is_git_repo() is False


def test_git_integration_commit_wave(tmp_path):
    """Should create commit after wave completion."""
    os.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)

    # Create a test file to commit
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    git = GitIntegration(tmp_path)

    tasks = [
        Task(id="1", title="Setup database", description="Setup DB", status=TaskStatus.COMPLETED),
        Task(id="2", title="Create models", description="Create models", status=TaskStatus.COMPLETED),
    ]

    commit_sha = git.commit_wave(wave_number=1, tasks=tasks)

    assert commit_sha is not None
    assert len(commit_sha) == 40  # Git SHA is 40 chars


def test_git_integration_commit_message_format(tmp_path):
    """Commit message should have proper format."""
    os.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)

    # Create and commit initial file
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], check=True, capture_output=True)

    # Modify file
    test_file.write_text("modified")

    git = GitIntegration(tmp_path)
    tasks = [Task(id="1", title="Setup database", description="Setup DB", status=TaskStatus.COMPLETED)]

    git.commit_wave(wave_number=1, tasks=tasks)

    # Check commit message
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"],
        capture_output=True,
        text=True,
        check=True
    )

    message = result.stdout.strip()
    assert "Wave 1" in message
    assert "Setup database" in message


def test_git_integration_no_changes_no_commit(tmp_path):
    """Should not create commit if no changes."""
    os.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)

    # Create initial commit
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], check=True, capture_output=True)

    git = GitIntegration(tmp_path)
    tasks = [Task(id="1", title="Test task", description="Test", status=TaskStatus.COMPLETED)]

    # Try to commit with no changes
    commit_sha = git.commit_wave(wave_number=1, tasks=tasks)

    assert commit_sha is None  # Should return None when no changes


def test_git_integration_includes_artifacts(tmp_path):
    """Commit message should list task artifacts."""
    os.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)

    # Create and commit initial file
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], check=True, capture_output=True)

    # Modify file
    test_file.write_text("modified")

    git = GitIntegration(tmp_path)
    tasks = [
        Task(
            id="1",
            title="Create models",
            description="Create models",
            status=TaskStatus.COMPLETED,
            artifacts=["models/user.py", "models/post.py"]
        )
    ]

    git.commit_wave(wave_number=1, tasks=tasks)

    # Check commit message includes artifacts
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"],
        capture_output=True,
        text=True,
        check=True
    )

    message = result.stdout.strip()
    assert "models/user.py" in message
    assert "models/post.py" in message


def test_should_auto_commit_flag():
    """should_auto_commit should respect board settings."""
    board = Board(id="test", goal="Test", context="", mode=Mode.SPRINT, tasks=[])

    # Default should be False
    assert should_auto_commit(board) is False

    # Enable auto-commit
    board.git_auto_commit = True
    assert should_auto_commit(board) is True


def test_board_has_git_auto_commit_field():
    """Board should have git_auto_commit field."""
    board = Board(id="test", goal="Test", context="", mode=Mode.SPRINT, tasks=[])
    assert hasattr(board, 'git_auto_commit')


def test_git_integration_wave_summary(tmp_path):
    """Commit message should include wave summary."""
    os.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)

    # Create and commit initial file
    test_file = tmp_path / "test.txt"
    test_file.write_text("initial")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], check=True, capture_output=True)

    # Modify file
    test_file.write_text("modified")

    git = GitIntegration(tmp_path)
    tasks = [
        Task(id="1", title="Setup", description="Setup", status=TaskStatus.COMPLETED, complexity=Complexity.SMALL),
        Task(id="2", title="Implement", description="Implement", status=TaskStatus.COMPLETED, complexity=Complexity.MEDIUM),
    ]

    git.commit_wave(wave_number=2, tasks=tasks)

    result = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"],
        capture_output=True,
        text=True,
        check=True
    )

    message = result.stdout.strip()
    assert "Wave 2" in message
    assert "2 tasks" in message.lower()
