# Persona System Analysis

## Current Personas

### Sprint Mode (6 personas)
1. **Tech Lead** (facilitator) - Plans and breaks down work
2. **Senior Dev** (pragmatist) - Estimates complexity, prefers simple solutions
3. **Explorer** (investigator) - Discovery and analysis tasks
4. **Skeptic** (risk_manager) - Identifies risks and ambiguities
5. **Maverick** (provocateur) - Cuts through BS, Sam Watkins voice
6. **The Reaper** (guardian) - Safety guardian, 1700s voice

### Kanban Mode (6 personas)
1. **Flow Master** (facilitator) - Optimizes flow and throughput
2. **Kaizen Voice** (improver) - Simplifies and eliminates waste
3. **Quality Gate** (quality_guardian) - Validates before passing downstream
4. **Value Stream** (value_focus) - Prioritizes by customer value
5. **Maverick** (provocateur) - Questions if work delivers value
6. **The Reaper** (guardian) - Safety guardian

## Parallelism Analysis

### Current Implementation
✅ **Already supports persona cloning!**
- Personas are templates, not singletons
- Multiple tasks can be assigned to same persona
- They execute in parallel using ThreadPoolExecutor
- Each task gets same persona system prompt but runs independently

### Current Limitations
❌ `max_parallel` hardcoded to 4 in `run_sprint()`
❌ Not configurable from CLI
❌ Documentation doesn't clarify cloning is supported

### Example: Current System Can Do This
```yaml
tasks:
  - id: "task-1"
    assigned_to: "Senior Dev"  # Instance 1
  - id: "task-2"
    assigned_to: "Senior Dev"  # Instance 2
  - id: "task-3"
    assigned_to: "Senior Dev"  # Instance 3
  - id: "task-4"
    assigned_to: "Explorer"    # Instance 1
```

All 4 would run simultaneously (if max_parallel >= 4 and no dependencies).
Default max_parallel is now 16, so up to 16 tasks can run at once.

## Persona Coverage Assessment

### Well Covered
✅ Planning/coordination (Tech Lead, Flow Master)
✅ Technical implementation (Senior Dev)
✅ Investigation/research (Explorer)
✅ Quality/risk (Skeptic, Quality Gate)
✅ Value focus (Value Stream)
✅ Momentum (Maverick)
✅ Safety (The Reaper)

### Potential Gaps
🤔 **Specialized Technical Roles** - Currently "Senior Dev" is generalist
- Frontend specialist
- Backend specialist
- DevOps/Infrastructure
- Database expert
- Security expert

**Analysis:** These are execution specializations, not planning perspectives. Current system handles this well - "Senior Dev" persona can be assigned to any technical task. During execution, Claude Code has full context and tooling to handle any specialty.

**Verdict:** No new personas needed for technical specialization.

🤔 **Product/UX Perspective** - No one advocating for user experience
- Could add "Product Voice" or "UX Advocate"
- Would focus on: usability, user journey, accessibility

**Analysis:** Useful for user-facing work, but most waverunner usage is backend/tooling. Could be optional persona.

**Verdict:** Consider adding if user-facing work becomes common.

## Recommendations

### 1. Make max_parallel Configurable ✅ DONE
CLI flag added with default of 16:
```bash
waverunner go "goal" --max-parallel 32  # Can scale even higher
```

Default changed from 4 to 16 for better parallelism out of the box.

### 2. Document Persona Cloning (HIGH PRIORITY)
Update docs to clarify:
- Personas are templates, not singletons
- Multiple tasks can use same persona
- Planning uses one instance per persona
- Execution clones as needed

### 3. Optional: Add Product/UX Persona (LOW PRIORITY)
Only if user-facing work becomes common:
```python
Persona(
    name="Product Voice",
    role="user_advocate",
    system_prompt="Focus on user experience, accessibility, usability..."
)
```

### 4. Consider Persona Assignment Smarts (FUTURE)
Currently planning team manually assigns tasks. Could add:
- Auto-assignment based on task type
- Load balancing across personas
- Persona specialization hints

But manual assignment works well and gives team control.

## Conclusion

**Current personas are well-balanced and complete.** No new personas needed.

**Main issue:** max_parallel is hardcoded. This artificially limits parallelism.

**Fix:** Make max_parallel configurable from CLI. System already supports arbitrary parallelism.
