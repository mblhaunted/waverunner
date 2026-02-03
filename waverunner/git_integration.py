"""
Git integration for automatic commits per wave.

Creates checkpoint commits after each wave completes.
"""

import subprocess
from pathlib import Path
from typing import List, Optional
from .models import Task, Board


def should_auto_commit(board: Board) -> bool:
    """Check if auto-commit is enabled for this board."""
    return getattr(board, 'git_auto_commit', False)


class GitIntegration:
    """Handles git operations for waverunner."""

    def __init__(self, repo_path: Path = None):
        """
        Initialize git integration.

        Args:
            repo_path: Path to git repository (defaults to current directory)
        """
        self.repo_path = repo_path or Path.cwd()

    def is_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                check=True
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return False

    def commit_wave(
        self,
        wave_number: int,
        tasks: List[Task],
        goal: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a commit for a completed wave.

        Args:
            wave_number: Wave number
            tasks: List of completed tasks in this wave
            goal: Optional sprint goal

        Returns:
            Commit SHA if successful, None if no changes or error
        """
        if not self.is_git_repo():
            return None

        if not self.has_changes():
            return None

        # Build commit message
        message_lines = [f"Wave {wave_number} complete"]

        if goal:
            message_lines.append(f"\nGoal: {goal}")

        message_lines.append(f"\nCompleted {len(tasks)} tasks:")
        for task in tasks:
            message_lines.append(f"- {task.title}")

            # Include artifacts if any
            if task.artifacts:
                for artifact in task.artifacts:
                    message_lines.append(f"  - {artifact}")

        message = "\n".join(message_lines)

        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )

            # Create commit
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )

            # Get commit SHA
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            return result.stdout.strip()

        except subprocess.CalledProcessError:
            return None
