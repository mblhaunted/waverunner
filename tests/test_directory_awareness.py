"""Tests for directory awareness and context detection."""

import pytest
import tempfile
from pathlib import Path
from waverunner.agent import detect_existing_work, should_warn_greenfield


def test_detects_non_empty_directory():
    """Should detect when directory has existing code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create some existing files
        (tmpdir / "README.md").write_text("# Existing Project")
        (tmpdir / "src").mkdir()
        (tmpdir / "src" / "main.py").write_text("print('hello')")
        (tmpdir / "tests").mkdir()
        (tmpdir / "tests" / "test_main.py").write_text("def test_main(): pass")

        existing_work = detect_existing_work(str(tmpdir))

        assert existing_work is not None
        assert existing_work["file_count"] > 0
        assert existing_work["has_code"] is True
        assert "README.md" in existing_work["significant_files"]


def test_empty_directory_no_warning():
    """Empty directories should not trigger warnings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        existing_work = detect_existing_work(str(tmpdir))

        assert existing_work is None or existing_work["file_count"] == 0
        assert should_warn_greenfield(str(tmpdir)) is False


def test_detects_python_project():
    """Should detect Python project structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Python project indicators
        (tmpdir / "setup.py").write_text("from setuptools import setup")
        (tmpdir / "requirements.txt").write_text("flask==2.0.0")
        (tmpdir / "myapp").mkdir()
        (tmpdir / "myapp" / "__init__.py").write_text("")

        existing_work = detect_existing_work(str(tmpdir))

        assert existing_work["project_type"] == "python"
        assert existing_work["has_tests"] is False  # No test directory


def test_detects_javascript_project():
    """Should detect JavaScript/Node project structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        (tmpdir / "package.json").write_text('{"name": "myapp"}')
        (tmpdir / "src").mkdir()
        (tmpdir / "src" / "index.js").write_text("console.log('hello')")

        existing_work = detect_existing_work(str(tmpdir))

        assert existing_work["project_type"] == "javascript"


def test_generates_context_from_existing_work():
    """Should generate helpful context string from detected work."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        (tmpdir / "README.md").write_text("# My App\nA cool app")
        (tmpdir / "ARCHITECTURE.md").write_text("# Architecture\nAPI + DB")
        (tmpdir / "src").mkdir()
        (tmpdir / "src" / "main.py").write_text("def main(): pass")
        (tmpdir / "tests").mkdir()
        (tmpdir / "tests" / "test_main.py").write_text("def test(): pass")

        from waverunner.agent import generate_existing_work_context
        context = generate_existing_work_context(str(tmpdir))

        assert "NOT a greenfield project" in context or "NOT greenfield" in context
        assert "README.md" in context
        assert "ARCHITECTURE.md" in context
        assert "src/" in context or "source code" in context.lower()
        assert "tests/" in context or "test" in context.lower()


def test_warns_when_many_files_exist():
    """Should warn when directory has many files (likely existing project)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create 30 files
        for i in range(30):
            (tmpdir / f"file{i}.py").write_text(f"# File {i}")

        assert should_warn_greenfield(str(tmpdir)) is True


def test_ignores_common_artifacts():
    """Should ignore __pycache__, .git, node_modules, etc."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create ignored directories
        (tmpdir / "__pycache__").mkdir()
        (tmpdir / "__pycache__" / "cache.pyc").write_text("")
        (tmpdir / ".git").mkdir()
        (tmpdir / ".git" / "HEAD").write_text("ref: refs/heads/main")
        (tmpdir / "node_modules").mkdir()

        existing_work = detect_existing_work(str(tmpdir))

        # Should not count ignored files
        assert existing_work is None or existing_work["file_count"] == 0


def test_detects_documentation():
    """Should detect documentation files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        (tmpdir / "README.md").write_text("# Docs")
        (tmpdir / "ARCHITECTURE.md").write_text("# Arch")
        (tmpdir / "API.md").write_text("# API")

        existing_work = detect_existing_work(str(tmpdir))

        assert existing_work["has_documentation"] is True
        assert len(existing_work["significant_files"]) >= 3
