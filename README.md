# Waverunner

Waverunner is an orchestrator for Claude Code that runs multiple agents in parallel based on a dependency graph. Instead of one agent working through tasks sequentially, a team of specialized agents plans together and executes in parallel waves.

## How it works

Planning runs about 11 LLM calls. Five independent agents (personas) each have a distinct role and system prompt. They don't share perspectives. They respond to the goal, debate approach, respond to each other, and the facilitator synthesizes a YAML task graph with concrete tasks, dependency assignments, complexity estimates, risks, and assumptions.

Once the plan is locked, waverunner calculates which tasks can run simultaneously (no unsatisfied dependencies), groups them into waves, and executes each wave with a thread pool. Tasks that depend on earlier work wait.

After execution, an evaluator reviews the results against the original goal. If the goal wasn't met, it generates a follow-up sprint with the failure context included. This repeats until the goal is achieved or you hit the iteration limit.

## Design decisions worth knowing about

**Architecture contract.** After planning, before any code runs, a binding technical spec is generated: exact file paths, function signatures, package choices, integration points. Every parallel agent gets this spec in their system prompt. This prevents two agents from choosing incompatible libraries or creating conflicting file structures.

**Wave integration guard.** Between waves, artifact files from implementation tasks are read and checked against the architecture contract. Deviations get appended to `board.integration_notes` and injected into the next wave's context.

**Reaper supervision.** Each running agent is monitored. Deterministic checks run first: silence timeout, infinite loop detection, CPU and process state. An LLM judgment is only used when those are inconclusive. Killed agents pass failure context and partial work to their successors.

**Resurrection negotiation.** When the Reaper kills a task, the agent and Reaper negotiate an adjustment before the successor starts. The successor gets specific guidance about what went wrong and what to try differently, not just a note that the previous attempt failed.

**Anti-laziness evaluation.** The evaluator explicitly fails implementations that outsource core logic to external APIs, return stubs or TODOs, or defer real work. Building an API wrapper when asked to build the thing itself is a failing grade.

**Spike tasks.** Investigation tasks run before implementation tasks that depend on them. The agent writes findings to `~/.waverunner/research/<board-id>/<spike-id>/`. Implementation tasks that list a spike as a dependency receive its findings in their system prompt.

**Ambiguity detection.** If the team identifies unclear references or implicit scope assumptions in the goal, it outputs `clarifications_needed` and blocks until the user answers. Planning reruns with the answers. This prevents building the wrong thing.

## Installation

```bash
git clone https://github.com/mblhaunted/waverunner.git
cd waverunner
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.10+ and the Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
claude auth
```

## Usage

```bash
waverunner go "your goal here"
```

Common flags:

```bash
waverunner go "goal" --auto              # skip confirmation prompts
waverunner go "goal" --verbose           # show live agent output
waverunner go "goal" --mode kanban       # continuous flow instead of sprint
waverunner go "goal" --mcp ~/mcp.json   # inject MCP servers into every agent
waverunner go "goal" --provider anthropic-api  # use Anthropic API directly
waverunner go "goal" --max-iter 3        # limit retry iterations
waverunner go "goal" --task-timeouts     # enable complexity-based timeouts
waverunner go "goal" --context "..."     # add context for the planning team
```

Board management:

```bash
waverunner status    # current progress
waverunner tasks     # task table with dependencies
waverunner run       # continue executing an existing board
waverunner retro     # sprint retrospective
waverunner reset     # delete board and start fresh
```

Waverunner saves state to `.waverunner.yaml` in the current directory after every task state change. Runs can be interrupted and resumed with `waverunner run`.

## Personas

**Sprint mode:** Tech Lead (facilitator), Senior Dev (pragmatist), Explorer (investigator), Skeptic (risk manager), Maverick (provocateur).

**Kanban mode:** Flow Master (facilitator), Kaizen Voice (improver), Quality Gate (quality guardian), Value Stream (value focus), Maverick.

Each persona is a real LLM call with its own system prompt. They only know their role. The Maverick challenges all reasoning in both modes. The Tech Lead or Flow Master synthesizes the final plan.

Task assignments follow role: Explorer takes discovery and investigation tasks, Senior Dev takes implementation, Skeptic takes testing and validation, Tech Lead takes coordination and documentation. The team that plans is the team that executes.

## Sprint vs Kanban

Sprint mode locks scope after planning. Tasks get complexity estimates (trivial / small / medium / large). The loop is: plan, execute, evaluate, iterate until the goal is achieved.

Kanban mode uses continuous flow with WIP limits. Tasks have priorities (critical / high / medium / low). The team applies Toyota Production System principles: minimize WIP, optimize flow, eliminate waste. Good for ongoing work and bug queues.

## Providers

By default waverunner spawns Claude Code subprocesses. To use the Anthropic API directly:

```bash
export ANTHROPIC_API_KEY=your-key
waverunner go "goal" --provider anthropic-api
```

The API provider uses prompt caching on system prompts. MCP injection only works with the Claude Code provider.

## Complexity-based timeouts

When `--task-timeouts` is enabled:

| Complexity | Warn after | Kill after |
|---|---|---|
| trivial | 4 min | 10 min |
| small | 10 min | 30 min |
| medium | 30 min | 90 min |
| large | 90 min | 4 hours |

## Development

```bash
pip install -e ".[dev]"
pytest                                         # run all tests
pytest --cov=waverunner --cov-report=html     # with coverage
```

The project uses TDD. New features get a failing test first, then implementation. Current suite: 142 tests.

Key files:

| File | Purpose |
|---|---|
| `waverunner/agent.py` | Planning, execution, evaluation, Reaper |
| `waverunner/models.py` | Board, Task, config dataclasses |
| `waverunner/personas.py` | Persona system prompts and synthesis prompts |
| `waverunner/prompts.py` | Execution and evaluation prompts |
| `waverunner/providers.py` | LLM provider abstraction |
| `waverunner/cli.py` | CLI commands |
| `waverunner/ui.py` | Terminal output |

## License

Apache 2.0
