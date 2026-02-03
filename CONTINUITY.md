# Persona Continuity in Waverunner

**Core Principle:** Personas are AGENTS, not functions. They must maintain continuity across all phases.

## Continuity Flow

### 1. Planning Phase
**What happens:**
- Tech Lead opens discussion
- Each persona responds (Senior Dev, Explorer, Skeptic, Maverick)
- Full discussion stored in `board.planning_discussion`

**Continuity maintained:**
✅ Full conversation history preserved
✅ Each persona sees what others said
✅ Discussion stored on board for later phases

### 2. Planning → Execution
**What happens:**
- Tasks assigned to personas during planning
- Assigned persona executes their task
- Persona receives planning context

**Continuity maintained:**
✅ Persona gets their own system prompt (personality intact)
✅ Persona sees full planning discussion: "You participated in planning. The team discussed..."
✅ Persona knows what they said they'd do

**Implementation:** `execute_task()` in agent.py, lines 558-602

### 3. Execution → Respawn (if killed by Reaper)
**What happens:**
- Agent fails or gets hung
- The Reaper kills the agent
- Agent generates death cry (their own words)
- The Reaper generates corrections
- New agent spawned with corrections

**Continuity maintained:**
✅ Death cry is contextual (agent knows what they were doing)
✅ Respawned agent gets: original prompt + failure reason + Reaper's corrections
✅ No memory loss - new agent knows they're a respawn and why

**Implementation:** `reaper_generate_corrections()` and `agent_generate_death_cry()` in agent.py

### 4. Sprint → Retry Sprint
**What happens:**
- Sprint fails evaluation
- New sprint generated with follow-up goal
- Board context updated with previous iteration context

**Continuity maintained:**
✅ Board context accumulates: original + clarifications + previous attempt learnings
✅ Personas see: "This is iteration 2. Previous attempt failed because..."
✅ Planning discussion from previous sprint available

**Implementation:** `run_sprint_loop()` and `generate_plan()` with iteration parameter

### 5. Evaluation
**What happens:**
- Evaluator reviews completed tasks
- Checks artifacts, acceptance criteria, notes

**Continuity maintained:**
✅ Evaluator sees what each persona claimed to accomplish
✅ Evaluator sees artifacts produced
✅ Evaluator sees task notes

**Implementation:** `evaluate_sprint()` in agent.py

## Anti-Patterns (What We DON'T Do)

❌ Hardcoded responses or death cries
❌ Forgetting what was said in planning
❌ Generic system prompts that don't include context
❌ Respawning agents without telling them why they failed
❌ Losing planning discussion between phases

## Ensuring Continuity

**When adding new features:**
1. Does the agent have access to prior context?
2. Does the agent know what happened before?
3. Are we generating responses dynamically or using hardcoded strings?
4. Is the persona's personality maintained across phases?

**Checklist:**
- [ ] Agent has access to planning discussion
- [ ] Agent knows if they're a respawn and why
- [ ] Agent sees what other personas did/said
- [ ] Agent's responses are generated, not hardcoded
- [ ] Context flows: planning → execution → evaluation → retry

## Examples of Good Continuity

**Planning:**
```
Senior Dev: "I'll use Flask with SQLite. Simple, proven stack."
```

**Execution (same agent):**
```
System Prompt: "You participated in planning and said you'd use Flask..."
Task: Implement backend
Agent: *uses Flask because they said they would*
```

**Failure:**
```
Reaper: "Agent hung for 3 minutes. KILL."
Agent generates death cry: "The Flask routes were almost done! Just needed—"
Reaper corrections: "Don't get stuck on edge cases. Ship the happy path first."
Respawned agent: "I'm restarting this task. I previously got stuck on edge cases.
                   This time: happy path first."
```

**Evaluation:**
```
Evaluator: "Senior Dev said they'd use Flask. Checking artifacts...
            ✓ app.py exists and uses Flask as planned
            ✓ SQLite database as discussed
            Plan matches execution. APPROVED."
```

This is what true persona continuity looks like.
