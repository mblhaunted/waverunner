# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Waverunner is a lightweight orchestrator for Claude Code that parallelizes tasks based on dependency graphs. It simulates team-based sprint planning and automatically executes tasks in parallel waves, with self-evaluation and retry loops.

**Key Concept:** Instead of running tasks sequentially, waverunner analyzes dependencies and groups independent tasks into "waves" that execute concurrently. After execution, it self-evaluates and retries with follow-up sprints if the goal wasn't achieved.

## Development Commands

### Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Running Waverunner
```bash
# Main command - plan and execute
waverunner go "Your goal here"

# With options
waverunner go "Goal" --auto          # Skip confirmations
waverunner go "Goal" --verbose       # Show detailed Claude output
waverunner go "Goal" --mode kanban   # Use Kanban mode
waverunner go "Goal" --mcp ~/config.json  # Inject MCP servers

# Other commands
waverunner status    # Current progress
waverunner tasks     # Task table
waverunner run       # Continue execution
waverunner do        # Execute next task
waverunner retro     # Sprint retrospective
waverunner reset     # Delete board, start fresh
```

### Testing
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=waverunner --cov-report=html

# Run specific test file
pytest tests/test_wave_calculation.py -v
```

Test suite covers:
- Wave calculation (dependency graph resolution)
- YAML parsing and error handling
- Board state management and persistence
- LLM provider abstraction
- Multi-agent persona system
- Task lifecycle and status transitions
- Reaper supervision and task retry behavior

### Testing Requirements

**CRITICAL: Use Test-Driven Development (TDD) for ALL changes.**

**For new features:**
1. Write the test FIRST (it will fail - that's expected)
2. Implement the feature to make the test pass
3. Run the full test suite to ensure no regressions
4. Commit test and implementation together

**For bug fixes:**
1. Create a minimal test that reproduces the bug (should fail initially)
2. Fix the bug
3. Verify the test passes
4. Run the full test suite to ensure no regressions
5. Commit the test WITH the fix

**Coverage goal:** Maintain high test coverage (currently 39% - needs improvement)

Example: The Reaper retry bug was fixed by:
- Creating test_reaper_retry.py with two tests
- Fixing the missing datetime import in agent.py
- Verifying both tests pass
- Running full test suite (pytest tests/)
- Committing both test and fix together

**Before creating tests for a feature, verify the feature is actually used in the codebase.**
Example: Chameleon persona tests were removed because the feature was no longer used.

This prevents regressions and documents expected behavior.

### Prompt Engineering Rules

**CRITICAL: NEVER hard-code specific tool/language/framework names in prompts.**

When writing system prompts or agent instructions:

**❌ WRONG - Hard-coded specifics:**
```
- If output shows "npm install", "pip install", "cargo build" → CONTINUE
- Use React for the frontend
- Deploy with Docker
- Store data in PostgreSQL
```

**✅ CORRECT - General, applicable concepts:**
```
- If output shows package/dependency management operations → CONTINUE
- Use appropriate frontend framework based on requirements
- Deploy with containerization if needed
- Store data in appropriate database based on access patterns
```

**Why this matters:**
- Hard-coded examples limit the agent to specific tools they've seen
- Agents are smart enough to apply general concepts to any tool/language
- Hard-coding creates blind spots for tools/approaches not listed
- General terms allow agents to make intelligent choices based on context

**When writing prompts:**
- Use categories instead of examples ("build tools" not "webpack, vite, rollup")
- Use patterns instead of instances ("progress indicators" not "Installing..., Downloading...")
- Use principles instead of prescriptions ("optimize for readability" not "use TypeScript")
- Trust the agent to apply general guidance to specific situations

**This applies to ALL prompts:**
- System prompts in personas.py
- Task execution prompts in agent.py
- Evaluation prompts in prompts.py
- Any guidance given to LLMs

## Architecture

### File Structure
- **cli.py** - Typer-based CLI interface, all commands and argument parsing
- **agent.py** - Sprint orchestration, multi-agent planning, execution, evaluation
- **personas.py** - Multi-agent persona system (Tech Lead, Senior Dev, Explorer, Skeptic, Maverick)
- **providers.py** - LLM provider abstraction (Claude Code, Mock, extensible)
- **models.py** - Data models (Board, Task, Sprint/Kanban configs)
- **prompts.py** - System prompts for execution and evaluation (planning now in personas.py)
- **ui.py** - Rich console output and formatting
- **tests/** - Comprehensive test suite using pytest

### Core Data Flow

1. **Planning** (`generate_plan()` in agent.py, personas in personas.py)
   - **MULTI-AGENT SYSTEM**: Each persona is an independent LLM agent, not simulated
   - Runs `run_multi_agent_discussion()` which orchestrates actual agent conversations
   - **Round 1**: Facilitator opens, introduces goal
   - **Round 2**: Each persona (Senior Dev, Explorer, Skeptic, Maverick) responds
   - **Round 3**: Follow-up round where personas can respond to each other
   - Facilitator synthesizes discussion into concrete plan via `get_facilitator_synthesis_prompt()`
   - **Assigns tasks to personas** based on expertise (Explorer→discovery, Senior Dev→implementation, etc.)
   - Stores full planning discussion on board for execution context
   - Team checks for ambiguities - if found, outputs `clarifications_needed` in YAML
   - User is prompted to answer clarifying questions
   - Planning re-runs with answers added to context
   - Final output: tasks with assigned owners, dependencies, risks, assumptions

2. **Wave Calculation** (`calculate_waves()` in cli.py)
   - Builds dependency graph from tasks
   - Groups tasks with satisfied dependencies into waves
   - Each wave can execute in parallel

3. **Execution** (`execute_task()` and `run_sprint()` in agent.py)
   - Each task executed by its **assigned persona** (e.g., "Senior Dev", "Explorer")
   - Persona uses their own system prompt + full planning discussion context
   - Persona remembers: "You participated in planning and discussed this task..."
   - Uses ThreadPoolExecutor for parallel task execution across multiple personas
   - Spawns Claude Code subprocesses for each task with persona context
   - Manages board state with thread locks
   - Automatically starts next wave when current wave completes
   - **Accountability**: Personas see if their complexity estimates were accurate

4. **Evaluation** (`evaluate_sprint()` in agent.py)
   - Claude critically reviews completed tasks against acceptance criteria
   - Returns success/failure with reasoning
   - If failed, generates follow-up sprint goal

5. **Retry Loop** (`run_sprint_loop()` in agent.py)
   - Repeats plan → execute → evaluate cycle
   - Continues until success or max_iterations reached
   - Each iteration adds context from previous attempts

### State Persistence

Board state is saved to `.waverunner.yaml` in the project directory. The file contains:
- Goal and context
- Mode (sprint/kanban) and mode-specific config
- All tasks with status, dependencies, artifacts
- Risks, assumptions, out_of_scope
- MCP configurations
- Timeout settings

### LLM Provider Abstraction

Waverunner uses a provider pattern to support multiple LLM backends:

**Provider Interface** (`providers.py`):
```python
class LLMProvider(ABC):
    def run(self, prompt, system_prompt, timeout, mcps, ...) -> str:
        pass
```

**Available Providers**:
- `ClaudeCodeProvider` - Default, uses Claude Code CLI
- `MockLLMProvider` - For testing, returns canned responses
- Extensible for future providers (Anthropic API, OpenAI, etc.)

**Provider Selection**:
```python
from waverunner.providers import get_provider, set_provider

provider = get_provider("claude-code")  # or "mock"
set_provider(provider)
```

The `run_claude()` function in agent.py delegates to the current provider:
- Manages process lifecycle with proper timeouts
- Streams output with spinner UI
- Extracts YAML responses from LLM output
- Handles keyboard interrupts and errors

### Multi-Agent Planning System

Waverunner uses **actual separate agents**, not simulation. Each persona runs as an independent LLM call:

**Persona Structure** (`personas.py`):
```python
@dataclass
class Persona:
    name: str          # "Tech Lead", "Senior Dev", etc.
    role: str          # "facilitator", "pragmatist", etc.
    system_prompt: str # Full persona instructions
    color: str         # UI display color
```

**Sprint Personas:**
- **Tech Lead** (facilitator): Breaks down goals, makes final decisions, keeps scope realistic
- **Senior Dev** (pragmatist): Estimates complexity, pushes back on complexity, suggests simpler approaches
- **Explorer** (investigator): Identifies unknowns, suggests discovery tasks, advocates for exploration
- **Skeptic** (risk_manager): Flags ambiguities, questions assumptions, identifies risks
- **Maverick** (provocateur): Challenges ALL reasoning, forces falsification, provocatively blunt

**Kanban Personas:**
- **Flow Master** (facilitator): Optimizes flow, identifies bottlenecks, keeps WIP low
- **Kaizen Voice** (improver): Simplifies, eliminates waste, suggests smallest solutions
- **Quality Gate** (quality_guardian): Flags ambiguities, validates before action, ensures genchi genbutsu
- **Value Stream** (value_focus): Prioritizes by value, cuts low-value work, thinks end-to-end
- **Maverick** (provocateur): Exposes waste through provocation, questions if work delivers value

**Discussion Flow** (`run_multi_agent_discussion()` in agent.py):
1. Facilitator opens with goal introduction (1 LLM call)
2. Each persona responds in sequence (4 LLM calls)
3. Follow-up round - personas respond to each other (5 LLM calls)
4. Facilitator synthesizes discussion into YAML plan (1 LLM call)

Total: ~11 LLM calls per planning session. Each agent has full conversation history and responds authentically.

**Why real agents vs simulation?**
- True diversity of thought - each agent only sees its own system prompt
- Emergent dynamics from actual conversation flow
- More authentic debate and challenges
- Better plans through genuine multi-perspective analysis

**Task Assignment & Execution Continuity**

The team that plans is the team that executes:

- During planning, facilitator assigns each task to a specific persona based on expertise
- Task model includes `assigned_to` field (e.g., "Senior Dev", "Explorer")
- During execution, the assigned persona executes their task using their own system prompt
- Personas receive full planning discussion context ("You discussed this with the team...")
- This creates accountability: personas see if their estimates were accurate

**Assignment Guidelines:**
- **Explorer**: Discovery, investigation, research, analysis tasks
- **Senior Dev**: Implementation, refactoring, core logic tasks
- **Skeptic**: Testing, validation, edge case verification
- **Tech Lead / Flow Master**: Coordination, integration, documentation
- Assignment based on task nature and who discussed it during planning

The Board stores `planning_discussion` so each persona has memory of what was said during planning.

### Two Modes

**Sprint Mode (default):**
- Upfront planning with locked scope
- Complexity estimates (trivial/small/medium/large)
- Team perspectives: Tech Lead, Senior Dev, Explorer, Skeptic, Maverick
- Maverick (Diogenes-style): Challenges all reasoning, forces falsification, provocatively blunt
- Tracks scope changes and estimate accuracy

**Kanban Mode:**
- Continuous flow with WIP limits
- Priority-based (critical/high/medium/low)
- Toyota Production System principles
- Team perspectives: Flow Master, Kaizen Voice, Quality Gate, Value Stream, Maverick
- Maverick: Questions whether work delivers value, exposes waste through provocation
- Tracks cycle time and throughput

### MCP Injection

When `--mcp` is specified, the configuration is:
1. Stored in `board.mcps` list
2. Injected into planning prompt (tells Claude tools are available)
3. Passed to every task execution subprocess via `--mcp-config` flag

This allows tasks to access external tools (databases, APIs) without setup.

### Ambiguity Detection and Clarification

Before committing to a plan, the team checks for ambiguities in the goal:
1. The Skeptic (Sprint) or Quality Gate (Kanban) raises unclear references
2. If ambiguities exist, team outputs `clarifications_needed` in YAML
3. User is prompted interactively to answer each clarification question
4. Answers are appended to board context as "Clarifications from user"
5. Planning runs again recursively with the clarified context
6. Process repeats until no clarifications needed

**Example ambiguities detected:**
- "this codebase" - which codebase? (tool vs. current repo)
- "create a plan" - plan for what specifically?
- Pronouns or context-dependent references
- Implicit scope assumptions

This prevents the team from making incorrect assumptions and running tasks based on misunderstood goals.

## Important Implementation Details

### Task Execution in Parallel
Tasks execute in parallel using ThreadPoolExecutor. The `run_sprint()` function:
- Maintains a pool of futures for running tasks
- Continuously checks for ready tasks (dependencies met)
- Fills available slots up to `max_parallel` (default: 4)
- Uses thread locks to safely update board state
- Saves board after each task state change

### Dependency Resolution
Tasks can only run when all dependencies are completed:
```python
ready = all(dep in completed_ids for dep in task.dependencies)
```

Circular dependencies or unsatisfied dependencies cause the sprint to halt with a warning.

### Complexity-Based Timeouts
When `--task-timeouts` is enabled, tasks get complexity-based timeouts defined in `COMPLEXITY_TIMEOUTS` (agent.py):
- TRIVIAL: 4min warn / 10min kill
- SMALL: 10min warn / 30min kill
- MEDIUM: 30min warn / 90min kill
- LARGE: 90min warn / 4 hours kill
- UNKNOWN: 30min warn / 2 hours kill

Custom timeout can be set with `--timeout <seconds>`.

### YAML Response Parsing
Claude's responses are expected to end with YAML blocks:
```yaml
artifacts:
  - path/to/file
actual_complexity: small
notes: "Observations"
```

The `extract_yaml_from_response()` function handles extraction from markdown code blocks.

### Verbose Mode
When `--verbose` is set:
- Shows live Claude output during execution
- Displays separator lines between agent calls
- Shows elapsed time and time since last output
- Prints debug command invocations

Without verbose, only shows spinner with elapsed time.

## Key Patterns

### When Modifying Planning Logic
The planning prompts in prompts.py embed team personas and rules. Changes to planning behavior should update:
- System prompt in `get_planning_prompt()`
- Team discussion instructions
- YAML output format expectations

### When Adding New Commands
1. Add command function to cli.py with `@app.command()` decorator
2. Load board with `load_board()` if command operates on existing board
3. Save board with `save_board(board)` after modifications
4. Add UI output using functions from ui.py

### When Modifying Task Execution
The `execute_task()` function handles single task execution. It:
- Builds prompts from task + board context
- Calls `run_claude()` with system prompt and MCPs
- Parses YAML response for artifacts/complexity
- Returns tuple: (artifacts, actual_complexity, notes)

The caller (run_sprint) handles updating task status and saving board.

## Dependencies

From pyproject.toml:
- **pyyaml>=6.0** - YAML parsing for board state and Claude responses
- **rich>=13.0** - Terminal UI (tables, colors, formatting)
- **typer>=0.9** - CLI framework

Requires Python 3.10+ and Claude Code CLI installed.

## Notes for Future Development

- No test coverage currently - add tests for wave calculation, dependency resolution, and YAML parsing
- Board file format is YAML by default, supports JSON with .json extension
- The project uses flat file structure (no packages) - all modules are top-level
- Error handling in Claude subprocess is basic - could be enhanced for specific failure modes
- Retrospective metrics track estimate accuracy and cycle times but aren't used for prediction yet
