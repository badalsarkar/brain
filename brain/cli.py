"""Command-line interface for brain."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from brain import __version__
from brain.config import get_config, reload_config
from brain.storage import get_storage
from brain.git_utils import get_git_manager
from brain import notes, tasks
from brain.focus import show_focus_view, show_stats


console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """Brain - Terminal-based note-taking and work management with AI."""
    pass


# ============================================================================
# INIT COMMAND
# ============================================================================


@cli.command()
def init():
    """Initialize a new brain workspace."""
    config = get_config()

    console.print(f"\n[bold cyan]Initializing brain workspace...[/bold cyan]\n")

    # Create directories
    config.ensure_directories()
    console.print(f"✓ Created data directory: {config.brain_data_dir}")

    # Initialize git
    git = get_git_manager()
    if git.is_repo():
        console.print("✓ Git repository initialized")
    else:
        console.print("[yellow]! Git not initialized (auto-commit disabled)[/yellow]")

    # Save config
    config.save_config()
    console.print(f"✓ Saved configuration to: {config.config_file}")

    console.print(f"\n[bold green]✓ Workspace initialized successfully![/bold green]\n")
    console.print(f"Data directory: {config.brain_data_dir}")
    console.print(f"AI Provider: {config.ai_provider}")
    console.print(f"\nTry: [bold]brain note \"My first note\"[/bold]\n")


# ============================================================================
# NOTE COMMANDS
# ============================================================================


@cli.command()
@click.argument("content", required=False)
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--from-stdin", is_flag=True, help="Read from stdin")
@click.option("--tags", "-t", multiple=True, help="Tags for the note")
@click.option("--category", "-c", help="Category")
@click.option("--project", "-p", help="Project name")
@click.option("--no-ai", is_flag=True, help="Disable AI auto-tagging")
def note(content, interactive, from_stdin, tags, category, project, no_ai):
    """Quick capture a note."""
    auto_tag = not no_ai

    if interactive:
        # Interactive mode
        title = click.prompt("Title")
        content_text = click.edit() or ""
        tags_input = click.prompt("Tags (comma-separated)", default="")
        category_input = click.prompt("Category", default="general")
        project_input = click.prompt("Project (optional)", default="")

        tags_list = [t.strip() for t in tags_input.split(",") if t.strip()]
        
        created_note = notes.create_note(
            title=title,
            content=content_text,
            tags=tags_list,
            category=category_input,
            project=project_input or None,
            auto_tag=auto_tag,
        )
    elif from_stdin:
        # Read from stdin
        created_note = notes.capture_from_stdin(auto_tag=auto_tag)
    elif content:
        # Quick capture
        lines = content.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        
        created_note = notes.create_note(
            title=title, 
            content=body, 
            tags=list(tags) if tags else None,
            category=category,
            project=project,
            auto_tag=auto_tag
        )
    else:
        console.print("[red]Error: Provide content, use --interactive, or --from-stdin[/red]")
        sys.exit(1)

    console.print(f"\n[bold green]✓ Note created![/bold green]")
    console.print(f"ID: {created_note.id}")
    console.print(f"Title: {created_note.title}")
    if created_note.tags:
        console.print(f"Tags: {', '.join(created_note.tags)}")
    console.print()


@cli.group()
def notes_group():
    """Manage notes."""
    pass


cli.add_command(notes_group, name="notes")


@notes_group.command(name="list")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--category", "-c", help="Filter by category")
@click.option("--project", "-p", help="Filter by project")
@click.option("--limit", "-n", type=int, help="Limit number of results")
def list_notes(tags, category, project, limit):
    """List all notes."""
    note_list = notes.list_notes(
        tags=list(tags) if tags else None,
        category=category,
        project=project,
        limit=limit,
    )

    if not note_list:
        console.print("[dim]No notes found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Title", style="bold")
    table.add_column("Category", width=12)
    table.add_column("Tags", width=25)
    table.add_column("Created", width=12)

    for note in note_list:
        table.add_row(
            note.id,
            note.title[:50],
            note.category,
            ", ".join(note.tags[:3]),
            note.created_at.strftime("%Y-%m-%d"),
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Total: {len(note_list)} notes[/dim]\n")


@notes_group.command(name="show")
@click.argument("note_id", required=False)
def show_note(note_id):
    """Show a note."""
    if not note_id:
        # Interactive selection
        import questionary
        
        recent_notes = notes.list_notes(limit=20)
        if not recent_notes:
            console.print("[dim]No notes found.[/dim]")
            return

        choices = []
        for note in recent_notes:
            created = note.created_at.strftime("%Y-%m-%d")
            choices.append(questionary.Choice(
                title=f"{note.title} ({note.id}) - {created}",
                value=note.id
            ))
            
        note_id = questionary.select(
            "Select a note to view:",
            choices=choices
        ).ask()
        
        if not note_id:
            return

    note = notes.get_note(note_id)

    if not note:
        console.print(f"[red]Note {note_id} not found.[/red]")
        sys.exit(1)

    console.print(f"\n[bold cyan]{note.title}[/bold cyan]")
    console.print(f"[dim]ID: {note.id} | Category: {note.category}[/dim]")
    if note.tags:
        console.print(f"[dim]Tags: {', '.join(note.tags)}[/dim]")
    if note.project:
        console.print(f"[dim]Project: {note.project}[/dim]")
    console.print(f"[dim]Created: {note.created_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
    console.print()

    # Render markdown content
    md = Markdown(note.content)
    console.print(md)
    console.print()


@notes_group.command(name="search")
@click.argument("query")
@click.option("--limit", "-n", type=int, help="Limit number of results")
def search_notes_cmd(query, limit):
    """Search notes by content."""
    results = notes.search_notes(query, limit=limit)

    if not results:
        console.print(f"[dim]No notes found matching '{query}'.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Title", style="bold")
    table.add_column("Preview", width=50)

    for note in results:
        preview = note.content[:100].replace("\n", " ")
        table.add_row(note.id, note.title[:40], preview)

    console.print()
    console.print(table)
    console.print(f"\n[dim]Found {len(results)} notes[/dim]\n")


@notes_group.command(name="edit")
@click.argument("note_id")
def edit_note(note_id):
    """Edit a note."""
    note = notes.get_note(note_id)

    if not note:
        console.print(f"[red]Note {note_id} not found.[/red]")
        sys.exit(1)

    # Edit content
    new_content = click.edit(note.content)
    if new_content and new_content != note.content:
        notes.update_note(note_id, content=new_content)
        console.print(f"[bold green]✓ Note updated![/bold green]")
    else:
        console.print("[dim]No changes made.[/dim]")


@notes_group.command(name="delete")
@click.argument("note_id")
@click.confirmation_option(prompt="Are you sure you want to delete this note?")
def delete_note(note_id):
    """Delete a note."""
    if notes.delete_note(note_id):
        console.print(f"[bold green]✓ Note {note_id} deleted.[/bold green]")
    else:
        console.print(f"[red]Note {note_id} not found.[/red]")


# ============================================================================
# TASK COMMANDS
# ============================================================================


@cli.command()
@click.argument("title", required=False)
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option("--description", "-d", help="Task description")
@click.option("--priority", "-p", type=click.Choice(["low", "medium", "high", "urgent"]), default="medium")
@click.option("--due", help="Due date (e.g., 'tomorrow', 'next friday', '2024-01-15')")
@click.option("--tags", "-t", multiple=True, help="Tags for the task")
@click.option("--project", help="Project name")
def task(title, interactive, description, priority, due, tags, project):
    """Create a new task."""
    if interactive:
        # Interactive mode
        title = click.prompt("Title")
        description = click.edit() or ""
        priority = click.prompt(
            "Priority",
            type=click.Choice(["low", "medium", "high", "urgent"]),
            default="medium",
        )
        due = click.prompt("Due date (optional)", default="")
        tags_input = click.prompt("Tags (comma-separated)", default="")
        project = click.prompt("Project (optional)", default="")

        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
    elif not title:
        console.print("[red]Error: Provide a title or use --interactive[/red]")
        sys.exit(1)

    created_task = tasks.create_task(
        title=title,
        description=description or "",
        priority=priority,
        due_date=due or None,
        tags=list(tags) if tags else None,
        project=project or None,
    )

    console.print(f"\n[bold green]✓ Task created![/bold green]")
    console.print(f"ID: {created_task.id}")
    console.print(f"Title: {created_task.title}")
    console.print(f"Priority: {created_task.priority.value}")
    if created_task.due_date:
        console.print(f"Due: {created_task.due_date.strftime('%Y-%m-%d')}")
    console.print()


@cli.group()
def tasks_group():
    """Manage tasks."""
    pass


cli.add_command(tasks_group, name="tasks")


@tasks_group.command(name="list")
@click.option("--status", "-s", type=click.Choice(["todo", "in-progress", "done", "blocked"]))
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--project", "-p", help="Filter by project")
def list_tasks_cmd(status, tags, project):
    """List all tasks."""
    task_list = tasks.list_tasks(
        status=status,
        tags=list(tags) if tags else None,
        project=project,
    )

    if not task_list:
        console.print("[dim]No tasks found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Priority", width=8)
    table.add_column("Title", style="bold")
    table.add_column("Status", width=12)
    table.add_column("Due", width=12)

    for task in task_list:
        # Priority color
        priority_colors = {"low": "green", "medium": "yellow", "high": "orange1", "urgent": "red"}
        priority_color = priority_colors.get(task.priority.value, "white")
        priority_text = f"[{priority_color}]{task.priority.value.upper()}[/{priority_color}]"

        # Due date
        due_text = task.due_date.strftime("%Y-%m-%d") if task.due_date else "-"
        if task.is_overdue():
            due_text = f"[red]{due_text}[/red]"

        table.add_row(
            task.id,
            priority_text,
            task.title[:50],
            task.status.value,
            due_text,
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Total: {len(task_list)} tasks[/dim]\n")


@tasks_group.command(name="today")
def tasks_today():
    """Show today's tasks."""
    task_list = tasks.get_tasks_by_timeframe("today")

    if not task_list:
        console.print("[dim]No tasks due today.[/dim]")
        return

    console.print("\n[bold cyan]📅 Tasks Due Today[/bold cyan]\n")
    for task in task_list:
        console.print(f"[bold]{task.title}[/bold] [{task.priority.value}]")
        if task.description:
            console.print(f"  {task.description[:100]}")
        console.print()


@tasks_group.command(name="week")
def tasks_week():
    """Show this week's tasks."""
    task_list = tasks.get_tasks_by_timeframe("week")

    if not task_list:
        console.print("[dim]No tasks due this week.[/dim]")
        return

    console.print("\n[bold cyan]📆 Tasks Due This Week[/bold cyan]\n")
    for task in task_list:
        due_str = task.due_date.strftime("%a %m/%d") if task.due_date else ""
        console.print(f"[bold]{task.title}[/bold] - {due_str} [{task.priority.value}]")
        if task.description:
            console.print(f"  {task.description[:100]}")
        console.print()


@tasks_group.command(name="done")
@click.argument("task_id")
def mark_done(task_id):
    """Mark a task as done."""
    task = tasks.complete_task(task_id)
    if task:
        console.print(f"[bold green]✓ Task '{task.title}' marked as done![/bold green]")
    else:
        console.print(f"[red]Task {task_id} not found.[/red]")


@tasks_group.command(name="show")
@click.argument("task_id")
def show_task(task_id):
    """Show task details."""
    task = tasks.get_task(task_id)

    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        sys.exit(1)

    console.print(f"\n[bold cyan]{task.title}[/bold cyan]")
    console.print(f"[dim]ID: {task.id}[/dim]")
    console.print(f"Status: {task.status.value}")
    console.print(f"Priority: {task.priority.value}")
    if task.due_date:
        console.print(f"Due: {task.due_date.strftime('%Y-%m-%d %H:%M')}")
    if task.tags:
        console.print(f"Tags: {', '.join(task.tags)}")
    if task.project:
        console.print(f"Project: {task.project}")
    console.print()

    if task.description:
        md = Markdown(task.description)
        console.print(md)
    console.print()


@tasks_group.command(name="edit")
@click.argument("task_id")
@click.option("--title", help="New title")
@click.option("--status", "-s", type=click.Choice(["todo", "in-progress", "done", "blocked"]))
@click.option("--priority", "-p", type=click.Choice(["low", "medium", "high", "urgent"]))
@click.option("--due", help="New due date")
@click.option("--tags", "-t", multiple=True, help="New tags (replaces existing)")
@click.option("--project", help="New project")
@click.option("--description", "-d", is_flag=True, help="Edit description interactively")
def edit_task(task_id, title, status, priority, due, tags, project, description):
    """Edit a task."""
    task = tasks.get_task(task_id)

    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        sys.exit(1)

    # Interactive description editing
    new_description = None
    if description:
        new_description = click.edit(task.description)
        if new_description is not None:
            new_description = new_description.strip()

    updated_task = tasks.update_task(
        task_id,
        title=title,
        status=status,
        priority=priority,
        due_date=due,
        tags=list(tags) if tags else None,
        project=project,
        description=new_description,
    )

    if updated_task:
        console.print(f"[bold green]✓ Task {task_id} updated![/bold green]")
        if title:
            console.print(f"Title: {updated_task.title}")
        if status:
            console.print(f"Status: {updated_task.status.value}")
        if priority:
            console.print(f"Priority: {updated_task.priority.value}")
        if due:
            due_str = updated_task.due_date.strftime('%Y-%m-%d') if updated_task.due_date else "None"
            console.print(f"Due: {due_str}")
        if tags:
            console.print(f"Tags: {', '.join(updated_task.tags)}")
        if project:
            console.print(f"Project: {updated_task.project}")
    else:
        # Should be covered by initial check, but just in case
        console.print(f"[red]Failed to update task {task_id}.[/red]")


# ============================================================================
# SEARCH COMMAND
# ============================================================================


@cli.command()
@click.argument("query", required=False)
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--project", "-p", help="Filter by project")
def search(query, tags, project):
    """Search notes and tasks globally."""
    storage = get_storage()
    notes_list, tasks_list = storage.search_all(
        query=query,
        tags=list(tags) if tags else None,
        project=project,
    )

    if not notes_list and not tasks_list:
        console.print("[dim]No matching results found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Type", width=6)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Title", style="bold")
    table.add_column("Project", width=15)
    table.add_column("Tags", width=20)
    table.add_column("Status/Date", width=12)

    # Add tasks first (usually more actionable)
    for task in tasks_list:
        table.add_row(
            "[blue]TASK[/blue]",
            task.id,
            task.title[:40],
            task.project or "-",
            ", ".join(task.tags[:2]),
            f"[{'green' if task.status.value == 'done' else 'yellow'}]{task.status.value}[/]",
        )

    # Add notes
    for note in notes_list:
        table.add_row(
            "[green]NOTE[/green]",
            note.id,
            note.title[:40],
            note.project or "-",
            ", ".join(note.tags[:2]),
            note.created_at.strftime("%Y-%m-%d"),
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Found {len(notes_list)} notes and {len(tasks_list)} tasks[/dim]\n")


# ============================================================================
# FOCUS COMMANDS
# ============================================================================


@cli.command()
@click.option("--no-ai", is_flag=True, help="Disable AI suggestions")
def focus(no_ai):
    """Show focus view dashboard."""
    show_focus_view(use_ai=not no_ai)


@cli.command()
def stats():
    """Show productivity statistics."""
    show_stats()


# ============================================================================
# UTILITY COMMANDS
# ============================================================================


@cli.command()
def config():
    """Show current configuration."""
    cfg = get_config()

    console.print("\n[bold cyan]Brain Configuration[/bold cyan]\n")
    console.print(f"Data Directory: {cfg.brain_data_dir}")
    console.print(f"AI Provider: {cfg.ai_provider}")
    console.print(f"Git Auto-commit: {cfg.git_auto_commit}")
    console.print(f"Config File: {cfg.config_file}")
    console.print()


@cli.command()
def sync():
    """Sync with git remote."""
    git = get_git_manager()

    if not git.is_repo():
        console.print("[red]Not a git repository.[/red]")
        sys.exit(1)

    console.print("Syncing with remote...")
    success, message = git.sync()

    if success:
        console.print(f"[bold green]✓ {message}[/bold green]")
    else:
        console.print(f"[red]✗ {message}[/red]")


@cli.command()
@click.option("--sort", type=click.Choice(["name", "count"]), default="count", help="Sort by name or count")
def tags(sort):
    """List all tags."""
    storage = get_storage()
    if not storage.index.tags:
        console.print("[dim]No tags found.[/dim]")
        return

    # Prepare data
    tag_data = []
    for tag, ids in storage.index.tags.items():
        notes_count = 0
        tasks_count = 0
        for item_id in ids:
            if item_id in storage.index.notes:
                notes_count += 1
            elif item_id in storage.index.tasks:
                tasks_count += 1
        
        tag_data.append((tag, notes_count, tasks_count, len(ids)))

    # Sort
    if sort == "name":
        tag_data.sort(key=lambda x: x[0])
    else:
        tag_data.sort(key=lambda x: x[3], reverse=True)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Tag", style="bold")
    table.add_column("Notes", justify="right")
    table.add_column("Tasks", justify="right")
    table.add_column("Total", justify="right")

    for tag, n_count, t_count, total in tag_data:
        table.add_row(tag, str(n_count), str(t_count), str(total))

    console.print()
    console.print(table)
    console.print(f"\n[dim]Total: {len(tag_data)} tags[/dim]\n")


@cli.command()
@click.option("--sort", type=click.Choice(["name", "count"]), default="count", help="Sort by name or count")
def projects(sort):
    """List all projects."""
    storage = get_storage()
    if not storage.index.projects:
        console.print("[dim]No projects found.[/dim]")
        return

    # Prepare data
    project_data = []
    for project, ids in storage.index.projects.items():
        notes_count = 0
        tasks_count = 0
        for item_id in ids:
            if item_id in storage.index.notes:
                notes_count += 1
            elif item_id in storage.index.tasks:
                tasks_count += 1
        
        project_data.append((project, notes_count, tasks_count, len(ids)))

    # Sort
    if sort == "name":
        project_data.sort(key=lambda x: x[0])
    else:
        project_data.sort(key=lambda x: x[3], reverse=True)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Project", style="bold")
    table.add_column("Notes", justify="right")
    table.add_column("Tasks", justify="right")
    table.add_column("Total", justify="right")

    for project, n_count, t_count, total in project_data:
        table.add_row(project, str(n_count), str(t_count), str(total))

    console.print()
    console.print(table)
    console.print(f"\n[dim]Total: {len(project_data)} projects[/dim]\n")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
