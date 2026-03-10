"""Command-line interface for brain."""

import os
import shutil
import sys
from datetime import datetime

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from brain import __version__
from brain.config import get_config
from brain.storage import get_storage
from brain.git_utils import get_git_manager
from brain import notes, tasks, projects as projects_mod
from brain.models import TaskStatus
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

    # Ensure default templates
    storage = get_storage()
    storage.ensure_default_templates()
    console.print("✓ Created default templates")

    # Save config
    config.save_config()
    console.print(f"✓ Saved configuration to: {config.config_file}")

    console.print(f"\n[bold green]✓ Workspace initialized successfully![/bold green]\n")
    console.print(f"Data directory: {config.brain_data_dir}")
    console.print(f"AI Provider: {config.ai_provider}")
    console.print(f'\nTry: [bold]brain note "My first note"[/bold]\n')


# ============================================================================
# NOTE COMMANDS
# ============================================================================


def _create_note(title, content, tags, category, project, no_ai, note_type=None):
    """Shared note creation logic with compact output."""
    auto_tag = not no_ai
    lines = title.split("\n", 1)
    title = lines[0].strip()
    body = lines[1].strip() if len(lines) > 1 else (content or "")

    created_note = notes.create_note(
        title=title,
        content=body,
        tags=list(tags) if tags else None,
        category=category,
        project=project or None,
        note_type=note_type,
        auto_tag=auto_tag,
    )

    parts = [f"[bold green]Note {created_note.id} created[/bold green]"]
    if created_note.note_type:
        parts.append(f"[dim]{created_note.note_type}[/dim]")
    if created_note.project:
        parts.append(f"@{created_note.project}")
    if created_note.tags:
        parts.append(" ".join(f"#{t}" for t in created_note.tags))
    if created_note.category and created_note.category != "general":
        parts.append(created_note.category)
    console.print("  ".join(parts))


def _create_note_from_template(template_name, title, tags, category, project, no_ai, note_type):
    """Create a note using a template. Opens editor with template body."""
    storage = get_storage()
    result = storage.load_template(template_name)
    if not result:
        console.print(f"[red]Template '{template_name}' not found.[/red]")
        available = storage.list_templates()
        if available:
            console.print(f"[dim]Available: {', '.join(available)}[/dim]")
        return

    tmpl_meta, tmpl_body = result

    # Prompt for title if not provided
    if not title:
        import questionary

        title = questionary.text("Title:").ask()
        if not title:
            console.print("[red]Title is required.[/red]")
            return

    # Build editor content
    editor_text = f"# {title}\n\n{tmpl_body}"
    editor = "nvim" if shutil.which("nvim") else None
    edited = click.edit(text=editor_text, editor=editor)
    if edited is None:
        console.print("[dim]Aborted.[/dim]")
        return

    # Parse result: first # Title line = title, rest = body
    lines = edited.strip().split("\n")
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body = "\n".join(lines[1:]).strip()
    else:
        body = edited.strip()

    # Merge: CLI args > template defaults > config defaults
    merged_type = note_type or tmpl_meta.get("type") or template_name
    merged_tags = list(tags) if tags else tmpl_meta.get("tags", [])
    merged_category = category or tmpl_meta.get("category")
    merged_project = project or tmpl_meta.get("project")

    _create_note(
        title, body, tuple(merged_tags), merged_category, merged_project, no_ai, merged_type
    )


def _fuzzy_select_note(prompt="Select a note:", note_list=None):
    """Present a fuzzy-filterable note selector. Returns note ID or None."""
    import questionary

    if note_list is None:
        note_list = notes.list_notes()

    if not note_list:
        console.print("[dim]No notes found.[/dim]")
        return None

    choices = []
    for n in note_list:
        tags_str = f"  [{', '.join(n.tags[:3])}]" if n.tags else ""
        cat_str = f"  {n.category}" if n.category and n.category != "general" else ""
        date_str = n.created_at.strftime("%m-%d")
        label = f"{n.id[:6]}{cat_str}  {n.title}{tags_str}  {date_str}"
        choices.append(questionary.Choice(title=label, value=n.id))

    return questionary.select(
        prompt,
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()


def _apply_note_filters(note_list, tags=None, category=None, project=None):
    """Apply optional filters to a note list."""
    if category:
        note_list = [n for n in note_list if n.category and n.category.lower() == category.lower()]
    if project:
        note_list = [n for n in note_list if n.project and n.project.lower() == project.lower()]
    if tags:
        tag_set = set(tags)
        note_list = [n for n in note_list if tag_set.issubset(set(n.tags))]
    return note_list


def _show_note_details(n):
    """Display full note details."""
    console.print(f"\n[bold cyan]{n.title}[/bold cyan]")
    type_str = f" | Type: {n.note_type}" if n.note_type else ""
    console.print(f"[dim]ID: {n.id} | Category: {n.category}{type_str}[/dim]")
    if n.tags:
        console.print(f"[dim]Tags: {', '.join(n.tags)}[/dim]")
    if n.project:
        console.print(f"[dim]Project: {n.project}[/dim]")
    console.print(f"[dim]Created: {n.created_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
    console.print()
    if n.content:
        md = Markdown(n.content)
        console.print(md)
    console.print()


@cli.group()
def note():
    """Manage notes."""
    pass


cli.add_command(
    click.Group(name="notes", commands=note.commands, help="Manage notes.", hidden=True)
)


@note.command(name="create")
@click.argument("content", required=False)
@click.option("--tags", "-t", multiple=True, help="Tags")
@click.option("--category", "-c", help="Category")
@click.option("--project", "-p", help="Project")
@click.option("--type", "-T", "note_type", help="Note type (e.g. meeting)")
@click.option("--template", "template_name", help="Template name")
@click.option("--no-ai", is_flag=True, help="Disable AI auto-tagging")
def create_note_cmd(content, tags, category, project, note_type, template_name, no_ai):
    """Create a note.

    \b
    Usage:
      brain note create "quick thought"              Scratch pad (quick dump)
      brain note create --template meeting            Template with editor
      brain note create --template meeting "title"    Template with title
      brain note create -T meeting "title"            Editor with type, no template
      brain note create                               Prompt for title, open editor
    """
    # Template flow: always opens editor
    if template_name:
        _create_note_from_template(
            template_name, content, tags, category, project, no_ai, note_type
        )
        return

    # Type flag without template: open editor with blank body
    if note_type:
        title = content
        if not title:
            import questionary

            title = questionary.text("Title:").ask()
            if not title:
                console.print("[red]Title is required.[/red]")
                return

        editor_text = f"# {title}\n\n"
        editor = "nvim" if shutil.which("nvim") else None
        edited = click.edit(text=editor_text, editor=editor)
        if edited is None:
            console.print("[dim]Aborted.[/dim]")
            return

        lines = edited.strip().split("\n")
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            body = "\n".join(lines[1:]).strip()
        else:
            body = edited.strip()

        _create_note(title, body, tags, category, project, no_ai, note_type)
        return

    # Bare content: quick dump to scratch pad
    if content:
        notes.quick_dump(content)
        console.print(f"[bold green]Saved to scratch pad[/bold green]")
        return

    # No args, no flags: prompt for title, open editor
    import questionary

    title = questionary.text("Title:").ask()
    if not title:
        console.print("[red]Title is required.[/red]")
        return

    editor_text = f"# {title}\n\n"
    editor = "nvim" if shutil.which("nvim") else None
    edited = click.edit(text=editor_text, editor=editor)
    if edited is None:
        console.print("[dim]Aborted.[/dim]")
        return

    lines = edited.strip().split("\n")
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body = "\n".join(lines[1:]).strip()
    else:
        body = edited.strip()

    _create_note(title, body, tags, category, project, no_ai)


@note.command(name="list")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--category", "-c", help="Filter by category")
@click.option("--project", "-p", help="Filter by project")
@click.option("--type", "-T", "note_type", help="Filter by note type")
@click.option("--limit", "-n", type=int, help="Limit number of results")
def list_notes_cmd(tags, category, project, note_type, limit):
    """List all notes."""
    note_list = notes.list_notes(
        tags=list(tags) if tags else None,
        category=category,
        project=project,
        note_type=note_type,
        limit=limit,
    )

    if not note_list:
        console.print("[dim]No notes found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Title", style="bold")
    table.add_column("Type", width=10)
    table.add_column("Category", width=12)
    table.add_column("Tags", width=25)
    table.add_column("Created", width=12)

    for n in note_list:
        table.add_row(
            n.id,
            n.title[:50],
            n.note_type or "",
            n.category,
            ", ".join(n.tags[:3]),
            n.created_at.strftime("%Y-%m-%d"),
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Total: {len(note_list)} notes[/dim]\n")


@note.command(name="show")
@click.argument("note_id", required=False)
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--category", "-c", help="Filter by category")
@click.option("--project", "-p", help="Filter by project")
def show_note(note_id, tags, category, project):
    """Show a note."""
    if not note_id:
        has_filters = any([tags, category, project])
        if has_filters:
            note_list = notes.list_notes(
                tags=list(tags) if tags else None, category=category, project=project
            )
        else:
            note_list = None
        note_id = _fuzzy_select_note("Show note (type to filter):", note_list)
        if not note_id:
            return

    n = notes.get_note(note_id)

    if not n:
        console.print(f"[red]Note {note_id} not found.[/red]")
        sys.exit(1)

    _show_note_details(n)


@note.command(name="search")
@click.argument("query", nargs=-1)
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--category", "-c", help="Filter by category")
@click.option("--project", "-p", help="Filter by project")
@click.option("--limit", "-n", type=int, help="Limit results")
def search_notes_cmd(query, tags, category, project, limit):
    """Search notes by content.

    \b
    With QUERY: shows matching notes as a table.
    Without QUERY: interactive fuzzy-filterable list.
    """
    query_str = " ".join(query) if query else None

    if query_str:
        results = notes.search_notes(query_str, limit=limit)
        results = _apply_note_filters(results, tags=tags, category=category, project=project)

        if not results:
            console.print(f"[dim]No notes found matching '{query_str}'.[/dim]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("ID", style="dim", width=8)
        table.add_column("Title", style="bold")
        table.add_column("Preview", width=50)

        for n in results:
            preview = n.content[:100].replace("\n", " ")
            table.add_row(n.id, n.title[:40], preview)

        console.print()
        console.print(table)
        console.print(f"\n[dim]Found {len(results)} notes[/dim]\n")
        return

    # Interactive mode: fuzzy select
    has_filters = any([tags, category, project])
    if has_filters:
        note_list = notes.list_notes(
            tags=list(tags) if tags else None, category=category, project=project
        )
    else:
        note_list = None

    selected_id = _fuzzy_select_note("Search notes (type to filter):", note_list)
    if not selected_id:
        return

    n = notes.get_note(selected_id)
    if not n:
        console.print(f"[red]Note {selected_id} not found.[/red]")
        return

    _show_note_details(n)


@note.command(name="edit")
@click.argument("note_id_or_title", required=False, metavar="[NOTE_ID_OR_TITLE]")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--category", "-c", help="Filter by category")
@click.option("--project", "-p", help="Filter by project")
def edit_note(note_id_or_title, tags, category, project):
    """Edit a note in your editor by ID or title."""
    note_id = note_id_or_title
    if not note_id:
        has_filters = any([tags, category, project])
        if has_filters:
            note_list = notes.list_notes(
                tags=list(tags) if tags else None, category=category, project=project
            )
        else:
            note_list = None
        note_id = _fuzzy_select_note("Edit note (type to filter):", note_list)
        if not note_id:
            return

    n = notes.get_note(note_id)

    # If not found by ID, try fuzzy match by title
    if not n:
        from difflib import SequenceMatcher

        all_notes = notes.list_notes(
            tags=list(tags) if tags else None, category=category, project=project
        )
        query = note_id.lower()
        scored = []
        for candidate in all_notes:
            title_lower = candidate.title.lower()
            if query in title_lower:
                scored.append((candidate, 1.0))
            else:
                ratio = SequenceMatcher(None, query, title_lower).ratio()
                if ratio > 0.4:
                    scored.append((candidate, ratio))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            console.print(f"[red]No note matching '{note_id}' found.[/red]")
            sys.exit(1)
        elif len(scored) == 1:
            n = scored[0][0]
        else:
            matched_notes = [s[0] for s in scored]
            selected = _fuzzy_select_note(
                prompt=f"Multiple matches for '{note_id}':", note_list=matched_notes
            )
            if not selected:
                return
            n = notes.get_note(selected)

    if not n:
        console.print(f"[red]Note '{note_id}' not found.[/red]")
        sys.exit(1)

    if not n.file_path or not n.file_path.exists():
        console.print("[red]Error: Note file not found on disk.[/red]")
        sys.exit(1)

    editor = "nvim" if shutil.which("nvim") else None
    if not editor and not os.environ.get("EDITOR"):
        console.print("[yellow]NVIM not found and EDITOR not set. Using default.[/yellow]")

    click.edit(filename=str(n.file_path), editor=editor)

    storage = get_storage()
    updated_note = storage._read_note_file(n.file_path)
    storage.save_note(updated_note)

    console.print(f"[bold green]✓ Note {note_id} updated![/bold green]")


@note.command(name="delete")
@click.argument("note_ids", nargs=-1)
@click.option("--all", "delete_all", is_flag=True, help="Delete all notes")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--tags", "-t", multiple=True, help="Filter by tags")
@click.option("--category", "-c", help="Filter by category")
@click.option("--project", "-p", help="Filter by project")
def delete_note(note_ids, delete_all, yes, tags, category, project):
    """Delete one or more notes.

    \b
    brain note delete abc123        # delete by ID
    brain note delete a1 b2 c3      # delete multiple
    brain note delete --all         # delete everything
    brain note delete -t work       # filtered fuzzy select
    """
    storage = get_storage()

    if delete_all:
        ids = list(storage.index.notes.keys())
        label = f"all {len(ids)} notes"
    elif note_ids:
        ids = list(note_ids)
        label = f"{len(ids)} note(s)"
    else:
        has_filters = any([tags, category, project])
        if has_filters:
            note_list = notes.list_notes(
                tags=list(tags) if tags else None, category=category, project=project
            )
        else:
            note_list = None
        selected_id = _fuzzy_select_note("Delete note (type to filter):", note_list)
        if not selected_id:
            return
        ids = [selected_id]
        label = "1 note"

    if not ids:
        console.print("[dim]No matching notes found.[/dim]")
        return

    if not yes:
        if not click.confirm(f"Delete {label}?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    deleted = 0
    for nid in ids:
        if notes.delete_note(nid):
            deleted += 1
        else:
            console.print(f"[yellow]Note {nid} not found.[/yellow]")

    console.print(f"[bold green]Deleted {deleted} note(s)[/bold green]")


@note.command(name="scratch")
def note_scratch_cmd():
    """Open the scratch pad in your editor."""
    storage = get_storage()
    scratch = storage.scratch_file

    if not scratch.exists():
        scratch.parent.mkdir(parents=True, exist_ok=True)
        scratch.write_text("# Scratch Pad\n")

    editor = "nvim" if shutil.which("nvim") else None
    click.edit(filename=str(scratch), editor=editor)


@note.command(name="template")
def note_template_cmd():
    """Open the templates directory in your editor."""
    config = get_config()
    templates_dir = config.templates_dir
    templates_dir.mkdir(parents=True, exist_ok=True)

    editor = "nvim" if shutil.which("nvim") else None
    if editor:
        import subprocess

        subprocess.run([editor, str(templates_dir)])
    else:
        click.launch(str(templates_dir))


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
            priority = (
                questionary.select(
                    "Priority:", choices=["low", "medium", "high", "urgent"], default="medium"
                ).ask()
                or "medium"
            )
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
cli.add_command(
    click.Group(name="tasks", commands=task.commands, help="Manage tasks.", hidden=True)
)


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


def _apply_task_filters(
    task_list, status=None, priority=None, project=None, tags=None, due=None, assignee=None
):
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
    query_str = " ".join(query) if query else None
    has_filters = any([status, priority, project, tags, due, assignee])

    # Get base task list
    if query_str:
        task_list = tasks.search_tasks(query_str)
        # Apply all filters on search results
        task_list = _apply_task_filters(
            task_list,
            status=status,
            priority=priority,
            project=project,
            tags=tags,
            due=due,
            assignee=assignee,
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
            task_list,
            priority=priority,
            assignee=assignee,
            due=due,
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
            task_list = tasks.list_tasks(
                status=status, tags=list(tags) if tags else None, project=project
            )
            task_list = _apply_task_filters(
                task_list, priority=priority, assignee=assignee, due=due
            )
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
            task_list = tasks.list_tasks(
                status=status, tags=list(tags) if tags else None, project=project
            )
            task_list = _apply_task_filters(
                task_list, priority=priority, assignee=assignee, due=due
            )
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
        pending = tasks.list_tasks(
            status=status, tags=list(tags) if tags else None, project=project
        )
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
def delete_task_cmd(
    task_ids, delete_all, delete_done, yes, status, priority, project, tags, due, assignee
):
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
        ids = [tid for tid, data in storage.index.tasks.items() if data.get("status") == "done"]
        label = f"{len(ids)} completed tasks"
    elif task_ids:
        ids = list(task_ids)
        label = f"{len(ids)} task(s)"
    else:
        task_list = tasks.list_tasks(
            status=status, tags=list(tags) if tags else None, project=project
        )
        task_list = _apply_task_filters(task_list, priority=priority, assignee=assignee, due=due)
        has_filters = any([status, priority, project, tags, due, assignee])
        selected_id = _fuzzy_select_task(
            "Delete task (type to filter):", task_list if has_filters else None
        )
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
        project="people-management",
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
        extra=extra,
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
            if n:
                team_notes.append(n)

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
            if t:
                assigned_tasks.append(t)

    # 2. Tagged items (notes and tasks)
    tagged_notes = []
    tagged_tasks = []

    if name in storage.index.tags:
        ids = storage.index.tags[name]
        for item_id in ids:
            n = storage.load_note(item_id)
            if n:
                tagged_notes.append(n)

            t = storage.load_task(item_id)
            if t:
                tagged_tasks.append(t)

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
                t.due_date.strftime("%Y-%m-%d") if t.due_date else "-",
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

            table.add_row(n.category, n.title[:50], n.created_at.strftime("%Y-%m-%d"))
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
@click.option("--project", "-p", default=None, help="Filter by project")
@click.option("--tag", "-t", multiple=True, help="Filter by tag (repeatable)")
@click.option("--top", "-n", "top_n", type=int, default=None, help="Show top N tasks per section")
@click.option(
    "--timeframe",
    "-tf",
    type=click.Choice(["today", "week", "month", "all"], case_sensitive=False),
    default="week",
    help="Lookahead timeframe (default: week)",
)
@click.option("--blocked", "-b", is_flag=True, help="Show blocked tasks section")
def focus(no_ai, project, tag, top_n, timeframe, blocked):
    """Show focus view dashboard."""
    tags = list(tag) if tag else None
    show_focus_view(
        use_ai=not no_ai,
        project=project,
        tags=tags,
        top_n=top_n,
        timeframe=timeframe,
        show_blocked=blocked,
    )


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
@click.option(
    "--sort", type=click.Choice(["name", "count"]), default="count", help="Sort by name or count"
)
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
        console.print(
            f"[bold green]✓ Renamed tag '{old_name}' to '{new_name}' in {count} items[/bold green]"
        )
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


@cli.group()
def project():
    """Manage projects (list, create, show, archive, rename, delete)."""
    pass


@project.command(name="list")
@click.option(
    "--all", "-a", "show_all", is_flag=True, help="Show all projects including archived/completed"
)
@click.option(
    "--status",
    "-s",
    type=click.Choice(["active", "archived", "completed"]),
    default=None,
    help="Filter by status",
)
@click.option(
    "--sort", type=click.Choice(["name", "count"]), default="count", help="Sort by name or count"
)
def project_list(show_all, status, sort):
    """List projects."""
    storage = get_storage()
    rich_projects = storage.list_projects_metadata()
    all_project_names = set(storage.index.projects.keys()) | set(rich_projects.keys())

    if not all_project_names:
        console.print("[dim]No projects found.[/dim]")
        return

    # Determine effective status filter
    if status:
        filter_status = status
    elif show_all:
        filter_status = None
    else:
        filter_status = "active"

    project_data = []
    for proj_name in all_project_names:
        ids = storage.index.projects.get(proj_name, [])
        notes_count = sum(1 for i in ids if i in storage.index.notes)
        tasks_count = sum(1 for i in ids if i in storage.index.tasks)

        # Determine project status
        proj_meta = rich_projects.get(proj_name)
        proj_status = proj_meta.status.value if proj_meta else "active"

        if filter_status and proj_status != filter_status:
            continue

        project_data.append((proj_name, notes_count, tasks_count, len(ids), proj_status))

    if not project_data:
        console.print("[dim]No projects match the filter.[/dim]")
        return

    if sort == "name":
        project_data.sort(key=lambda x: x[0])
    else:
        project_data.sort(key=lambda x: x[3], reverse=True)

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Project", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Notes", justify="right")
    table.add_column("Tasks", justify="right")
    table.add_column("Total", justify="right")

    status_colors = {"active": "green", "archived": "dim", "completed": "cyan"}

    for proj_name, n_count, t_count, total, proj_status in project_data:
        color = status_colors.get(proj_status, "white")
        table.add_row(
            proj_name,
            f"[{color}]{proj_status}[/{color}]",
            str(n_count),
            str(t_count),
            str(total),
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Total: {len(project_data)} projects[/dim]\n")


@project.command(name="rename")
@click.argument("old_name")
@click.argument("new_name")
def project_rename(old_name, new_name):
    """Rename a project."""
    storage = get_storage()
    count = storage.rename_project(old_name, new_name)
    if count > 0:
        console.print(
            f"[bold green]✓ Renamed project '{old_name}' to '{new_name}' in {count} items[/bold green]"
        )
    else:
        console.print(f"[yellow]Project '{old_name}' not found or no items updated.[/yellow]")


@project.command(name="delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this project from all items?")
def project_delete(name):
    """Delete a project."""
    storage = get_storage()
    count = storage.delete_project(name)
    if count > 0:
        console.print(f"[bold green]✓ Deleted project '{name}' from {count} items[/bold green]")
    else:
        console.print(f"[yellow]Project '{name}' not found.[/yellow]")


@project.command(name="create")
@click.argument("name", required=False)
@click.option("--description", "-d", help="Project description")
@click.option("--end-date", "-e", help="Project end date (e.g., 'next month')")
def project_create(name, description, end_date):
    """Create a new project.

    NAME is the project name. If omitted, you'll be prompted interactively.
    """
    if not name:
        import questionary

        name = questionary.text("Project Name:").ask()
        if not name:
            console.print("[red]Project name is required.[/red]")
            return

        if not description:
            description = click.edit("")
            if description is not None:
                description = description.strip()

    proj = projects_mod.create_project(
        name=name,
        description=description or "",
        end_date=end_date,
    )

    console.print(f"\n[bold green]✓ Project '{proj.name}' created/updated![/bold green]")
    if proj.end_date:
        console.print(f"End Date: {proj.end_date.strftime('%Y-%m-%d')}")
    console.print()


@project.command(name="show")
@click.argument("name", required=False)
def project_show(name):
    """Show project details."""
    storage = get_storage()

    if name is None:
        # Interactive selection from active projects
        all_metadata = storage.list_projects_metadata()
        index_names = set(storage.index.projects.keys())
        metadata_names = set(all_metadata.keys())
        all_names = index_names | metadata_names

        # Filter to active projects only
        active_names = []
        for n in sorted(all_names):
            meta = all_metadata.get(n)
            if meta and meta.status.value != "active":
                continue
            item_count = len(storage.index.projects.get(n, []))
            active_names.append((n, item_count))

        if not active_names:
            console.print("[dim]No active projects found.[/dim]")
            return

        import questionary

        choices = [f"{n} ({count} items)" for n, count in active_names]
        selected = questionary.select("Select a project:", choices=choices).ask()
        if not selected:
            return
        name = selected.split(" (")[0]

    project_meta = projects_mod.get_project(name)

    canonical_name = storage.get_canonical_project(name)
    has_index = canonical_name in storage.index.projects

    if not project_meta and not has_index:
        console.print(f"[red]Project '{name}' not found.[/red]")
        return

    console.print(f"\n[bold cyan]Project: {canonical_name}[/bold cyan]")

    if project_meta:
        status_colors = {"active": "green", "archived": "dim", "completed": "cyan"}
        color = status_colors.get(project_meta.status.value, "white")
        console.print(f"[bold]Status:[/bold] [{color}]{project_meta.status.value}[/{color}]")

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
    console.print(f"\n[dim]Stats: {notes_count} notes, {tasks_count} tasks[/dim]")

    # Show actual items
    proj_notes, proj_tasks = storage.get_project_items(canonical_name)

    if proj_notes:
        console.print(f"\n[bold]Notes ({len(proj_notes)}):[/bold]")
        notes_table = Table(show_header=True, header_style="bold")
        notes_table.add_column("Title")
        notes_table.add_column("Date", justify="right")
        notes_table.add_column("Tags")
        for n in proj_notes:
            notes_table.add_row(
                n.title,
                n.created_at.strftime("%Y-%m-%d"),
                ", ".join(n.tags) if n.tags else "",
            )
        console.print(notes_table)

    if proj_tasks:
        console.print(f"\n[bold]Tasks ({len(proj_tasks)}):[/bold]")
        tasks_table = Table(show_header=True, header_style="bold")
        tasks_table.add_column("ID", justify="right")
        tasks_table.add_column("Title")
        tasks_table.add_column("Status")
        tasks_table.add_column("Priority")
        tasks_table.add_column("Due", justify="right")

        priority_colors = {"low": "dim", "medium": "white", "high": "yellow", "urgent": "red"}
        status_style = {"todo": "white", "in-progress": "cyan", "done": "green", "blocked": "red"}

        for t in proj_tasks:
            p_color = priority_colors.get(t.priority.value, "white")
            s_color = status_style.get(t.status.value, "white")
            tasks_table.add_row(
                str(t.id),
                t.title,
                f"[{s_color}]{t.status.value}[/{s_color}]",
                f"[{p_color}]{t.priority.value}[/{p_color}]",
                t.due_date.strftime("%Y-%m-%d") if t.due_date else "",
            )
        console.print(tasks_table)

    console.print()


@project.command(name="archive")
@click.argument("name")
def project_archive(name):
    """Archive a project."""
    result = projects_mod.set_project_status(name, "archived")
    if result:
        console.print(f"[bold green]✓ Project '{result.name}' archived.[/bold green]")
    else:
        console.print(f"[yellow]Project '{name}' not found.[/yellow]")


@project.command(name="edit")
@click.argument("name")
@click.option("--note", "-n", default=None, help="Edit a note within the project")
def project_edit(name, note):
    """Edit project description or a specific note by title.

    Without --note, opens the project description for editing.
    With --note, finds the matching note in the project and opens it in your editor.
    """
    storage = get_storage()
    canonical_name = storage.get_canonical_project(name)

    if note:
        project_notes, _ = storage.get_project_items(canonical_name)
        if not project_notes:
            console.print(f"[yellow]No notes found in project '{canonical_name}'.[/yellow]")
            return

        # Fuzzy/substring match against note titles
        from difflib import SequenceMatcher

        query = note.lower()
        scored = []
        for n in project_notes:
            title_lower = n.title.lower()
            if query in title_lower:
                scored.append((n, 1.0))
            else:
                ratio = SequenceMatcher(None, query, title_lower).ratio()
                if ratio > 0.4:
                    scored.append((n, ratio))

        scored.sort(key=lambda x: x[1], reverse=True)

        if not scored:
            console.print(f"[red]No notes matching '{note}' in project '{canonical_name}'.[/red]")
            return

        if len(scored) == 1:
            note_id = scored[0][0].id
        else:
            matched_notes = [s[0] for s in scored]
            note_id = _fuzzy_select_note(
                prompt=f"Multiple matches for '{note}':", note_list=matched_notes
            )
            if not note_id:
                return

        matched = notes.get_note(note_id)
        if not matched or not matched.file_path or not matched.file_path.exists():
            console.print("[red]Error: Note file not found on disk.[/red]")
            return

        editor = "nvim" if shutil.which("nvim") else None
        if not editor and not os.environ.get("EDITOR"):
            console.print("[yellow]NVIM not found and EDITOR not set. Using default.[/yellow]")

        click.edit(filename=str(matched.file_path), editor=editor)

        updated_note = storage._read_note_file(matched.file_path)
        storage.save_note(updated_note)
        console.print(f"[bold green]✓ Note '{matched.title}' updated![/bold green]")
        return

    proj = storage.get_project(canonical_name)
    if not proj:
        from brain.models import Project

        proj = Project(name=canonical_name, description="")

    new_description = click.edit(proj.description)
    if new_description is not None:
        proj.description = new_description.strip()
        storage.save_project(proj)
        console.print(f"[bold green]✓ Project metadata updated for '{canonical_name}'[/bold green]")
    else:
        console.print("[dim]No changes made.[/dim]")


# Add 'projects' as a hidden alias for 'project'
cli.add_command(
    click.Group(name="projects", commands=project.commands, help=project.help, hidden=True)
)


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
