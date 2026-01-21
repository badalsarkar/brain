"""Focus view and productivity insights."""

from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from brain.ai.factory import get_ai_provider
from brain.models import Task
from brain.tasks import get_tasks_by_timeframe, list_tasks


def show_focus_view(use_ai: bool = True) -> None:
    """Display focus view dashboard.

    Args:
        use_ai: Whether to include AI suggestions
    """
    console = Console()

    # Get tasks by timeframe
    overdue = get_tasks_by_timeframe("overdue")
    today = get_tasks_by_timeframe("today")
    this_week = get_tasks_by_timeframe("week")

    # Display header
    console.print("\n[bold cyan]🎯 Focus View[/bold cyan]\n")

    # Overdue tasks (high priority)
    if overdue:
        console.print("[bold red]⚠️  Overdue Tasks[/bold red]")
        _display_task_table(console, overdue)
        console.print()

    # Today's tasks
    if today:
        console.print("[bold yellow]📅 Today[/bold yellow]")
        _display_task_table(console, today)
        console.print()

    # This week's tasks
    if this_week:
        console.print("[bold green]📆 This Week[/bold green]")
        _display_task_table(console, this_week)
        console.print()

    # No tasks
    if not overdue and not today and not this_week:
        console.print("[dim]No upcoming tasks. You're all caught up! 🎉[/dim]\n")

    # AI suggestions
    if use_ai:
        ai = get_ai_provider()
        if ai.is_available():
            all_tasks = overdue + today + this_week
            if all_tasks:
                console.print("[bold magenta]🤖 AI Suggestions[/bold magenta]")
                suggestion = ai.suggest_focus(all_tasks)
                panel = Panel(suggestion, border_style="magenta")
                console.print(panel)
                console.print()


def _display_task_table(console: Console, tasks: list[Task]) -> None:
    """Display tasks in a formatted table.

    Args:
        console: Rich console
        tasks: List of tasks to display
    """
    # Sort tasks: Priority (Urgent->Low), Due Date (Ascending), Title (A-Z)
    priority_map = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    tasks.sort(key=lambda t: (
        priority_map.get(t.priority.value, 4),
        t.due_date.timestamp() if t.due_date else datetime.max.timestamp(),
        t.title
    ))

    table = Table(show_header=True, header_style="bold")
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
                    due_text = f"[yellow]Today[/yellow]"
                elif days_until == 1:
                    due_text = f"[yellow]Tomorrow[/yellow]"
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
