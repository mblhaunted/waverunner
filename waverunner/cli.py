"""CLI interface for waverunner."""

from pathlib import Path
from datetime import datetime
from typing import Optional

import typer
from rich.markdown import Markdown

from .models import Board, Task, Mode, TaskStatus, Complexity, Priority
from .prompts import get_retro_prompt
from .agent import generate_plan, execute_task, run_sprint, run_sprint_loop, set_verbose, calculate_waves
from . import ui


app = typer.Typer(
    name="waverunner",
    help="Lightweight code agent orchestrator with sprint-based planning",
    no_args_is_help=True,
)

DEFAULT_BOARD_FILE = ".waverunner.yaml"


def find_board_file() -> Optional[Path]:
    """Find board file in current directory or parents."""
    current = Path.cwd()
    while current != current.parent:
        board_file = current / DEFAULT_BOARD_FILE
        if board_file.exists():
            return board_file
        current = current.parent
    return None


def load_board() -> Board:
    """Load board from file or error."""
    board_file = find_board_file()
    if not board_file:
        ui.console.print(f"[{ui.ERROR}]No board found. Run 'waverunner go <goal>' first.[/]")
        raise typer.Exit(1)
    return Board.load(str(board_file))


def save_board(board: Board):
    """Save board to file."""
    board_file = find_board_file()
    if not board_file:
        board_file = Path.cwd() / DEFAULT_BOARD_FILE
    board.save(str(board_file))


class BoardExistsError(Exception):
    """Raised when attempting to overwrite existing board without confirmation."""
    pass


def check_existing_board(directory: str = None) -> Optional[Path]:
    """
    Check if board file exists in directory.

    Returns:
        Path to board file if exists, None otherwise
    """
    if directory is None:
        directory = Path.cwd()
    else:
        directory = Path(directory)

    board_file = directory / DEFAULT_BOARD_FILE
    if board_file.exists():
        return board_file
    return None


def require_no_existing_board(directory: str = None, force: bool = False):
    """
    Ensure no board exists, or raise BoardExistsError.

    Args:
        directory: Directory to check (default: current)
        force: If True, skip check (allow overwrite)

    Raises:
        BoardExistsError if board exists and force=False
    """
    if force:
        return  # Allow overwrite

    existing_board = check_existing_board(directory)
    if existing_board:
        try:
            board = Board.load(str(existing_board))
            raise BoardExistsError(
                f"Board already exists: {existing_board}\n"
                f"Goal: {board.goal}\n"
                f"Tasks: {len(board.tasks)} ({sum(1 for t in board.tasks if t.status == TaskStatus.COMPLETED)} completed)\n"
                f"\n"
                f"Options:\n"
                f"  - Use 'waverunner run' to continue existing work\n"
                f"  - Use 'waverunner reset' to delete and start fresh\n"
                f"  - Use --force flag to overwrite (destroys existing work)"
            )
        except Exception as e:
            # Board file exists but can't be loaded
            raise BoardExistsError(
                f"Board file exists but is corrupted: {existing_board}\n"
                f"Error: {e}\n"
                f"Use 'waverunner reset' or --force flag to overwrite"
            )


def load_or_create_board(directory: str = None, continue_existing: bool = False) -> Optional[Board]:
    """
    Load existing board if continue_existing=True, otherwise return None.

    Args:
        directory: Directory to check (default: current)
        continue_existing: If True, load and return existing board

    Returns:
        Board if exists and continue_existing=True, None otherwise
    """
    if not continue_existing:
        return None

    existing_board = check_existing_board(directory)
    if existing_board:
        return Board.load(str(existing_board))

    return None


# ============================================================================
# MAIN COMMANDS
# ============================================================================

@app.command()
def go(
    goal: str = typer.Argument(..., help="What do you want to build?"),
    mode: str = typer.Option("sprint", "--mode", "-m", help="sprint or kanban"),
    context: str = typer.Option("", "--context", "-c", help="Additional context"),
    confirm: bool = typer.Option(False, "--confirm", help="Ask for confirmation before executing"),
    force: bool = typer.Option(False, "--force", help="Force overwrite existing board without warning"),
    max_iter: Optional[int] = typer.Option(None, "--max-iter", "-i", help="Max iterations (default: infinite, retries until success)"),
    max_parallel: int = typer.Option(8, "--max-parallel", "-p", help="Max tasks to run in parallel (default: 8)"),
    mcp: Optional[list[str]] = typer.Option(None, "--mcp", help="MCP config (JSON string or path). Can repeat."),
    timeout: Optional[int] = typer.Option(None, "--timeout", "-t", help="Task timeout in seconds (overrides defaults)"),
    task_timeouts: bool = typer.Option(False, "--task-timeouts", help="Enable complexity-based task timeouts"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed agent output"),
    planning_mode: str = typer.Option("collaborative", "--planning-mode", help="Planning model: collaborative (default) or independent"),
    dashboard: bool = typer.Option(False, "--dashboard", help="Launch real-time web dashboard"),
):
    """
    Plan and execute a sprint. This is the main command.

    Automatically parallelizes tasks based on the dependency graph.

    Examples:
        waverunner go "Add user authentication"
        waverunner go "Fix bugs" --mode kanban
        waverunner go "Build API" --dashboard
    """
    # Set verbose mode
    set_verbose(verbose)

    # Check for existing board (unless --force specified)
    try:
        require_no_existing_board(force=force)
    except BoardExistsError as e:
        ui.console.print(f"[{ui.ERROR}]{e}[/]")
        raise typer.Exit(1)

    # Start dashboard if requested
    if dashboard:
        try:
            from . import dashboard_server
            import webbrowser

            server = dashboard_server.DashboardServer()
            server.start()

            # Give server a moment to start
            import time
            time.sleep(1)

            # Open browser
            webbrowser.open('http://localhost:3000')

            ui.console.print("[dim]Dashboard running at http://localhost:3000[/]")
        except Exception as e:
            ui.console.print(f"[yellow]Warning: Could not start dashboard: {e}[/]")
            ui.console.print("[dim]Continuing without dashboard...[/]")

    board_file = Path.cwd() / DEFAULT_BOARD_FILE

    # Show logo
    ui.print_logo()

    # Detect existing work and append to context
    from .agent import generate_existing_work_context
    existing_work_context = generate_existing_work_context(str(Path.cwd()))
    if existing_work_context:
        # Prepend existing work context to user context
        full_context = f"{existing_work_context}\n\n{context}" if context else existing_work_context
    else:
        full_context = context

    # Init
    board_mode = Mode.KANBAN if mode.lower() == "kanban" else Mode.SPRINT
    board_id = f"{board_mode.value}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    board = Board(
        id=board_id,
        goal=goal,
        context=full_context,
        mode=board_mode,
        planning_mode=planning_mode,
        mcps=mcp or [],
        task_timeout=timeout,
        use_default_timeouts=task_timeouts,
    )

    # Show goal
    ui.print_goal(goal, board_mode.value)

    # Show MCPs if configured
    if mcp:
        ui.console.print(f"\n[{ui.CYAN}]MCPs:[/] [{ui.DIM}]{', '.join(mcp)}[/]")

    # Plan
    ui.print_header("Planning")
    board = generate_plan(board, iteration=1, max_iterations=max_iter, auto=False, planning_mode=planning_mode)
    board.save(str(board_file))

    ui.print_tasks_created(len(board.tasks))

    # Calculate and show execution waves
    waves = calculate_waves(board.tasks)
    ui.print_wave_plan(waves)

    if confirm:
        if not typer.confirm("Execute?"):
            ui.console.print(f"[{ui.DIM}]Plan saved. Run waverunner run when ready.[/]")
            raise typer.Exit(0)

    # Execute
    run_sprint_loop(board, max_iterations=max_iter, max_parallel=max_parallel)

    # Done
    ui.console.print(f"\n[{ui.DIM}]Run [bold]waverunner retro[/bold] to see what happened.[/]")


@app.command()
def run(
    max_parallel: int = typer.Option(8, "--max-parallel", "-p", help="Max tasks to run in parallel (default: 8)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed agent output"),
):
    """
    Continue executing the current plan.

    Picks up where you left off. Parallelizes automatically based on dependencies.
    """
    set_verbose(verbose)
    ui.print_logo()
    board = load_board()
    ui.print_goal(board.goal, board.mode.value)
    run_sprint(board, max_parallel=max_parallel)


@app.command()
def do(
    task_id: str = typer.Argument(None, help="Task ID to execute (or next if not specified)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed agent output"),
):
    """
    Execute a single task with Claude.
    """
    set_verbose(verbose)
    board = load_board()

    if task_id:
        task = board.get_task(task_id)
        if not task:
            ui.console.print(f"[{ui.ERROR}]Task not found: {task_id}[/]")
            raise typer.Exit(1)
    else:
        task = board.next_task()
        if not task:
            ui.console.print(f"[{ui.SUCCESS}]No tasks remaining.[/]")
            raise typer.Exit(0)

    ui.print_task_start(task.id, task.title)

    task.start()
    save_board(board)

    artifacts, actual, notes = execute_task(board, task)

    task.complete(artifacts=artifacts, actual_complexity=actual)
    if notes:
        task.notes = notes
    save_board(board)

    ui.print_task_complete(task.id)
    if artifacts:
        ui.console.print(f"  [{ui.DIM}]Artifacts: {', '.join(artifacts)}[/]")


# ============================================================================
# STATUS COMMANDS
# ============================================================================

@app.command()
def status():
    """Show current progress."""
    board = load_board()
    ui.print_status_board(
        board.goal,
        board.mode.value,
        board.status,
        board.progress,
        board.mode == Mode.SPRINT
    )

    # Tasks by status
    in_progress = [t for t in board.tasks if t.status == TaskStatus.IN_PROGRESS]
    blocked = [t for t in board.tasks if t.status == TaskStatus.BLOCKED]
    ready = [t for t in board.tasks if t.status in [TaskStatus.PLANNED, TaskStatus.READY, TaskStatus.BACKLOG]]
    completed = [t for t in board.tasks if t.status == TaskStatus.COMPLETED]

    if in_progress:
        ui.console.print(f"\n[{ui.CYAN}]In Progress:[/]")
        for t in in_progress:
            ui.console.print(f"  [{ui.CYAN}]▸[/] [{ui.WHITE}]{t.id}[/] [{ui.DIM}]{t.title}[/]")

    if blocked:
        ui.console.print(f"\n[{ui.ERROR}]Blocked:[/]")
        for t in blocked:
            ui.console.print(f"  [{ui.ERROR}]✗[/] [{ui.WHITE}]{t.id}[/] [{ui.DIM}]{t.blocked_reason}[/]")

    next_task = board.next_task()
    if next_task and next_task not in in_progress:
        ui.console.print(f"\n[{ui.SUCCESS}]Next up:[/] [{ui.WHITE}]{next_task.id}[/] [{ui.DIM}]{next_task.title}[/]")

    ui.console.print(f"\n[{ui.DIM}]{len(completed)} completed, {len(ready)} remaining[/]")


@app.command()
def retro():
    """Show what happened: tasks completed, files created, estimate accuracy."""
    board = load_board()
    content = get_retro_prompt(board)
    ui.print_retro(content, board.goal)


@app.command()
def tasks():
    """List all tasks."""
    board = load_board()
    ui.print_task_table(board.tasks, board.goal)


@app.command()
def help():
    """Show comprehensive help documentation from CLAUDE.md."""
    claude_md_path = Path(__file__).parent / "CLAUDE.md"

    try:
        content = claude_md_path.read_text()
        ui.console.print(Markdown(content))
    except FileNotFoundError:
        ui.console.print(f"[{ui.ERROR}]Help file not found: {claude_md_path}[/]")
        ui.console.print(f"[{ui.DIM}]Expected location: {claude_md_path.absolute()}[/]")
        raise typer.Exit(1)


# ============================================================================
# MANUAL TASK MANAGEMENT (if you need fine control)
# ============================================================================

@app.command()
def add(
    task_id: str = typer.Argument(..., help="Unique task ID"),
    title: str = typer.Argument(..., help="Task title"),
    description: str = typer.Option("", "--desc", "-d", help="Task description"),
    complexity: str = typer.Option("unknown", "--complexity", "-x", help="trivial/small/medium/large"),
    priority: str = typer.Option("medium", "--priority", "-p", help="critical/high/medium/low"),
    depends_on: Optional[list[str]] = typer.Option(None, "--depends", help="Task IDs this depends on"),
):
    """Add a task manually."""
    board = load_board()

    task = Task(
        id=task_id,
        title=title,
        description=description,
        complexity=Complexity(complexity),
        priority=Priority(priority),
        dependencies=depends_on or [],
    )

    board.add_task(task)
    save_board(board)
    ui.console.print(f"[{ui.SUCCESS}]✓ Added:[/] [{ui.WHITE}]{task_id}[/]")


@app.command()
def skip(
    task_id: str = typer.Argument(..., help="Task ID to skip"),
):
    """Skip a task."""
    board = load_board()
    task = board.get_task(task_id)

    if not task:
        ui.console.print(f"[{ui.ERROR}]Task not found: {task_id}[/]")
        raise typer.Exit(1)

    task.status = TaskStatus.SKIPPED
    save_board(board)
    ui.console.print(f"[{ui.DIM}]Skipped: {task_id}[/]")


@app.command()
def reset():
    """Delete the board and start fresh."""
    board_file = find_board_file()
    if board_file:
        board_file.unlink()
        ui.console.print(f"[{ui.SUCCESS}]✓ Board deleted.[/]")
    else:
        ui.console.print(f"[{ui.WARN}]No board found.[/]")


if __name__ == "__main__":
    app()
