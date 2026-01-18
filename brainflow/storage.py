"""Storage operations for notes and tasks."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import frontmatter

from brainflow.config import get_config
from brainflow.models import Note, Task, MetadataIndex
from brainflow.git_utils import get_git_manager


class Storage:
    """Handle file system operations for notes and tasks."""

    def __init__(self):
        """Initialize storage."""
        self.config = get_config()
        self.config.ensure_directories()
        self.git = get_git_manager()
        self.index = self._load_index()

    def _load_index(self) -> MetadataIndex:
        """Load metadata index from file."""
        if self.config.index_file.exists():
            try:
                data = json.loads(self.config.index_file.read_text())
                return MetadataIndex(**data)
            except Exception as e:
                print(f"Warning: Could not load index: {e}")
                return MetadataIndex()
        return MetadataIndex()

    def _save_index(self) -> None:
        """Save metadata index to file."""
        self.config.index_file.write_text(
            self.index.model_dump_json(indent=2)
        )

    def _get_note_path(self, note: Note) -> Path:
        """Get file path for a note."""
        # Organize by date: notes/YYYY/MM/DD/title-id.md
        date = note.created_at
        date_dir = self.config.notes_dir / str(date.year) / f"{date.month:02d}" / f"{date.day:02d}"
        date_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize title for filename
        safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in note.title.lower())
        safe_title = safe_title[:50]  # Limit length

        filename = f"{safe_title}-{note.id}.md"
        return date_dir / filename

    def _get_task_path(self, task: Task) -> Path:
        """Get file path for a task."""
        # Organize by status: tasks/status/title-id.md
        status_dir = self.config.tasks_dir / task.status.value
        status_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize title for filename
        safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in task.title.lower())
        safe_title = safe_title[:50]  # Limit length

        filename = f"{safe_title}-{task.id}.md"
        return status_dir / filename

    def save_note(self, note: Note) -> Path:
        """Save note to file system.

        Args:
            note: Note to save

        Returns:
            Path where note was saved
        """
        # Update timestamp
        note.updated_at = datetime.now()

        # Get file path
        if note.file_path is None:
            note.file_path = self._get_note_path(note)

        # Create frontmatter document
        post = frontmatter.Post(note.content)
        post.metadata = note.to_frontmatter_dict()

        # Write to file
        note.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(note.file_path, "w") as f:
            f.write(frontmatter.dumps(post))

        # Update index
        self.index.add_note(note)
        self._save_index()

        # Git commit
        self.git.auto_commit(f"Add/update note: {note.title}", [note.file_path])

        return note.file_path

    def load_note(self, note_id: str) -> Optional[Note]:
        """Load note by ID.

        Args:
            note_id: Note ID

        Returns:
            Note object or None if not found
        """
        if note_id not in self.index.notes:
            return None

        file_path = Path(self.index.notes[note_id]["file_path"])
        if not file_path.exists():
            return None

        return self._read_note_file(file_path)

    def _read_note_file(self, file_path: Path) -> Note:
        """Read note from file.

        Args:
            file_path: Path to note file

        Returns:
            Note object
        """
        with open(file_path) as f:
            post = frontmatter.load(f)

        return Note.from_frontmatter(post.metadata, post.content, file_path)

    def save_task(self, task: Task) -> Path:
        """Save task to file system.

        Args:
            task: Task to save

        Returns:
            Path where task was saved
        """
        # Update timestamp
        task.updated_at = datetime.now()

        # If task status changed, move file
        old_path = task.file_path
        new_path = self._get_task_path(task)

        if old_path and old_path != new_path and old_path.exists():
            # Move file to new status directory
            old_path.rename(new_path)
            task.file_path = new_path
        elif task.file_path is None:
            task.file_path = new_path

        # Create frontmatter document
        post = frontmatter.Post(task.description)
        post.metadata = task.to_frontmatter_dict()

        # Write to file
        task.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(task.file_path, "w") as f:
            f.write(frontmatter.dumps(post))

        # Update index
        self.index.add_task(task)
        self._save_index()

        # Git commit
        self.git.auto_commit(f"Add/update task: {task.title}", [task.file_path])

        return task.file_path

    def load_task(self, task_id: str) -> Optional[Task]:
        """Load task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task object or None if not found
        """
        if task_id not in self.index.tasks:
            return None

        file_path = Path(self.index.tasks[task_id]["file_path"])
        if not file_path.exists():
            return None

        return self._read_task_file(file_path)

    def _read_task_file(self, file_path: Path) -> Task:
        """Read task from file.

        Args:
            file_path: Path to task file

        Returns:
            Task object
        """
        with open(file_path) as f:
            post = frontmatter.load(f)

        return Task.from_frontmatter(post.metadata, post.content, file_path)

    def delete_note(self, note_id: str) -> bool:
        """Delete note.

        Args:
            note_id: Note ID

        Returns:
            True if deleted, False if not found
        """
        if note_id not in self.index.notes:
            return False

        file_path = Path(self.index.notes[note_id]["file_path"])
        if file_path.exists():
            file_path.unlink()

        self.index.remove_note(note_id)
        self._save_index()

        self.git.auto_commit(f"Delete note: {note_id}")

        return True

    def delete_task(self, task_id: str) -> bool:
        """Delete task.

        Args:
            task_id: Task ID

        Returns:
            True if deleted, False if not found
        """
        if task_id not in self.index.tasks:
            return False

        file_path = Path(self.index.tasks[task_id]["file_path"])
        if file_path.exists():
            file_path.unlink()

        self.index.remove_task(task_id)
        self._save_index()

        self.git.auto_commit(f"Delete task: {task_id}")

        return True

    def list_notes(
        self,
        tags: Optional[list[str]] = None,
        category: Optional[str] = None,
        project: Optional[str] = None,
    ) -> list[Note]:
        """List notes with optional filtering.

        Args:
            tags: Filter by tags (OR logic)
            category: Filter by category
            project: Filter by project

        Returns:
            List of notes
        """
        note_ids = set(self.index.notes.keys())

        # Filter by tags
        if tags:
            tag_ids = set()
            for tag in tags:
                if tag in self.index.tags:
                    tag_ids.update(self.index.tags[tag])
            note_ids &= tag_ids

        # Filter by category
        if category and category in self.index.categories:
            note_ids &= set(self.index.categories[category])

        # Filter by project
        if project and project in self.index.projects:
            note_ids &= set(self.index.projects[project])

        # Load notes
        notes = []
        for note_id in note_ids:
            note = self.load_note(note_id)
            if note:
                notes.append(note)

        # Sort by created date (newest first)
        notes.sort(key=lambda n: n.created_at, reverse=True)

        return notes

    def list_tasks(
        self,
        status: Optional[str] = None,
        tags: Optional[list[str]] = None,
        project: Optional[str] = None,
    ) -> list[Task]:
        """List tasks with optional filtering.

        Args:
            status: Filter by status
            tags: Filter by tags (OR logic)
            project: Filter by project

        Returns:
            List of tasks
        """
        task_ids = set(self.index.tasks.keys())

        # Filter by status
        if status:
            task_ids = {
                tid for tid in task_ids
                if self.index.tasks[tid]["status"] == status
            }

        # Filter by tags
        if tags:
            tag_ids = set()
            for tag in tags:
                if tag in self.index.tags:
                    tag_ids.update(self.index.tags[tag])
            task_ids &= tag_ids

        # Filter by project
        if project and project in self.index.projects:
            task_ids &= set(self.index.projects[project])

        # Load tasks
        tasks = []
        for task_id in task_ids:
            task = self.load_task(task_id)
            if task:
                tasks.append(task)

        # Sort by due date (earliest first), then priority
        tasks.sort(
            key=lambda t: (
                t.due_date or datetime.max,
                ["low", "medium", "high", "urgent"].index(t.priority.value),
            )
        )

        return tasks

    def search_notes(self, query: str) -> list[Note]:
        """Search notes by content.

        Args:
            query: Search query

        Returns:
            List of matching notes
        """
        query_lower = query.lower()
        matching_notes = []

        for note_id in self.index.notes.keys():
            note = self.load_note(note_id)
            if note and (
                query_lower in note.title.lower()
                or query_lower in note.content.lower()
            ):
                matching_notes.append(note)

        matching_notes.sort(key=lambda n: n.created_at, reverse=True)
        return matching_notes

    def rebuild_index(self) -> None:
        """Rebuild index by scanning all files."""
        self.index = MetadataIndex()

        # Scan notes
        for note_file in self.config.notes_dir.rglob("*.md"):
            try:
                note = self._read_note_file(note_file)
                self.index.add_note(note)
            except Exception as e:
                print(f"Error reading {note_file}: {e}")

        # Scan tasks
        for task_file in self.config.tasks_dir.rglob("*.md"):
            try:
                task = self._read_task_file(task_file)
                self.index.add_task(task)
            except Exception as e:
                print(f"Error reading {task_file}: {e}")

        self._save_index()


# Global storage instance
_storage: Optional[Storage] = None


def get_storage() -> Storage:
    """Get the global storage instance."""
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage
