"""Command-line interface for brain."""

import sys
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from brain import __version__
from brain.config import get_config, reload_config
from brain.storage import get_storage
from brain.git_utils import get_git_manager
from brain import notes, tasks, projects as projects_mod
from brain.models import TaskStatus, TaskPriority
from brain.utils import parse_date
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


TASK_ALIASES = {
    "view": "show",
}


class TaskAliasGroup(click.Group):
    """Group that supports command aliases."""

    def get_command(self, ctx, cmd_name):
        cmd_name = TASK_ALIASES.get(cmd_name, cmd_name)
        return super().get_command(ctx, cmd_name)


@cli.group(cls=TaskAliasGroup)
def task():
    """Manage tasks."""
    pass


def _create_task_interactive():
    """Interactive task creation with pick-what-you-need menu."""
    import questionary

    title = questionary.text("Title:").ask()
    if not title:
        console.print("[red]Title is required.[/red]")
        return

    description = ""
    priority = "medium"
    due = None
    tags = []
    project = None
    assign = None

    while True:
        fields = questionary.checkbox(
            "Set optional fields (space to select, enter to continue):",
            choices=[
                questionary.Choice("Priority", value="priority"),
                questionary.Choice("Due date", value="due"),
                questionary.Choice("Tags", value="tags"),
                questionary.Choice("Project", value="project"),
                questionary.Choice("Assignee", value="assign"),
                questionary.Choice("Description (editor)", value="description"),
            ],
        ).ask()

        if fields is None:
            return

        if "priority" in fields:
            priority = questionary.select(
                "Priority:", choices=["low", "medium", "high", "urgent"], default="medium"
            ).ask() or "medium"
        if "due" in fields:
            due = questionary.text("Due date:").ask() or None
        if "tags" in fields:
            tags_input = questionary.text("Tags (comma-separated):").ask() or ""
            tags = [t.strip() for t in tags_input.split(",") if t.strip()]
        if "project" in fields:
            project = questionary.text("Project:").ask() or None
        if "assign" in fields:
            assign = questionary.text("Assignee:").ask() or None
        if "description" in fields:
            description = click.edit() or ""
        break

    _create_task(title, description, priority, due, tuple(tags), project, assign)


def _create_task(title, description, priority, due, tags, project, assign):
    """Shared task creation logic with compact output."""
    from brain.shorthand import parse_shorthand

    parsed = parse_shorthand(title)
    title = parsed["title"]
    if parsed["priority"] and priority == "medium":
        priority = parsed["priority"]
    if parsed["project"] and not project:
        project = parsed["project"]
    if parsed["tags"] and not tags:
        tags = tuple(parsed["tags"])
    if parsed["due"] and not due:
        due = parsed["due"]
    if parsed["assignee"] and not assign:
        assign = parsed["assignee"]

    created_task = tasks.create_task(
        title=title,
        description=description or "",
        priority=priority,
        due_date=due or None,
        tags=list(tags) if tags else None,
        project=project or None,
        assignee=assign or None,
    )

    # Compact output
    parts = [f"[bold green]Task #{created_task.id} created[/bold green]"]
    priority_colors = {"low": "green", "medium": "yellow", "high": "orange1", "urgent": "red"}
    pc = priority_colors.get(created_task.priority.value, "white")
    parts.append(f"[{pc}]{created_task.priority.value.upper()}[/{pc}]")
    if created_task.project:
        parts.append(f"@{created_task.project}")
    if created_task.due_date:
        parts.append(f"~{created_task.due_date.strftime('%Y-%m-%d')}")
    if created_task.tags:
        parts.append(" ".join(f"#{t}" for t in created_task.tags))
    if created_task.assignee:
        parts.append(f">{created_task.assignee}")
    console.print("  ".join(parts))


@task.command(name="create")
@click.argument("titles", nargs=-1)
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
@click.option(
    "--file", "-f", "input_file", type=click.Path(exists=True), help="Batch: read tasks from file"
)
@click.option("--batch", "-b", is_flag=True, help="Batch: create multiple tasks")
def create_task_cmd(titles, interactive, input_file, batch):
    """Create tasks (single, interactive, or batch).

    \b
    Usage:
      brain task create "title ^high @project #tag ~fri"          Single task
      brain task create -i                                        Interactive mode
      brain task create -b "task one ^high" "task two @proj"      Batch inline
      brain task create -f tasks.txt                              Batch from file

    \b
    Shorthand syntax (inline in title):
      ^priority   ^low ^medium ^high ^urgent ^crit  (or ! instead of ^)
      @project    @webapp @backend
      #tag        #bug #auth (multiple allowed)
      ~due        ~today ~tod ~tomorrow ~tmrw
                  ~mon ~tue ~wed ~thu ~fri ~sat ~sun
                  ~1d ~2d ~3d ~1w ~2w ~1m
                  ~nw (next week) ~nm (next month)
                  ~eow (end of week) ~eom (end of month)
                  ~2024-03-15 ~"next friday"
      >assignee   >alice >bob
    """
    if interactive:
        _create_task_interactive()
        return

    if input_file:
        with open(input_file) as f:
            lines = f.read().splitlines()
        count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            _create_task(line, "", "medium", None, (), None, None)
            count += 1
        if count > 1:
            console.print(f"\n[bold green]{count} tasks created[/bold green]")
        return

    if batch:
        if not titles:
            console.print("[red]Provide task titles as arguments with -b.[/red]")
            console.print('[dim]Example: brain task create -b "Task one" "Task two ^high"[/dim]')
            sys.exit(1)
        for title in titles:
            _create_task(title, "", "medium", None, (), None, None)
        if len(titles) > 1:
            console.print(f"\n[bold green]{len(titles)} tasks created[/bold green]")
        return

    if not sys.stdin.isatty() and not titles:
        lines = sys.stdin.read().splitlines()
        count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            _create_task(line, "", "medium", None, (), None, None)
            count += 1
        if count > 1:
            console.print(f"\n[bold green]{count} tasks created[/bold green]")
        return

    if len(titles) == 1:
        _create_task(titles[0], "", "medium", None, (), None, None)
        return

    if len(titles) > 1:
        console.print("[yellow]Multiple titles given. Use -b for batch mode.[/yellow]")
        sys.exit(1)

    # No args — show help
    ctx = click.get_current_context()
    click.echo(ctx.get_help())


# Keep `brain tasks` as alias
cli.add_command(task, name="tasks")


@task.command(name="list")
@click.option("--status", "-s", type=click.Choice(["todo", "in-progress", "done", "blocked"]))
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--project", "-p", help="Filter by project")
@click.option("--assignee", "-a", help="Filter by assignee")
@click.option("--search", "-q", help="Fuzzy search tasks")
def list_tasks_cmd(status, tags, project, assignee, search):
    """List all tasks."""
    if search:
        task_list = tasks.search_tasks(search)
        if status:
            task_list = [t for t in task_list if t.status.value == status]
    else:
        all_tasks = tasks.list_tasks(
            status=status,
            tags=list(tags) if tags else None,
            project=project,
        )
        task_list = []
        if assignee:
            for t in all_tasks:
                if t.assignee and t.assignee.lower() == assignee.lower():
                    task_list.append(t)
        else:
            task_list = all_tasks

    if not task_list:
        console.print("[dim]No tasks found.[/dim]")
        return

    _print_task_table(task_list)


def _print_task_table(task_list):
    """Render a list of tasks as a Rich table."""
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Priority", width=8)
    table.add_column("Title", style="bold")
    table.add_column("Assignee", width=12)
    table.add_column("Status", width=12)
    table.add_column("Due", width=12)

    for task in task_list:
        priority_colors = {"low": "green", "medium": "yellow", "high": "orange1", "urgent": "red"}
        priority_color = priority_colors.get(task.priority.value, "white")
        priority_text = f"[{priority_color}]{task.priority.value.upper()}[/{priority_color}]"

        due_text = task.due_date.strftime("%Y-%m-%d") if task.due_date else "-"
        if task.is_overdue():
            due_text = f"[red]{due_text}[/red]"

        table.add_row(
            task.id,
            priority_text,
            task.title[:50],
            task.assignee or "-",
            task.status.value,
            due_text,
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Total: {len(task_list)} tasks[/dim]\n")


def _apply_task_filters(task_list, status=None, priority=None, project=None, tags=None, due=None, assignee=None):
    """Apply optional filters to a task list."""
    if status:
        task_list = [t for t in task_list if t.status.value == status]
    if priority:
        task_list = [t for t in task_list if t.priority.value == priority]
    if project:
        task_list = [t for t in task_list if t.project and t.project.lower() == project.lower()]
    if tags:
        tag_set = set(tags)
        task_list = [t for t in task_list if tag_set.issubset(set(t.tags))]
    if assignee:
        task_list = [t for t in task_list if t.assignee and t.assignee.lower() == assignee.lower()]
    if due:
        from datetime import timedelta
        now = datetime.now()
        filtered = []
        for t in task_list:
            if not t.due_date:
                continue
            if due == "today" and t.due_date.date() == now.date():
                filtered.append(t)
            elif due == "overdue" and t.is_overdue():
                filtered.append(t)
            elif due == "week" and t.due_date.date() <= (now + timedelta(days=7)).date():
                filtered.append(t)
            else:
                try:
                    target = datetime.strptime(due, "%Y-%m-%d").date()
                    if t.due_date.date() == target:
                        filtered.append(t)
                except ValueError:
                    pass
        task_list = filtered
    return task_list


def _fuzzy_select_task(prompt="Select a task:", task_list=None):
    """Present a fuzzy-filterable task selector. Returns task ID or None."""
    import questionary

    if task_list is None:
        task_list = tasks.list_tasks(status=None)

    if not task_list:
        console.print("[dim]No tasks found.[/dim]")
        return None

    choices = []
    for t in task_list:
        priority_abbr = t.priority.value[0].upper()
        due_str = f" due:{t.due_date.strftime('%m-%d')}" if t.due_date else ""
        label = f"{t.id[:6]}  {priority_abbr}  [{t.status.value}]  {t.title}{due_str}"
        choices.append(questionary.Choice(title=label, value=t.id))

    return questionary.select(
        prompt,
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()


@task.command(name="search")
@click.argument("query", nargs=-1)
@click.option("--status", "-s", type=click.Choice(["todo", "in-progress", "done", "blocked"]))
@click.option("--priority", "-p", type=click.Choice(["low", "medium", "high", "urgent"]))
@click.option("--project", "--proj", help="Filter by project")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--due", "-d", help="Filter by due date (today, overdue, week, or YYYY-MM-DD)")
@click.option("--assignee", "-a", help="Filter by assignee")
def search_task_cmd(query, status, priority, project, tags, due, assignee):
    """Search tasks with fuzzy matching and filters.

    With QUERY: shows matching tasks as a table.
    Without QUERY: interactive fuzzy-filterable list.
    """
    import questionary

    query_str = " ".join(query) if query else None
    has_filters = any([status, priority, project, tags, due, assignee])

    # Get base task list
    if query_str:
        task_list = tasks.search_tasks(query_str)
        # Apply all filters on search results
        task_list = _apply_task_filters(
            task_list, status=status, priority=priority, project=project,
            tags=tags, due=due, assignee=assignee,
        )
    else:
        task_list = tasks.list_tasks(
            status=status,
            tags=list(tags) if tags else None,
            project=project,
        )
        # If no query and no filters, default to non-complete tasks
        if not has_filters:
            task_list = [t for t in task_list if t.status != TaskStatus.DONE]
        # Apply filters not handled by list_tasks
        task_list = _apply_task_filters(
            task_list, priority=priority, assignee=assignee, due=due,
        )

    if not task_list:
        console.print("[dim]No tasks found.[/dim]")
        return

    # Direct mode: print table
    if query_str:
        _print_task_table(task_list)
        return

    # Interactive mode: fuzzy select
    selected_id = _fuzzy_select_task("Search tasks (type to filter):", task_list)

    if not selected_id:
        return

    selected_task = tasks.get_task(selected_id)
    if not selected_task:
        console.print(f"[red]Task {selected_id} not found.[/red]")
        return

    # Display task details (same as show_task)
    console.print(f"\n[bold cyan]{selected_task.title}[/bold cyan]")
    console.print(f"[dim]ID: {selected_task.id}[/dim]")
    console.print(f"Status: {selected_task.status.value}")
    console.print(f"Priority: {selected_task.priority.value}")
    if selected_task.assignee:
        console.print(f"Assignee: [bold yellow]{selected_task.assignee}[/bold yellow]")
    if selected_task.due_date:
        console.print(f"Due: {selected_task.due_date.strftime('%Y-%m-%d %H:%M')}")
    if selected_task.tags:
        console.print(f"Tags: {', '.join(selected_task.tags)}")
    if selected_task.project:
        console.print(f"Project: {selected_task.project}")
    console.print()
    if selected_task.description:
        md = Markdown(selected_task.description)
        console.print(md)
    console.print()


# ... today/week/done commands ...

@task.command(name="show")
@click.argument("task_id", required=False)
@click.option("--status", "-s", type=click.Choice(["todo", "in-progress", "done", "blocked"]))
@click.option("--priority", "-p", type=click.Choice(["low", "medium", "high", "urgent"]))
@click.option("--project", "--proj", help="Filter by project")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--due", "-d", help="Filter by due date (today, overdue, week, or YYYY-MM-DD)")
@click.option("--assignee", "-a", help="Filter by assignee")
def show_task(task_id, status, priority, project, tags, due, assignee):
    """Show task details."""
    if not task_id:
        has_filters = any([status, priority, project, tags, due, assignee])
        if has_filters:
            task_list = tasks.list_tasks(status=status, tags=list(tags) if tags else None, project=project)
            task_list = _apply_task_filters(task_list, priority=priority, assignee=assignee, due=due)
        else:
            task_list = None
        task_id = _fuzzy_select_task("Show task (type to filter):", task_list)
        if not task_id:
            return

    task = tasks.get_task(task_id)

    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        sys.exit(1)

    console.print(f"\n[bold cyan]{task.title}[/bold cyan]")
    console.print(f"[dim]ID: {task.id}[/dim]")
    console.print(f"Status: {task.status.value}")
    console.print(f"Priority: {task.priority.value}")
    if task.assignee:
        console.print(f"Assignee: [bold yellow]{task.assignee}[/bold yellow]")
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


import shutil

# ... existing code ...

@task.command(name="edit")
@click.argument("task_id", required=False)
@click.option("--status", "-s", type=click.Choice(["todo", "in-progress", "done", "blocked"]))
@click.option("--priority", "-p", type=click.Choice(["low", "medium", "high", "urgent"]))
@click.option("--project", "--proj", help="Filter by project")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--due", "-d", help="Filter by due date (today, overdue, week, or YYYY-MM-DD)")
@click.option("--assignee", "-a", help="Filter by assignee")
def edit_task(task_id, status, priority, project, tags, due, assignee):
    """Edit a task in your editor."""
    if not task_id:
        has_filters = any([status, priority, project, tags, due, assignee])
        if has_filters:
            task_list = tasks.list_tasks(status=status, tags=list(tags) if tags else None, project=project)
            task_list = _apply_task_filters(task_list, priority=priority, assignee=assignee, due=due)
        else:
            task_list = None
        task_id = _fuzzy_select_task("Edit task (type to filter):", task_list)
        if not task_id:
            return

    task = tasks.get_task(task_id)

    if not task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        sys.exit(1)

    if not task.file_path or not task.file_path.exists():
        console.print("[red]Error: Task file not found on disk.[/red]")
        sys.exit(1)

    editor = "nvim" if shutil.which("nvim") else None
    if not editor and not os.environ.get("EDITOR"):
        console.print("[yellow]NVIM not found and EDITOR not set. Using default.[/yellow]")

    click.edit(filename=str(task.file_path), editor=editor)

    storage = get_storage()
    updated_task_obj = storage._read_task_file(task.file_path)
    storage.save_task(updated_task_obj)

    console.print(f"[bold green]✓ Task {task_id} updated![/bold green]")



@task.command(name="done")
@click.argument("task_id", required=False)
@click.option("--status", "-s", type=click.Choice(["todo", "in-progress", "blocked"]))
@click.option("--priority", "-p", type=click.Choice(["low", "medium", "high", "urgent"]))
@click.option("--project", "--proj", help="Filter by project")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--due", "-d", help="Filter by due date (today, overdue, week, or YYYY-MM-DD)")
@click.option("--assignee", "-a", help="Filter by assignee")
def complete_task_cmd(task_id, status, priority, project, tags, due, assignee):
    """Mark a task as complete."""
    if not task_id:
        pending = tasks.list_tasks(status=status, tags=list(tags) if tags else None, project=project)
        pending = [t for t in pending if t.status != TaskStatus.DONE]
        pending = _apply_task_filters(pending, priority=priority, assignee=assignee, due=due)
        task_id = _fuzzy_select_task("Complete task (type to filter):", pending)
        if not task_id:
            return

    # Perform completion
    updated_task = tasks.complete_task(task_id)

    if not updated_task:
        console.print(f"[red]Task {task_id} not found.[/red]")
        sys.exit(1)

    console.print(f"[bold green]✓ Task marked as complete![/bold green]")
    console.print(f"[dim]{updated_task.title}[/dim]")



@task.command(name="delete")
@click.argument("task_ids", nargs=-1)
@click.option("--all", "delete_all", is_flag=True, help="Delete all tasks")
@click.option("--done", "delete_done", is_flag=True, help="Delete all completed tasks")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--status", "-s", type=click.Choice(["todo", "in-progress", "done", "blocked"]))
@click.option("--priority", "-p", type=click.Choice(["low", "medium", "high", "urgent"]))
@click.option("--project", "--proj", help="Filter by project")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--due", "-d", help="Filter by due date")
@click.option("--assignee", "-a", help="Filter by assignee")
def delete_task_cmd(task_ids, delete_all, delete_done, yes, status, priority, project, tags, due, assignee):
    """Delete one or more tasks.

    \b
    brain task delete 3          # delete task #3
    brain task delete 1 2 3      # delete multiple
    brain task delete --done     # delete all completed tasks
    brain task delete --all      # delete everything
    """
    storage = get_storage()

    if delete_all:
        ids = list(storage.index.tasks.keys())
        label = f"all {len(ids)} tasks"
    elif delete_done:
        ids = [
            tid for tid, data in storage.index.tasks.items()
            if data.get("status") == "done"
        ]
        label = f"{len(ids)} completed tasks"
    elif task_ids:
        ids = list(task_ids)
        label = f"{len(ids)} task(s)"
    else:
        task_list = tasks.list_tasks(status=status, tags=list(tags) if tags else None, project=project)
        task_list = _apply_task_filters(task_list, priority=priority, assignee=assignee, due=due)
        has_filters = any([status, priority, project, tags, due, assignee])
        selected_id = _fuzzy_select_task("Delete task (type to filter):", task_list if has_filters else None)
        if not selected_id:
            return
        ids = [selected_id]
        label = "1 task"

    if not ids:
        console.print("[dim]No matching tasks found.[/dim]")
        return

    if not yes:
        if not click.confirm(f"Delete {label}?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    deleted = 0
    for tid in ids:
        if tasks.delete_task(tid):
            deleted += 1
        else:
            console.print(f"[yellow]Task {tid} not found.[/yellow]")

    console.print(f"[bold green]Deleted {deleted} task(s)[/bold green]")




@cli.command()
@click.argument("person")
@click.argument("message")
def feedback(person, message):
    """Add feedback for a person.
    
    Creates a note tagged with the person's name and categorized as 'feedback'.
    """
    note = notes.create_note(
        title=f"Feedback: {person}",
        content=message,
        category="feedback",
        tags=[person],
        project="people-management"
    )
    console.print(f"[bold green]✓ Feedback recorded for {person}![/bold green]")


@cli.group()
def team():
    """Manage team members."""
    pass


@team.command(name="add")
@click.argument("name")
@click.option("--role", help="Person's role")
@click.option("--email", help="Person's email")
def team_add(name, role, email):
    """Add a new team member."""
    extra = {}
    content = ""
    if role:
        extra["role"] = role
        content += f"Role: {role}\n"
    if email:
        extra["email"] = email
        content += f"Email: {email}\n"

    notes.create_note(
        title=name,
        content=content.strip() or f"Profile for {name}",
        category="person",
        tags=[],
        extra=extra
    )
    console.print(f"[bold green]✓ Team member '{name}' added![/bold green]")


@team.command(name="list")
def team_list():
    """List all team members."""
    storage = get_storage()
    team_notes = []
    
    # Scan notes for category='person'
    if "person" in storage.index.categories:
        ids = storage.index.categories["person"]
        for nid in ids:
            n = storage.load_note(nid)
            if n: team_notes.append(n)
            
    if not team_notes:
        console.print("[dim]No team members found.[/dim]")
        return
        
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Role")
    table.add_column("Email")
    
    for p in team_notes:
        role = p.extra.get("role", "-")
        email = p.extra.get("email", "-")
        table.add_row(p.title, role, email)
        
    console.print(table)


@team.command(name="show")
@click.argument("name")
def team_show(name):
    """Show all info related to a person (Tasks & Notes)."""
    # 1. Search Tasks assigned to person
    storage = get_storage()
    
    # 1. Assignee tasks
    assigned_tasks = []
    if name in storage.index.assignees:
        for tid in storage.index.assignees[name]:
            t = storage.load_task(tid)
            if t: assigned_tasks.append(t)
            
    # 2. Tagged items (notes and tasks)
    tagged_notes = []
    tagged_tasks = []
    
    if name in storage.index.tags:
        ids = storage.index.tags[name]
        for item_id in ids:
            n = storage.load_note(item_id)
            if n: tagged_notes.append(n)
            
            t = storage.load_task(item_id)
            if t: tagged_tasks.append(t)
            
    # Quick check for Person Profile Note
    profile_note = None
    if "person" in storage.index.categories:
        ids = storage.index.categories["person"]
        for nid in ids:
            n = storage.load_note(nid)
            if n and n.title.lower() == name.lower():
                profile_note = n
                break
            
    # Merge tasks (avoid duplicates if task is both assigned AND tagged)
    unique_tasks = {t.id: t for t in assigned_tasks + tagged_tasks}
    
    console.print(f"\n[bold cyan]👤 Person: {name}[/bold cyan]\n")
    
    if profile_note:
        if "role" in profile_note.extra:
            console.print(f"Role: {profile_note.extra['role']}")
        if "email" in profile_note.extra:
            console.print(f"Email: {profile_note.extra['email']}")
        console.print()
    
    # Assigned Tasks
    console.print(f"[bold]Assigned Tasks / Related Tasks:[/bold]")
    if not unique_tasks:
        console.print("[dim]No tasks.[/dim]")
    else:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("State", width=12)
        table.add_column("Title", style="bold")
        table.add_column("Due", width=12)
        
        sorted_tasks = sorted(unique_tasks.values(), key=lambda t: t.due_date or datetime.max)
        for t in sorted_tasks:
            relation = "Assigned" if t.assignee == name else "Tagged"
            # Highlight status
            status = t.status.value
            if status == "done":
                status = f"[green]{status}[/green]"
            elif status == "urgent":
                 status = f"[red]{status}[/red]"
                 
            table.add_row(
                f"{status} ({relation})",
                t.title[:50],
                t.due_date.strftime("%Y-%m-%d") if t.due_date else "-"
            )
        console.print(table)
        
    console.print()
    
    # Related Notes (Feedback, etc)
    console.print(f"[bold]Related Notes & Feedback:[/bold]")
    if not tagged_notes:
        console.print("[dim]No notes.[/dim]")
    else:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Category", width=12)
        table.add_column("Title", style="bold")
        table.add_column("Date", width=12)
        
        sorted_notes = sorted(tagged_notes, key=lambda n: n.created_at, reverse=True)
        for n in sorted_notes:
            # Skip the profile note itself from related notes to avoid recursion visual
            if profile_note and n.id == profile_note.id:
                continue
                
            table.add_row(
                n.category,
                n.title[:50],
                n.created_at.strftime("%Y-%m-%d")
            )
        console.print(table)
    console.print()


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
    table.add_column("Project", overflow="fold")
    table.add_column("Tags", overflow="fold")
    table.add_column("Status/Date", width=12)

    # Add tasks first (usually more actionable)
    for task in tasks_list:
        table.add_row(
            "[blue]TASK[/blue]",
            task.id,
            task.title,
            task.project or "-",
            ", ".join(task.tags),
            f"[{'green' if task.status.value == 'done' else 'yellow'}]{task.status.value}[/]",
        )

    # Add notes
    for note in notes_list:
        table.add_row(
            "[green]NOTE[/green]",
            note.id,
            note.title,
            note.project or "-",
            ", ".join(note.tags),
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


@cli.group(invoke_without_command=True)
@click.option("--sort", type=click.Choice(["name", "count"]), default="count", help="Sort by name or count")
@click.pass_context
def tags(ctx, sort):
    """Manage tags (list, rename, delete)."""
    if ctx.invoked_subcommand is None:
        # Default behavior: list tags
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


@tags.command(name="rename")
@click.argument("old_name")
@click.argument("new_name")
def tags_rename(old_name, new_name):
    """Rename a tag."""
    storage = get_storage()
    count = storage.rename_tag(old_name, new_name)
    if count > 0:
        console.print(f"[bold green]✓ Renamed tag '{old_name}' to '{new_name}' in {count} items[/bold green]")
    else:
        console.print(f"[yellow]Tag '{old_name}' not found or no items updated.[/yellow]")


@tags.command(name="delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this tag from all items?")
def tags_delete(name):
    """Delete a tag."""
    storage = get_storage()
    count = storage.delete_tag(name)
    if count > 0:
        console.print(f"[bold green]✓ Deleted tag '{name}' from {count} items[/bold green]")
    else:
        console.print(f"[yellow]Tag '{name}' not found.[/yellow]")


@cli.group(invoke_without_command=True)
@click.option("--sort", type=click.Choice(["name", "count"]), default="count", help="Sort by name or count")
@click.pass_context
def projects(ctx, sort):
    """Manage projects (list, rename, delete)."""
    if ctx.invoked_subcommand is None:
        # Default behavior: list projects
        storage = get_storage()
        # Prepare data
        rich_projects = storage.list_projects_metadata()
        all_project_names = set(storage.index.projects.keys()) | set(rich_projects.keys())
        
        if not all_project_names:
            console.print("[dim]No projects found.[/dim]")
            return

        project_data = []
        for project in all_project_names:
            ids = storage.index.projects.get(project, [])
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
        table.add_column("Meta", justify="center")
        table.add_column("Notes", justify="right")
        table.add_column("Tasks", justify="right")
        table.add_column("Total", justify="right")

        rich_projects = storage.list_projects_metadata()

        for project, n_count, t_count, total in project_data:
            has_meta = "✓" if project in rich_projects else ""
            table.add_row(project, has_meta, str(n_count), str(t_count), str(total))

        console.print()
        console.print(table)
        console.print(f"\n[dim]Total: {len(project_data)} projects[/dim]\n")


@projects.command(name="rename")
@click.argument("old_name")
@click.argument("new_name")
def projects_rename(old_name, new_name):
    """Rename a project."""
    storage = get_storage()
    count = storage.rename_project(old_name, new_name)
    if count > 0:
        console.print(f"[bold green]✓ Renamed project '{old_name}' to '{new_name}' in {count} items[/bold green]")
    else:
        console.print(f"[yellow]Project '{old_name}' not found or no items updated.[/yellow]")


@projects.command(name="delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this project from all items?")
def projects_delete(name):
    """Delete a project."""
    storage = get_storage()
    count = storage.delete_project(name)
    if count > 0:
        console.print(f"[bold green]✓ Deleted project '{name}' from {count} items[/bold green]")
    else:
        console.print(f"[yellow]Project '{name}' not found.[/yellow]")


@projects.command(name="create")
@click.option("--name", "-n", help="Project name")
@click.option("--description", "-d", help="Project description")
@click.option("--end-date", "-e", help="Project end date (e.g., 'next month')")
@click.option("--interactive", "-i", is_flag=True, help="Interactive mode")
def projects_create(name, description, end_date, interactive):
    """Create a new project."""
    if interactive:
        import questionary
        
        if not name:
            name = questionary.text("Project Name:").ask()
            if not name:
                console.print("[red]Project name is required.[/red]")
                return

        if not description:
            description = questionary.text("Description:").ask()

        if not end_date:
            end_date = questionary.text("End Date (optional, e.g., 'next friday'):").ask()

    if not name:
        console.print("[red]Project name is required. Use --name or --interactive.[/red]")
        sys.exit(1)

    project = projects_mod.create_project(
        name=name,
        description=description or "",
        end_date=end_date
    )

    console.print(f"\n[bold green]✓ Project '{project.name}' created/updated![/bold green]")
    if project.end_date:
        console.print(f"End Date: {project.end_date.strftime('%Y-%m-%d')}")
    console.print()


@projects.command(name="show")
@click.argument("name")
def projects_show(name):
    """Show project details."""
    storage = get_storage()
    project_meta = projects_mod.get_project(name)
    
    # Check if project exists in index (even if no rich metadata)
    canonical_name = storage.get_canonical_project(name)
    has_index = canonical_name in storage.index.projects
    
    if not project_meta and not has_index:
        console.print(f"[red]Project '{name}' not found.[/red]")
        return

    console.print(f"\n[bold cyan]Project: {canonical_name}[/bold cyan]")
    
    if project_meta and project_meta.description:
        console.print("\n[bold]Description:[/bold]")
        console.print(Markdown(project_meta.description))
    else:
        console.print("\n[dim]No description provided.[/dim]")

    if project_meta and project_meta.end_date:
        console.print(f"\n[bold]End Date:[/bold] {project_meta.end_date.strftime('%Y-%m-%d')}")

    # Show stats
    ids = storage.index.projects.get(canonical_name, [])
    notes_count = sum(1 for i in ids if i in storage.index.notes)
    tasks_count = sum(1 for i in ids if i in storage.index.tasks)
    
    console.print(f"\n[dim]Stats: {notes_count} notes, {tasks_count} tasks[/dim]\n")


@projects.command(name="edit")
@click.argument("name")
def projects_edit(name):
    """Edit project description."""
    storage = get_storage()
    canonical_name = storage.get_canonical_project(name)
    
    # It's okay to edit a project that doesn't exist in index yet (to pre-create metadata)
    project = storage.get_project(canonical_name)
    if not project:
        from brain.models import Project
        project = Project(name=canonical_name, description="")

    new_description = click.edit(project.description)
    if new_description is not None:
        project.description = new_description.strip()
        storage.save_project(project)
        console.print(f"[bold green]✓ Project metadata updated for '{canonical_name}'[/bold green]")
    else:
        console.print("[dim]No changes made.[/dim]")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
