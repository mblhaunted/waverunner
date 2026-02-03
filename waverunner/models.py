"""Core data models for waverunner."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import yaml
import json


class Mode(str, Enum):
    SPRINT = "sprint"    # Agile sprint - upfront planning, locked scope, commitment
    KANBAN = "kanban"    # Continuous flow - WIP limits, pull-based, flexible scope


class TaskStatus(str, Enum):
    BACKLOG = "backlog"          # Kanban: in backlog, not yet prioritized
    PLANNED = "planned"          # Sprint: committed to this sprint
    READY = "ready"              # Ready to pull (dependencies met)
    IN_PROGRESS = "in_progress"  # Currently being worked
    IN_REVIEW = "in_review"      # Done, awaiting verification
    BLOCKED = "blocked"          # Can't proceed
    COMPLETED = "completed"      # Done and verified
    SKIPPED = "skipped"          # Won't do


class Complexity(str, Enum):
    TRIVIAL = "trivial"      # < 5 min, single file, obvious change
    SMALL = "small"          # 5-15 min, 1-2 files, straightforward
    MEDIUM = "medium"        # 15-45 min, multiple files, some thinking
    LARGE = "large"          # 45+ min, significant changes, risks
    UNKNOWN = "unknown"      # needs investigation first


class Priority(str, Enum):
    CRITICAL = "critical"    # Do first, blocks everything
    HIGH = "high"            # Important, do soon
    MEDIUM = "medium"        # Normal priority
    LOW = "low"              # Nice to have


class TaskType(str, Enum):
    IMPLEMENTATION = "implementation"  # Build/code/create something
    SPIKE = "spike"                    # Investigate/research/answer a question


@dataclass
class PersonaAccountability:
    """Track a persona's track record across iterations."""
    persona_name: str
    estimates_given: int = 0          # How many complexity estimates they made
    estimates_accurate: int = 0       # How many were correct
    estimates_low: int = 0            # How many underestimated
    estimates_high: int = 0           # How many overestimated
    risks_raised: int = 0             # How many risks they flagged
    risks_materialized: int = 0       # How many actually happened
    recommendations_made: int = 0     # How many suggestions they gave
    recommendations_adopted: int = 0  # How many made it into final plan
    spikes_proposed: int = 0          # How many investigation tasks
    spikes_found_issues: int = 0      # How many found blocking issues

    def to_dict(self) -> dict:
        return {
            "persona_name": self.persona_name,
            "estimates_given": self.estimates_given,
            "estimates_accurate": self.estimates_accurate,
            "estimates_low": self.estimates_low,
            "estimates_high": self.estimates_high,
            "risks_raised": self.risks_raised,
            "risks_materialized": self.risks_materialized,
            "recommendations_made": self.recommendations_made,
            "recommendations_adopted": self.recommendations_adopted,
            "spikes_proposed": self.spikes_proposed,
            "spikes_found_issues": self.spikes_found_issues,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PersonaAccountability":
        return cls(
            persona_name=data["persona_name"],
            estimates_given=data.get("estimates_given", 0),
            estimates_accurate=data.get("estimates_accurate", 0),
            estimates_low=data.get("estimates_low", 0),
            estimates_high=data.get("estimates_high", 0),
            risks_raised=data.get("risks_raised", 0),
            risks_materialized=data.get("risks_materialized", 0),
            recommendations_made=data.get("recommendations_made", 0),
            recommendations_adopted=data.get("recommendations_adopted", 0),
            spikes_proposed=data.get("spikes_proposed", 0),
            spikes_found_issues=data.get("spikes_found_issues", 0),
        )

    def accuracy_rate(self) -> float:
        """Return estimate accuracy as 0-1 ratio."""
        if self.estimates_given == 0:
            return 0.0
        return self.estimates_accurate / self.estimates_given

    def risk_hit_rate(self) -> float:
        """Return risk prediction accuracy as 0-1 ratio."""
        if self.risks_raised == 0:
            return 0.0
        return self.risks_materialized / self.risks_raised

    def adoption_rate(self) -> float:
        """Return recommendation adoption rate as 0-1 ratio."""
        if self.recommendations_made == 0:
            return 0.0
        return self.recommendations_adopted / self.recommendations_made


@dataclass
class Decision:
    """Tracks a planning decision - whether consensus was reached or leader made the call."""
    topic: str                          # What was being decided
    consensus: bool                      # True if team agreed, False if leader decided
    decision: str                        # What was decided
    reasoning: str                       # Why this decision was made
    perspectives: list[str] = field(default_factory=list)  # What each persona said
    dissenting: list[str] = field(default_factory=list)    # Who disagreed (if !consensus)
    decided_by: str = ""                 # Who made final call (if !consensus)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "consensus": self.consensus,
            "decision": self.decision,
            "reasoning": self.reasoning,
            "perspectives": self.perspectives,
            "dissenting": self.dissenting,
            "decided_by": self.decided_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Decision":
        return cls(
            topic=data["topic"],
            consensus=data["consensus"],
            decision=data["decision"],
            reasoning=data["reasoning"],
            perspectives=data.get("perspectives", []),
            dissenting=data.get("dissenting", []),
            decided_by=data.get("decided_by", ""),
        )


@dataclass
class ResurrectionRecord:
    """Record of a previous failed attempt at a task."""
    attempt_number: int
    persona: str
    kill_reason: str
    partial_notes: str
    killed_at: str
    elapsed_seconds: int

    def to_dict(self) -> dict:
        return {
            "attempt_number": self.attempt_number,
            "persona": self.persona,
            "kill_reason": self.kill_reason,
            "partial_notes": self.partial_notes,
            "killed_at": self.killed_at,
            "elapsed_seconds": self.elapsed_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResurrectionRecord":
        return cls(
            attempt_number=data["attempt_number"],
            persona=data["persona"],
            kill_reason=data["kill_reason"],
            partial_notes=data.get("partial_notes", ""),
            killed_at=data["killed_at"],
            elapsed_seconds=data.get("elapsed_seconds", 0),
        )


@dataclass
class Task:
    id: str
    title: str
    description: str
    complexity: Complexity = Complexity.UNKNOWN
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.BACKLOG
    task_type: TaskType = TaskType.IMPLEMENTATION
    acceptance_criteria: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    blocked_reason: str = ""
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    actual_complexity: Optional[Complexity] = None
    cycle_time_seconds: Optional[int] = None  # For Kanban metrics
    assigned_to: str = ""  # Persona name who owns this task (e.g., "Senior Dev", "Explorer")
    reaper_kill_count: int = 0  # How many times Reaper has killed this task
    resurrection_history: list[ResurrectionRecord] = field(default_factory=list)  # Previous failed attempts

    def start(self):
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now().isoformat()

    def block(self, reason: str):
        self.status = TaskStatus.BLOCKED
        self.blocked_reason = reason

    def complete(self, artifacts: list[str] = None, actual_complexity: Complexity = None):
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        if artifacts:
            self.artifacts = artifacts
        if actual_complexity:
            self.actual_complexity = actual_complexity
        # Calculate cycle time
        if self.started_at:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            self.cycle_time_seconds = int((end - start).total_seconds())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "complexity": self.complexity.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "task_type": self.task_type.value,
            "acceptance_criteria": self.acceptance_criteria,
            "artifacts": self.artifacts,
            "dependencies": self.dependencies,
            "blocked_reason": self.blocked_reason,
            "notes": self.notes,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "actual_complexity": self.actual_complexity.value if self.actual_complexity else None,
            "cycle_time_seconds": self.cycle_time_seconds,
            "reaper_kill_count": self.reaper_kill_count,
            "resurrection_history": [r.to_dict() for r in self.resurrection_history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            complexity=Complexity(data.get("complexity", "unknown")),
            priority=Priority(data.get("priority", "medium")),
            status=TaskStatus(data.get("status", "backlog")),
            task_type=TaskType(data.get("task_type", "implementation")),
            acceptance_criteria=data.get("acceptance_criteria", []),
            artifacts=data.get("artifacts", []),
            dependencies=data.get("dependencies", []),
            blocked_reason=data.get("blocked_reason", ""),
            notes=data.get("notes", ""),
            assigned_to=data.get("assigned_to", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            actual_complexity=Complexity(data["actual_complexity"]) if data.get("actual_complexity") else None,
            cycle_time_seconds=data.get("cycle_time_seconds"),
            reaper_kill_count=data.get("reaper_kill_count", 0),
            resurrection_history=[ResurrectionRecord.from_dict(r) for r in data.get("resurrection_history", [])],
        )


@dataclass
class SprintConfig:
    """Configuration specific to Sprint mode."""
    scope_locked: bool = False              # Once true, no new tasks without flag
    scope_changes: list[str] = field(default_factory=list)  # Track any scope creep
    velocity_baseline: Optional[int] = None  # Expected tasks per sprint

    def to_dict(self) -> dict:
        return {
            "scope_locked": self.scope_locked,
            "scope_changes": self.scope_changes,
            "velocity_baseline": self.velocity_baseline,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SprintConfig":
        return cls(
            scope_locked=data.get("scope_locked", False),
            scope_changes=data.get("scope_changes", []),
            velocity_baseline=data.get("velocity_baseline"),
        )


@dataclass
class KanbanConfig:
    """Configuration specific to Kanban mode."""
    wip_limit: int = 2                      # Max tasks in progress at once

    def to_dict(self) -> dict:
        return {
            "wip_limit": self.wip_limit,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KanbanConfig":
        return cls(
            wip_limit=data.get("wip_limit", 2),
        )


@dataclass
class Board:
    """
    The main container - works for both Sprint and Kanban modes.

    Sprint mode: Board = one sprint with committed scope
    Kanban mode: Board = continuous backlog with WIP limits
    """
    id: str
    goal: str
    context: str
    mode: Mode = Mode.SPRINT
    tasks: list[Task] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Planning artifacts
    risks: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    definition_of_done: list[str] = field(default_factory=list)
    planning_discussion: str = ""  # Full transcript of multi-agent planning discussion
    decisions: list[Decision] = field(default_factory=list)  # Track consensus vs leader decisions
    planning_mode: str = "collaborative"  # "collaborative" or "independent"

    # Mode-specific config
    sprint_config: SprintConfig = field(default_factory=SprintConfig)
    kanban_config: KanbanConfig = field(default_factory=KanbanConfig)

    # Retrospective (Sprint) / Metrics (Kanban)
    retro_notes: str = ""

    # Persona accountability across iterations
    persona_accountability: dict[str, PersonaAccountability] = field(default_factory=dict)

    # MCP servers to inject into spawned agents
    mcps: list[str] = field(default_factory=list)

    # Task timeout in seconds (None = use default behavior)
    task_timeout: Optional[int] = None
    # Whether to use complexity-based default timeouts (default: False = no timeouts)
    use_default_timeouts: bool = False

    # Cost tracking
    cost_data: dict = field(default_factory=dict)  # Stores CostTracker.to_dict() output

    # Git integration
    git_auto_commit: bool = False  # Auto-commit after each wave if True

    @property
    def status(self) -> str:
        if not self.tasks:
            return "empty"

        # Sprint mode: done when all committed tasks complete
        if self.mode == Mode.SPRINT:
            planned_tasks = [t for t in self.tasks if t.status != TaskStatus.BACKLOG]
            if not planned_tasks:
                return "planning"
            if all(t.status == TaskStatus.COMPLETED for t in planned_tasks):
                return "completed"
            if any(t.status == TaskStatus.IN_PROGRESS for t in planned_tasks):
                return "in_progress"
            if any(t.status == TaskStatus.BLOCKED for t in planned_tasks):
                return "blocked"
            return "ready"

        # Kanban mode: always "active" unless explicitly closed
        else:
            if self.completed_at:
                return "closed"
            in_progress = [t for t in self.tasks if t.status == TaskStatus.IN_PROGRESS]
            if in_progress:
                return "flowing"
            return "idle"

    @property
    def progress(self) -> dict:
        if self.mode == Mode.SPRINT:
            # Sprint: progress against committed scope
            committed = [t for t in self.tasks if t.status not in [TaskStatus.BACKLOG, TaskStatus.SKIPPED]]
            total = len(committed)
            if total == 0:
                return {"total": 0, "completed": 0, "percent": 0}
            completed = sum(1 for t in committed if t.status == TaskStatus.COMPLETED)
            return {
                "total": total,
                "completed": completed,
                "percent": round(completed / total * 100),
            }
        else:
            # Kanban: throughput metrics
            completed = [t for t in self.tasks if t.status == TaskStatus.COMPLETED]
            in_progress = [t for t in self.tasks if t.status == TaskStatus.IN_PROGRESS]
            backlog = [t for t in self.tasks if t.status in [TaskStatus.BACKLOG, TaskStatus.READY]]
            return {
                "completed": len(completed),
                "in_progress": len(in_progress),
                "backlog": len(backlog),
                "wip_limit": self.kanban_config.wip_limit,
                "wip_available": max(0, self.kanban_config.wip_limit - len(in_progress)),
            }

    @property
    def metrics(self) -> dict:
        """Calculate metrics for retrospective/analysis."""
        completed_tasks = [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

        # Estimate accuracy (Sprint mode focus)
        estimated_vs_actual = []
        for t in completed_tasks:
            if t.actual_complexity and t.complexity != Complexity.UNKNOWN:
                estimated_vs_actual.append({
                    "task": t.id,
                    "estimated": t.complexity.value,
                    "actual": t.actual_complexity.value,
                    "accurate": t.complexity == t.actual_complexity,
                })

        # Cycle times (Kanban mode focus)
        cycle_times = [t.cycle_time_seconds for t in completed_tasks if t.cycle_time_seconds]
        avg_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else None

        return {
            "tasks_completed": len(completed_tasks),
            "tasks_skipped": sum(1 for t in self.tasks if t.status == TaskStatus.SKIPPED),
            "estimate_accuracy": estimated_vs_actual,
            "accuracy_rate": (
                sum(1 for e in estimated_vs_actual if e["accurate"]) / len(estimated_vs_actual)
                if estimated_vs_actual else None
            ),
            "avg_cycle_time_seconds": avg_cycle_time,
            "scope_changes": len(self.sprint_config.scope_changes) if self.mode == Mode.SPRINT else None,
        }

    def get_task(self, task_id: str) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def next_task(self) -> Optional[Task]:
        """Get the next task that's ready to work on."""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}

        # Check WIP limit in Kanban mode
        if self.mode == Mode.KANBAN:
            in_progress = sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS)
            if in_progress >= self.kanban_config.wip_limit:
                return None  # At WIP limit

        # Find next ready task by priority
        ready_tasks = []
        for task in self.tasks:
            if task.status in [TaskStatus.PLANNED, TaskStatus.READY, TaskStatus.BACKLOG]:
                if all(dep in completed_ids for dep in task.dependencies):
                    ready_tasks.append(task)

        if not ready_tasks:
            return None

        # Sort by priority
        priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
        ready_tasks.sort(key=lambda t: priority_order.get(t.priority, 2))
        return ready_tasks[0]

    def add_task(self, task: Task, force: bool = False) -> tuple[bool, str]:
        """
        Add a task to the board.
        In Sprint mode with locked scope, tracks as scope change unless forced.
        """
        if self.mode == Mode.SPRINT and self.sprint_config.scope_locked and not force:
            self.sprint_config.scope_changes.append(f"Added: {task.id} - {task.title}")
            task.notes += " [SCOPE CHANGE]"

        self.tasks.append(task)
        return True, f"Task {task.id} added"

    def lock_scope(self):
        """Sprint mode: lock the scope, start the sprint."""
        if self.mode != Mode.SPRINT:
            return False, "Can only lock scope in Sprint mode"
        self.sprint_config.scope_locked = True
        self.started_at = datetime.now().isoformat()
        # Move all backlog items to planned
        for task in self.tasks:
            if task.status == TaskStatus.BACKLOG:
                task.status = TaskStatus.PLANNED
        return True, "Scope locked, sprint started"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "context": self.context,
            "mode": self.mode.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "risks": self.risks,
            "assumptions": self.assumptions,
            "out_of_scope": self.out_of_scope,
            "definition_of_done": self.definition_of_done,
            "planning_discussion": self.planning_discussion,
            "decisions": [d.to_dict() for d in self.decisions],
            "planning_mode": self.planning_mode,
            "sprint_config": self.sprint_config.to_dict(),
            "kanban_config": self.kanban_config.to_dict(),
            "retro_notes": self.retro_notes,
            "persona_accountability": {k: v.to_dict() for k, v in self.persona_accountability.items()},
            "mcps": self.mcps,
            "task_timeout": self.task_timeout,
            "use_default_timeouts": self.use_default_timeouts,
            "cost_data": self.cost_data,
            "git_auto_commit": self.git_auto_commit,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Board":
        board = cls(
            id=data["id"],
            goal=data["goal"],
            context=data.get("context", ""),
            mode=Mode(data.get("mode", "sprint")),
            created_at=data.get("created_at", datetime.now().isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            risks=data.get("risks", []),
            assumptions=data.get("assumptions", []),
            out_of_scope=data.get("out_of_scope", []),
            definition_of_done=data.get("definition_of_done", []),
            planning_discussion=data.get("planning_discussion", ""),
            planning_mode=data.get("planning_mode", "collaborative"),
            retro_notes=data.get("retro_notes", ""),
            mcps=data.get("mcps", []),
            task_timeout=data.get("task_timeout"),
            use_default_timeouts=data.get("use_default_timeouts", False),
        )
        if "sprint_config" in data:
            board.sprint_config = SprintConfig.from_dict(data["sprint_config"])
        if "kanban_config" in data:
            board.kanban_config = KanbanConfig.from_dict(data["kanban_config"])
        board.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        board.decisions = [Decision.from_dict(d) for d in data.get("decisions", [])]
        board.persona_accountability = {
            k: PersonaAccountability.from_dict(v)
            for k, v in data.get("persona_accountability", {}).items()
        }
        board.cost_data = data.get("cost_data", {})
        board.git_auto_commit = data.get("git_auto_commit", False)
        return board

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False, allow_unicode=True)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_yaml(cls, content: str) -> "Board":
        data = yaml.safe_load(content)
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, content: str) -> "Board":
        data = json.loads(content)
        return cls.from_dict(data)

    def save(self, path: str):
        with open(path, "w") as f:
            if path.endswith(".json"):
                f.write(self.to_json())
            else:
                f.write(self.to_yaml())

    @classmethod
    def load(cls, path: str) -> "Board":
        with open(path, "r") as f:
            content = f.read()
        if path.endswith(".json"):
            return cls.from_json(content)
        return cls.from_yaml(content)
