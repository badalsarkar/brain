"""Focus view and productivity insights."""

from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from brain.ai.factory import get_ai_provider
from brain.models import Task
from brain.tasks import (
    get_tasks_by_timeframe,
    get_unscheduled_important_tasks,
    get_blocked_tasks,
    list_tasks,
)


def compute_focus_score(task: Task) -> int:
    """Compute a numeric focus score for ranking tasks.

    Higher score = more important to focus on.
    """
    score = 0

    # Priority weight
    priority_scores = {"urgent": 40, "high": 30, "medium": 20, "low": 10}
    score += priority_scores.get(task.priority.value, 10)

    # Due date urgency
    days = task.days_until_due()
    if days is None:
        score += 5  # no due date — mild bump so it's not zero
    elif days < 0:
        score += 30  # overdue
    elif days == 0:
        score += 20  # today
    elif days == 1:
        score += 15  # tomorrow
    elif days <= 7:
        score += 10  # this week

    # Staleness — how long has the task been sitting around
    age_days = (datetime.now() - task.created_at).days
    score += min(age_days, 15)

    # In-progress momentum bonus
    if task.status.value == "in-progress":
        score += 5

    return score


def show_focus_view(
    use_ai: bool = True,
    project: Optional[str] = None,
    tags: Optional[list[str]] = None,
    top_n: Optional[int] = None,
    timeframe: str = "week",
    show_blocked: bool = False,
) -> None:
    """Display focus view dashboard."""
    console = Console()

    # Header
    console.print("\n[bold cyan]🎯 Focus View[/bold cyan]")
    filters = []
    if project:
        filters.append(f"project: {project}")
    if tags:
        filters.append(f"tags: {', '.join(tags)}")
    if filters:
        console.print(f"[dim]Filtered by {' | '.join(filters)}[/dim]")
    console.print()

    filter_kwargs = {"project": project, "tags": tags}

    # Gather sections
    overdue = get_tasks_by_timeframe("overdue", **filter_kwargs)
    today = get_tasks_by_timeframe("today", **filter_kwargs)

    # Period tasks (deduplicated against overdue + today)
    timeframe_labels = {"today": None, "week": "This Week", "month": "This Month", "all": "All"}
    period_label = timeframe_labels.get(timeframe)
    this_period = []
    if period_label:
        raw = get_tasks_by_timeframe(timeframe, **filter_kwargs)
        seen_ids = {t.id for t in overdue + today}
        this_period = [t for t in raw if t.id not in seen_ids]

    # Unscheduled high-priority tasks
    unscheduled = get_unscheduled_important_tasks(**filter_kwargs)

    # Blocked tasks
    blocked = get_blocked_tasks(**filter_kwargs) if show_blocked else []

    # Sort each section by focus score
    for section in [overdue, today, this_period, unscheduled, blocked]:
        section.sort(key=compute_focus_score, reverse=True)

    # Display sections
    sections = [
        (overdue, "[bold red]⚠️  Overdue Tasks[/bold red]"),
        (today, "[bold yellow]📅 Today[/bold yellow]"),
    ]
    if period_label:
        sections.append((this_period, f"[bold green]📆 {period_label}[/bold green]"))
    sections.append((unscheduled, "[bold orange1]🔥 Unscheduled High Priority[/bold orange1]"))
    if show_blocked:
        sections.append((blocked, "[dim bold]🚫 Blocked[/dim bold]"))

    any_shown = False
    for task_list, header in sections:
        if not task_list:
            continue
        any_shown = True
        console.print(header)
        display_list = task_list
        if top_n and len(task_list) > top_n:
            display_list = task_list[:top_n]
            _display_task_table(console, display_list)
            console.print(f"[dim](showing top {top_n} of {len(task_list)})[/dim]")
        else:
            _display_task_table(console, display_list)
        console.print()

    if not any_shown:
        console.print("[dim]No upcoming tasks. You're all caught up! 🎉[/dim]\n")

    # AI suggestions
    if use_ai:
        ai = get_ai_provider()
        if ai.is_available():
            all_tasks = overdue + today + this_period + unscheduled
            if all_tasks:
                console.print("[bold magenta]🤖 AI Suggestions[/bold magenta]")
                suggestion = ai.suggest_focus(all_tasks)
                panel = Panel(suggestion, border_style="magenta")
                console.print(panel)
                console.print()


def _display_task_table(console: Console, tasks: list[Task], dim: bool = False) -> None:
    """Display tasks in a formatted table.

    Args:
        console: Rich console
        tasks: List of tasks to display (assumed pre-sorted)
        dim: Whether to dim the entire table (for blocked tasks)
    """
    table = Table(show_header=True, header_style="bold", style="dim" if dim else None)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Priority", width=8)
    table.add_column("Title", style="bold")
    table.add_column("Project", overflow="fold")
    table.add_column("Due", width=12)
    table.add_column("Tags", overflow="fold")

    for task in tasks:
        # Priority with color
        priority_colors = {
            "low": "green",
            "medium": "yellow",
            "high": "orange1",
            "urgent": "red",
        }
        priority_color = priority_colors.get(task.priority.value, "white")
        priority_text = f"[{priority_color}]{task.priority.value.upper()}[/{priority_color}]"

        # Due date with color
        if task.due_date:
            days_until = task.days_until_due()
            if days_until is not None:
                if days_until < 0:
                    due_text = f"[red]{task.due_date.strftime('%m/%d')}[/red]"
                elif days_until == 0:
                    due_text = "[yellow]Today[/yellow]"
                elif days_until == 1:
                    due_text = "[yellow]Tomorrow[/yellow]"
                else:
                    due_text = task.due_date.strftime("%m/%d")
            else:
                due_text = task.due_date.strftime("%m/%d")
        else:
            due_text = "[dim]-[/dim]"

        # Tags
        tags_text = ", ".join(task.tags) if task.tags else "[dim]-[/dim]"
        project_text = task.project if task.project else "[dim]-[/dim]"

        table.add_row(
            task.id,
            priority_text,
            task.title,
            project_text,
            due_text,
            tags_text,
        )

    console.print(table)


def get_productivity_stats() -> dict:
    """Get productivity statistics.

    Returns:
        Dictionary with stats
    """
    all_tasks = list_tasks()
    completed_tasks = list_tasks(status="done")
    overdue_tasks = get_tasks_by_timeframe("overdue")

    # Count tasks by priority
    priority_counts = {"low": 0, "medium": 0, "high": 0, "urgent": 0}
    for task in all_tasks:
        if task.status != "done":
            priority_counts[task.priority.value] += 1

    # Calculate completion rate
    total = len(all_tasks)
    completed = len(completed_tasks)
    completion_rate = (completed / total * 100) if total > 0 else 0

    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "active_tasks": total - completed,
        "overdue_tasks": len(overdue_tasks),
        "completion_rate": completion_rate,
        "priority_counts": priority_counts,
    }


def show_stats() -> None:
    """Display productivity statistics."""
    console = Console()
    stats = get_productivity_stats()

    console.print("\n[bold cyan]📊 Productivity Stats[/bold cyan]\n")

    # Overview
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Total Tasks", str(stats["total_tasks"]))
    table.add_row("Completed", f"[green]{stats['completed_tasks']}[/green]")
    table.add_row("Active", f"[yellow]{stats['active_tasks']}[/yellow]")
    table.add_row("Overdue", f"[red]{stats['overdue_tasks']}[/red]")
    table.add_row("Completion Rate", f"{stats['completion_rate']:.1f}%")

    console.print(table)
    console.print()

    # Priority breakdown
    if stats["active_tasks"] > 0:
        console.print("[bold]Active Tasks by Priority:[/bold]")
        priority_table = Table(show_header=False, box=None)
        priority_table.add_column("Priority", style="bold")
        priority_table.add_column("Count")

        for priority, count in stats["priority_counts"].items():
            if count > 0:
                priority_table.add_row(priority.capitalize(), str(count))

        console.print(priority_table)
        console.print()
