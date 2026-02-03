"""
Stunning UI components for waverunner.

Synthwave aesthetics meets Japanese wave art.
"""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.align import Align
from rich.box import DOUBLE, ROUNDED, HEAVY
from rich.style import Style

# Synthwave color palette
DEEP_PURPLE = "#1a0a2e"
PURPLE = "#7b2cbf"
MAGENTA = "#e040fb"
HOT_PINK = "#ff006e"
NEON_PINK = "#ff66b2"
CYAN = "#00ffff"
ELECTRIC_BLUE = "#00d4ff"
SUNSET_ORANGE = "#ff8c00"
GOLD = "#ffd700"
WHITE = "#ffffff"
DIM = "#6b5b7d"
SUCCESS = "#00ff9f"
ERROR = "#ff4757"
WARN = "#ffd93d"

console = Console()

# Japanese wave inspired ASCII art (Hokusai style)
LOGO = r"""
                                          。
                                        。 ・
                                   ゜ ・ 。゜
                              . 。゜ ・ 。゜ .
                          ∴∵∴ 。 ゜ 。゜ ∵∴∵
                     ～～～～ ∴∵∴ ゜ ∵∴∵ ～～～～
                 ～～～≈≈≈～～～∴∵∴∵∴～～～≈≈≈～～～
              ～≈≈≈∽∽∽≈≈≈～～～～～～～≈≈≈∽∽∽≈≈≈～
           ∽∽∽∿∿∿∽∽∽≈≈≈≈≈≈≈≈≈≈≈≈∽∽∽∿∿∿∽∽∽
         ∿∿∿∿∿∿∿∿∽∽∽∽∽∽∽∽∽∽∽∽∽∿∿∿∿∿∿∿∿
       ≋≋≋≋≋≋≋≋≋∿∿∿∿∿∿∿∿∿∿∿∿∿∿≋≋≋≋≋≋≋≋≋
     ════════════════════════════════════════════

     ██╗    ██╗ █████╗ ██╗   ██╗███████╗
     ██║    ██║██╔══██╗██║   ██║██╔════╝
     ██║ █╗ ██║███████║██║   ██║█████╗
     ██║███╗██║██╔══██║╚██╗ ██╔╝██╔══╝
     ╚███╔███╔╝██║  ██║ ╚████╔╝ ███████╗
      ╚══╝╚══╝ ╚═╝  ╚═╝  ╚═══╝  ╚══════╝
     ██████╗ ██╗   ██╗███╗   ██╗███╗   ██╗███████╗██████╗
     ██╔══██╗██║   ██║████╗  ██║████╗  ██║██╔════╝██╔══██╗
     ██████╔╝██║   ██║██╔██╗ ██║██╔██╗ ██║█████╗  ██████╔╝
     ██╔══██╗██║   ██║██║╚██╗██║██║╚██╗██║██╔══╝  ██╔══██╗
     ██║  ██║╚██████╔╝██║ ╚████║██║ ╚████║███████╗██║  ██║
     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝
"""

LOGO_COMPACT = """
  ╦ ╦╔═╗╦  ╦╔═╗╦═╗╦ ╦╔╗╔╔╗╔╔═╗╦═╗
  ║║║╠═╣╚╗╔╝║╣ ╠╦╝║ ║║║║║║║║╣ ╠╦╝
  ╚╩╝╩ ╩ ╚╝ ╚═╝╩╚═╚═╝╝╚╝╝╚╝╚═╝╩╚═
"""

WAVE_DIVIDER = "～≈∽∿≋≋∿∽≈～" * 5

# Team member colors for the planning debate
TEAM_COLORS = {
    "Tech Lead": HOT_PINK,
    "Senior Dev": CYAN,
    "Explorer": ELECTRIC_BLUE,
    "Skeptic": SUNSET_ORANGE,
    "Flow Master": MAGENTA,
    "Kaizen Voice": SUCCESS,
    "Quality Gate": WARN,
    "Value Stream": CYAN,
}


def print_logo():
    """Print the epic synthwave Japanese wave logo."""
    lines = LOGO.strip().split('\n')

    # Synthwave gradient for the wave: purple → magenta → pink → cyan
    wave_colors = [DEEP_PURPLE, PURPLE, MAGENTA, HOT_PINK, NEON_PINK, CYAN, ELECTRIC_BLUE, WHITE]

    for i, line in enumerate(lines):
        if i < 11:  # Wave art part
            color_idx = min(i, len(wave_colors) - 1)
            centered = Align.center(Text(line, style=wave_colors[color_idx]))
            console.print(centered)
        elif i == 11:  # Divider line
            centered = Align.center(Text(line, style=GOLD))
            console.print(centered)
        else:  # WAVERUNNER text
            if '██' in line and 'WAVE' not in line and i < 18:
                # WAVE part - hot pink to magenta gradient
                centered = Align.center(Text(line, style=f"bold {HOT_PINK}"))
            else:
                # RUNNER part - cyan to electric blue
                centered = Align.center(Text(line, style=f"bold {CYAN}"))
            console.print(centered)

    # Tagline
    console.print()
    tagline = Text()
    tagline.append("░▒▓", style=PURPLE)
    tagline.append(" parallel wave execution ", style=f"italic {NEON_PINK}")
    tagline.append("▓▒░", style=PURPLE)
    console.print(Align.center(tagline))
    console.print()


def print_logo_compact():
    """Print smaller logo for status screens."""
    for line in LOGO_COMPACT.strip().split('\n'):
        console.print(Align.center(Text(line, style=f"bold {CYAN}")))
    console.print()


def print_header(text: str, style: str = MAGENTA):
    """Print a styled header with synthwave accent."""
    console.print()
    header = Text()
    header.append("▓▒░ ", style=PURPLE)
    header.append(text, style=f"bold {style}")
    header.append(" ░▒▓", style=PURPLE)
    console.print(header)


def print_team_debate(discussion: str, mode: str = "sprint"):
    """
    Print the team planning debate with clean, colorful formatting.
    Each persona gets their own color.
    """
    import re

    # Persona color mapping (includes all possible personas)
    persona_colors = {
        # Sprint personas
        "Tech Lead": CYAN,
        "Senior Dev": "green",
        "Explorer": "yellow",
        "Skeptic": "red",
        "Maverick": MAGENTA,
        "The Reaper": "bold white on red",
        # Kanban personas
        "Flow Master": CYAN,
        "Kaizen Voice": "green",
        "Quality Gate": "yellow",
        "Value Stream": "blue",
        # Chameleon can have any name - default to yellow if not found
    }

    # Known persona name patterns (for validation)
    known_persona_prefixes = [
        "Tech Lead", "Senior Dev", "Explorer", "Skeptic", "Maverick", "The Reaper",
        "Flow Master", "Kaizen Voice", "Quality Gate", "Value Stream",
        "The "  # Matches chameleon names like "The Cartographer", "The Detective", etc.
    ]

    console.print()
    console.print(f"[{PURPLE}]╔{'═' * 68}╗[/]")
    if mode == "sprint":
        console.print(f"[{PURPLE}]║[/] [{HOT_PINK}]⚡ SPRINT PLANNING SESSION ⚡[/]                                     [{PURPLE}]║[/]")
    else:
        console.print(f"[{PURPLE}]║[/] [{HOT_PINK}]🏭 KANBAN SESSION — THE TOYOTA WAY 🏭[/]                            [{PURPLE}]║[/]")
    console.print(f"[{PURPLE}]╚{'═' * 68}╝[/]")
    console.print()

    # Split discussion into persona messages
    # Format: "**Name**: message"
    # ONLY split on ACTUAL persona names, not random section headers
    messages = []
    current_message = ""

    def is_persona_line(line):
        """Check if line starts with a known persona name."""
        match = re.match(r'^\*\*([^*]+)\*\*:\s', line)
        if not match:
            return False
        name = match.group(1).strip()
        # Check if it matches any known persona
        return any(name.startswith(prefix) or name == prefix.strip() for prefix in known_persona_prefixes)

    for line in discussion.strip().split('\n'):
        # Check if this line starts a new persona message
        if is_persona_line(line):
            if current_message:
                messages.append(current_message)
            current_message = line
        else:
            if current_message:
                current_message += '\n' + line
            else:
                # First line, start accumulating
                current_message = line

    # Don't forget the last message
    if current_message:
        messages.append(current_message)

    for msg_block in messages:
        if not msg_block.strip():
            continue

        # Extract persona name and message
        match = re.match(r'^\*\*([^*]+)\*\*:\s*(.*)', msg_block, re.DOTALL)
        if not match:
            # Not a persona message - skip it silently (it's formatting within a message)
            continue

        persona_name = match.group(1).strip()
        message = match.group(2).strip()

        # Get color for this persona (default to white for chameleons)
        color = persona_colors.get(persona_name, WHITE)

        # Print persona name with colored bullet
        speaker_line = Text()
        speaker_line.append("  ● ", style=f"bold {color}")
        speaker_line.append(persona_name, style=f"bold {color}")
        console.print(speaker_line)

        # Print message content with indent, PRESERVING structure
        # Don't use fill() which destroys markdown formatting

        # Add indent to each line but preserve structure
        lines = message.split('\n')
        for line in lines:
            # Preserve blank lines
            if not line.strip():
                console.print()
            else:
                # Add indent but don't word-wrap (preserves markdown)
                console.print(f"[{WHITE}]    {line}[/]")
        console.print()

    console.print(f"[{PURPLE}]{WAVE_DIVIDER}[/]")
    console.print()


def print_goal(goal: str, mode: str):
    """Print the goal in a synthwave panel."""
    content = Text()

    # Mode badge
    mode_color = SUNSET_ORANGE if mode.lower() == "kanban" else MAGENTA
    content.append("┌", style=mode_color)
    content.append(f" {mode.upper()} ", style=f"bold {mode_color}")
    content.append("┐\n\n", style=mode_color)

    content.append(goal, style=f"bold {WHITE}")

    panel = Panel(
        Align.center(content),
        border_style=MAGENTA,
        box=HEAVY,
        padding=(1, 3),
        title=f"[{HOT_PINK}]░▒▓ MISSION ▓▒░[/]",
        title_align="center",
    )
    console.print(panel)


def print_tasks_created(count: int):
    """Announce tasks created with style."""
    console.print()
    console.print(f"[{PURPLE}]∿≋∿[/] [{SUCCESS}]✓[/] [bold {WHITE}]{count} tasks generated[/] [{PURPLE}]∿≋∿[/]")


def print_wave_plan(waves: list):
    """Print the execution wave plan with synthwave flair."""
    total_tasks = sum(len(w) for w in waves)

    # Calculate spacing for proper alignment
    box_width = 54
    title = "EXECUTION PLAN"
    task_info = f"{total_tasks} tasks"
    # Account for: "║ " + title + spaces + task_info + " ║"
    # That's 2 chars for borders/spaces at edges, title length, task_info length
    content_length = len(title) + len(task_info)
    spaces_needed = box_width - content_length - 2  # -2 for the border characters and spaces

    console.print()
    console.print(f"[{MAGENTA}]╔{'═' * box_width}╗[/]")
    console.print(f"[{MAGENTA}]║[/] [{HOT_PINK}]{title}[/]{' ' * spaces_needed}[{DIM}]{task_info}[/] [{MAGENTA}]║[/]")
    console.print(f"[{MAGENTA}]╠{'═' * box_width}╣[/]")

    for i, wave in enumerate(waves):
        parallel = len(wave) > 1
        is_last = i == len(waves) - 1

        # Wave header
        prefix = "╠" if not is_last else "╚"
        parallel_str = f" [{PURPLE}]⫘×{len(wave)}[/]" if parallel else f" [{DIM}]→[/]"
        console.print(f"[{MAGENTA}]{prefix}─▸[/] [{CYAN}]Wave {i+1}[/]{parallel_str}")

        # Task list with titles
        for j, task in enumerate(wave):
            sub_prefix = "║   " if not is_last else "    "
            bullet = "├─" if j < len(wave) - 1 else "└─"
            title = task.title[:38] + "..." if len(task.title) > 38 else task.title
            console.print(f"[{MAGENTA}]{sub_prefix}[/][{DIM}]{bullet}[/] [{WHITE}]{task.id}[/] [{DIM}]{title}[/]")

    console.print()


def print_wave_start(wave_num: int, tasks: list, parallel: bool):
    """Print wave start with synthwave visuals."""
    console.print()
    console.print(f"[{PURPLE}]{WAVE_DIVIDER}[/]")

    parallel_str = f"  [{PURPLE}]⫘ ×{len(tasks)} PARALLEL[/]" if parallel else ""
    console.print(f"[{MAGENTA}]◆[/] [{CYAN}]WAVE {wave_num}[/] [{MAGENTA}]◆[/]{parallel_str}")

    # Show task list with titles and complexity
    for task in tasks:
        title = task.title[:40] + "..." if len(task.title) > 40 else task.title
        complexity = f"[{CYAN}]{task.complexity.value}[/]" if hasattr(task, 'complexity') else ""
        console.print(f"[{DIM}]├─[/] [{WHITE}]{task.id}[/] {complexity} [{DIM}]{title}[/]")

    console.print(f"[{PURPLE}]{WAVE_DIVIDER}[/]")
    console.print()


def print_task_start(task_id: str, title: str, description: str = "", assigned_to: str = ""):
    """Print task starting with indicator and optional description."""
    line = Text()
    line.append("\n▸▸ ", style=MAGENTA)
    line.append(task_id, style=WHITE)
    line.append(f" {title}", style=f"bold {WHITE}")

    # Show assigned persona
    if assigned_to:
        line.append(f" [{assigned_to}]", style=CYAN)

    console.print(line)

    # Show description if provided (truncated)
    if description:
        desc = description[:80] + "..." if len(description) > 80 else description
        console.print(f"   [{DIM}]{desc}[/]")


def print_task_complete(task_id: str, accuracy: str = ""):
    """Print task completion."""
    line = Text()
    line.append("  ✓✓ ", style=SUCCESS)
    line.append(task_id, style=WHITE)
    if accuracy:
        line.append(f" {accuracy}", style=DIM)
    console.print(line)


def print_task_failed(task_id: str, error: str):
    """Print task failure."""
    line = Text()
    line.append("  ✗✗ ", style=ERROR)
    line.append(task_id, style=WHITE)
    line.append(f" {error[:50]}", style=ERROR)
    console.print(line)


def print_sprint_complete(task_count: int, wave_count: int):
    """Print sprint completion with synthwave celebration."""
    console.print()
    console.print(f"[{MAGENTA}]∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿[/]")
    console.print(f"[bold {SUCCESS}]✓ ✓ ✓   SPRINT COMPLETE   ✓ ✓ ✓[/]")
    console.print(f"[{WHITE}]{task_count} tasks  │  {wave_count} waves[/]")
    console.print(f"[{MAGENTA}]∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿[/]")
    console.print()


def print_iteration(current: int, max_iter: Optional[int]):
    """Print iteration header with progress visualization."""
    box_width = 50

    if max_iter is None:
        # Infinite mode - just show current iteration
        iteration_text = f"ITERATION {current}/∞"
        progress_text = "◆" * min(current, 10)  # Cap visual at 10 diamonds

        content_length = len(iteration_text) + len(progress_text)
        spaces_needed = box_width - content_length - 2

        console.print()
        console.print(f"[{MAGENTA}]╔{'═' * box_width}╗[/]")
        console.print(f"[{MAGENTA}]║[/] [{HOT_PINK}]{iteration_text}[/]{' ' * spaces_needed}[{CYAN}]{progress_text}[/] [{MAGENTA}]║[/]")
        console.print(f"[{MAGENTA}]╚{'═' * box_width}╝[/]")
    else:
        # Limited iterations - show progress bar
        filled = "◆" * current
        empty = "◇" * (max_iter - current)

        iteration_text = f"ITERATION {current}/{max_iter}"
        progress_text = f"{filled}{empty}"

        content_length = len(iteration_text) + len(progress_text)
        spaces_needed = box_width - content_length - 2

        console.print()
        console.print(f"[{MAGENTA}]╔{'═' * box_width}╗[/]")
        console.print(f"[{MAGENTA}]║[/] [{HOT_PINK}]{iteration_text}[/]{' ' * spaces_needed}[{CYAN}]{filled}[/][{DIM}]{empty}[/] [{MAGENTA}]║[/]")
        console.print(f"[{MAGENTA}]╚{'═' * box_width}╝[/]")


def print_evaluating():
    """Print evaluation start."""
    line = Text()
    line.append("\n▸ ", style=MAGENTA)
    line.append("Analyzing results...", style=WHITE)
    line.append(" ⟳", style=DIM)
    console.print(line)


def print_eval_success(confidence: str, reasoning: str):
    """Print successful evaluation."""
    conf_color = SUCCESS if confidence == "high" else CYAN if confidence == "medium" else WARN

    line = Text()
    line.append("\n✓ SPRINT SUCCESSFUL ", style=f"bold {SUCCESS}")
    line.append(f"● {confidence}", style=conf_color)
    console.print(line)

    if reasoning:
        reason_line = Text()
        reason_line.append("  └─ ", style=DIM)
        reason_line.append(reasoning, style=WHITE)
        console.print(reason_line)


def print_eval_incomplete(confidence: str, reasoning: str, issues: list):
    """Print incomplete evaluation."""
    line = Text()
    line.append("\n○ SPRINT INCOMPLETE ", style=f"bold {WARN}")
    line.append(f"({confidence} confidence)", style=DIM)
    console.print(line)

    if reasoning:
        console.print(f"  [{WHITE}]{reasoning}[/]")
    if issues:
        for issue in issues:
            console.print(f"    [{WARN}]▸[/] [{WHITE}]{issue}[/]")


def print_goal_achieved():
    """Print epic goal achieved banner."""
    banner = """
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║    ██████╗  ██████╗  █████╗ ██╗                          ║
║   ██╔════╝ ██╔═══██╗██╔══██╗██║                          ║
║   ██║  ███╗██║   ██║███████║██║                          ║
║   ██║   ██║██║   ██║██╔══██║██║                          ║
║   ╚██████╔╝╚██████╔╝██║  ██║███████╗                     ║
║    ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝                     ║
║                                                          ║
║    █████╗  ██████╗██╗  ██╗██╗███████╗██╗   ██╗███████╗██████╗  ║
║   ██╔══██╗██╔════╝██║  ██║██║██╔════╝██║   ██║██╔════╝██╔══██╗ ║
║   ███████║██║     ███████║██║█████╗  ██║   ██║█████╗  ██║  ██║ ║
║   ██╔══██║██║     ██╔══██║██║██╔══╝  ╚██╗ ██╔╝██╔══╝  ██║  ██║ ║
║   ██║  ██║╚██████╗██║  ██║██║███████╗ ╚████╔╝ ███████╗██████╔╝ ║
║   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝╚══════╝  ╚═══╝  ╚══════╝╚═════╝  ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""
    console.print(f"[bold {SUCCESS}]{banner}[/]")


def print_goal_achieved_small():
    """Print compact goal achieved message."""
    console.print()
    console.print(f"[{MAGENTA}]∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿[/]")
    console.print(f"[bold {SUCCESS}]◆ ◆ ◆   GOAL ACHIEVED   ◆ ◆ ◆[/]")
    console.print(f"[{MAGENTA}]∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿≋∿[/]")


def print_max_iterations(max_iter: int):
    """Print max iterations warning."""
    console.print(f"\n[{WARN}]⚠[/] [{WHITE}]Max iterations ({max_iter}) reached[/]")


def print_followup(goal: str):
    """Print follow-up sprint message."""
    line = Text()
    line.append("\n∿≋∿ ", style=PURPLE)
    line.append("Generating follow-up sprint", style=WHITE)
    console.print(line)
    console.print(f"    [{HOT_PINK}]{goal}[/]")


def print_status_board(goal: str, mode: str, status: str, progress: dict, is_sprint: bool):
    """Print a synthwave status board."""
    print_logo_compact()

    status_color = SUCCESS if status == "completed" else CYAN if status in ["flowing", "in_progress"] else WHITE
    mode_color = SUNSET_ORANGE if mode.lower() == "kanban" else MAGENTA

    content = Text()
    content.append(f"{goal}\n\n", style=f"bold {WHITE}")
    content.append("Mode: ", style=DIM)
    content.append(mode.upper(), style=f"bold {mode_color}")
    content.append("  │  ", style=DIM)
    content.append("Status: ", style=DIM)
    content.append(status.upper(), style=f"bold {status_color}")

    panel = Panel(content, border_style=MAGENTA, box=ROUNDED)
    console.print(panel)

    if is_sprint:
        pct = progress['percent']
        completed = progress['completed']
        total = progress['total']

        bar_width = 40
        filled = int(bar_width * pct / 100)

        # Synthwave gradient progress bar
        bar_filled = ""
        for i in range(filled):
            if i < bar_width * 0.25:
                bar_filled += f"[{PURPLE}]█[/]"
            elif i < bar_width * 0.5:
                bar_filled += f"[{MAGENTA}]█[/]"
            elif i < bar_width * 0.75:
                bar_filled += f"[{HOT_PINK}]█[/]"
            else:
                bar_filled += f"[{CYAN}]█[/]"

        bar_empty = f"[{DIM}]{'░' * (bar_width - filled)}[/]"

        console.print(f"\n  {bar_filled}{bar_empty} [{WHITE}]{completed}/{total}[/] [{DIM}]({pct}%)[/]")
    else:
        console.print(f"\n  [{SUCCESS}]●[/] {progress['completed']} done  [{CYAN}]●[/] {progress['in_progress']}/{progress['wip_limit']} WIP  [{DIM}]●[/] {progress['backlog']} backlog")


def print_task_table(tasks: list, goal: str):
    """Print a synthwave task table."""
    table = Table(
        title=f"[bold {HOT_PINK}]{goal}[/]",
        box=ROUNDED,
        border_style=MAGENTA,
        header_style=f"bold {CYAN}",
        row_styles=[WHITE, DIM],
        title_justify="center",
        caption=f"[{DIM}]{len(tasks)} total tasks[/]",
        caption_justify="right",
    )

    table.add_column("ID", style=MAGENTA)
    table.add_column("Title")
    table.add_column("Type", justify="center")
    table.add_column("Assigned", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Complexity", justify="center")
    table.add_column("Deps")

    status_styles = {
        "completed": (SUCCESS, "✓"),
        "in_progress": (CYAN, "▸"),
        "blocked": (ERROR, "✗"),
        "skipped": (DIM, "○"),
        "planned": (MAGENTA, "◇"),
        "backlog": (DIM, "◇"),
    }

    type_icons = {
        "spike": "🔍",  # Magnifying glass for investigation
        "implementation": "⚙️",  # Gear for building
    }

    for task in tasks:
        color, icon = status_styles.get(task.status.value, (WHITE, "◇"))
        deps = ", ".join(task.dependencies) if task.dependencies else "─"
        title = task.title[:36] + "..." if len(task.title) > 36 else task.title
        assigned = task.assigned_to if task.assigned_to else "─"
        task_type = getattr(task, "task_type", None)
        type_display = type_icons.get(task_type.value if task_type else "implementation", "⚙️")

        table.add_row(
            task.id,
            title,
            type_display,
            f"[{CYAN}]{assigned}[/]",
            f"[{color}]{icon} {task.status.value}[/]",
            task.complexity.value,
            deps,
        )

    console.print(table)


def print_retro(content: str, goal: str):
    """Print retrospective in a synthwave panel."""
    panel = Panel(
        content,
        title=f"[bold {HOT_PINK}]░▒▓ Sprint Retrospective ▓▒░[/]",
        subtitle=f"[{DIM}]{goal}[/]",
        border_style=MAGENTA,
        box=DOUBLE,
        padding=(1, 2),
    )
    console.print(panel)


def print_spike_report(task_id: str, title: str, findings: str, artifacts: list[str] = None):
    """Print spike investigation results in a styled panel."""
    # If findings are short (< 500 chars) and no artifacts, show inline
    # Otherwise show summary and point to artifacts

    if artifacts and len(artifacts) > 0:
        # They created report files
        summary = findings[:400] + "..." if len(findings) > 400 else findings
        artifact_list = "\n".join([f"  → {art}" for art in artifacts])
        content = f"""{summary}

[{CYAN}]📄 Full report available:[/]
{artifact_list}"""
        subtitle = f"[{DIM}]Investigation complete • See artifacts for details[/]"
    else:
        # Short report, display inline
        content = findings
        subtitle = f"[{DIM}]Investigation complete[/]"

    panel = Panel(
        content,
        title=f"[bold {ELECTRIC_BLUE}]🔍 SPIKE REPORT[/] [{MAGENTA}]{task_id}[/] [{WHITE}]{title}[/]",
        subtitle=subtitle,
        border_style=CYAN,
        box=HEAVY,
        padding=(1, 2),
    )
    console.print(panel)


def spinner_context(message: str):
    """Return a progress context for showing a spinner."""
    return Progress(
        SpinnerColumn(spinner_name="dots", style=MAGENTA),
        TextColumn(f"[{WHITE}]{message}[/]"),
        transient=True,
    )
