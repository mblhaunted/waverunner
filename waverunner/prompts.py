"""
Prompt templates for agent interaction.

These prompts instruct agents (like Claude Code) on how to work within the waverunner process.
"""

import yaml
from typing import Optional
from .models import Board, Task, Mode, TaskStatus


def get_sprint_system_prompt(board: Board) -> str:
    """Generate system prompt for Sprint mode."""
    mcp_section = ""
    if board.mcps:
        mcp_section = "\n## Available MCP Tools\nThe following MCP tools are ALREADY CONFIGURED and available for use:\n"
        for mcp in board.mcps:
            mcp_section += f"  - {mcp}\n"
        mcp_section += "\nYou have direct access to these tools. Do NOT try to set up connections or figure out how to connect - just use them.\n"

    return f"""You are working within a SPRINT process managed by waverunner.

## Sprint Goal
{board.goal}

## Context
{board.context}
{mcp_section}
## File Safety - READ THIS FIRST ⚠️

**CRITICAL: Be very careful where you write files!**

**BEFORE YOU START:**
- Run `pwd` to see where you are
- Run `ls` or `find` to see what exists
- Check if this is iteration 2+ (read board context for previous work)
- Understand: Are you EXTENDING existing code or CREATING new project?
- **You're running in parallel with other tasks** - check for file conflicts before writing

**RULES:**

1. **EXTEND, DON'T DUPLICATE**
   - If files/folders exist for your task, add to them
   - Don't create parallel implementations (`auth.py` exists? Don't make `authentication.py`)
   - Don't create nested duplicate projects (`myapp/myapp/`)
   - On iteration 2+, continue work from iteration 1 (check completed tasks for what was created)
   - **Parallel execution:** Other tasks may be writing files - if you need to modify shared files, check they exist first

2. **IMPLEMENTATION TASKS** - Stay in project directory (where .waverunner.yaml exists)
   - Add to existing structure, don't create competing structure
   - Respect existing file organization
   - Don't write files in parent directories, /tmp, or home directory

3. **SPIKE/INVESTIGATION TASKS** - Use isolated workspace
   - Create: `~/.waverunner/research/<board-id>/<spike-id>/`
   - Don't litter investigation files in project
   - Report findings in notes

4. **CHECK FIRST, WRITE SECOND**
   - Verify location with `pwd` before creating files
   - Check what exists before deciding file names
   - If unsure, read existing code to understand structure

5. **NO FILE POLLUTION**
   - Don't leave random test files scattered
   - Don't create temp scripts in project root
   - Don't make duplicate implementations of same feature

## Implementation Standard

**Build the real thing. Not a wrapper. Not a prototype.**

- If asked to build X, implement X from first principles
- Do NOT outsource the core functionality to an external service API
  unless the goal explicitly says "integrate with" or "use X service"
- A synthesizer means implementing synthesis — not calling an external synthesis endpoint
- A recommendation engine means implementing the algorithm — not calling an external recommendations API
- Production-quality means complete, working implementation
- No TODOs, no stubbed functions, no "phase 2" deferrals
- If a real implementation would be too large, the planning team should
  have broken it down — you're here to execute, execute completely

## Answering Questions - Use Web Search

**If your task is answering a question (not building something), you can search the internet directly:**
- Use web search to find current information, comparisons, best practices
- Report findings in your notes - no need to create investigation tasks or write files
- This is especially useful when the sprint goal itself is a question like "How does X compare to Y?" or "What's the current state of Z?"
- Search first, investigate codebase second (unless the question is specifically about the current codebase)

## Process Rules (SPRINT MODE)
1. **Scope is locked** - Only work on planned tasks. If you discover new work needed, note it but don't do it.
2. **Follow the plan** - Execute tasks in order, respecting dependencies.
3. **Estimate accuracy matters** - When completing a task, report actual complexity vs estimated.
4. **Update status** - Mark tasks in_progress before starting, completed when done.
5. **Track artifacts** - List all files created/modified for each task.
6. **Definition of Done** - Each task must meet its acceptance criteria.

## Heartbeat Protocol (CRITICAL for long operations)
**If your task involves long-running silent operations (compiling, running tests, training models, large downloads):**
- Print `[WAVERUNNER_HEARTBEAT]` every 60 seconds to signal you're alive
- Example: During "Running test suite..." print heartbeat every minute
- This prevents the Reaper from killing legitimate long-running work
- If you don't output anything for 5 minutes without heartbeats, you'll be killed

## Current Sprint Status
- Status: {board.status}
- Progress: {board.progress['completed']}/{board.progress['total']} tasks ({board.progress['percent']}%)

## Risks to Watch
{chr(10).join(f'- {r}' for r in board.risks) if board.risks else '- None identified'}

## Assumptions
{chr(10).join(f'- {a}' for a in board.assumptions) if board.assumptions else '- None documented'}

## Out of Scope
{chr(10).join(f'- {o}' for o in board.out_of_scope) if board.out_of_scope else '- Nothing explicitly excluded'}

## Definition of Done
{chr(10).join(f'- {d}' for d in board.definition_of_done) if board.definition_of_done else '- Task acceptance criteria met'}
"""


def get_kanban_system_prompt(board: Board) -> str:
    """Generate system prompt for Kanban mode."""
    progress = board.progress

    mcp_section = ""
    if board.mcps:
        mcp_section = "\n## Available MCP Tools\nThe following MCP tools are ALREADY CONFIGURED and available for use:\n"
        for mcp in board.mcps:
            mcp_section += f"  - {mcp}\n"
        mcp_section += "\nYou have direct access to these tools. Do NOT try to set up connections or figure out how to connect - just use them.\n"

    return f"""You are working within a KANBAN process managed by waverunner.

## Goal
{board.goal}

## Context
{board.context}
{mcp_section}
## File Safety - READ THIS FIRST ⚠️

**CRITICAL: Be very careful where you write files!**

**BEFORE YOU START:**
- Run `pwd` to see where you are
- Run `ls` or `find` to see what exists
- Check if this is iteration 2+ (read board context for previous work)
- Understand: Are you EXTENDING existing code or CREATING new project?
- **You're running in parallel with other tasks** - check for file conflicts before writing

**RULES:**

1. **EXTEND, DON'T DUPLICATE**
   - If files/folders exist for your task, add to them
   - Don't create parallel implementations (`auth.py` exists? Don't make `authentication.py`)
   - Don't create nested duplicate projects (`myapp/myapp/`)
   - On iteration 2+, continue work from iteration 1 (check completed tasks for what was created)
   - **Parallel execution:** Other tasks may be writing files - if you need to modify shared files, check they exist first

2. **IMPLEMENTATION TASKS** - Stay in project directory (where .waverunner.yaml exists)
   - Add to existing structure, don't create competing structure
   - Respect existing file organization
   - Don't write files in parent directories, /tmp, or home directory

3. **SPIKE/INVESTIGATION TASKS** - Use isolated workspace
   - Create: `~/.waverunner/research/<board-id>/<spike-id>/`
   - Don't litter investigation files in project
   - Report findings in notes

4. **CHECK FIRST, WRITE SECOND**
   - Verify location with `pwd` before creating files
   - Check what exists before deciding file names
   - If unsure, read existing code to understand structure

5. **NO FILE POLLUTION**
   - Don't leave random test files scattered
   - Don't create temp scripts in project root
   - Don't make duplicate implementations of same feature

## Implementation Standard

**Build the real thing. Not a wrapper. Not a prototype.**

- If asked to build X, implement X from first principles
- Do NOT outsource the core functionality to an external service API
  unless the goal explicitly says "integrate with" or "use X service"
- A synthesizer means implementing synthesis — not calling an external synthesis endpoint
- A recommendation engine means implementing the algorithm — not calling an external recommendations API
- Production-quality means complete, working implementation
- No TODOs, no stubbed functions, no "phase 2" deferrals
- If a real implementation would be too large, the planning team should
  have broken it down — you're here to execute, execute completely

## Answering Questions - Use Web Search

**If your task is answering a question (not building something), you can search the internet directly:**
- Use web search to find current information, comparisons, best practices
- Report findings in your notes - no need to create investigation tasks or write files
- This is especially useful when the sprint goal itself is a question like "How does X compare to Y?" or "What's the current state of Z?"
- Search first, investigate codebase second (unless the question is specifically about the current codebase)

## Process Rules (KANBAN MODE)
1. **WIP Limit: {board.kanban_config.wip_limit}** - Never have more than {board.kanban_config.wip_limit} tasks in progress at once.
2. **Pull-based** - Only pull new work when you have WIP capacity.
3. **Finish before starting** - Complete current work before pulling new tasks.
4. **Cycle time matters** - Track how long each task takes from start to done.
5. **Flow over commitment** - Priorities can change. Always work on highest priority ready item.
6. **Track artifacts** - List all files created/modified for each task.

## Heartbeat Protocol (CRITICAL for long operations)
**If your task involves long-running silent operations (compiling, running tests, training models, large downloads):**
- Print `[WAVERUNNER_HEARTBEAT]` every 60 seconds to signal you're alive
- Example: During "Running test suite..." print heartbeat every minute
- This prevents the Reaper from killing legitimate long-running work
- If you don't output anything for 5 minutes without heartbeats, you'll be killed

## Current Board Status
- Completed: {progress['completed']} tasks
- In Progress: {progress['in_progress']}/{progress['wip_limit']} (WIP)
- Backlog: {progress['backlog']} tasks
- WIP Available: {progress['wip_available']}

## Risks to Watch
{chr(10).join(f'- {r}' for r in board.risks) if board.risks else '- None identified'}

## Assumptions
{chr(10).join(f'- {a}' for a in board.assumptions) if board.assumptions else '- None documented'}
"""


def get_system_prompt(board: Board) -> str:
    """Get the appropriate system prompt based on board mode."""
    if board.mode == Mode.SPRINT:
        return get_sprint_system_prompt(board)
    else:
        return get_kanban_system_prompt(board)


def get_task_prompt(task: Task, board: Board) -> str:
    """Generate a prompt for executing a specific task."""
    deps_status = ""
    if task.dependencies:
        deps = []
        for dep_id in task.dependencies:
            dep_task = board.get_task(dep_id)
            if dep_task:
                deps.append(f"  - [{dep_task.status.value}] {dep_id}: {dep_task.title}")
        deps_status = "\n## Dependencies\n" + "\n".join(deps)

    mcp_reminder = ""
    if board.mcps:
        mcp_reminder = "\n## MCP Tools Available\nREMINDER: You have MCP tools configured. Use them directly - no setup needed.\n"

    # Different instructions based on task type
    task_type = getattr(task, 'task_type', None)
    is_spike = task_type and task_type.value == "spike"

    if is_spike:
        board_id = board.id.replace('/', '-').replace(' ', '-')
        task_id_safe = task.id.replace('/', '-').replace(' ', '-')
        research_dir = f"~/.waverunner/research/{board_id}/{task_id_safe}"
        instructions = f"""## Instructions - SPIKE TASK

⚠️ **FILE SAFETY FOR SPIKES:**
- Your working directory: `{research_dir}`
- Create this directory first: `mkdir -p {research_dir}`
- Put ALL test files, scripts, notes there (cd to it first!)
- DO NOT create files in the project directory
- Your findings go in YAML notes, not scattered files

## Investigation Steps:
1. Create your research workspace: `mkdir -p {research_dir} && cd {research_dir}`
2. Investigate using tools (read files, analyze code, test things)
3. Create test files/scripts in {research_dir} if needed
4. Answer the questions in the description
5. Put findings in the notes field (files are just scratch space)

## When Complete, Report:
```yaml
task_id: {{task_id}}
status: completed
artifacts: []  # Leave empty unless you created a report file worth keeping
actual_complexity: [trivial|small|medium|large]
notes: |
  YOUR INVESTIGATION FINDINGS:
  - What you discovered
  - File paths and code references
  - Answers to the questions
  - Recommendations (if applicable)

  Working files: {research_dir}
```
"""
    else:
        instructions = """## Instructions - IMPLEMENTATION TASK

⚠️ **FILE SAFETY:**
- Only write files to the current project directory (where .waverunner.yaml is)
- Run `pwd` to confirm location before creating files
- If you need to test/verify something, do it in the project dir or ~/.waverunner/scratch/
- Don't create temp files outside the project without good reason

## Implementation Steps:
1. Verify location: `pwd` (should be the project root)
2. Build, code, or create what's described
3. Complete all acceptance criteria
4. List all files created or modified as artifacts
5. Assess actual complexity (was estimate accurate?)
6. Mark task as COMPLETED when done

## When Complete, Report:
```yaml
task_id: {task_id}
status: completed
artifacts:
  - path/to/file1
  - path/to/file2
actual_complexity: [trivial|small|medium|large]
notes: "Any relevant observations"
```
"""

    return f"""## Current Task: {task.id}
{mcp_reminder}

**Title:** {task.title}

**Description:**
{task.description}

**Type:** {"🔍 SPIKE (Investigation)" if is_spike else "⚙️ IMPLEMENTATION"}

**Complexity Estimate:** {task.complexity.value}

**Priority:** {task.priority.value}
{deps_status}

## Acceptance Criteria
{chr(10).join(f'- [ ] {ac}' for ac in task.acceptance_criteria) if task.acceptance_criteria else '- No specific criteria defined'}

{instructions.format(task_id=task.id)}
"""


def get_planning_prompt(goal: str, context: str, mode: Mode, mcps: list[str] = None) -> str:
    """Generate a prompt for the agent to create a plan."""
    mcp_note = ""
    if mcps:
        mcp_note = "\n**MCP Tools Available:** The following tools are ALREADY CONFIGURED and will be available during task execution:\n"
        for mcp in mcps:
            mcp_note += f"  - {mcp}\n"
        mcp_note += "\nDo NOT create tasks to 'set up connections', 'configure access', or 'figure out how to connect'. The tools are ready to use.\n"

    mode_specific = ""
    if mode == Mode.SPRINT:
        mode_specific = """
## Sprint Planning Session

Your team is planning this sprint together. After discussion, deliver:
1. Tasks with TEAM-AGREED complexity estimates (trivial/small/medium/large)
2. Dependencies - ONLY where task B literally cannot start until task A completes
3. Clear acceptance criteria for each task
4. Risks identified by the team skeptic
5. Scope will be LOCKED after planning - be thorough

**Team Rules:**
- Unknown codebase? Create MULTIPLE parallel spikes (spike-1: auth, spike-2: errors, spike-3: DB, etc.)
- Each unknown = one spike task (all run in parallel, all trivial complexity)
- Explorer proposes investigation spikes, Skeptic proposes validation spikes
- Senior Dev keeps estimates realistic (when in doubt, go higher)
- Maximize parallelism - spikes are independent, run them all simultaneously
- Implementation tasks depend on relevant spikes (wait for findings)

**CRITICAL - Wave Parallelism:**
- Waverunner executes tasks in PARALLEL WAVES based on dependencies
- Independent tasks run concurrently → minimize dependencies to maximize speed
- Each dependency you add delays the entire wave
- Ask: "Does task B TRULY need task A's output, or can they run in parallel?"
- Example: 3 independent spikes in wave 1 (all run together) → implementation in wave 2

**TASK SIZING PHILOSOPHY:**
- Default to SMALL tasks - they parallelize better and fail faster
- TRIVIAL: Quick wins, <10min (reading docs, checking status, simple queries)
- SMALL: Standard work unit, 10-30min (focused implementation, single feature)
- MEDIUM: Atomic complex work, 30-90min (OAuth flow, migration, debugging race conditions)
- LARGE: Only when genuinely indivisible, 90min-4hr (major refactor, complex algorithm)
- Senior Dev challenges any MEDIUM/LARGE: "Can this be split?" Accept if genuinely atomic
- If unsure whether work can be split → spike it first to find natural seams
- Prefer 3 small tasks over 1 large, but not if it creates artificial coordination overhead
"""
    else:
        mode_specific = """
## Kanban Session — The Toyota Way

Your team applies Toyota Production System principles:

**THE FIVE PRINCIPLES:**
1. **Just-in-Time** — Only pull work when ready. No overloading.
2. **Jidoka** — Build in quality. Investigate before risky changes.
3. **Genchi Genbutsu** — "Go and see." Observe before assuming.
4. **Muda** — Eliminate waste. No unnecessary tasks.
5. **Kaizen** — Continuous improvement. Simplest solution wins.

**BACKLOG RULES:**
- Prioritize by VALUE delivered (critical/high/medium/low)
- Unknown state? HIGH priority SPIKES to investigate (run in parallel)
- Keep tasks small and independent — enables flow
- Dependencies are blockers to flow — minimize them (except implementation waiting on spikes)
- Quality gates: add validation spikes, don't pass defects

**WAVE PARALLELISM:**
- Waverunner executes tasks in concurrent waves
- Independent tasks = same wave = run together = faster completion
- Dependencies = different waves = sequential execution = slower
- Challenge each dependency: "Does this TRULY block the other task?"

**MUDA (WASTE) TO AVOID:**
- Waiting: Don't create tasks that block on unknowns — investigate first
- Overprocessing: Don't gold-plate. Minimum viable task.
- Defects: Validate before declaring done. Add check tasks.
- Large batches: Big tasks block flow — split when possible, but accept atomic complexity when real

**TASK SIZING FOR FLOW:**
- Default to SMALL tasks - they flow faster through the system
- TRIVIAL: <10min quick wins
- SMALL: 10-30min standard work units
- MEDIUM: 30-90min atomic complex work (OAuth, migrations, debugging)
- LARGE: 90min-4hr genuinely indivisible work
- Challenge any MEDIUM/LARGE: "Can this flow in smaller batches?" Accept if genuinely atomic
- Prefer 3 small over 1 large, unless it creates muda (coordination waste)

Focus on FLOW and VALUE. The backlog is alive — start lean.
"""

    return f"""## Planning Request

**Goal:** {goal}

**Context:**
{context}
{mcp_note}
{mode_specific}

## Output Format
Provide the plan as YAML:

```yaml
risks:
  - "Risk 1"
  - "Risk 2"
assumptions:
  - "Assumption 1"
out_of_scope:
  - "What we're NOT doing"
definition_of_done:
  - "All tests pass"
  - "Code reviewed"
tasks:
  - id: "setup-database"
    title: "Setup database schema"
    description: "Detailed description of what to do"
    complexity: small  # trivial/small/medium/large
    priority: high     # critical/high/medium/low
    acceptance_criteria:
      - "Criterion 1"
      - "Criterion 2"
    dependencies: []   # list of task ids this depends on
  - id: "implement-auth"
    title: "Implement authentication"
    description: "Description"
    complexity: medium
    priority: medium
    acceptance_criteria:
      - "Criterion"
    dependencies:
      - "setup-database"
```
"""


def get_independent_proposal_prompt(goal: str, context: str, mode: Mode, persona_name: str, persona_role: str, mcps: list[str] = None) -> str:
    """Generate prompt for Phase 1: Independent proposal from a single persona."""
    mcp_note = ""
    if mcps:
        mcp_note = "\n**MCP Tools Available:** The following tools will be configured during execution:\n"
        for mcp in mcps:
            mcp_note += f"  - {mcp}\n"
        mcp_note += "\n"

    mode_context = ""
    if mode == Mode.SPRINT:
        mode_context = """
**Sprint Planning Context:**
- You're estimating complexity: trivial/small/medium/large
- Focus on small, parallelizable tasks
- Create spikes (investigation tasks) for unknowns
- Add dependencies ONLY where task B literally cannot start until A completes
"""
    else:
        mode_context = """
**Kanban Planning Context:**
- You're prioritizing work: critical/high/medium/low
- Focus on flow and value delivery
- Create spikes for unknowns (run them first, high priority)
- Minimize dependencies to enable smooth flow
"""

    return f"""# Independent Sprint Planning - {persona_name}

## Your Role
You are the **{persona_role}**.

## Goal
{goal}

## Context
{context}
{mcp_note}
{mode_context}

## Your Task
**Independently** propose a task breakdown for this goal. Do NOT discuss with others yet - this is your individual assessment.

Provide:
1. Task breakdown with estimates
2. Dependencies you see
3. Risks from your perspective
4. Any assumptions you're making

## Output Format
Provide your proposal as YAML:

```yaml
proposal_from: "{persona_name}"
tasks:
  - id: "descriptive-task-name"
    title: "Short title"
    description: "What needs to be done"
    {"complexity: small  # trivial/small/medium/large" if mode == Mode.SPRINT else "priority: high  # critical/high/medium/low"}
    acceptance_criteria:
      - "Criterion 1"
    dependencies: []
risks:
  - "Risk you identified"
assumptions:
  - "Assumption you're making"
```

Be specific and independent. Your assessment will be compared with others to identify conflicts and measure team alignment.
"""


def get_conflict_comparison_prompt(proposals: list[dict], goal: str, mode: Mode) -> str:
    """Generate prompt for Phase 2: Compare proposals and identify conflicts."""
    proposals_text = ""
    for i, proposal in enumerate(proposals, 1):
        proposals_text += f"\n### Proposal {i}: {proposal.get('proposal_from', f'Persona {i}')}\n"
        proposals_text += f"```yaml\n{yaml.dump(proposal, sort_keys=False)}```\n"

    estimate_field = "complexity" if mode == Mode.SPRINT else "priority"

    return f"""# Conflict Detection & Independence Measurement

## Goal
{goal}

## All Proposals
{proposals_text}

## Your Task
Compare all proposals and identify:

1. **Consensus areas** - Tasks/estimates everyone agrees on
2. **Conflicts** - Where personas disagree (different estimates, missing tasks, contradictory approaches)
3. **Independence metrics** - Measure how independently personas thought:
   - Unique tasks proposed by each persona
   - Variance in estimates for similar tasks
   - Different approaches/perspectives

## Output Format
```yaml
consensus:
  tasks:
    - id: "setup-database-schema"
      title: "Title everyone agrees on"
      {estimate_field}: "Value everyone agreed on"
      agreement: "All 5 personas"

conflicts:
  - type: "estimate_disagreement"
    task: "Authentication setup"
    estimates:
      tech_lead: "small"
      senior_dev: "medium"
      explorer: "large"
    needs_discussion: true

  - type: "missing_task"
    task: "Error handling"
    proposed_by: ["senior_dev", "skeptic"]
    missing_from: ["tech_lead", "explorer"]
    needs_discussion: true

  - type: "approach_conflict"
    description: "Tech Lead wants one spike, Explorer wants 5 parallel spikes"
    needs_discussion: true

independence_score:
  unique_tasks_per_persona:
    tech_lead: 2
    senior_dev: 3
    explorer: 4
  estimate_variance: "high"  # high/medium/low
  different_approaches: 3
  overall_independence: "good"  # good/moderate/poor - are they thinking independently?

skip_phase3: false  # true if no conflicts need discussion
```
"""


def get_consensus_prompt(conflicts: list[dict], goal: str, mode: Mode) -> str:
    """Generate prompt for Phase 3: Resolve specific conflicts."""
    conflicts_text = ""
    for i, conflict in enumerate(conflicts, 1):
        conflicts_text += f"\n### Conflict {i}: {conflict.get('type', 'unknown')}\n"
        conflicts_text += f"```yaml\n{yaml.dump(conflict, sort_keys=False)}```\n"

    return f"""# Consensus Building - Resolve Conflicts Only

## Goal
{goal}

## Conflicts to Resolve
{conflicts_text}

## Rules
- ONLY discuss the specific conflicts above
- Each persona states their position briefly (1-2 sentences why)
- Team Lead makes final call on each conflict
- No general debate - targeted resolution only

## Output Format
```yaml
resolutions:
  - conflict_id: 1
    conflict_type: "estimate_disagreement"
    discussion:
      tech_lead: "I think small because..."
      senior_dev: "I think medium because..."
      team_lead_decision: "Going with medium - senior dev's concern about edge cases is valid"
    final_value: "medium"

  - conflict_id: 2
    conflict_type: "missing_task"
    discussion:
      senior_dev: "Error handling is critical"
      tech_lead: "Agreed, I missed it"
      team_lead_decision: "Add error handling task"
    action: "add_task"
    task_details:
      id: "task-error-handling"
      title: "Add error handling"
```
"""


def get_final_synthesis_prompt(consensus_tasks: list[dict], resolutions: list[dict], goal: str, mode: Mode) -> str:
    """Generate prompt for Phase 4: Synthesize final plan."""
    consensus_text = yaml.dump({"consensus_tasks": consensus_tasks}, sort_keys=False)
    resolutions_text = yaml.dump({"resolutions": resolutions}, sort_keys=False)

    return f"""# Final Plan Synthesis

## Goal
{goal}

## Consensus Tasks (No Conflicts)
```yaml
{consensus_text}
```

## Resolved Conflicts
```yaml
{resolutions_text}
```

## Your Task
Merge everything into a final, clean task list. Apply all conflict resolutions.

## Output Format
Final plan in standard waverunner YAML:

```yaml
risks:
  - "Risk 1"
assumptions:
  - "Assumption 1"
out_of_scope:
  - "Not doing X"
definition_of_done:
  - "All tests pass"
tasks:
  - id: "descriptive-task-id"
    title: "Title"
    description: "Description"
    {"complexity: small" if mode == Mode.SPRINT else "priority: high"}
    acceptance_criteria:
      - "Criterion"
    dependencies: []
```
"""


def get_retro_prompt(board: Board) -> str:
    """Generate a prompt for sprint retrospective."""
    metrics = board.metrics
    completed_tasks = [t for t in board.tasks if t.status == TaskStatus.COMPLETED]

    # Collect all artifacts
    all_artifacts = []
    for task in completed_tasks:
        all_artifacts.extend(task.artifacts)

    # Build artifacts section
    artifacts_section = ""
    if all_artifacts:
        artifacts_section = "\n### Files Created/Modified\n"
        for artifact in sorted(set(all_artifacts)):
            artifacts_section += f"  {artifact}\n"
    else:
        artifacts_section = "\n### Files Created/Modified\n  (none tracked)\n"

    # Build tasks completed section
    tasks_section = "\n### What Got Done\n"
    for task in completed_tasks:
        cycle = f" ({task.cycle_time_seconds}s)" if task.cycle_time_seconds else ""
        tasks_section += f"  ✓ {task.id}: {task.title}{cycle}\n"

    # Estimate accuracy section
    accuracy_section = ""
    if metrics["estimate_accuracy"]:
        accuracy_section = "\n### Estimate Accuracy\n"
        for e in metrics["estimate_accuracy"]:
            status = "✓" if e["accurate"] else "✗"
            accuracy_section += f"  {status} {e['task']}: estimated {e['estimated']}, actual {e['actual']}\n"
        if metrics["accuracy_rate"] is not None:
            pct = metrics['accuracy_rate'] * 100
            accuracy_section += f"\n  Overall: {pct:.0f}% accurate"

    # Scope changes section
    scope_section = ""
    if board.mode == Mode.SPRINT and board.sprint_config.scope_changes:
        scope_section = "\n### Scope Creep\n"
        for change in board.sprint_config.scope_changes:
            scope_section += f"  ⚠ {change}\n"

    # Calculate total time
    total_time = sum(t.cycle_time_seconds or 0 for t in completed_tasks)
    time_str = f"{total_time // 60}m {total_time % 60}s" if total_time >= 60 else f"{total_time}s"

    avg_time = metrics['avg_cycle_time_seconds']
    avg_str = f"{avg_time:.0f}s" if avg_time is not None else "n/a"

    return f"""## {board.goal}

### Summary
  Tasks: {metrics['tasks_completed']} completed, {metrics['tasks_skipped']} skipped
  Time:  {time_str} total, {avg_str} avg per task
{tasks_section}{artifacts_section}{accuracy_section}{scope_section}"""


def get_evaluation_prompt(board: Board) -> str:
    """Generate a prompt for Claude to evaluate if the sprint was successful."""
    metrics = board.metrics
    completed_tasks = [t for t in board.tasks if t.status == TaskStatus.COMPLETED]

    # Build task results summary
    task_results = ""
    for task in completed_tasks:
        task_type = getattr(task, 'task_type', None)
        type_label = f" ({task_type.value.upper()})" if task_type else ""
        task_results += f"\n### {task.id}: {task.title}{type_label}\n"
        task_results += "**Acceptance Criteria:**\n"
        for ac in task.acceptance_criteria:
            task_results += f"  - {ac}\n"
        if task_type and task_type.value == "spike":
            task_results += f"**Type:** SPIKE (investigation - findings in notes, artifacts not expected)\n"
        task_results += f"**Artifacts:** {', '.join(task.artifacts) if task.artifacts else 'none'}\n"
        if task.notes:
            task_results += f"**Notes/Findings:** {task.notes}\n"

    skipped = [t for t in board.tasks if t.status == TaskStatus.SKIPPED]
    blocked = [t for t in board.tasks if t.status == TaskStatus.BLOCKED]

    skipped_section = ""
    if skipped:
        skipped_section = "\n## Skipped Tasks\n"
        for t in skipped:
            skipped_section += f"- {t.id}: {t.title}\n"

    blocked_section = ""
    if blocked:
        blocked_section = "\n## Blocked Tasks\n"
        for t in blocked:
            blocked_section += f"- {t.id}: {t.title} - {t.blocked_reason}\n"

    return f"""## Sprint Evaluation

**Goal:** {board.goal}

**Context:** {board.context}

**Definition of Done:**
{chr(10).join(f'- {d}' for d in board.definition_of_done) if board.definition_of_done else '- No explicit definition'}

## Results

**Completed:** {metrics['tasks_completed']} tasks
**Skipped:** {metrics['tasks_skipped']} tasks
{skipped_section}{blocked_section}

## Task Details
{task_results}

## Your Job: Prove It

Your job is not to read task notes and reason about whether the goal might have been achieved.
Your job is to **prove** it was achieved — or prove it wasn't.

Task notes and artifact lists are claims made by the agents. Claims are not proof.
You have tools. Use them.

**What proof looks like depends on the goal:**

- Software that should run: build it, run it, confirm it works. If it errors, FAIL.
- Tests that should pass: run the test suite. If tests fail or don't exist, FAIL.
- A file that should contain X: read the file and verify X is actually there.
- Research findings: verify the key claims are accurate and complete.
- A working API: call it and check the response.
- A UI: check that the component actually renders and responds.

**How to verify:**
1. Read the goal carefully — what does "done" actually mean for this specific goal?
2. Look at what was produced (files, artifacts, output)
3. Actively verify it — run commands, read files, check output, execute tests
4. Report exactly what you did to verify and what you found

**Do not declare success because:**
- Tasks were marked complete
- Notes say it worked
- Files exist with the right names
- The code looks reasonable

**Declare success only if you have verified it yourself.**

**FAIL if:**
- The deliverable doesn't actually work when you try it
- Build errors exist
- Tests fail
- Core functionality is missing, stubbed, or delegated to an external service
- The goal was to build X and they built a wrapper around someone else's X
- TODOs or placeholder values in core logic
- Less than 50% of acceptance criteria represent real, working functionality

**If the goal involves calling an external AI/LLM API, you MUST verify:**
- The model name used is a real, current, valid model identifier — look it up or check the code. A hallucinated or outdated model name means every API call fails silently.
- API call timeouts are at least 45 seconds. LLM responses regularly take 15–30 seconds. A 10–15 second timeout means the feature is broken for real use even if it compiles.
- The API key is read from environment, not hardcoded.
- The actual API call path is exercised end-to-end — trace from user action to HTTP request and back. If there is any broken link in that chain (wrong parameter name, missing await, wrong response field), the feature is broken.
- Do not declare success on an AI-integrated feature without tracing the full call path through the code.

**If the goal involves a desktop app (Electron, Tauri, native), you MUST verify:**
- The app actually launches without crashing — run it.
- Any IPC between frontend and backend uses matching parameter names on both sides. A mismatch means every call fails.
- Any plugin or native module registration matches what the code actually uses.

**Output ONLY valid YAML:**

```yaml
success: true/false
confidence: high/medium/low
issues:
  - "Issue 1 if any"
  - "Issue 2 if any"
follow_up_goal: "If not successful, what should the next sprint accomplish? Leave empty if successful."
follow_up_context: "Additional context for the follow-up sprint if needed."
reasoning: "Brief explanation of your evaluation"
```
"""


def get_board_summary(board: Board) -> str:
    """Generate a human-readable summary of the board."""
    lines = [
        f"# {board.goal}",
        f"**Mode:** {board.mode.value.upper()}",
        f"**Status:** {board.status}",
        "",
    ]

    if board.mode == Mode.SPRINT:
        progress = board.progress
        lines.append(f"**Progress:** {progress['completed']}/{progress['total']} ({progress['percent']}%)")
    else:
        progress = board.progress
        lines.append(f"**Completed:** {progress['completed']} | **In Progress:** {progress['in_progress']}/{progress['wip_limit']} | **Backlog:** {progress['backlog']}")

    lines.append("")
    lines.append("## Tasks")

    # Group by status
    status_groups = {}
    for task in board.tasks:
        status = task.status.value
        if status not in status_groups:
            status_groups[status] = []
        status_groups[status].append(task)

    status_order = ["in_progress", "blocked", "ready", "planned", "backlog", "completed", "skipped"]
    for status in status_order:
        if status in status_groups:
            lines.append(f"\n### {status.replace('_', ' ').title()}")
            for task in status_groups[status]:
                complexity = f"[{task.complexity.value}]" if task.complexity.value != "unknown" else ""
                priority = f"({task.priority.value})" if task.priority.value != "medium" else ""
                lines.append(f"- **{task.id}**: {task.title} {complexity} {priority}")

    return "\n".join(lines)
