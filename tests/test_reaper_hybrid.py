"""
Test hybrid Reaper detection - deterministic checks + LLM fallback.

Hybrid approach:
1. Deterministic checks (cheap, reliable): heartbeat, CPU, patterns
2. LLM fallback (expensive, nuanced): only when inconclusive
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from waverunner.models import Task, Complexity
from waverunner.personas import Persona
from waverunner.agent import reaper_monitor_task


def test_heartbeat_timeout_kills_task():
    """Test that missing heartbeat for 900s+ triggers KILL (15+ min API timeout)."""
    task = Task(
        id="test",
        title="Test Task",
        description="",
        complexity=Complexity.SMALL,
        dependencies=[]
    )

    persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test",
        color="white"
    )

    # Recent output with last heartbeat 950 seconds ago (over 15 min)
    recent_output = [
        "Starting work...\n",
        "[WAVERUNNER_HEARTBEAT]\n",  # Last heartbeat
        "Some output...\n",
        "More output...\n"
    ]

    # 950 seconds of silence since last heartbeat (over 15 min threshold)
    action, reason = reaper_monitor_task(
        task=task,
        persona=persona,
        silence_seconds=950,
        elapsed_seconds=1000,
        recent_output=recent_output
    )

    assert action == "KILL", "Should kill when no heartbeat for >900s (15 min)"
    assert "heartbeat" in reason.lower(), f"Reason should mention heartbeat, got: {reason}"


def test_heartbeat_present_continues():
    """Test that recent heartbeat allows continuation."""
    task = Task(
        id="test",
        title="Test Task",
        description="",
        complexity=Complexity.SMALL,
        dependencies=[]
    )

    persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test",
        color="white"
    )

    # Recent heartbeat (under 15 min threshold)
    recent_output = [
        "Starting work...\n",
        "Processing...\n",
        "[WAVERUNNER_HEARTBEAT]\n",  # Recent heartbeat
        "Still working...\n"
    ]

    # 800 seconds of silence (under 900s threshold), heartbeat is present
    action, reason = reaper_monitor_task(
        task=task,
        persona=persona,
        silence_seconds=800,
        elapsed_seconds=850,
        recent_output=recent_output
    )

    assert action == "CONTINUE", "Should continue with heartbeat under 15 min threshold"


def test_infinite_loop_pattern_kills_task():
    """Test that identical repeating lines trigger KILL."""
    task = Task(
        id="test",
        title="Test Task",
        description="",
        complexity=Complexity.SMALL,
        dependencies=[]
    )

    persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test",
        color="white"
    )

    # Same line repeated 50 times = infinite loop
    recent_output = ["Retrying connection...\n"] * 50

    action, reason = reaper_monitor_task(
        task=task,
        persona=persona,
        silence_seconds=0,  # No silence, actively outputting
        elapsed_seconds=100,
        recent_output=recent_output
    )

    assert action == "KILL", "Should kill on infinite loop pattern"
    assert "loop" in reason.lower() or "repeat" in reason.lower(), \
        f"Reason should mention loop/repeat, got: {reason}"


def test_low_cpu_with_long_silence_kills():
    """Test that 0% CPU + 15+ min silence → KILL."""
    task = Task(
        id="test",
        title="Test Task",
        description="",
        complexity=Complexity.SMALL,
        dependencies=[]
    )

    persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test",
        color="white"
    )

    recent_output = [
        "Starting...\n",
        "Waiting for response...\n"
    ]

    # Mock psutil to show 0% CPU, no network connections
    with patch('waverunner.agent.get_process_status', return_value=(0.0, 'sleeping', 0)):
        action, reason = reaper_monitor_task(
            task=task,
            persona=persona,
            silence_seconds=950,  # 15+ minutes silence (over threshold)
            elapsed_seconds=1000,
            recent_output=recent_output,
            process_pid=12345
        )

    assert action == "KILL", "Should kill with 0% CPU + 15+ min silence"
    assert "cpu" in reason.lower() or "idle" in reason.lower() or "hung" in reason.lower(), \
        f"Reason should mention CPU/idle/hung, got: {reason}"


def test_high_cpu_with_long_silence_continues():
    """Test that high CPU + silence = legitimate computation, CONTINUE."""
    task = Task(
        id="test",
        title="Test Task",
        description="",
        complexity=Complexity.LARGE,
        dependencies=[]
    )

    persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test",
        color="white"
    )

    recent_output = [
        "Compiling project...\n",
        "Building dependencies...\n"
    ]

    # Mock psutil to show 95% CPU (actively computing), no network connections
    with patch('waverunner.agent.get_process_status', return_value=(95.0, 'running', 0)):
        action, reason = reaper_monitor_task(
            task=task,
            persona=persona,
            silence_seconds=950,  # 15+ min silence but high CPU = legitimate computation
            elapsed_seconds=1000,
            recent_output=recent_output,
            process_pid=12345
        )

    assert action == "CONTINUE", "Should continue with high CPU even with 15+ min silence (computation)"


def test_llm_fallback_only_when_inconclusive():
    """Test that LLM is only called when deterministic checks are inconclusive."""
    task = Task(
        id="test",
        title="Test Task",
        description="",
        complexity=Complexity.SMALL,
        dependencies=[]
    )

    persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test",
        color="white"
    )

    # Ambiguous case: no process_pid (can't check CPU), very long silence, no output
    # After 30min initialization period, no output is suspicious but not definitive
    # Can't check CPU, so no deterministic signal - need LLM judgment
    recent_output = []  # No output yet

    llm_called = {"count": 0}

    def mock_run_claude(*args, **kwargs):
        llm_called["count"] += 1
        return "CONTINUE"

    with patch('waverunner.agent.run_claude', side_effect=mock_run_claude):
        action, reason = reaper_monitor_task(
            task=task,
            persona=persona,
            silence_seconds=1850,  # 30+ min silence - past initialization period (1800s threshold)
            elapsed_seconds=1900,
            recent_output=recent_output,
            process_pid=None  # No PID = can't check CPU = truly ambiguous
        )

    # In this ambiguous case (30+ min silence, no CPU data, no output), should fall back to LLM
    assert llm_called["count"] == 1, "LLM should be called when no CPU data and silence exceeds 30min threshold"
    assert action == "CONTINUE"


def test_deterministic_kill_skips_llm():
    """Test that deterministic KILL decision skips expensive LLM call."""
    task = Task(
        id="test",
        title="Test Task",
        description="",
        complexity=Complexity.SMALL,
        dependencies=[]
    )

    persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test",
        color="white"
    )

    # Clear infinite loop - should kill without LLM
    recent_output = ["Error: connection refused\n"] * 60

    llm_called = {"count": 0}

    def mock_run_claude(*args, **kwargs):
        llm_called["count"] += 1
        return "KILL: infinite loop"

    with patch('waverunner.agent.run_claude', side_effect=mock_run_claude):
        action, reason = reaper_monitor_task(
            task=task,
            persona=persona,
            silence_seconds=0,
            elapsed_seconds=100,
            recent_output=recent_output
        )

    assert llm_called["count"] == 0, "LLM should NOT be called when deterministic check succeeds"
    assert action == "KILL", "Should kill on infinite loop"


def test_recent_heartbeat_with_long_silence_continues():
    """Test that recent heartbeat + long silence = CONTINUE (API wait is normal)."""
    task = Task(
        id="test",
        title="Test Task",
        description="",
        complexity=Complexity.SMALL,
        dependencies=[]
    )

    persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test",
        color="white"
    )

    # Scenario: last output is heartbeat, silence, 0% CPU BUT open network connections
    # This is NORMAL when waiting for Claude API response (can take 15+ min)
    # Should NOT kill - network connection proves it's waiting for I/O
    recent_output = [
        "Starting task...\n",
        "Calling Claude API...\n",
        "[WAVERUNNER_HEARTBEAT]\n"  # Last output = heartbeat
    ]

    # Mock: 0% CPU but has open network connections (waiting for API)
    # Network connection detection should catch this before heartbeat check
    with patch('waverunner.agent.get_process_status', return_value=(0.0, 'sleeping', 1)):
        action, reason = reaper_monitor_task(
            task=task,
            persona=persona,
            silence_seconds=950,  # Even 15+ min silence is OK with network connection
            elapsed_seconds=1000,
            recent_output=recent_output,
            process_pid=12345
        )

    assert action == "CONTINUE", "Should continue with open network connection (waiting for API)"


def test_varied_output_pattern_continues():
    """Test that varied output (not repeating) continues without killing."""
    task = Task(
        id="test",
        title="Test Task",
        description="",
        complexity=Complexity.MEDIUM,
        dependencies=[]
    )

    persona = Persona(
        name="Test Agent",
        role="Test",
        system_prompt="Test",
        color="white"
    )

    # Varied output showing progress
    recent_output = [
        "[WAVERUNNER_HEARTBEAT]\n",
        "Processing file 1 of 100\n",
        "Processing file 2 of 100\n",
        "Processing file 3 of 100\n",
        "Processing file 4 of 100\n",
        "[WAVERUNNER_HEARTBEAT]\n",
        "Processing file 5 of 100\n",
    ]

    action, reason = reaper_monitor_task(
        task=task,
        persona=persona,
        silence_seconds=30,
        elapsed_seconds=100,
        recent_output=recent_output
    )

    assert action == "CONTINUE", "Should continue with varied output and heartbeats"
