"""Task management operations."""

from datetime import datetime, timedelta
from typing import Optional

from dateutil import parser as date_parser

from brain.ai.factory import get_ai_provider
from brain.config import get_config
from brain.models import Task, TaskStatus, TaskPriority
from brain.storage import get_storage


def create_task(
    title: str,
    description: str = "",
    priority: str = "medium",
    due_date: Optional[str] = None,
    tags: Optional[list[str]] = None,
    project: Optional[str] = None,
    assignee: Optional[str] = None,
) -> Task:
    """Create a new task.

    Args:
        title: Task title
        description: Task description
        priority: Priority level (low, medium, high, urgent)
        due_date: Due date (string or datetime)
        tags: List of tags
        project: Project name
        assignee: Assigned person

    Returns:
        Created task
    """
    config = get_config()
    storage = get_storage()

    # Parse due date
    parsed_due_date = None
    if due_date:
        parsed_due_date = parse_due_date(due_date)

    # Use defaults if not provided
    if tags is None:
        tags = config.default_tags.copy()

    # Canonicalize project and tags
    if project:
        project = storage.get_canonical_project(project)
    if tags:
        tags = [storage.get_canonical_tag(t) for t in tags]

    # Create task
    task = Task(
        title=title,
        description=description,
        priority=TaskPriority(priority),
        due_date=parsed_due_date,
        tags=tags,
        project=project,
        assignee=assignee,
    )

    # Save to storage
    storage.save_task(task)

    return task

import re
from dateutil.relativedelta import relativedelta

def parse_due_date(date_str: str) -> Optional[datetime]:
    """Parse due date from various formats.

    Args:
        date_str: Date string (e.g., "tomorrow", "in 2 days", "next week")

    Returns:
        Parsed datetime or None
    """
    date_str = date_str.lower().strip()
    now = datetime.now()
    
    # Common mappings
    if date_str == "today":
        return now.replace(hour=23, minute=59, second=59)
    elif date_str == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    elif date_str == "next week":
        return (now + timedelta(weeks=1)).replace(hour=23, minute=59, second=59)
    elif date_str == "next month":
        return (now + relativedelta(months=1)).replace(hour=23, minute=59, second=59)

    # Regex patterns for relative dates
    # "in 3 days", "after 5 days", "2 weeks", "after 1 month"
    patterns = [
        (r"(?:in|after)?\s*(\d+)\s*days?", "days"),
        (r"(?:in|after)?\s*(\d+)\s*weeks?", "weeks"),
        (r"(?:in|after)?\s*(\d+)\s*months?", "months"),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, date_str)
        if match:
            amount = int(match.group(1))
            if unit == "days":
                return (now + timedelta(days=amount)).replace(hour=23, minute=59, second=59)
            elif unit == "weeks":
                return (now + timedelta(weeks=amount)).replace(hour=23, minute=59, second=59)
            elif unit == "months":
                return (now + relativedelta(months=amount)).replace(hour=23, minute=59, second=59)

    # Fallback to fuzzy parsing
    try:
        dt = date_parser.parse(date_str, fuzzy=True)
        # If the parsed date is in the past (and no year specified), usually assume future
        return dt.replace(hour=23, minute=59, second=59)
    except:
        return None


def get_task(task_id: str) -> Optional[Task]:
    """Get task by ID.

    Args:
        task_id: Task ID

    Returns:
        Task or None if not found
    """
    storage = get_storage()
    return storage.load_task(task_id)

def update_task(
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
    tags: Optional[list[str]] = None,
    project: Optional[str] = None,
    assignee: Optional[str] = None,
) -> Optional[Task]:
    """Update an existing task.

    Args:
        task_id: Task ID
        title: New title (optional)
        description: New description (optional)
        status: New status (optional)
        priority: New priority (optional)
        due_date: New due date (optional)
        tags: New tags (optional)
        project: New project (optional)
        assignee: New assignee (optional)

    Returns:
        Updated task or None if not found
    """
    storage = get_storage()
    task = storage.load_task(task_id)

    if not task:
        return None

    # Update fields
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if status is not None:
        task.status = TaskStatus(status)
        if status == "done" and task.completed_at is None:
            task.completed_at = datetime.now()
    if priority is not None:
        task.priority = TaskPriority(priority)
    if due_date is not None:
        task.due_date = parse_due_date(due_date)
    if tags is not None:
        task.tags = [storage.get_canonical_tag(t) for t in tags]
    if project is not None:
        task.project = storage.get_canonical_project(project)
    if assignee is not None:
        task.assignee = assignee

    # Save changes
    storage.save_task(task)

    return task


def complete_task(task_id: str) -> Optional[Task]:
    """Mark task as complete.

    Args:
        task_id: Task ID

    Returns:
        Updated task or None if not found
    """
    return update_task(task_id, status="done")


def delete_task(task_id: str) -> bool:
    """Delete a task.

    Args:
        task_id: Task ID

    Returns:
        True if deleted, False if not found
    """
    storage = get_storage()
    return storage.delete_task(task_id)


def list_tasks(
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
    project: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[Task]:
    """List tasks with optional filtering.

    Args:
        status: Filter by status
        tags: Filter by tags
        project: Filter by project
        limit: Maximum number of tasks to return

    Returns:
        List of tasks
    """
    storage = get_storage()
    tasks = storage.list_tasks(
        status=status,
        tags=tags,
        project=project
    )

    if limit:
        tasks = tasks[:limit]

    return tasks


def get_tasks_by_timeframe(timeframe: str = "today") -> list[Task]:
    """Get tasks by timeframe.

    Args:
        timeframe: "today", "week", "month", or "overdue"

    Returns:
        List of tasks
    """
    storage = get_storage()
    all_tasks = storage.list_tasks(status="todo") + storage.list_tasks(status="in-progress")

    now = datetime.now()
    filtered_tasks = []

    for task in all_tasks:
        if timeframe == "overdue":
            if task.is_overdue():
                filtered_tasks.append(task)
        elif timeframe == "today":
            if task.due_date and task.due_date.date() == now.date():
                filtered_tasks.append(task)
        elif timeframe == "week":
            if task.due_date and task.due_date <= now + timedelta(days=7):
                filtered_tasks.append(task)
        elif timeframe == "month":
            if task.due_date and task.due_date <= now + timedelta(days=30):
                filtered_tasks.append(task)

    return filtered_tasks


def extract_tasks_from_note(note_content: str) -> list[str]:
    """Extract tasks from note content using AI.

    Args:
        note_content: Note content

    Returns:
        List of extracted task descriptions
    """
    ai = get_ai_provider()
    if not ai.is_available():
        return []

    return ai.extract_tasks(note_content)
