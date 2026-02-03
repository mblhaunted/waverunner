# Waverunner Project Structure

## Overview
Waverunner is a lightweight orchestrator for Claude Code that parallelizes tasks based on dependency graphs. It simulates team-based sprint planning and automatically executes tasks in parallel waves.

## Entry Points

### CLI Entry Point (cli.py)
- **Main entry**: `waverunner` command defined in `pyproject.toml` → `waverunner.cli:app`
- **Framework**: Typer CLI framework
- **Commands**:
  - `go` - Main command: plan and execute a goal
  - `status` - Show current sprint/board progress
  - `tasks` - Display task table
  - `run` - Continue execution of current board
  - `do` - Execute next ready task
  - `retro` - Sprint retrospective
  - `reset` - Delete board and start fresh

## Core Modules

### 1. **cli.py** (10,369 bytes)
- Typer-based CLI interface
- All commands and argument parsing
- Wave calculation logic (`calculate_waves()`)
- Board loading/saving helpers
- Default board file: `.waverunner.yaml`

### 2. **agent.py** (33,257 bytes)
- Sprint orchestration and execution engine
- Multi-agent planning system
- Task execution with parallel processing (ThreadPoolExecutor)
- Evaluation and retry loops
- Key functions:
  - `generate_plan()` - Creates task plan using multi-agent discussion
  - `run_multi_agent_discussion()` - Orchestrates persona conversations
  - `execute_task()` - Executes individual tasks
  - `run_sprint()` - Parallel task execution with wave management
  - `run_sprint_loop()` - Retry loop with evaluation
  - `evaluate_sprint()` - Critical review of completed tasks

### 3. **models.py** (17,170 bytes)
- Data models using Python dataclasses
- Core entities:
  - `Board` - Main state container (goal, tasks, config, risks, assumptions)
  - `Task` - Task definition with dependencies, status, complexity
  - `Sprint` / `Kanban` - Mode-specific configurations
  - Enums: `Mode`, `TaskStatus`, `Complexity`, `Priority`
- YAML serialization/deserialization support

### 4. **personas.py** (23,317 bytes)
- Multi-agent persona system
- Each persona is an independent LLM agent
- **Sprint Personas**:
  - Tech Lead (facilitator)
  - Senior Dev (pragmatist)
  - Explorer (investigator)
  - Skeptic (risk_manager)
  - Maverick (provocateur)
- **Kanban Personas**:
  - Flow Master (facilitator)
  - Kaizen Voice (improver)
  - Quality Gate (quality_guardian)
  - Value Stream (value_focus)
  - Maverick (provocateur)
- System prompts and role definitions

### 5. **providers.py** (8,106 bytes)
- LLM provider abstraction layer
- Provider interface: `LLMProvider` (ABC)
- Implementations:
  - `ClaudeCodeProvider` - Default, uses Claude Code CLI
  - `MockLLMProvider` - For testing
- Provider management: `get_provider()`, `set_provider()`

### 6. **prompts.py** (16,439 bytes)
- System prompts for execution and evaluation
- Planning prompts now in personas.py
- Templates for:
  - Task execution context
  - Sprint evaluation
  - Retrospectives
  - YAML response formats

### 7. **ui.py** (22,950 bytes)
- Rich console output and formatting
- Progress displays, tables, spinners
- Color-coded task status
- Board visualization
- Verbose mode output handling

## Test Suite

Located in `/tests/` directory:

- **test_wave_calculation.py** - Dependency graph resolution tests
- **test_yaml_parsing.py** - YAML parsing and error handling tests
- **test_board.py** - Board state management and persistence tests
- **test_providers.py** - LLM provider abstraction tests
- **test_personas.py** - Multi-agent persona system tests

Test framework: pytest with coverage support

## Documentation

- **CLAUDE.md** (14,138 bytes) - Comprehensive project documentation for Claude Code
- **README.md** (9,444 bytes) - User-facing documentation
- **CONTINUITY.md** (4,165 bytes) - Additional context documentation
- **PERSONA_ANALYSIS.md** (4,243 bytes) - Persona design analysis
- **PERSONA_MODELS.md** (2,483 bytes) - Persona models reference

## Configuration Files

- **pyproject.toml** - Python project configuration, dependencies, entry points
- **.gitignore** - Git ignore patterns
- **.waverunner.yaml** - Board state persistence file (created during execution)
- **.claude/** - Claude Code configuration directory

## Dependencies

From pyproject.toml:
- **pyyaml>=6.0** - YAML parsing for board state
- **rich>=13.0** - Terminal UI
- **typer>=0.9** - CLI framework
- Python 3.10+ required

## Architecture Flow

```
CLI (cli.py)
  └─> Agent (agent.py)
       ├─> Personas (personas.py) - Multi-agent planning
       ├─> Providers (providers.py) - LLM abstraction
       ├─> Models (models.py) - Data structures
       ├─> Prompts (prompts.py) - System prompts
       └─> UI (ui.py) - Rich output
```

## Data Flow

1. **Planning** - Multi-agent discussion → YAML task plan → Board state
2. **Wave Calculation** - Dependency graph → Parallel execution waves
3. **Execution** - ThreadPool → Persona-assigned tasks → Artifacts
4. **Evaluation** - Critical review → Success/failure → Optional retry
5. **State Persistence** - Board serialization to `.waverunner.yaml`

## File Organization

Flat file structure - all core modules are top-level in the package. No nested packages, keeping the architecture simple and accessible.
