"""Note management operations."""

import sys
from datetime import datetime
from typing import Optional

from brain.ai.factory import get_ai_provider
from brain.config import get_config
from brain.models import Note
from brain.storage import get_storage


def create_note(
    title: str,
    content: str,
    tags: Optional[list[str]] = None,
    category: Optional[str] = None,
    project: Optional[str] = None,
    auto_tag: bool = False,
    extra: Optional[dict] = None,
) -> Note:
    """Create a new note.

    Args:
        title: Note title
        content: Note content
        tags: List of tags
        category: Category
        project: Project name
        auto_tag: Use AI to generate additional tags
        extra: Additional metadata

    Returns:
        Created note
    """
    config = get_config()
    storage = get_storage()

    # Use defaults if not provided
    if tags is None:
        tags = config.default_tags.copy()
    if category is None:
        category = config.default_category

    # Auto-generate tags with AI
    if auto_tag:
        ai = get_ai_provider()
        if ai.is_available():
            ai_tags = ai.generate_tags(content)
            # Merge with existing tags, avoiding duplicates
            tags = list(set(tags + ai_tags))

    # Create note
    note = Note(
        title=title,
        content=content,
        tags=tags,
        category=category,
        project=project,
        extra=extra or {},
    )

    # Save to storage
    storage.save_note(note)

    return note


def quick_capture(content: str, auto_tag: bool = True) -> Note:
    """Quick capture a note from command line.

    Args:
        content: Note content (first line becomes title)
        auto_tag: Use AI to generate tags

    Returns:
        Created note
    """
    # Use first line as title, rest as content
    lines = content.split("\n", 1)
    title = lines[0].strip()
    body = lines[1].strip() if len(lines) > 1 else ""

    return create_note(title, body, auto_tag=auto_tag)


def capture_from_stdin(auto_tag: bool = True) -> Note:
    """Capture note from stdin.

    Args:
        auto_tag: Use AI to generate tags

    Returns:
        Created note
    """
    content = sys.stdin.read().strip()
    return quick_capture(content, auto_tag=auto_tag)


def get_note(note_id: str) -> Optional[Note]:
    """Get note by ID.

    Args:
        note_id: Note ID

    Returns:
        Note or None if not found
    """
    storage = get_storage()
    return storage.load_note(note_id)


def update_note(
    note_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[list[str]] = None,
    category: Optional[str] = None,
    project: Optional[str] = None,
) -> Optional[Note]:
    """Update an existing note.

    Args:
        note_id: Note ID
        title: New title (optional)
        content: New content (optional)
        tags: New tags (optional)
        category: New category (optional)
        project: New project (optional)

    Returns:
        Updated note or None if not found
    """
    storage = get_storage()
    note = storage.load_note(note_id)

    if not note:
        return None

    # Update fields
    if title is not None:
        note.title = title
    if content is not None:
        note.content = content
    if tags is not None:
        note.tags = tags
    if category is not None:
        note.category = category
    if project is not None:
        note.project = project

    # Save changes
    storage.save_note(note)

    return note


def delete_note(note_id: str) -> bool:
    """Delete a note.

    Args:
        note_id: Note ID

    Returns:
        True if deleted, False if not found
    """
    storage = get_storage()
    return storage.delete_note(note_id)


def list_notes(
    tags: Optional[list[str]] = None,
    category: Optional[str] = None,
    project: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[Note]:
    """List notes with optional filtering.

    Args:
        tags: Filter by tags
        category: Filter by category
        project: Filter by project
        limit: Maximum number of notes to return

    Returns:
        List of notes
    """
    storage = get_storage()
    notes = storage.list_notes(
        tags=tags,
        category=category,
        project=project
    )

    if limit:
        notes = notes[:limit]

    return notes


def search_notes(query: str, limit: Optional[int] = None) -> list[Note]:
    """Search notes by content.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        List of matching notes
    """
    storage = get_storage()
    notes = storage.search_notes(query)

    if limit:
        notes = notes[:limit]

    return notes


def add_tags(note_id: str, tags: list[str]) -> Optional[Note]:
    """Add tags to a note.

    Args:
        note_id: Note ID
        tags: Tags to add

    Returns:
        Updated note or None if not found
    """
    storage = get_storage()
    note = storage.load_note(note_id)

    if not note:
        return None

    # Add new tags (avoid duplicates)
    note.tags = list(set(note.tags + tags))
    storage.save_note(note)

    return note


def remove_tags(note_id: str, tags: list[str]) -> Optional[Note]:
    """Remove tags from a note.

    Args:
        note_id: Note ID
        tags: Tags to remove

    Returns:
        Updated note or None if not found
    """
    storage = get_storage()
    note = storage.load_note(note_id)

    if not note:
        return None

    # Remove tags
    note.tags = [t for t in note.tags if t not in tags]
    storage.save_note(note)

    return note
