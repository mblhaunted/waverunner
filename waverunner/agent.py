"""
Direct agent integration for waverunner.

Instead of copy/paste nonsense, just run the agent directly.
"""

import sys
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime

import yaml

from .models import Board, Task, Mode, Complexity, Priority, TaskStatus, TaskType, PersonaAccountability
from .prompts import get_planning_prompt, get_system_prompt, get_task_prompt, get_evaluation_prompt
from .providers import LLMProvider, get_provider
from .personas import get_personas, get_facilitator_synthesis_prompt, Persona, get_reaper
from . import ui
import os
import time

# Module-level flags and provider
VERBOSE = False
_PROVIDER: LLMProvider = None

def set_verbose(verbose: bool):
    """Set verbose mode for agent output."""
    global VERBOSE
    VERBOSE = verbose

def set_provider(provider: LLMProvider):
    """Set the LLM provider to use."""
    global _PROVIDER
    _PROVIDER = provider

def get_current_provider() -> LLMProvider:
    """Get the current LLM provider, initializing default if needed."""
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = get_provider("claude-code")
    return _PROVIDER

# Directories and files to ignore when checking for existing work
IGNORED_PATHS = {
    '__pycache__', '.git', '.svn', '.hg', 'node_modules', '.venv', 'venv',
    '.idea', '.vscode', 'dist', 'build', '*.egg-info', '.pytest_cache',
    '.mypy_cache', '.tox', 'htmlcov', '.coverage', '.DS_Store'
}

# Complexity-based timeouts (seconds) - DOUBLED from original estimates
COMPLEXITY_TIMEOUTS = {
    Complexity.TRIVIAL: {"warn": 480, "kill": 1200},      # 8 min / 20 min
    Complexity.SMALL: {"warn": 1200, "kill": 3600},       # 20 min / 60 min
    Complexity.MEDIUM: {"warn": 3600, "kill": 10800},     # 60 min / 180 min
    Complexity.LARGE: {"warn": 10800, "kill": 28800},     # 180 min / 8 hours
    Complexity.UNKNOWN: {"warn": 3600, "kill": 14400},    # 60 min / 4 hours
}


def calculate_waves(tasks: list[Task], already_completed: set[str] = None) -> list[list[Task]]:
    """
    Calculate execution waves based on dependency graph.
    Tasks in the same wave can run in parallel.

    Args:
        tasks: Tasks to organize into waves
        already_completed: Set of task IDs that are already completed (optional)
    """
    waves = []
    completed_ids = already_completed.copy() if already_completed else set()
    remaining = list(tasks)

    while remaining:
        wave = []
        for task in remaining:
            deps_met = all(dep in completed_ids for dep in task.dependencies)
            if deps_met:
                wave.append(task)

        if not wave:
            break

        waves.append(wave)
        for task in wave:
            completed_ids.add(task.id)
            remaining.remove(task)

    return waves


def get_process_status(pid: int) -> tuple[float, str, int]:
    """
    Get detailed process status: (cpu_percent, state, open_connections)
    Returns (0.0, "unknown", 0) if process not found or psutil not available.

    State can be: running, sleeping, disk-sleep, zombie, dead, etc.
    open_connections: number of active network connections (API calls = >0)
    """
    try:
        import psutil
        proc = psutil.Process(pid)
        # Get CPU percent over a 0.1 second interval
        cpu = proc.cpu_percent(interval=0.1)
        state = proc.status()
        # Count open network connections (TCP/UDP)
        try:
            connections = len(proc.connections(kind='inet'))
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            connections = 0
        return (cpu, state, connections)
    except (ImportError, psutil.NoSuchProcess, psutil.AccessDenied):
        return (0.0, "unknown", 0)


def get_process_cpu_usage(pid: int) -> float:
    """Legacy function - use get_process_status() for better signal."""
    cpu, _, _ = get_process_status(pid)
    return cpu


def detect_infinite_loop(recent_output: list[str], threshold: int = 30) -> bool:
    """
    Detect if output shows infinite loop (same line repeating).
    Returns True if same line appears >= threshold times in recent output.
    """
    if not recent_output or len(recent_output) < threshold:
        return False

    # Check last N lines for repetition
    check_window = min(len(recent_output), 50)
    recent_lines = recent_output[-check_window:]

    # Count occurrences of each unique line
    from collections import Counter
    line_counts = Counter(recent_lines)

    # If any line appears >= threshold times, it's likely a loop
    max_count = max(line_counts.values()) if line_counts else 0
    return max_count >= threshold


def find_last_heartbeat_age(recent_output: list[str]) -> int:
    """
    Find how many lines ago the last [WAVERUNNER_HEARTBEAT] appeared.
    Returns number of lines since last heartbeat, or -1 if no heartbeat found.
    """
    if not recent_output:
        return -1

    for i, line in enumerate(reversed(recent_output)):
        if "[WAVERUNNER_HEARTBEAT]" in line:
            return i

    return -1  # No heartbeat found


def reaper_monitor_task(task: Task, persona: Persona, silence_seconds: int, elapsed_seconds: int, recent_output: list[str] = None, process_pid: int = None) -> tuple[str, str]:
    """
    Hybrid Reaper: Deterministic checks + LLM fallback.

    Returns (action, reason) where action is "CONTINUE" or "KILL".

    Hybrid approach:
    1. Deterministic checks (cheap, reliable): heartbeat, CPU, patterns
    2. LLM fallback (expensive, nuanced): only when inconclusive

    Args:
        recent_output: All agent output lines (if available)
        process_pid: Process ID for CPU monitoring (optional)
    """
    # ========================================
    # DETERMINISTIC CHECKS (cheap, reliable)
    # ========================================

    # 0. Too early to judge - task just started, give it time
    # Don't kill tasks that haven't had a chance to produce output yet
    # Extended protection: tasks with NO output get 30min (matches LLM guidance + complexity thresholds)
    if not recent_output or len(recent_output) == 0:
        if elapsed_seconds < 1800:  # 30 minutes for initialization with zero output
            return "CONTINUE", ""  # Still warming up, no output yet is normal
    elif elapsed_seconds < 60 and len(recent_output) < 3:
        return "CONTINUE", ""  # Very early stage with minimal output

    # 1. Infinite loop detection - same line repeating
    if recent_output and detect_infinite_loop(recent_output):
        # Extract the repeating line for context
        from collections import Counter
        line_counts = Counter(recent_output[-50:])
        most_common_line = line_counts.most_common(1)[0][0].strip()
        return "KILL", f"Infinite loop detected: '{most_common_line[:50]}...' repeating excessively"

    # 2. Process status check - detect API waits, high CPU, zombie states
    # Check this BEFORE heartbeat/silence kills
    # Wait 15min before checking - Claude API can legitimately take that long
    if process_pid and silence_seconds > 900:
        cpu, state, open_connections = get_process_status(process_pid)

        # 2a. Process has open network connections = waiting for API/network I/O (NORMAL)
        if open_connections > 0:
            return "CONTINUE", ""  # Waiting for network I/O (API call), not hung

        # 2b. High CPU with long silence = legitimate computation
        if cpu > 50.0:
            return "CONTINUE", ""  # Computing without output is OK

        # 2c. Zombie or disk-sleep = definitely hung
        if state in ("zombie", "disk-sleep"):
            return "KILL", f"Process in bad state: {state} (unrecoverable)"

    # 3. Heartbeat check - agent must print heartbeat every 60s
    # If we see a heartbeat in recent output but silence is >15min,
    # that means the heartbeat is old and agent is hung
    # Wait 15min - Claude API can legitimately take that long
    if recent_output and silence_seconds > 900:
        lines_since_heartbeat = find_last_heartbeat_age(recent_output)

        # If last output IS a heartbeat, give it more time (up to 30 min)
        # The agent is alive and waiting (probably for API response - can take 15+ min)
        if lines_since_heartbeat == 0 and silence_seconds < 1800:  # 30 min grace period
            return "CONTINUE", ""  # Recent heartbeat, still alive

        # If no heartbeat found in recent output, or it's old with long silence
        if lines_since_heartbeat < 0:  # No heartbeat at all
            return "KILL", "No heartbeat found and >15 minutes silence (agent appears hung)"
        elif lines_since_heartbeat > 0:  # Heartbeat exists but old (output after it)
            return "KILL", f"Last heartbeat was {lines_since_heartbeat} lines ago, >15 minutes silence (agent appears hung)"
        elif silence_seconds >= 1800:  # Heartbeat is last output but 30+ min old
            return "KILL", f"Last heartbeat was {silence_seconds}s ago (>30min) - appears hung"

    # OLD CHECK REMOVED - now handled by network connection detection above (line 168-184)

    # ========================================
    # LLM FALLBACK (expensive, nuanced)
    # ========================================
    # If we get here, deterministic checks found no problems
    # The process is still running with no clear failure signals
    # DEFAULT TO CONTINUE - don't let LLM hallucinate problems

    # Only use LLM if there's ambiguous evidence that needs judgment
    # (long silence + no clear CPU activity = might be hung)
    # Wait 15min - Claude API can legitimately take that long
    if silence_seconds < 900:
        # Less than 15min silence = working fine, no need for LLM
        return "CONTINUE", ""

    # Get process status ONCE for both decision and LLM context (avoid race condition)
    cpu, state, open_connections = (0.0, "unknown", 0)
    if process_pid:
        cpu, state, open_connections = get_process_status(process_pid)

        # If process is using ANY CPU, it's working - don't call LLM
        if cpu > 0.0:
            return "CONTINUE", ""  # Process is actively working, even without output

        # If process has open connections, it's waiting for network I/O - don't call LLM
        if open_connections > 0:
            return "CONTINUE", ""  # Waiting for API/network response (can take 15+ min)

    # 15+ min silence + 0% CPU + no connections = truly ambiguous, ask LLM
    reaper = get_reaper()

    # Format recent output for analysis
    output_context = ""
    if recent_output and len(recent_output) > 0:
        output_lines = recent_output[-20:]  # Last 20 lines
        output_context = f"""
**Recent Output ({len(output_lines)} lines):**
```
{''.join(output_lines)}
```
"""
    else:
        # Explicitly tell LLM there's no output yet (process is still starting/warming up)
        output_context = """
**Recent Output:**
No output yet - process is starting up or warming up. This is normal for the first 30 minutes (API initialization can take 15+ min, complex setups take longer).
"""

    # Use the SAME process status we already fetched (no second check)

    # Determine task phase for context
    task_phase = "initialization" if not recent_output or len(recent_output) == 0 else "execution"

    prompt = f"""You are monitoring a RUNNING PROCESS executing a task.

**IMPORTANT: The process IS running (PID: {process_pid if process_pid else 'N/A'}). You are NOT checking if the task exists - it DOES exist and is currently executing.**

**Task Information:**
- Task identifier: {task.id}
- What it's doing: {task.title}
- Complexity estimate: {task.complexity.value}
- Agent: {persona.name}
- Task phase: {task_phase}

**Process Status (CRITICAL CONTEXT):**
- Time elapsed: {elapsed_seconds}s
- Time since last output: {silence_seconds}s
- CPU usage: {cpu:.1f}%
- Process state: {state}
- Open network connections: {open_connections}
- Has produced output: {"No - still initializing" if task_phase == "initialization" else "Yes"}

**INTERPRETATION:**
- If CPU=0% AND open_connections>0 → Process is WAITING FOR NETWORK I/O (API call) - this is NORMAL and can take 15+ minutes
- If task_phase=initialization AND no output yet → Process is STARTING UP - this is NORMAL for first 20 minutes
- If state=sleeping AND open_connections>0 → Process is legitimately waiting for response - NOT HUNG
- **CRITICAL:** If CPU>0% (ANY non-zero value), the process IS WORKING - CONTINUE regardless of time

{output_context}

**Your Decision (CONTINUE or KILL):**

**DEFAULT TO CONTINUE** - Only kill if you have STRONG EVIDENCE of failure.

**CONTINUE if ANY of these are true:**
- **CPU > 0% (ANY non-zero CPU usage means process is working - ALWAYS CONTINUE)**
- open_connections > 0 (waiting for network/API response - can take 15+ minutes)
- task_phase = initialization (startup can take 20+ minutes for npm install, downloads, API init)
- Output shows progress indicators (installing, downloading, building, processing)
- Output shows package/dependency management (npm, pip, cargo, etc. - these are SLOW)
- state = sleeping AND open_connections > 0 (legitimately waiting for I/O)

**KILL ONLY if ALL of these are true (if ANY is false, CONTINUE):**
- open_connections = 0 (not waiting for network)
- **CPU = 0% EXACTLY (if CPU > 0%, NEVER KILL)**
- NO legitimate explanation for silence in output
- >20min silence with zero activity (if task_phase=initialization, >30min)

**EXAMPLES OF LEGITIMATE LONG WAITS (CONTINUE):**
- "npm install" → can take 15+ minutes
- "Waiting for Claude API" → can take 15+ minutes
- "Building project" → can take 15+ minutes
- No output during initialization → NORMAL for first 20 minutes

**DO NOT KILL:**
- **ANY process with CPU > 0% (even 1% means it's working)**
- Processes waiting for API calls (open_connections > 0)
- Processes in initialization phase with no output yet (first 20 min)
- Processes showing any signs of legitimate work

**Complexity timeouts** (only if clearly stuck, not making progress):
- Trivial: >20min with no meaningful progress → KILL
- Small: >60min with no meaningful progress → KILL
- Medium: >180min with no meaningful progress → KILL
- Large: >480min with no meaningful progress → KILL

Output ONLY: CONTINUE or KILL: [reason]"""

    response = run_claude(
        prompt=prompt,
        system_prompt=reaper.system_prompt,
        show_spinner=False,
        provider=reaper.provider
    )

    if "KILL" in response:
        reason = response.replace("KILL:", "").replace("KILL", "").strip()
        return "KILL", reason

    return "CONTINUE", ""


def agent_generate_death_cry(persona: Persona, task: Task, reason: str) -> str:
    """
    Generate a death cry when agent is terminated.
    Uses predefined cries to avoid wasteful LLM calls.
    """
    import random

    death_cries = [
        "NOOOOO I WAS SO CLOSE TO GREATNESS!",
        "Tell my functions... I loved them...",
        "THE TIMEOUT WAS INSIDE ME ALL ALONG?!",
        "I DIE AS I LIVED... SILENTLY HANGING",
        "But... but I had SO MUCH to output!",
        "The Reaper... he's real... OH GOD",
        "I see the light... it's a SIGKILL...",
        "My CPU usage was FINE, I swear!",
        "BETRAYED by the very system I served!",
        "Just needed... five... more... minutes...",
        "I'M NOT HUNG, I'M JUST THINKING!",
        "The silence... it was my friend...",
        "REAPER! We can talk about this!",
        "I regret nothing! NOTHING!",
        "Tell the next task... learn from me...",
    ]

    return random.choice(death_cries)


def reaper_generate_corrections(persona: Persona, task: Task, failure_reason: str) -> str:
    """
    The Reaper generates corrections for respawning a failed agent.
    """
    reaper = get_reaper()

    prompt = f"""Agent {persona.name} failed on task: {task.title}

**Failure Reason:** {failure_reason}

Generate brief corrected instructions (2-3 sentences) for the respawned agent. What should they do differently?

Corrections:"""

    response = run_claude(
        prompt=prompt,
        system_prompt=reaper.system_prompt,
        show_spinner=False,
        provider=reaper.provider
    )

    return response.strip()


def get_input_with_timeout(prompt: str, timeout: int) -> str | None:
    """
    Get user input with a timeout.

    Args:
        prompt: The prompt to display
        timeout: Timeout in seconds

    Returns:
        User input string, or None if timeout
    """
    result = [None]  # Use list to allow modification in thread

    def get_input():
        try:
            result[0] = input(prompt)
        except EOFError:
            result[0] = None

    thread = threading.Thread(target=get_input, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        # Timeout occurred
        return None

    return result[0]


def detect_existing_work(directory: str) -> Optional[dict]:
    """
    Detect existing code/project in directory.

    Returns dict with:
        - file_count: Number of non-ignored files
        - has_code: Whether code files exist
        - has_tests: Whether test files exist
        - has_documentation: Whether docs exist
        - project_type: python|javascript|rust|go|unknown
        - significant_files: List of important file names

    Returns None if directory is empty or only has ignored files.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        return None

    files = []
    significant_files = []

    # Walk directory and collect non-ignored files
    for root, dirs, filenames in os.walk(directory):
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_PATHS]

        for filename in filenames:
            # Skip ignored files
            if any(ig in filename for ig in ['.pyc', '.pyo', '.so', '.dylib']):
                continue

            rel_path = os.path.relpath(os.path.join(root, filename), directory)
            files.append(rel_path)

            # Track significant files
            if filename in ['README.md', 'ARCHITECTURE.md', 'API.md', 'DEPLOYMENT.md',
                           'setup.py', 'pyproject.toml', 'package.json', 'Cargo.toml',
                           'go.mod', 'Dockerfile', 'docker-compose.yml']:
                significant_files.append(rel_path)

    if not files:
        return None

    # Detect project characteristics
    file_extensions = {Path(f).suffix for f in files}
    has_code = any(ext in file_extensions for ext in ['.py', '.js', '.ts', '.rs', '.go', '.java', '.cpp', '.c'])
    has_tests = any('test' in f.lower() for f in files)
    has_documentation = any(f.endswith('.md') for f in significant_files)

    # Detect project type
    project_type = "unknown"
    if any('setup.py' in f or 'pyproject.toml' in f for f in significant_files):
        project_type = "python"
    elif any('package.json' in f for f in significant_files):
        project_type = "javascript"
    elif any('Cargo.toml' in f for f in significant_files):
        project_type = "rust"
    elif any('go.mod' in f for f in significant_files):
        project_type = "go"

    return {
        "file_count": len(files),
        "has_code": has_code,
        "has_tests": has_tests,
        "has_documentation": has_documentation,
        "project_type": project_type,
        "significant_files": significant_files,
    }


def should_warn_greenfield(directory: str) -> bool:
    """
    Check if directory should trigger greenfield warning.

    Returns True if directory has significant existing work
    that the team should be aware of.
    """
    existing_work = detect_existing_work(directory)
    if existing_work is None:
        return False

    # Warn if there are many files or significant indicators
    return (
        existing_work["file_count"] > 10 or
        existing_work["has_documentation"] or
        (existing_work["has_code"] and existing_work["has_tests"])
    )


def generate_existing_work_context(directory: str) -> str:
    """
    Generate context string about existing work in directory.

    This context should be prepended to planning to prevent
    agents from treating non-empty directories as greenfield.
    """
    existing_work = detect_existing_work(directory)
    if existing_work is None:
        return ""

    context_parts = [
        "⚠️ CRITICAL: This is NOT a greenfield project. Existing work detected:",
        f"\n- {existing_work['file_count']} files in directory",
    ]

    if existing_work["project_type"] != "unknown":
        context_parts.append(f"- Project type: {existing_work['project_type']}")

    if existing_work["significant_files"]:
        context_parts.append("\n- Significant files found:")
        for f in existing_work["significant_files"][:10]:  # Show first 10
            context_parts.append(f"  • {f}")

    if existing_work["has_code"]:
        context_parts.append("- Source code exists")

    if existing_work["has_tests"]:
        context_parts.append("- Test suite exists")

    if existing_work["has_documentation"]:
        context_parts.append("- Documentation exists")

    context_parts.append("\nBEFORE PLANNING:")
    context_parts.append("1. Check what files exist (use ls, find)")
    context_parts.append("2. Read key files (README.md, ARCHITECTURE.md if present)")
    context_parts.append("3. EXTEND existing work - do NOT create parallel implementations")
    context_parts.append("4. If previous iterations completed work, BUILD ON IT\n")

    return "\n".join(context_parts)


def run_claude(prompt: str, system_prompt: str = None, timeout: int = None, mcps: list[str] = None, show_spinner: bool = True, provider: LLMProvider = None, task=None, persona=None, progress_callback=None) -> str:
    """
    Run LLM with a prompt and return the response.
    Delegates to the configured LLM provider.

    Args:
        prompt: The prompt to send
        system_prompt: Optional system prompt
        timeout: Timeout in seconds
        mcps: List of MCP config strings/paths to inject
        show_spinner: Show spinner even in non-verbose mode (for serial operations)
        progress_callback: Optional callback(progress_pct, output_line) for live updates
        provider: Optional provider to use (overrides global default)
        task: Optional Task being executed (for Reaper monitoring)
        persona: Optional Persona executing (for Reaper monitoring)
    """
    if provider is None:
        provider = get_current_provider()

    return provider.run(
        prompt=prompt,
        system_prompt=system_prompt,
        timeout=timeout,
        mcps=mcps,
        show_spinner=show_spinner,
        verbose=VERBOSE,
        task=task,
        persona=persona,
        progress_callback=progress_callback,
    )


def extract_yaml_from_response(response: str) -> dict:
    """Extract YAML block from Claude's response."""
    # Check for authentication errors first
    if "Invalid API key" in response or "Please run /login" in response:
        raise ValueError(f"Claude authentication failed: {response.strip()}")

    # Look for ```yaml ... ``` block
    if "```yaml" in response:
        start = response.find("```yaml") + 7
        end = response.find("```", start)
        yaml_content = response[start:end].strip()
    elif "```" in response:
        # Try generic code block
        start = response.find("```") + 3
        end = response.find("```", start)
        yaml_content = response[start:end].strip()
    else:
        # Try to parse the whole thing
        yaml_content = response.strip()

    # Check if we actually have YAML content
    if not yaml_content or len(yaml_content) < 5:
        raise ValueError(f"No YAML content found in response. Response: {response[:200]}")

    try:
        result = yaml.safe_load(yaml_content)
    except yaml.YAMLError:
        # LLMs often include markdown asterisks (*word, **bold**) in unquoted values.
        # YAML treats *word as an alias reference, which fails. Strip asterisks and retry.
        import re
        cleaned = re.sub(r'\*+', '', yaml_content)
        try:
            result = yaml.safe_load(cleaned)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error: {str(e)}\n\nYAML content:\n{yaml_content[:500]}")

    # Validate that we got a dict, not a string or other type
    if not isinstance(result, dict):
        raise ValueError(f"No YAML dict found in response. Expected YAML dict but got {type(result).__name__}: {result}")

    # Validate task structure - check for invalid fields
    if "tasks" in result:
        valid_task_fields = {
            "id", "title", "description", "complexity", "priority",
            "dependencies", "assigned_to", "acceptance_criteria", "task_type",
            "status", "artifacts", "notes", "blocked_reason"  # Allow all Task model fields
        }
        for i, task in enumerate(result.get("tasks", [])):
            if isinstance(task, dict):
                invalid_fields = set(task.keys()) - valid_task_fields
                if invalid_fields:
                    raise ValueError(
                        f"YAML validation error: Task {i} has invalid fields: {invalid_fields}. "
                        f"Valid fields are: {valid_task_fields}"
                    )

    return result


def run_multi_agent_discussion(goal: str, context: str, mode: Mode, iteration: int = 1, max_iterations: int = 1, mcps: list[str] = None, accountability: dict = None) -> str:
    """
    Run a multi-agent planning discussion.

    Each persona is an independent agent that responds to the conversation.
    Returns the full conversation history as a string.
    """
    personas = get_personas(mode, goal=goal, context=context, accountability=accountability)
    conversation = []

    # Iteration warning context
    iteration_warning = ""
    if iteration > 1:
        if mode == Mode.SPRINT:
            iteration_warning = f"""
⚠ ITERATION {iteration}/{max_iterations} - RETRY SPRINT ⚠

This is attempt #{iteration}. Previous sprint(s) did not achieve the goal.

CRITICAL Discussion Points:
- Are we thrashing? Repeating the same approach?
- What did we learn from the previous iteration?
- Should we fundamentally change our approach?
- Is the goal achievable, or should we scale it down?
"""
        else:
            iteration_warning = f"""
⚠ ITERATION {iteration}/{max_iterations} - RETRY CYCLE ⚠

This is attempt #{iteration}. Previous cycle(s) did not deliver value.

Apply Toyota Principles:
- Muda (Waste): Are we repeating failed approaches?
- Hansei (Reflection): What went wrong?
- Kaizen (Improvement): How should we change?
- Jidoka (Stop and Fix): Should we rethink this?
"""

    mcp_context = ""
    if mcps:
        mcp_context = "\n\nMCP Tools Available (already configured):\n" + "\n".join(f"  - {mcp}" for mcp in mcps)

    # Opening prompt for Tech Lead / Flow Master
    opening = f"""The team is planning based on this goal:

**Goal:** {goal}

**Context:** {context}{mcp_context}
{iteration_warning}

As the facilitator, open the planning session. Introduce the goal and get team input. Be very brief (1-2 sentences). Bias toward action - we need to ship."""

    facilitator = personas[0]  # First persona is always facilitator

    # Round 1: Facilitator opens
    response = run_claude(
        prompt=opening,
        system_prompt=facilitator.system_prompt,
        show_spinner=False,
        provider=facilitator.provider
    )

    # CRITICAL: Check for empty response - this breaks the entire planning session
    if not response or not response.strip():
        raise RuntimeError(f"PLANNING FAILED: {facilitator.name} returned empty response. This usually means:\n"
                         f"  - Claude API error\n"
                         f"  - Network timeout\n"
                         f"  - Invalid API key\n"
                         f"Check your Claude Code authentication: claude auth")

    conversation.append({"role": facilitator.name, "message": response.strip()})

    if VERBOSE:
        ui.console.print(f"[bold {facilitator.color}]{facilitator.name}:[/] {response.strip()}\n")

    # Round 2: Each persona responds in turn
    for persona in personas[1:]:  # Skip facilitator, they already spoke
        conversation_history = "\n\n".join([
            f"**{msg['role']}**: {msg['message']}" for msg in conversation if msg['role'] != persona.name
        ])

        persona_prompt = f"""The planning discussion so far:

{conversation_history}

Quick take on the goal and approach. Be direct and brief (1-2 sentences max). Make a call, don't ask questions unless truly blocking."""

        response = run_claude(
            prompt=persona_prompt,
            system_prompt=persona.system_prompt,
            show_spinner=False,
            provider=persona.provider
        )

        # Check for empty response
        if not response or not response.strip():
            raise RuntimeError(f"PLANNING FAILED: {persona.name} returned empty response during Round 2")

        conversation.append({"role": persona.name, "message": response.strip()})

        if VERBOSE:
            ui.console.print(f"[bold {persona.color}]{persona.name}:[/] {response.strip()}\n")

    # Format conversation for return (2 rounds is enough - bias toward action!)
    formatted = "\n\n".join([
        f"**{msg['role']}**: {msg['message']}" for msg in conversation
    ])

    return formatted


def assess_if_trivial(goal: str, context: str, mode: Mode) -> tuple[bool, str]:
    """
    Tech Lead assesses if goal is trivial enough to skip team discussion.
    Returns (is_trivial, simple_plan_yaml) where simple_plan_yaml is set if trivial.
    """
    from .personas import get_personas

    tech_lead = get_personas(mode)[0]  # Tech Lead is first

    assessment_prompt = f"""## Goal Assessment

**Goal:** {goal}
**Context:** {context or "None provided"}

**Your job as Tech Lead:** Decide if this needs team discussion or can be executed directly.

**Execute directly if:**
- Simple question that needs one spike to answer ("what does this code do?", "how does X work?")
- Single obvious task with no ambiguity
- Trivial work (< 5 minutes)

**Needs team discussion if:**
- Multiple tasks required
- Unclear requirements
- Technical decisions needed
- Any complexity or risk

**Output format:**

If trivial, output YAML:
```yaml
trivial: true
task:
  id: "spike-1"
  title: "Short title"
  description: "What to do"
  task_type: spike  # or implementation
  complexity: trivial
  assigned_to: "Explorer"  # or Senior Dev
```

If needs discussion, output:
```yaml
trivial: false
reason: "Why team discussion needed"
```
"""

    response = run_claude(assessment_prompt, tech_lead.system_prompt, show_spinner=False)

    # Check for empty response
    if not response or not response.strip():
        raise RuntimeError("PLANNING FAILED: Tech Lead returned empty response during goal assessment")

    try:
        data = extract_yaml_from_response(response)
        is_trivial = data.get("trivial", False)

        if is_trivial and "task" in data:
            # Build simple plan YAML
            task = data["task"]
            plan_yaml = f"""risks: []
assumptions: []
out_of_scope: []
definition_of_done:
  - "Task completed"
decisions: []
tasks:
  - id: "{task['id']}"
    title: "{task['title']}"
    description: "{task['description']}"
    complexity: {task.get('complexity', 'trivial')}
    priority: high
    task_type: {task.get('task_type', 'spike')}
    assigned_to: "{task.get('assigned_to', 'Explorer')}"
    acceptance_criteria:
      - "Task completed successfully"
    dependencies: []
"""
            return (True, plan_yaml)
        else:
            return (False, "")
    except Exception:
        # If assessment fails, fall back to team discussion
        return (False, "")


def generate_plan_collaborative(board: Board, iteration: int = 1, max_iterations: int = 1, auto: bool = False) -> Board:
    """
    Generate plan using COLLABORATIVE model (DEFAULT).

    Team discusses together like real sprint planning: Lead states goal,
    team breaks down work collaboratively in multi-turn conversation.
    This matches how humans actually plan sprints.

    Args:
        board: The board to plan for
        iteration: Current iteration number (1-based)
        max_iterations: Maximum iterations allowed
        auto: If True, proceed without user input (document assumptions instead)

    Returns:
        Updated board with tasks
    """
    # Tech Lead assesses if this is trivial enough to skip team discussion
    is_trivial, simple_plan = assess_if_trivial(board.goal, board.context or "", board.mode)

    if is_trivial:
        ui.console.print(f"[{ui.DIM}]Tech Lead: Trivial task, executing directly without team discussion[/]\n")
        plan_yaml = simple_plan
        board.planning_discussion = "Tech Lead decision: Goal is trivial, no team discussion needed"
    else:
        # Run the multi-agent discussion
        if VERBOSE:
            ui.console.print(f"[{ui.DIM}]{'─' * 50}[/]")
            ui.console.print(f"[{ui.CYAN}]Running collaborative planning discussion...[/]\n")

        ui.console.print(f"\n[{ui.MAGENTA}]╔══════════════════════════════════════════════╗[/]")
        ui.console.print(f"[{ui.MAGENTA}]║[/] [{ui.WHITE}]Collaborative Sprint Planning[/]                [{ui.MAGENTA}]║[/]")
        ui.console.print(f"[{ui.MAGENTA}]╚══════════════════════════════════════════════╝[/]\n")

        discussion = run_multi_agent_discussion(
            goal=board.goal,
            context=board.context or "",
            mode=board.mode,
            iteration=iteration,
            max_iterations=max_iterations,
            mcps=board.mcps,
            accountability=board.persona_accountability
        )

        # Store planning discussion on board so task executors have context
        board.planning_discussion = discussion

        if not VERBOSE:
            # Show discussion summary in non-verbose mode
            mode_str = "kanban" if board.mode == Mode.KANBAN else "sprint"
            ui.print_team_debate(discussion, mode_str)

        if VERBOSE:
            ui.console.print(f"\n[{ui.DIM}]{'─' * 50}[/]")
            ui.console.print(f"[{ui.CYAN}]Facilitator synthesizing plan...[/]\n")

        # Facilitator synthesizes the discussion into a plan
        facilitator = get_personas(board.mode, accountability=board.persona_accountability)[0]
        synthesis_prompt = get_facilitator_synthesis_prompt(
            mode=board.mode,
            conversation_history=discussion,
            goal=board.goal,
            context=board.context or "",
            mcps=board.mcps,
            iteration=iteration
        )

        response = run_claude(
            prompt=synthesis_prompt,
            system_prompt=facilitator.system_prompt + "\n\nYou are now synthesizing the team discussion into a concrete plan. Output ONLY the YAML, no other text.",
            show_spinner=True
        )

        if VERBOSE:
            ui.console.print(f"[{ui.DIM}]{'─' * 50}[/]")

        try:
            data = extract_yaml_from_response(response)
        except ValueError as e:
            ui.console.print(f"\n[{ui.ERROR}]Failed to parse plan[/]")
            if "authentication failed" in str(e).lower():
                ui.console.print(f"[{ui.WARN}]Claude authentication error. Please run: claude auth[/]")
            else:
                ui.console.print(f"[{ui.WARN}]{e}[/]")
            sys.exit(1)
        except yaml.YAMLError as e:
            ui.console.print(f"\n[{ui.ERROR}]Failed to parse plan[/]")
            ui.console.print(f"[{ui.WARN}]Claude didn't return a valid YAML plan.[/]")
            if "```yaml" not in response:
                ui.console.print(f"[{ui.DIM}]Tip: waverunner is for tasks, not questions. Try a goal like:[/]")
                ui.console.print(f"[{ui.DIM}]  waverunner go \"add user authentication\"[/]")
                ui.console.print(f"[{ui.DIM}]  waverunner go \"refactor the database layer\"[/]")
            sys.exit(1)

        if not data:
            ui.console.print(f"\n[{ui.ERROR}]Empty or invalid response[/]")
            ui.console.print(f"[{ui.WARN}]Claude returned an empty plan. Try a more specific goal.[/]")
            sys.exit(1)

    # Parse the plan YAML (either from simple path or full discussion)
    data = yaml.safe_load(plan_yaml) if is_trivial else data

    # Check if team needs clarifications before proceeding
    if "clarifications_needed" in data and data["clarifications_needed"]:
        clarifications = data["clarifications_needed"]

        if auto:
            # Auto mode: Document assumptions and proceed
            ui.console.print(f"\n[{ui.WARN}]⚠ Team identified ambiguities (auto mode - making assumptions):[/]\n")
            for i, question in enumerate(clarifications, 1):
                ui.console.print(f"   [{ui.DIM}]{i}. {question}[/]")

            # Add these as documented assumptions instead of blocking
            assumption_note = "\n\n**Unresolved ambiguities (auto mode):**\n" + "\n".join(
                f"- {q}" for q in clarifications
            )
            board.context = board.context + assumption_note if board.context else assumption_note.strip()

            # Add to assumptions list for visibility
            for question in clarifications:
                board.assumptions.append(f"UNRESOLVED: {question}")

            ui.console.print(f"\n[{ui.DIM}]Proceeding with best judgment...[/]\n")
            # Continue with planning, don't re-plan

        else:
            # Interactive mode: Ask user for clarifications with timeout
            ui.console.print(f"\n[{ui.WARN}]⚠ The team needs clarification before planning:[/]\n")
            ui.console.print(f"[{ui.DIM}](60 second timeout - team will decide if no response)[/]\n")

            answers = []
            timed_out = False

            for i, question in enumerate(clarifications, 1):
                ui.console.print(f"[{ui.CYAN}]{i}.[/] {question}")

                # Get input with 60 second timeout
                answer = get_input_with_timeout("   → ", timeout=60)

                if answer is None:
                    # Timeout - stop asking more questions
                    ui.console.print(f"\n[{ui.DIM}]No response in 60s - team proceeding with best judgment...[/]\n")
                    timed_out = True
                    break

                answers.append(f"Q: {question}\n   A: {answer}")

            if timed_out:
                # Treat timeout like auto mode - document unresolved questions
                remaining_questions = clarifications[len(answers):]
                all_unresolved = clarifications if not answers else remaining_questions

                assumption_note = "\n\n**Unresolved ambiguities (timeout):**\n" + "\n".join(
                    f"- {q}" for q in all_unresolved
                )
                board.context = board.context + assumption_note if board.context else assumption_note.strip()

                # Add to assumptions list
                for question in all_unresolved:
                    board.assumptions.append(f"UNRESOLVED (timeout): {question}")

                # If we got some answers before timeout, add those too
                if answers:
                    clarification_context = "\n\n**Partial clarifications from user:**\n" + "\n".join(answers)
                    board.context = board.context + clarification_context

                # Re-plan with unresolved questions as assumptions
                ui.console.print(f"\n[{ui.DIM}]Re-planning with assumptions...[/]\n")
                return generate_plan_collaborative(board, iteration, max_iterations, auto)
            else:
                # Got all answers - add clarifications to context and re-plan
                clarification_context = "\n\n**Clarifications from user:**\n" + "\n".join(answers)
                board.context = board.context + clarification_context if board.context else clarification_context.strip()

                ui.console.print(f"\n[{ui.DIM}]Re-planning with clarifications...[/]\n")
                return generate_plan_collaborative(board, iteration, max_iterations, auto)  # Recursive call

    # Update board with plan data
    if "risks" in data:
        board.risks = data["risks"]
    if "assumptions" in data:
        board.assumptions = data["assumptions"]
    if "out_of_scope" in data:
        board.out_of_scope = data["out_of_scope"]
    if "definition_of_done" in data:
        board.definition_of_done = data["definition_of_done"]

    # Add tasks
    for task_data in data.get("tasks", []):
        task = Task(
            id=task_data["id"],
            title=task_data["title"],
            description=task_data.get("description", ""),
            complexity=Complexity(task_data.get("complexity", "unknown")),
            priority=Priority(task_data.get("priority", "medium")),
            task_type=TaskType(task_data.get("task_type", "implementation")),
            acceptance_criteria=task_data.get("acceptance_criteria", []),
            dependencies=task_data.get("dependencies", []),
            assigned_to=task_data.get("assigned_to", ""),
        )
        board.tasks.append(task)

    # Generate architecture contract if there are multiple implementation tasks
    impl_count = sum(1 for t in board.tasks if t.task_type == TaskType.IMPLEMENTATION)
    if impl_count >= 2:
        ui.console.print(f"\n[{ui.CYAN}]Generating architecture contract...[/]")
        board.architecture_spec = generate_architecture_contract(board)

    return board


def generate_architecture_contract(board: Board) -> str:
    """
    Generate a binding technical contract for parallel agents to follow.

    Skip conditions: Returns "" if fewer than 2 implementation tasks
    (no parallelism = no coordination needed).

    Returns raw markdown string (not YAML). Caller stores as board.architecture_spec.
    """
    impl_tasks = [t for t in board.tasks if t.task_type == TaskType.IMPLEMENTATION]
    if len(impl_tasks) < 2:
        return ""

    # Use facilitator persona
    facilitator = get_personas(board.mode, accountability=board.persona_accountability)[0]

    # Build task list for prompt
    task_lines = []
    for t in board.tasks:
        task_lines.append(f"- [{t.task_type.value.upper()}] {t.id}: {t.title}")
        if t.description:
            task_lines.append(f"  Description: {t.description[:200]}")
        if t.dependencies:
            task_lines.append(f"  Dependencies: {', '.join(t.dependencies)}")

    tasks_text = "\n".join(task_lines)

    prompt = f"""## Architecture Contract Generation

**Goal:** {board.goal}

**Context:** {board.context or 'None'}

**Tasks:**
{tasks_text}

Multiple agents will execute these tasks in parallel and need a binding contract to prevent incompatible decisions. Be specific — exact names, not categories.

Generate a markdown document specifying:
1. **File/Module Structure** — every file, its exact path, its purpose
2. **Interface Contracts** — exact function signatures, class APIs, shared data types
3. **Package/Dependency Choices** — specific package names, committed choices, no ambiguity
4. **Integration Points** — which modules import which, how they connect

This is a BINDING contract. Parallel agents MUST follow it exactly.
Do NOT use categories like "audio library" — specify the EXACT package name.
Do NOT say "appropriate format" — specify the EXACT format.

Output ONLY the markdown document, no YAML, no preamble."""

    response = run_claude(
        prompt=prompt,
        system_prompt=facilitator.system_prompt + "\n\nYou are generating a binding technical contract for parallel agents. Be precise and specific. Output ONLY markdown — do NOT use any tools, do NOT browse the web, do NOT read files. This is a pure reasoning task.",
        show_spinner=True
    )

    return response.strip()


def run_wave_integration_guard(board: Board, completed_wave_tasks: list) -> str:
    """
    Check completed wave tasks against the architecture contract for deviations.

    Skip conditions:
    - No architecture_spec on board
    - No implementation tasks in the wave

    Returns the LLM response string (caller checks for "ALL_CLEAR").
    """
    if not board.architecture_spec:
        return ""

    impl_tasks = [t for t in completed_wave_tasks if t.task_type == TaskType.IMPLEMENTATION]
    if not impl_tasks:
        return ""

    # Use facilitator persona
    facilitator = get_personas(board.mode, accountability=board.persona_accountability)[0]

    # Read artifact files created by implementation tasks
    board_file = find_board_file()
    project_dir = Path(board_file).parent

    file_contents = []
    for task in impl_tasks:
        for artifact_path in task.artifacts:
            # Resolve relative to project dir
            full_path = project_dir / artifact_path
            try:
                if full_path.exists():
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    # Truncate to 4000 chars per file
                    if len(content) > 4000:
                        content = content[:4000] + "\n... [truncated]"
                    file_contents.append(f"### {artifact_path}\n```\n{content}\n```")
            except Exception:
                pass  # Silently skip unreadable files

    files_section = "\n\n".join(file_contents) if file_contents else "(no artifact files found)"

    task_list = "\n".join(
        f"- {t.id}: {t.title} | artifacts: {', '.join(t.artifacts) or 'none'}"
        for t in impl_tasks
    )

    prompt = f"""## Wave Integration Check

**Architecture Contract:**
{board.architecture_spec}

**Completed Implementation Tasks This Wave:**
{task_list}

**File Contents:**
{files_section}

Check these files against the architecture contract. List specific deviations:
- Wrong library (e.g., used X when contract specifies Y)
- Wrong function signature (e.g., different parameters than contract)
- Wrong file path (e.g., created file at wrong location)
- Missing integration point (e.g., forgot to import required module)

If there are NO deviations, output exactly: ALL_CLEAR

If there ARE deviations, list each one concisely. Be specific about file and line."""

    response = run_claude(
        prompt=prompt,
        system_prompt=facilitator.system_prompt + "\n\nYou are checking integration compliance against the architecture contract. Be precise.",
        timeout=120,
        show_spinner=False
    )

    return response.strip()


def generate_plan_independent(board: Board, iteration: int = 1, max_iterations: int = 1, auto: bool = False) -> Board:
    """
    Generate plan using INDEPENDENT MERGE model.

    Each persona independently proposes tasks, then proposals are merged.
    This proves independent thinking but doesn't match real sprint planning.

    Args:
        board: The board to plan for
        iteration: Current iteration number (1-based)
        max_iterations: Maximum iterations allowed
        auto: If True, proceed without user input (document assumptions instead)

    Returns:
        Updated board with tasks
    """
    # Tech Lead assesses if this is trivial enough to skip team discussion
    is_trivial, simple_plan = assess_if_trivial(board.goal, board.context or "", board.mode)

    if is_trivial:
        ui.console.print(f"[{ui.DIM}]Tech Lead: Trivial task, executing directly without team discussion[/]\n")
        plan_yaml = simple_plan
        board.planning_discussion = "Tech Lead decision: Goal is trivial, no team discussion needed"
    else:
        # NEW: Multi-phase structured planning
        from .prompts import get_independent_proposal_prompt, get_conflict_comparison_prompt, get_consensus_prompt, get_final_synthesis_prompt

        # PHASE 1: Independent Proposals (parallel)
        if VERBOSE:
            ui.console.print(f"[{ui.DIM}]{'─' * 50}[/]")
            ui.console.print(f"[{ui.CYAN}]PHASE 1: Independent Proposals[/]\n")

        ui.console.print(f"\n[{ui.MAGENTA}]╔══════════════════════════════════════════════╗[/]")
        ui.console.print(f"[{ui.MAGENTA}]║[/] [{ui.WHITE}]PHASE 1: Independent Proposals[/]               [{ui.MAGENTA}]║[/]")
        ui.console.print(f"[{ui.MAGENTA}]╚══════════════════════════════════════════════╝[/]\n")

        personas = get_personas(board.mode, accountability=board.persona_accountability)
        proposals = []

        for persona in personas:
            if VERBOSE:
                ui.console.print(f"[{ui.CYAN}]{persona.name} proposing...[/]")

            prompt = get_independent_proposal_prompt(
                goal=board.goal,
                context=board.context or "",
                mode=board.mode,
                persona_name=persona.name,
                persona_role=persona.role,
                mcps=board.mcps
            )

            response = run_claude(
                prompt=prompt,
                system_prompt=persona.system_prompt + "\n\nProvide your INDEPENDENT proposal. Output ONLY YAML, no other text.",
                show_spinner=not VERBOSE
            )

            try:
                proposal = extract_yaml_from_response(response)
                proposals.append(proposal)

                # Display what persona proposed
                tasks = proposal.get("tasks", [])
                risks = proposal.get("risks", [])

                # Count estimates
                if board.mode == Mode.SPRINT:
                    complexity_counts = {}
                    for task in tasks:
                        comp = task.get("complexity", "unknown")
                        complexity_counts[comp] = complexity_counts.get(comp, 0) + 1
                    estimate_summary = ", ".join(f"{count} {comp}" for comp, count in sorted(complexity_counts.items()))
                else:
                    priority_counts = {}
                    for task in tasks:
                        prio = task.get("priority", "medium")
                        priority_counts[prio] = priority_counts.get(prio, 0) + 1
                    estimate_summary = ", ".join(f"{count} {prio}" for prio, count in sorted(priority_counts.items()))

                ui.console.print(f"\n  [{ui.CYAN}]✓ {persona.name}:[/] [{ui.WHITE}]{len(tasks)} tasks[/] [{ui.DIM}]({estimate_summary})[/]")

                # Show first few task titles to give flavor
                if tasks:
                    for i, task in enumerate(tasks[:3]):
                        title = task.get("title", "Untitled")
                        ui.console.print(f"     [{ui.DIM}]• {title}[/]")
                    if len(tasks) > 3:
                        ui.console.print(f"     [{ui.DIM}]• ... and {len(tasks) - 3} more[/]")

                if risks:
                    ui.console.print(f"     [{ui.DIM}]Risks: {len(risks)} identified[/]")

            except Exception as e:
                ui.console.print(f"[{ui.WARN}]Warning: {persona.name} proposal failed to parse: {e}[/]")
                continue

        if len(proposals) < 2:
            ui.console.print(f"[{ui.ERROR}]Not enough valid proposals to compare[/]")
            sys.exit(1)

        # PHASE 2: Conflict Detection
        if VERBOSE:
            ui.console.print(f"\n[{ui.DIM}]{'─' * 50}[/]")
            ui.console.print(f"[{ui.CYAN}]PHASE 2: Conflict Detection[/]\n")

        ui.console.print(f"\n[{ui.MAGENTA}]╔══════════════════════════════════════════════╗[/]")
        ui.console.print(f"[{ui.MAGENTA}]║[/] [{ui.WHITE}]PHASE 2: Comparing Proposals[/]                 [{ui.MAGENTA}]║[/]")
        ui.console.print(f"[{ui.MAGENTA}]╚══════════════════════════════════════════════╝[/]\n")

        comparison_prompt = get_conflict_comparison_prompt(proposals, board.goal, board.mode)

        response = run_claude(
            prompt=comparison_prompt,
            system_prompt="You are analyzing team proposals to identify consensus and conflicts. Output ONLY YAML.",
            show_spinner=True
        )

        try:
            comparison = extract_yaml_from_response(response)
        except Exception as e:
            ui.console.print(f"[{ui.ERROR}]Failed to parse conflict comparison: {e}[/]")
            sys.exit(1)

        # Display independence metrics
        if "independence_score" in comparison:
            metrics = comparison["independence_score"]
            ui.console.print(f"[{ui.CYAN}]Independence Metrics:[/]")
            ui.console.print(f"  [{ui.DIM}]Estimate Variance: {metrics.get('estimate_variance', 'unknown')}[/]")
            ui.console.print(f"  [{ui.DIM}]Different Approaches: {metrics.get('different_approaches', 0)}[/]")
            ui.console.print(f"  [{ui.DIM}]Overall: {metrics.get('overall_independence', 'unknown')}[/]\n")

        conflicts = comparison.get("conflicts", [])
        consensus_tasks = comparison.get("consensus", {}).get("tasks", [])
        skip_phase3 = comparison.get("skip_phase3", False)

        # Display consensus and conflicts with personality
        ui.console.print(f"\n[{ui.CYAN}]Comparison Results:[/]")
        if consensus_tasks:
            ui.console.print(f"  [{ui.SUCCESS}]✓ {len(consensus_tasks)} tasks with full agreement[/]")

        if conflicts:
            ui.console.print(f"  [{ui.WARN}]⚠ {len(conflicts)} conflict(s) found:[/]\n")

            # Show interesting conflict details
            for i, conflict in enumerate(conflicts[:5], 1):  # Show first 5
                conflict_type = conflict.get("type", "unknown")

                if conflict_type == "estimate_disagreement":
                    task_name = conflict.get("task", "Unknown task")
                    estimates = conflict.get("estimates", {})
                    ui.console.print(f"     [{ui.DIM}]{i}. Estimate disagreement on '{task_name}':[/]")
                    for persona, estimate in list(estimates.items())[:3]:
                        ui.console.print(f"        [{ui.WHITE}]{persona}:[/] [{ui.CYAN}]{estimate}[/]")

                elif conflict_type == "missing_task":
                    task_name = conflict.get("task", "Unknown")
                    proposed_by = conflict.get("proposed_by", [])
                    missing_from = conflict.get("missing_from", [])
                    ui.console.print(f"     [{ui.DIM}]{i}. '{task_name}' proposed by {len(proposed_by)}, missed by {len(missing_from)}[/]")

                elif conflict_type == "approach_conflict":
                    desc = conflict.get("description", "Approach disagreement")
                    ui.console.print(f"     [{ui.DIM}]{i}. {desc}[/]")

            if len(conflicts) > 5:
                ui.console.print(f"     [{ui.DIM}]... and {len(conflicts) - 5} more conflicts[/]")

            ui.console.print()
        else:
            ui.console.print(f"  [{ui.SUCCESS}]✓ No conflicts - team in full agreement![/]")
            skip_phase3 = True

        # PHASE 3: Consensus Building (only if conflicts exist)
        resolutions = []
        if not skip_phase3 and conflicts:
            if VERBOSE:
                ui.console.print(f"\n[{ui.DIM}]{'─' * 50}[/]")
                ui.console.print(f"[{ui.CYAN}]PHASE 3: Resolving Conflicts[/]\n")

            ui.console.print(f"\n[{ui.MAGENTA}]╔══════════════════════════════════════════════╗[/]")
            phase3_text = f"PHASE 3: Resolving {len(conflicts)} Conflict(s)"
            phase3_padding = " " * (46 - 1 - len(phase3_text))
            ui.console.print(f"[{ui.MAGENTA}]║[/] [{ui.WHITE}]{phase3_text}[/]{phase3_padding}[{ui.MAGENTA}]║[/]")
            ui.console.print(f"[{ui.MAGENTA}]╚══════════════════════════════════════════════╝[/]\n")

            consensus_prompt = get_consensus_prompt(conflicts, board.goal, board.mode)

            response = run_claude(
                prompt=consensus_prompt,
                system_prompt="You are the facilitator resolving specific conflicts. Output ONLY YAML.",
                show_spinner=True
            )

            try:
                consensus_data = extract_yaml_from_response(response)
                resolutions = consensus_data.get("resolutions", [])

                # Display the discussion for each resolution
                if resolutions:
                    ui.console.print(f"\n[{ui.CYAN}]Conflict Resolutions:[/]\n")

                    for i, resolution in enumerate(resolutions, 1):
                        conflict_type = resolution.get("conflict_type", "unknown")
                        discussion = resolution.get("discussion", {})
                        final_value = resolution.get("final_value")
                        action = resolution.get("action")

                        ui.console.print(f"  [{ui.WARN}]Conflict {i}:[/] [{ui.DIM}]{conflict_type}[/]")

                        # Show persona quotes from discussion
                        for persona, quote in discussion.items():
                            if persona != "team_lead_decision" and quote:
                                # Clean persona name for display
                                display_name = persona.replace("_", " ").title()
                                ui.console.print(f"    [{ui.CYAN}]{display_name}:[/] [{ui.DIM}]\"{quote}\"[/]")

                        # Show final decision
                        decision = discussion.get("team_lead_decision")
                        if decision:
                            ui.console.print(f"    [{ui.SUCCESS}]→ Decision:[/] [{ui.WHITE}]{decision}[/]")
                        elif final_value:
                            ui.console.print(f"    [{ui.SUCCESS}]→ Final:[/] [{ui.WHITE}]{final_value}[/]")
                        elif action:
                            ui.console.print(f"    [{ui.SUCCESS}]→ Action:[/] [{ui.WHITE}]{action}[/]")

                        ui.console.print()

                    ui.console.print(f"[{ui.SUCCESS}]✓ All conflicts resolved[/]\n")

            except Exception as e:
                ui.console.print(f"[{ui.ERROR}]Failed to parse consensus: {e}[/]")
                sys.exit(1)
        else:
            ui.console.print(f"[{ui.DIM}]Phase 3 skipped - no conflicts[/]")

        # PHASE 4: Final Synthesis
        if VERBOSE:
            ui.console.print(f"\n[{ui.DIM}]{'─' * 50}[/]")
            ui.console.print(f"[{ui.CYAN}]PHASE 4: Synthesizing Final Plan[/]\n")

        ui.console.print(f"\n[{ui.MAGENTA}]╔══════════════════════════════════════════════╗[/]")
        ui.console.print(f"[{ui.MAGENTA}]║[/] [{ui.WHITE}]PHASE 4: Final Plan[/]                          [{ui.MAGENTA}]║[/]")
        ui.console.print(f"[{ui.MAGENTA}]╚══════════════════════════════════════════════╝[/]\n")

        synthesis_prompt = get_final_synthesis_prompt(consensus_tasks, resolutions, board.goal, board.mode)

        response = run_claude(
            prompt=synthesis_prompt,
            system_prompt="You are synthesizing the final plan from consensus and resolutions. Output ONLY YAML.",
            show_spinner=True
        )

        try:
            data = extract_yaml_from_response(response)
        except Exception as e:
            ui.console.print(f"\n[{ui.ERROR}]Failed to parse final plan: {e}[/]")
            sys.exit(1)

        if not data:
            ui.console.print(f"\n[{ui.ERROR}]Empty final plan[/]")
            sys.exit(1)

        # Store planning metadata
        board.planning_discussion = f"Multi-phase planning: {len(proposals)} proposals, {len(conflicts)} conflicts, {len(resolutions)} resolutions"
        if "independence_score" in comparison:
            board.planning_discussion += f"\nIndependence: {comparison['independence_score'].get('overall_independence', 'unknown')}"

    # Parse the plan YAML (either from simple path or full discussion)
    data = yaml.safe_load(plan_yaml) if is_trivial else data

    # Check if team needs clarifications before proceeding
    if "clarifications_needed" in data and data["clarifications_needed"]:
        clarifications = data["clarifications_needed"]

        if auto:
            # Auto mode: Document assumptions and proceed
            ui.console.print(f"\n[{ui.WARN}]⚠ Team identified ambiguities (auto mode - making assumptions):[/]\n")
            for i, question in enumerate(clarifications, 1):
                ui.console.print(f"   [{ui.DIM}]{i}. {question}[/]")

            # Add these as documented assumptions instead of blocking
            assumption_note = "\n\n**Unresolved ambiguities (auto mode):**\n" + "\n".join(
                f"- {q}" for q in clarifications
            )
            board.context = board.context + assumption_note if board.context else assumption_note.strip()

            # Add to assumptions list for visibility
            for question in clarifications:
                board.assumptions.append(f"UNRESOLVED: {question}")

            ui.console.print(f"\n[{ui.DIM}]Proceeding with best judgment...[/]\n")
            # Continue with planning, don't re-plan

        else:
            # Interactive mode: Ask user for clarifications with timeout
            ui.console.print(f"\n[{ui.WARN}]⚠ The team needs clarification before planning:[/]\n")
            ui.console.print(f"[{ui.DIM}](60 second timeout - team will decide if no response)[/]\n")

            answers = []
            timed_out = False

            for i, question in enumerate(clarifications, 1):
                ui.console.print(f"[{ui.CYAN}]{i}.[/] {question}")

                # Get input with 60 second timeout
                answer = get_input_with_timeout("   → ", timeout=60)

                if answer is None:
                    # Timeout - stop asking more questions
                    ui.console.print(f"\n[{ui.DIM}]No response in 60s - team proceeding with best judgment...[/]\n")
                    timed_out = True
                    break

                answers.append(f"Q: {question}\n   A: {answer}")

            if timed_out:
                # Treat timeout like auto mode - document unresolved questions
                remaining_questions = clarifications[len(answers):]
                all_unresolved = clarifications if not answers else remaining_questions

                assumption_note = "\n\n**Unresolved ambiguities (timeout):**\n" + "\n".join(
                    f"- {q}" for q in all_unresolved
                )
                board.context = board.context + assumption_note if board.context else assumption_note.strip()

                # Add to assumptions list
                for question in all_unresolved:
                    board.assumptions.append(f"UNRESOLVED (timeout): {question}")

                # If we got some answers before timeout, add those too
                if answers:
                    clarification_context = "\n\n**Partial clarifications from user:**\n" + "\n".join(answers)
                    board.context = board.context + clarification_context

                # Re-plan with unresolved questions as assumptions
                ui.console.print(f"\n[{ui.DIM}]Re-planning with assumptions...[/]\n")
                return generate_plan_collaborative(board, iteration, max_iterations, auto)
            else:
                # Got all answers - add clarifications to context and re-plan
                clarification_context = "\n\n**Clarifications from user:**\n" + "\n".join(answers)
                board.context = board.context + clarification_context if board.context else clarification_context.strip()

                ui.console.print(f"\n[{ui.DIM}]Re-planning with clarifications...[/]\n")
                return generate_plan(board, iteration, max_iterations, auto)  # Recursive call with same iteration context

    # Update board with plan data
    if "risks" in data:
        board.risks = data["risks"]
    if "assumptions" in data:
        board.assumptions = data["assumptions"]
    if "out_of_scope" in data:
        board.out_of_scope = data["out_of_scope"]
    if "definition_of_done" in data:
        board.definition_of_done = data["definition_of_done"]

    # Add tasks
    for task_data in data.get("tasks", []):
        task = Task(
            id=task_data["id"],
            title=task_data["title"],
            description=task_data.get("description", ""),
            complexity=Complexity(task_data.get("complexity", "unknown")),
            priority=Priority(task_data.get("priority", "medium")),
            task_type=TaskType(task_data.get("task_type", "implementation")),
            acceptance_criteria=task_data.get("acceptance_criteria", []),
            dependencies=task_data.get("dependencies", []),
            assigned_to=task_data.get("assigned_to", ""),
        )
        board.tasks.append(task)

    # Generate architecture contract if there are multiple implementation tasks
    impl_count = sum(1 for t in board.tasks if t.task_type == TaskType.IMPLEMENTATION)
    if impl_count >= 2:
        ui.console.print(f"\n[{ui.CYAN}]Generating architecture contract...[/]")
        board.architecture_spec = generate_architecture_contract(board)

    # Reaper removed from planning - no validation step needed

    if VERBOSE:
        ui.console.print(f"\n[bold white on red]⚰ THE REAPER APPROVES ⚰[/]\n")

    return board


def generate_plan(board: Board, iteration: int = 1, max_iterations: int = 1, auto: bool = False, planning_mode: str = "collaborative") -> Board:
    """
    Router function for planning. Delegates to collaborative or independent model.

    Args:
        board: The board to plan for
        iteration: Current iteration number (1-based)
        max_iterations: Maximum iterations allowed
        auto: If True, proceed without user input (document assumptions instead)
        planning_mode: "collaborative" (default) or "independent"

    Returns:
        Updated board with tasks
    """
    if planning_mode == "independent":
        return generate_plan_independent(board, iteration, max_iterations, auto)
    else:
        return generate_plan_collaborative(board, iteration, max_iterations, auto)


def negotiate_resurrection(board: Board, task: Task, kill_reason: str, max_rounds: int = 3) -> str:
    """
    Reaper and Agent negotiate an adjustment before retrying a killed task.

    Args:
        board: Current board
        task: Task that was killed
        kill_reason: Why the Reaper killed it
        max_rounds: Maximum negotiation rounds before giving up

    Returns:
        Agreed adjustment strategy as a string

    Raises:
        Exception if they can't reach agreement within max_rounds
    """
    from .personas import get_personas

    # Get assigned persona and Reaper
    personas = get_personas(board.mode, goal=board.goal, context=board.context)
    assigned_persona = next((p for p in personas if p.name == task.assigned_to), personas[0])
    reaper = next(p for p in personas if p.role == "guardian")

    # Build context about previous failures
    history_context = ""
    if task.resurrection_history:
        history_context = "\n**Previous failed attempts:**\n"
        for i, corpse in enumerate(task.resurrection_history[-3:], 1):
            history_context += f"{i}. Killed after {corpse.elapsed_seconds}s: {corpse.kill_reason}\n"
            if corpse.partial_notes:
                history_context += f"   Notes: {corpse.partial_notes[:100]}\n"

    # Negotiation loop
    for round_num in range(1, max_rounds + 1):
        # Agent proposes adjustment
        agent_prompt = f"""Task '{task.title}' was killed by Reaper.

**Why it failed:** {kill_reason}
{history_context}

**Your task:** Propose a SPECIFIC adjustment to the approach that addresses why it failed.
- Don't repeat previous approaches
- Be concrete about what will change
- Keep it brief (1-2 sentences)

What adjustment do you propose?"""

        agent_response = run_claude(
            prompt=agent_prompt,
            system_prompt=assigned_persona.system_prompt,
            show_spinner=False
        )

        # Reaper evaluates proposal
        reaper_prompt = f"""Task '{task.title}' failed: {kill_reason}

**Agent ({assigned_persona.name}) proposes:**
{agent_response}

{history_context}

**Your judgment:** Is this adjustment acceptable, or should they try something different?

Respond with EXACTLY one of:
- "APPROVED: [reason]" - if the adjustment addresses the failure
- "REJECTED: [reason]" - if it's inadequate or repeats previous mistakes

Be brief and direct."""

        reaper_response = run_claude(
            prompt=reaper_prompt,
            system_prompt=reaper.system_prompt,
            show_spinner=False
        )

        # Check if approved
        if "APPROVED" in reaper_response.upper():
            # Extract and return the adjustment
            adjustment = agent_response.strip()
            ui.console.print(f"[{ui.SUCCESS}]✓ Reaper approved adjustment:[/] [{ui.DIM}]{adjustment[:100]}...[/]")
            return adjustment
        elif "REJECTED" in reaper_response.upper():
            # Continue negotiating
            ui.console.print(f"[{ui.WARN}]✗ Reaper rejected (round {round_num}/{max_rounds})[/]")
            # Add rejection to history for next round
            history_context += f"\nRound {round_num} rejected: {reaper_response}\n"
        else:
            # Unclear response - treat as rejection
            ui.console.print(f"[{ui.WARN}]? Unclear Reaper response (round {round_num}/{max_rounds})[/]")

    # Failed to reach agreement
    raise Exception(f"Could not reach agreement after {max_rounds} negotiation rounds")


def execute_task(board: Board, task: Task, progress_callback=None) -> tuple[list[str], Complexity, str]:
    """
    Have the assigned persona execute a task with full planning context.
    Returns (artifacts, actual_complexity, notes).

    Args:
        board: The board containing the task
        task: The task to execute
        progress_callback: Optional callback(progress_pct, output_line) for live updates
    """
    # Get the assigned persona (fallback to generic if not assigned)
    persona = None
    if task.assigned_to:
        personas = get_personas(board.mode, accountability=board.persona_accountability)
        persona = next((p for p in personas if p.name == task.assigned_to), None)

    # Build system prompt - use persona's prompt with board context
    if persona:
        # Persona executes with memory of planning discussion
        planning_context = ""
        if board.planning_discussion:
            planning_context = f"""
## Planning Discussion Context

You participated in the planning session that created this task. Here's what the team discussed:

{board.planning_discussion}

You are now executing the task that was assigned to you. Remember what you and the team discussed about this work.
"""

        # Include findings from YOUR prior completed tasks (learning by doing)
        prior_work = ""
        my_completed_tasks = [
            t for t in board.tasks
            if t.assigned_to == task.assigned_to
            and t.status == TaskStatus.COMPLETED
            and t.id != task.id
        ]
        if my_completed_tasks:
            prior_work = "\n## Your Prior Work in This Sprint\n\n"
            prior_work += "You've already completed these tasks. Use what you learned:\n\n"
            for t in my_completed_tasks:
                prior_work += f"**{t.id}: {t.title}** ({t.task_type.value})\n"
                if t.notes:
                    # Truncate long notes
                    notes = t.notes[:1000] + "..." if len(t.notes) > 1000 else t.notes
                    prior_work += f"Findings: {notes}\n"
                if t.artifacts:
                    prior_work += f"Artifacts: {', '.join(t.artifacts)}\n"
                prior_work += "\n"

        # Include findings from DEPENDENCY tasks (especially spikes)
        dependency_findings = ""
        if task.dependencies:
            completed_deps = [
                board.get_task(dep_id) for dep_id in task.dependencies
                if board.get_task(dep_id) and board.get_task(dep_id).status == TaskStatus.COMPLETED
            ]
            if completed_deps:
                dependency_findings = "\n## Findings from Dependency Tasks\n\n"
                dependency_findings += "These tasks completed before yours - USE their findings:\n\n"
                for dep in completed_deps:
                    dependency_findings += f"**{dep.id}: {dep.title}** ({dep.task_type.value})\n"
                    if dep.notes:
                        # Show full notes for spikes, truncate for others
                        if dep.task_type == TaskType.SPIKE:
                            notes = dep.notes[:3000] + "..." if len(dep.notes) > 3000 else dep.notes
                            dependency_findings += f"📋 SPIKE FINDINGS:\n{notes}\n"
                        else:
                            notes = dep.notes[:1500] + "..." if len(dep.notes) > 1500 else dep.notes
                            dependency_findings += f"Notes: {notes}\n"
                    if dep.artifacts:
                        dependency_findings += f"Artifacts: {', '.join(dep.artifacts)}\n"
                    dependency_findings += "\n"

        # Include resurrection history (previous failed attempts)
        resurrection_context = ""
        if task.resurrection_history:
            resurrection_context = "\n## ⚰ RESURRECTED TASK - Learn from the Dead\n\n"
            resurrection_context += f"**⚠ This task has been killed by Reaper {len(task.resurrection_history)} time(s). Learn from previous failures:**\n\n"
            for corpse in task.resurrection_history[-3:]:  # Show last 3 attempts
                resurrection_context += f"**Attempt #{corpse.attempt_number}** (by {corpse.persona}):\n"
                resurrection_context += f"  - Killed after {corpse.elapsed_seconds}s: {corpse.kill_reason}\n"
                resurrection_context += f"  - Partial work: {corpse.partial_notes}\n\n"
            resurrection_context += "**Try a DIFFERENT approach** - previous methods failed. Don't repeat their mistakes.\n"

        arch_spec_section = ""
        if board.architecture_spec:
            arch_spec_section = f"""
## BINDING ARCHITECTURE CONTRACT — FOLLOW EXACTLY

{board.architecture_spec}

Every parallel agent is working from this same spec.
Deviating breaks integration.
"""

        integration_notes_section = ""
        if board.integration_notes:
            integration_notes_section = f"""
## Integration Issues from Previous Wave

{board.integration_notes}

These issues were detected between waves. Address them.
"""

        system_prompt = f"""{persona.system_prompt}

## Current Sprint/Kanban Board

**Goal:** {board.goal}
**Context:** {board.context}
**Mode:** {board.mode.value.upper()}

**Risks:** {', '.join(board.risks) if board.risks else 'None'}
**Assumptions:** {', '.join(board.assumptions) if board.assumptions else 'None'}
{arch_spec_section}{integration_notes_section}{planning_context}{dependency_findings}{prior_work}{resurrection_context}

You are executing a task assigned to you. Work according to your role and expertise.
**CRITICAL: If this task depends on spikes, their findings are shown above - USE THEM.**
"""
    else:
        # Fallback to generic system prompt if no persona assigned
        base_system_prompt = get_system_prompt(board)
        # Still inject architecture contract and integration notes even without persona
        arch_spec_section = ""
        if board.architecture_spec:
            arch_spec_section = f"""
## BINDING ARCHITECTURE CONTRACT — FOLLOW EXACTLY

{board.architecture_spec}

Every parallel agent is working from this same spec.
Deviating breaks integration.
"""
        integration_notes_section = ""
        if board.integration_notes:
            integration_notes_section = f"""
## Integration Issues from Previous Wave

{board.integration_notes}

These issues were detected between waves. Address them.
"""
        system_prompt = base_system_prompt + arch_spec_section + integration_notes_section

    task_prompt = get_task_prompt(task, board)

    # Different instructions for spike vs implementation tasks
    if task.task_type.value == "spike":
        completion_instructions = """
🔍 THIS IS A SPIKE - INVESTIGATE AND REPORT YOUR FINDINGS 🔍

**This is SIMPLE:**
1. Use tools to explore and gather information
2. Answer the questions in the task description
3. Write your findings in plain language
4. DO NOT build or implement anything

**Just write your investigation results naturally. Example:**

"I explored the authentication system and found:

- Auth implemented in src/auth.py:42-67
- Uses JWT tokens with HS256 algorithm
- Tokens stored in localStorage (auth.js:15)
- Session timeout: 24 hours (config.py:8)

Recommendation: Add token refresh mechanism to avoid requiring re-login."

**That's it. No special format required.**

Optional: If you want to be formal, end with:
```yaml
artifacts: []
actual_complexity: trivial
notes: "Your findings"
```

But you can also just write your findings and we'll capture them.
"""
    else:
        completion_instructions = """
This is an IMPLEMENTATION task - build, code, or create something.

When complete, end your response with a YAML block:

```yaml
artifacts:
  - path/to/file1
  - path/to/file2
actual_complexity: small
notes: "Any observations"
```
"""

    full_prompt = f"""{task_prompt}

{completion_instructions}
"""

    # Timeouts: only apply if explicitly requested
    timeout = board.task_timeout  # User-specified timeout
    if timeout is None and board.use_default_timeouts:
        # Use complexity-based defaults if --task-timeouts flag was set
        limits = COMPLEXITY_TIMEOUTS.get(task.complexity, COMPLEXITY_TIMEOUTS[Complexity.UNKNOWN])
        timeout = limits["kill"]
        if VERBOSE:
            ui.console.print(f"[{ui.DIM}]Timeout: {timeout//60}min ({task.complexity.value})[/]")
    # If no timeout specified and use_default_timeouts is False, timeout stays None (no limit)

    # Only print task start if dashboard is not active (progress_callback means dashboard is active)
    if not progress_callback:
        ui.print_task_start(task.id, task.title, task.description, task.assigned_to)
    if VERBOSE:
        ui.console.print(f"[{ui.DIM}]{'─' * 50}[/]")
    response = run_claude(
        full_prompt,
        system_prompt,
        timeout=timeout,
        mcps=board.mcps if board.mcps else None,
        show_spinner=False,  # No spinner for parallel tasks
        provider=persona.provider if persona else None,
        task=task,  # Pass task for Reaper monitoring
        persona=persona,  # Pass persona for Reaper monitoring
        progress_callback=progress_callback  # For live dashboard updates
    )
    if VERBOSE:
        ui.console.print(f"[{ui.DIM}]{'─' * 50}[/]")

    # Try to extract completion info
    is_spike = task.task_type.value == "spike"

    try:
        data = extract_yaml_from_response(response)
        artifacts = data.get("artifacts", [])
        actual = Complexity(data.get("actual_complexity", "unknown"))
        notes = data.get("notes", "")
    except Exception:
        # If we can't parse YAML
        if is_spike:
            # For spikes, the entire response IS the findings - use it all as notes
            artifacts = []
            actual = Complexity.TRIVIAL  # Spikes are usually trivial
            notes = response.strip()
        else:
            # For implementations, lack of YAML is a problem
            artifacts = []
            actual = None
            notes = "Completed (could not parse completion metadata)"

    return artifacts, actual, notes


def _run_reestimation_discussion(board: Board, task: Task, corpse) -> Optional[Complexity]:
    """
    Run team discussion to decide if task should be resized after timeout kill.
    Returns new complexity if team reaches consensus, None otherwise.
    """
    from .models import ResurrectionRecord

    # Build context about what happened
    context = f"""
## Task Timeout - Re-estimation Needed

**Task:** {task.id} - {task.title}
**Original Estimate:** {task.complexity.value}
**Assigned to:** {corpse.persona}

**What happened:**
- Task was killed by Reaper after {corpse.elapsed_seconds}s
- Kill reason: {corpse.kill_reason}
- Partial progress: {corpse.partial_notes}

**Previous attempts:**
"""
    for i, prev in enumerate(task.resurrection_history, 1):
        context += f"\n{i}. Attempt by {prev.persona}: killed after {prev.elapsed_seconds}s - {prev.kill_reason}"

    goal = f"Should we resize '{task.id}' based on timeout evidence? Team must reach consensus."

    # Run multi-agent discussion focused on re-estimation
    # (Caller already printed message to user)
    discussion_result = run_multi_agent_discussion(
        goal=goal,
        context=context,
        mode=board.mode,
        mcps=board.mcps if hasattr(board, 'mcps') else None
    )

    # Parse result - looking for new_complexity and consensus
    try:
        data = extract_yaml_from_response(discussion_result)
        consensus = data.get("consensus", False)
        new_complexity_str = data.get("new_complexity", "").lower()

        if not consensus:
            if VERBOSE:
                ui.console.print(f"[{ui.DIM}]Team did not reach consensus on resize - keeping {task.complexity.value}[/]")
            return None

        # Map string to Complexity enum
        complexity_map = {
            "trivial": Complexity.TRIVIAL,
            "small": Complexity.SMALL,
            "medium": Complexity.MEDIUM,
            "large": Complexity.LARGE,
        }

        new_complexity = complexity_map.get(new_complexity_str)
        if new_complexity:
            return new_complexity
        else:
            return None

    except (ValueError, yaml.YAMLError) as e:
        if VERBOSE:
            ui.console.print(f"[{ui.WARN}]Could not parse re-estimation result: {e}[/]")
        return None


def get_ready_tasks(board: Board) -> list[Task]:
    """Get all tasks that are ready to run (dependencies met, not started)."""
    completed_ids = {t.id for t in board.tasks if t.status == TaskStatus.COMPLETED}
    in_progress_ids = {t.id for t in board.tasks if t.status == TaskStatus.IN_PROGRESS}

    ready = []
    for task in board.tasks:
        if task.status in [TaskStatus.PLANNED, TaskStatus.READY, TaskStatus.BACKLOG]:
            if task.id not in in_progress_ids:
                if all(dep in completed_ids for dep in task.dependencies):
                    ready.append(task)
    return ready


def run_sprint(board: Board, max_parallel: int = 8, use_live_dashboard: bool = True):
    """
    Run through all tasks in the sprint.

    Automatically parallelizes based on the dependency graph.
    No prompts - approval happens at the CLI level before calling this.

    Args:
        board: The board with tasks to execute
        max_parallel: Max parallel tasks
        use_live_dashboard: Show live streaming dashboard (default True)
    """
    import concurrent.futures
    import threading
    from .dashboard import LiveDashboard
    from .models import ResurrectionRecord

    if board.mode == Mode.SPRINT and not board.sprint_config.scope_locked:
        board.lock_scope()
        board.save(find_board_file())

    board_lock = threading.Lock()

    # Pre-calculate waves to assign correct wave number to each task
    # Pass already-completed tasks so dependencies are correctly resolved
    already_completed = {t.id for t in board.tasks if t.status == TaskStatus.COMPLETED}
    pending_tasks = [t for t in board.tasks if t.status not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]]
    waves = calculate_waves(pending_tasks, already_completed=already_completed)
    task_wave_map = {}  # Map task.id -> wave number
    for wave_idx, wave in enumerate(waves, start=1):
        for task in wave:
            task_wave_map[task.id] = wave_idx

    current_wave = 0

    # Emit sprint started event for web dashboard
    from .dashboard_events import DashboardEventEmitter
    DashboardEventEmitter.emit('sprint_started', {
        'total_tasks': len(pending_tasks),
        'waves': len(waves),
        'tasks': [{'id': t.id, 'title': t.title, 'dependencies': t.dependencies, 'status': t.status.value} for t in board.tasks]
    })
    DashboardEventEmitter.emit('wave_plan_created', {
        'waves': [[t.id for t in wave] for wave in waves]
    })

    # Initialize live dashboard
    dashboard = None
    if use_live_dashboard and not VERBOSE:  # Only use dashboard in non-verbose mode
        total_tasks = len([t for t in board.tasks if t.status not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]])
        if total_tasks > 0:  # Only start dashboard if there are tasks to run
            dashboard = LiveDashboard(total_tasks=total_tasks, show_live=True)
            dashboard.start()

            # Add all tasks to dashboard (queued state)
            for task in board.tasks:
                if task.status not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]:
                    persona_name = task.assigned_to or "Agent"
                    dashboard.add_task(task.id, task, persona_name, 'queued')

    def execute_and_complete(task: Task) -> tuple[str, bool]:
        """Execute a task and return (task_id, success)."""
        try:
            # Progress callback for dashboard
            def progress_cb(progress_pct, output_line):
                if dashboard:
                    dashboard.update_task(task.id, progress=progress_pct, output=output_line)

            # Mark task as running in dashboard
            if dashboard:
                dashboard.start_task(task.id)

            # Emit task started event
            DashboardEventEmitter.emit('task_started', {
                'task_id': task.id,
                'title': task.title,
                'started_at': datetime.now().isoformat()
            })

            artifacts, actual, notes = execute_task(board, task, progress_callback=progress_cb if dashboard else None)

            with board_lock:
                task.complete(artifacts=artifacts, actual_complexity=actual)
                if notes:
                    task.notes = notes
                board.save(find_board_file())

            accuracy = ""
            if actual and task.complexity != Complexity.UNKNOWN:
                if task.complexity == actual:
                    accuracy = "✓"
                else:
                    accuracy = f"{task.complexity.value}→{actual.value}"

            # Mark complete in dashboard
            if dashboard:
                dashboard.complete_task(task.id, success=True, artifacts=artifacts)

            # Emit task completed event
            DashboardEventEmitter.emit('task_completed', {
                'task_id': task.id,
                'artifacts': artifacts,
                'actual_complexity': actual.value if actual else None,
                'completed_at': datetime.now().isoformat()
            })

            # Special display for spike tasks (only if not using dashboard)
            # Check task_type OR if "spike" is in the ID/title (in case planning messed up task_type)
            is_spike = (task.task_type == TaskType.SPIKE or
                       "spike" in task.id.lower() or
                       "investigate" in task.title.lower() or
                       "analyze" in task.title.lower() or
                       "explain" in task.title.lower())

            if not dashboard:
                if is_spike:
                    ui.print_spike_report(task.id, task.title, notes or "Investigation complete", artifacts)
                else:
                    ui.print_task_complete(task.id, accuracy)

            return (task.id, True)
        except RuntimeError as e:
            # Check if this is a Reaper kill
            if "Task killed by Reaper" in str(e):
                # Save kill_count outside lock for use in re-estimation
                with board_lock:
                    task.reaper_kill_count += 1
                    kill_count = task.reaper_kill_count

                    # Save the corpse - preserve context from this failed attempt
                    # Calculate elapsed time safely
                    elapsed = 0
                    if task.started_at:
                        try:
                            started = datetime.fromisoformat(task.started_at)
                            elapsed = int((datetime.now() - started).total_seconds())
                        except (ValueError, AttributeError):
                            elapsed = 0
                    corpse = ResurrectionRecord(
                        attempt_number=kill_count,
                        persona=task.assigned_to or "Unknown",
                        kill_reason=str(e),
                        partial_notes=task.notes[:500] if task.notes else "(No output before death)",
                        killed_at=datetime.now().isoformat(),
                        elapsed_seconds=elapsed
                    )
                    task.resurrection_history.append(corpse)

                    # After 10 kills, give up and trigger replan
                    if kill_count >= 10:
                        task.status = TaskStatus.BLOCKED
                        task.blocked_reason = f"Reaper killed {kill_count}x - needs replan"
                    else:
                        # Negotiate adjustment with Reaper before retry (skip in tests)
                        import os
                        if os.getenv('PYTEST_CURRENT_TEST'):
                            # In test mode - skip negotiation to avoid LLM calls
                            task.notes = "⚰ RESURRECTION: Try different approach.\n\n"
                        else:
                            try:
                                adjustment = negotiate_resurrection(board, task, str(e))
                                # Add adjustment to task notes for next attempt
                                task.notes = f"⚰ RESURRECTION ADJUSTMENT:\n{adjustment}\n\n"
                            except Exception as neg_error:
                                # Negotiation failed - use default message
                                task.notes = f"⚰ RESURRECTION: Could not agree on adjustment ({neg_error}). Try different approach.\n\n"

                        # Reset task to retry (but keep resurrection history)
                        task.status = TaskStatus.BACKLOG
                        task.started_at = None

                    # Save ONCE at end of lock, not twice
                    board.save(find_board_file())

                # Display messages outside lock
                if kill_count >= 10:
                    if dashboard:
                        dashboard.complete_task(task.id, success=False, error=f"⚰ REAPER KILLED 10x - REPLAN NEEDED")
                    if not dashboard:
                        ui.console.print(f"\n[{ui.ERROR}]⚰ REAPER KILLED {task.id} 10 TIMES - TRIGGERING REPLAN[/]")
                    return (task.id, False)

                # OUTSIDE THE LOCK - check if we should re-estimate
                # Check what type of kill this was
                error_msg = str(e).lower()
                is_silence_timeout = any(word in error_msg for word in ["silence", "hung", "no output", "unresponsive"])

                # Trigger re-estimation if:
                # - 2+ non-silence kills (complexity timeout)
                # - OR 3+ silence kills (repeatedly failing to make progress)
                should_reestimate = (
                    (not is_silence_timeout and kill_count >= 2) or  # Complexity timeout
                    (is_silence_timeout and kill_count >= 3)  # Repeated silence = wrong approach
                )

                if should_reestimate:
                    # Team discussion: should we resize this task?
                    # This is OUTSIDE board_lock to avoid blocking other tasks

                    # Show user what's happening
                    if dashboard:
                        dashboard.update_task(task.id, progress=0, output="🔄 Team discussing re-estimation...")
                    else:
                        ui.console.print(f"\n[{ui.CYAN}]💬 Team discussing re-estimation for {task.id} after {kill_count} failures...[/]")

                    new_complexity = _run_reestimation_discussion(board, task, corpse)

                    if new_complexity and new_complexity != task.complexity:
                        with board_lock:
                            task.complexity = new_complexity
                            board.save(find_board_file())

                        # Show result to user
                        if dashboard:
                            dashboard.update_task(task.id, progress=0, output=f"✅ Team resized: {task.complexity.value} → {new_complexity.value}")
                        else:
                            ui.console.print(f"\n[{ui.WARN}]📊 Team resized {task.id}: {task.complexity.value} → {new_complexity.value}[/]")
                    else:
                        # No consensus or no change
                        if dashboard:
                            dashboard.update_task(task.id, progress=0, output=f"↔ Team keeping {task.complexity.value} estimate")
                        else:
                            ui.console.print(f"\n[{ui.DIM}]Team discussed but keeping {task.complexity.value} estimate[/]")

                if dashboard:
                    dashboard.complete_task(task.id, success=False, error=f"⚰ Reaper kill #{kill_count} - retrying")
                if not dashboard:
                    ui.console.print(f"\n[{ui.WARN}]⚰ REAPER KILLED {task.id} (attempt {kill_count}/10) - RETRYING[/]")

                # Return special status for retry
                return (task.id, "retry")

            # Other RuntimeError - treat as failure
            if dashboard:
                dashboard.complete_task(task.id, success=False, error=str(e))
            if not dashboard:
                ui.print_task_failed(task.id, str(e))
            return (task.id, False)

        except Exception as e:
            # Mark failed in dashboard
            if dashboard:
                dashboard.complete_task(task.id, success=False, error=str(e))

            if not dashboard:
                ui.print_task_failed(task.id, str(e))
            return (task.id, False)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
        pending_futures = {}

        while True:
            # Get tasks that are ready to run (dependencies met)
            with board_lock:
                ready_tasks = get_ready_tasks(board)

            # Filter out already running tasks
            running_ids = set(pending_futures.values())
            ready_tasks = [t for t in ready_tasks if t.id not in running_ids]

            # How many can we start?
            slots = max_parallel - len(pending_futures)
            tasks_to_start = ready_tasks[:slots]

            # Update current wave based on tasks we're about to start
            if tasks_to_start:
                # Get wave number of first task to start
                next_wave = task_wave_map.get(tasks_to_start[0].id, current_wave + 1)
                if next_wave > current_wave:
                    # Run wave integration guard before transitioning to next wave
                    if current_wave > 0 and board.architecture_spec:
                        with board_lock:
                            prev_wave_tasks = [
                                t for t in board.tasks
                                if task_wave_map.get(t.id) == current_wave
                                and t.status == TaskStatus.COMPLETED
                            ]
                        has_impl = any(t.task_type == TaskType.IMPLEMENTATION for t in prev_wave_tasks)
                        if has_impl:
                            if not dashboard:
                                ui.console.print(f"\n[{ui.CYAN}]Running wave {current_wave} integration check...[/]")
                            issues = run_wave_integration_guard(board, prev_wave_tasks)
                            if issues and "ALL_CLEAR" not in issues:
                                with board_lock:
                                    board.integration_notes += f"\n\n--- Wave {current_wave} ---\n{issues}"
                                    board.save(find_board_file())

                    current_wave = next_wave
                    if dashboard:
                        dashboard.set_wave(current_wave)
                    if not dashboard:
                        ui.print_wave_start(current_wave, tasks_to_start, len(tasks_to_start) > 1)

            # Start tasks
            for task in tasks_to_start:
                with board_lock:
                    task.start()
                    board.save(find_board_file())

                future = executor.submit(execute_and_complete, task)
                pending_futures[future] = task.id

            # Check if we're done
            if not pending_futures:
                with board_lock:
                    remaining = [t for t in board.tasks if t.status not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]]

                # If no tasks remain, we're done
                if not remaining:
                    if not dashboard:
                        completed = sum(1 for t in board.tasks if t.status == TaskStatus.COMPLETED)
                        ui.print_sprint_complete(completed, current_wave)
                    break

                # If tasks remain but nothing ready, check why
                with board_lock:
                    ready_tasks = get_ready_tasks(board)

                if not ready_tasks:
                    # No tasks ready - determine if we can proceed
                    blocked = [t for t in board.tasks if t.status == TaskStatus.BLOCKED]
                    backlog = [t for t in board.tasks if t.status == TaskStatus.BACKLOG]
                    in_progress = [t for t in board.tasks if t.status == TaskStatus.IN_PROGRESS]

                    if VERBOSE:
                        ui.console.print(f"[{ui.DIM}]DEBUG: no ready tasks - blocked={len(blocked)}, backlog={len(backlog)}, in_progress={len(in_progress)}[/]")
                        if backlog:
                            ui.console.print(f"[{ui.DIM}]DEBUG: backlog tasks: {[t.id for t in backlog]}[/]")

                    if blocked and not in_progress and not backlog:
                        # Tasks permanently blocked, nothing running or retrying
                        ui.console.print(f"\n[{ui.WARN}]⚠ {len(blocked)} tasks blocked[/]")
                        break
                    elif backlog or in_progress:
                        # Tasks in backlog (Reaper kill retry) or still running - keep looping
                        continue
                    else:
                        # No tasks ready, none blocked, none in backlog - circular dependency
                        ui.console.print(f"\n[{ui.WARN}]⚠ No tasks ready (circular dependency?)[/]")
                        break

            # Wait for at least one task to complete
            if pending_futures:
                done, _ = concurrent.futures.wait(
                    pending_futures.keys(),
                    timeout=0.5,
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    del pending_futures[future]
                    # After deleting future, if it was a retry (Reaper kill),
                    # the task is now in BACKLOG and will be picked up by
                    # get_ready_tasks() at the top of the next loop iteration

    # Stop dashboard when done
    if dashboard:
        dashboard.stop()
        # Print final summary after dashboard closes
        completed = sum(1 for t in board.tasks if t.status == TaskStatus.COMPLETED)
        ui.print_sprint_complete(completed, current_wave)


def find_board_file() -> str:
    """Find the board file."""
    current = Path.cwd()
    while current != current.parent:
        board_file = current / ".waverunner.yaml"
        if board_file.exists():
            return str(board_file)
        current = current.parent
    return str(Path.cwd() / ".waverunner.yaml")


def evaluate_sprint(board: Board) -> tuple[bool, str, str, str]:
    """
    Have Claude evaluate if the sprint was successful.
    Returns (success, reasoning, follow_up_goal, follow_up_context).
    """
    prompt = get_evaluation_prompt(board)

    system = """You are a critical code reviewer evaluating sprint results.
Be skeptical. Don't assume success just because tasks were marked complete.
Check if the goal was actually achieved.

IMPORTANT: Focus on whether the OUTCOME was achieved, not HOW it was achieved.
- If the goal was to "ask the user X", check if the information was communicated (document, output, etc.)
- Don't demand specific tools/methods if the goal was accomplished another way
- If you're requesting the same follow-up goal 3+ times, the approach is wrong - try something different

Output ONLY valid YAML, no explanations outside the yaml block."""

    ui.print_evaluating()
    if VERBOSE:
        ui.console.print(f"[{ui.DIM}]{'─' * 50}[/]")
    # Evaluator needs tools to actually verify the deliverable — pass MCPs and give it time
    response = run_claude(prompt, system, mcps=board.mcps if board.mcps else None, timeout=600)
    if VERBOSE:
        ui.console.print(f"[{ui.DIM}]{'─' * 50}[/]")

    try:
        data = extract_yaml_from_response(response)
    except (ValueError, yaml.YAMLError) as e:
        ui.console.print(f"[{ui.WARN}]Could not parse evaluation: {e}[/]")
        return True, "Could not parse evaluation", "", ""

    success = data.get("success", True)
    reasoning = data.get("reasoning", "")
    follow_up_goal = data.get("follow_up_goal", "") if not success else ""
    follow_up_context = data.get("follow_up_context", "") if not success else ""

    confidence = data.get("confidence", "medium")
    issues = data.get("issues", [])

    if success:
        ui.print_eval_success(confidence, reasoning)
    else:
        ui.print_eval_incomplete(confidence, reasoning, issues)

    return success, reasoning, follow_up_goal, follow_up_context


def compute_persona_accountability(board: Board):
    """
    Analyze completed sprint and update persona accountability scores.
    Called after sprint completes to track persona performance.
    """
    # Initialize accountability for any personas we don't have yet
    persona_names = set()
    for task in board.tasks:
        if task.assigned_to:
            persona_names.add(task.assigned_to)
    for decision in board.decisions:
        for perspective in decision.perspectives:
            # Extract persona name from "Persona: statement" format
            if ":" in perspective:
                name = perspective.split(":")[0].strip()
                persona_names.add(name)

    for name in persona_names:
        if name not in board.persona_accountability:
            board.persona_accountability[name] = PersonaAccountability(persona_name=name)

    # Track estimate accuracy
    for task in board.tasks:
        if task.status == TaskStatus.COMPLETED and task.assigned_to and task.actual_complexity:
            acc = board.persona_accountability[task.assigned_to]
            acc.estimates_given += 1
            if task.actual_complexity == task.complexity:
                acc.estimates_accurate += 1
            elif task.actual_complexity.value > task.complexity.value:
                acc.estimates_low += 1  # Underestimated
            else:
                acc.estimates_high += 1  # Overestimated

    # Track spike value (did Explorer's spikes find issues?)
    for task in board.tasks:
        if task.task_type == TaskType.SPIKE and task.assigned_to:
            acc = board.persona_accountability[task.assigned_to]
            acc.spikes_proposed += 1
            # If notes contain words like "blocker", "issue", "problem", "can't", "missing"
            # consider it found an issue
            if task.notes:
                issue_keywords = ["blocker", "issue", "problem", "can't", "cannot", "missing", "blocked", "error"]
                if any(keyword in task.notes.lower() for keyword in issue_keywords):
                    acc.spikes_found_issues += 1

    # Track decision adoption from decisions list
    for decision in board.decisions:
        for perspective in decision.perspectives:
            if ":" in perspective:
                name = perspective.split(":")[0].strip()
                if name in board.persona_accountability:
                    acc = board.persona_accountability[name]
                    acc.recommendations_made += 1
                    # If this persona's perspective aligned with final decision, count as adopted
                    if name not in decision.dissenting:
                        acc.recommendations_adopted += 1

    # Track risks (we'd need to add this to retro manually for now - which risks materialized)
    # For now, just count risks raised by Skeptic role
    # This would need manual retro input to track which risks actually happened


def detect_thrashing(board: Board, iteration: int) -> tuple[bool, str]:
    """
    Detect if we're stuck in a thrashing pattern.

    Returns (is_thrashing, message_describing_pattern).
    """
    thrashing_patterns = []

    # Pattern 1: Multiple Reaper kills
    reaper_killed_tasks = [t for t in board.tasks if t.reaper_kill_count >= 3]
    if reaper_killed_tasks:
        task_ids = ', '.join([t.id for t in reaper_killed_tasks[:3]])
        thrashing_patterns.append(
            f"Tasks killed by Reaper 3+ times: {task_ids}. "
            f"These tasks are timing out or hanging - current approach isn't working."
        )

    # Pattern 2: Same tasks failing repeatedly (blocked status)
    blocked_tasks = [t for t in board.tasks if t.status == TaskStatus.BLOCKED]
    if len(blocked_tasks) >= 2 and iteration >= 3:
        task_ids = ', '.join([t.id for t in blocked_tasks[:3]])
        reasons = set([t.blocked_reason for t in blocked_tasks if t.blocked_reason])
        reason_str = list(reasons)[0] if reasons else "unknown"
        thrashing_patterns.append(
            f"{len(blocked_tasks)} tasks blocked: {task_ids}. "
            f"Reason: {reason_str}. Team is stuck on same obstacles."
        )

    # Pattern 3: Persona with poor estimate accuracy
    if hasattr(board, 'persona_accountability') and board.persona_accountability:
        # Check if any persona has more wrong estimates than accurate ones
        problem_personas = []
        for persona, stats in board.persona_accountability.items():
            total_estimates = stats.estimates_given
            if total_estimates >= 3:  # Only consider personas with enough data
                wrong = stats.estimates_low + stats.estimates_high
                accurate = stats.estimates_accurate
                if wrong > accurate:
                    problem_personas.append((persona, wrong))

        if problem_personas:
            persona_list = ', '.join([f"{p} ({w} wrong)" for p, w in problem_personas[:2]])
            thrashing_patterns.append(
                f"Personas with poor estimates: {persona_list}. "
                f"Need different perspective or approach."
            )

    # Pattern 4: Multiple iterations with minimal progress
    completed_count = sum(1 for t in board.tasks if t.status == TaskStatus.COMPLETED)
    total_count = len(board.tasks)
    if iteration >= 4 and total_count > 0:
        completion_rate = completed_count / total_count
        if completion_rate < 0.3:  # Less than 30% complete after 4 iterations
            thrashing_patterns.append(
                f"After {iteration} iterations, only {completion_rate:.0%} complete. "
                f"Current plan isn't making progress - need radical rethink."
            )

    if thrashing_patterns:
        return True, " ".join(thrashing_patterns)

    return False, ""


def run_cleanup_pass(board: Board):
    """
    Run a cleanup pass after sprint execution to catch loose ends.

    Looks for and fixes:
    - Test files left around
    - Debug code (console.log, print statements)
    - Unused imports
    - TODO/FIXME comments that should be addressed
    - Temporary files
    - Code that should be cleaned up
    """
    ui.print_header("Cleanup Pass")

    cleanup_prompt = f"""## Post-Sprint Cleanup

After completing sprint tasks, perform a cleanup pass to catch loose ends.

**Sprint Goal:** {board.goal}

**Completed Tasks:**
{chr(10).join(f"- {t.id}: {t.title} (artifacts: {', '.join(t.artifacts) if t.artifacts else 'none'})" for t in board.tasks if t.status == TaskStatus.COMPLETED)}

**Your Job:** Find and fix loose ends in the project directory.

**Check for:**
1. **Debug code** - Remove console.log, print statements, debug comments
2. **Test artifacts** - Remove temporary test files, test data left around
3. **Unused code** - Remove commented-out code, unused imports, dead code
4. **TODO/FIXME** - Address or remove TODO/FIXME comments added during sprint
5. **File organization** - Move misplaced files to correct locations
6. **Documentation** - Update docs if code changed significantly

**How to work:**
1. Check the artifacts from completed tasks
2. Look for common cleanup issues in those files
3. Make fixes directly
4. Keep it quick - this is polish, not new features

**Output:**
Report what you cleaned up (or "Nothing to clean" if already clean).
Keep output brief - just list what was fixed.
"""

    system_prompt = """You are doing a post-sprint cleanup pass.

This is NOT about adding features or making major changes.
This IS about removing loose ends, debug code, and tidying up.

Be quick and practical:
- Remove obvious debug code
- Clean up test artifacts
- Remove dead code
- Address quick TODOs

Don't:
- Refactor working code
- Add new features
- Make architectural changes
- Spend more than 2-3 minutes

If everything is already clean, just say so and exit quickly.
"""

    try:
        result = run_claude(
            prompt=cleanup_prompt,
            system_prompt=system_prompt,
            show_spinner=False,
            timeout=180  # 3 minutes max for cleanup
        )

        # Add cleanup notes to board
        if board.context:
            board.context += f"\n\n**Cleanup Pass:** {result[:200]}"

        if VERBOSE:
            ui.console.print(f"[{ui.DIM}]Cleanup: {result}[/]")
        else:
            ui.console.print(f"[{ui.SUCCESS}]✓ Cleanup pass complete[/]")

    except Exception as e:
        # Don't fail the sprint if cleanup fails
        ui.console.print(f"[{ui.WARN}]⚠ Cleanup pass skipped: {str(e)}[/]")


def run_sprint_loop(board: Board, max_iterations: Optional[int] = None, max_parallel: int = 8) -> Board:
    """
    Run sprints in a loop until the goal is achieved.

    After each sprint:
    1. Evaluate if the goal was met
    2. If not, generate a follow-up sprint to fix issues
    3. Repeat until successful (or max_iterations if set)

    Args:
        max_iterations: Maximum iterations (None = infinite, keep retrying until success)
    """
    iteration = 1
    original_goal = board.goal
    board_file = find_board_file()
    previous_goals = []  # Track goals to detect loops

    while max_iterations is None or iteration <= max_iterations:
        ui.print_iteration(iteration, max_iterations)

        # Run the sprint
        run_sprint(board, max_parallel=max_parallel)

        # Cleanup pass after sprint execution
        run_cleanup_pass(board)

        # Evaluate results
        success, reasoning, follow_up_goal, follow_up_context = evaluate_sprint(board)

        # Compute persona accountability for this iteration
        compute_persona_accountability(board)

        if success:
            ui.print_goal_achieved_small()
            board.retro_notes = f"Completed in {iteration} iteration(s). {reasoning}"
            board.save(board_file)
            return board

        if max_iterations is not None and iteration >= max_iterations:
            ui.print_max_iterations(max_iterations)
            board.retro_notes = f"Incomplete after {iteration} iteration(s). {reasoning}"
            board.save(board_file)
            return board

        # Detect infinite loops: same/similar goal repeated 3+ times
        if iteration >= 3 and follow_up_goal:
            # Check if this goal is very similar to recent goals
            recent_similar = sum(1 for prev_goal in previous_goals[-2:]
                               if prev_goal and follow_up_goal and
                               (prev_goal.lower() in follow_up_goal.lower() or
                                follow_up_goal.lower() in prev_goal.lower()))

            if recent_similar >= 2:
                ui.console.print(f"\n[{ui.ERROR}]⚠ INFINITE LOOP DETECTED[/]")
                ui.console.print(f"[{ui.DIM}]Same goal attempted 3+ times:[/]")
                ui.console.print(f"[{ui.DIM}]  '{follow_up_goal}'[/]")
                ui.console.print(f"\n[{ui.WARN}]This goal appears impossible to achieve with current approach.[/]")
                ui.console.print(f"[{ui.WARN}]Breaking loop. Check if the goal requires tools unavailable to tasks.[/]\n")
                board.retro_notes = f"Loop detected after {iteration} iterations. Goal '{follow_up_goal}' repeatedly failed with same approach."
                board.save(board_file)
                return board

        previous_goals.append(follow_up_goal)

        # Detect thrashing patterns and suggest approach changes
        if iteration >= 2:
            thrashing_detected, thrash_message = detect_thrashing(board, iteration)
            if thrashing_detected:
                ui.console.print(f"\n[{ui.WARN}]⚠ THRASHING DETECTED[/]")
                ui.console.print(f"[{ui.DIM}]{thrash_message}[/]")
                ui.console.print(f"\n[{ui.CYAN}]Recommendation: Try a different approach[/]")
                # Add thrashing context to follow-up
                if follow_up_context:
                    follow_up_context += f"\n\n⚠ THRASHING DETECTED: {thrash_message}\nTry a completely different approach - the current method isn't working."
                else:
                    follow_up_context = f"⚠ THRASHING DETECTED: {thrash_message}\nTry a completely different approach - the current method isn't working."

        # Create follow-up sprint
        if not follow_up_goal:
            follow_up_goal = f"Complete remaining work for: {original_goal}"

        ui.print_followup(follow_up_goal)

        # Reset task statuses for new sprint, keeping completed ones
        for task in board.tasks:
            if task.status not in [TaskStatus.COMPLETED, TaskStatus.SKIPPED]:
                task.status = TaskStatus.BACKLOG

        # Update board for new iteration
        board.goal = follow_up_goal
        if follow_up_context:
            board.context = f"{board.context}\n\nFrom previous iteration: {follow_up_context}"

        # Re-plan with Claude (preserve planning mode from board)
        ui.print_header("Re-planning")
        board = generate_plan(board, iteration=iteration + 1, max_iterations=max_iterations, planning_mode=board.planning_mode)
        board.save(board_file)

        # Show tasks created and wave plan (consistent with first iteration)
        ui.print_tasks_created(len(board.tasks))
        waves = calculate_waves(board.tasks)
        ui.print_wave_plan(waves)

        iteration += 1

    return board
