"""Data models for brain."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status enumeration."""

    TODO = "todo"
    IN_PROGRESS = "in-progress"
    DONE = "done"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    """Task priority enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Project(BaseModel):
    """Rich project model."""

    name: str # canonical name
    description: str = ""
    end_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    file_path: Optional[Path] = None

    def to_frontmatter_dict(self) -> dict:
        """Convert to dictionary for YAML frontmatter."""
        return {
            "name": self.name,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_frontmatter(cls, metadata: dict, content: str, file_path: Path) -> "Project":
        """Create Project from frontmatter metadata and content."""
        return cls(
            name=metadata.get("name", file_path.stem),
            description=content,
            end_date=datetime.fromisoformat(metadata["end_date"])
            if metadata.get("end_date")
            else None,
            created_at=datetime.fromisoformat(metadata["created_at"])
            if "created_at" in metadata
            else datetime.now(),
            updated_at=datetime.fromisoformat(metadata["updated_at"])
            if "updated_at" in metadata
            else datetime.now(),
            file_path=file_path,
        )


class Note(BaseModel):
    """Note model."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    category: str = "general"
    note_type: Optional[str] = None
    project: Optional[str] = None
    extra: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    file_path: Optional[Path] = None

    def to_frontmatter_dict(self) -> dict:
        """Convert to dictionary for YAML frontmatter."""
        base_dict = {
            "id": self.id,
            "title": self.title,
            "type": self.note_type,
            "tags": self.tags,
            "category": self.category,
            "project": self.project,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        # Merge extra fields
        base_dict.update(self.extra)
        return base_dict

    @classmethod
    def from_frontmatter(cls, metadata: dict, content: str, file_path: Path) -> "Note":
        """Create Note from frontmatter metadata and content."""
        # separate known fields from extra
        known_fields = {
            "id", "title", "type", "tags", "category", "project", "created_at", "updated_at"
        }
        extra = {k: v for k, v in metadata.items() if k not in known_fields}
        
        return cls(
            id=metadata.get("id", uuid4().hex[:8]),
            title=metadata.get("title", "Untitled"),
            content=content,
            note_type=metadata.get("type"),
            tags=metadata.get("tags", []),
            category=metadata.get("category", "general"),
            project=metadata.get("project"),
            extra=extra,
            created_at=datetime.fromisoformat(metadata["created_at"])
            if "created_at" in metadata
            else datetime.now(),
            updated_at=datetime.fromisoformat(metadata["updated_at"])
            if "updated_at" in metadata
            else datetime.now(),
            file_path=file_path,
        )


class Task(BaseModel):
    """Task model."""

    id: str = Field(default="0")
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    tags: list[str] = Field(default_factory=list)
    project: Optional[str] = None
    assignee: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    file_path: Optional[Path] = None

    def to_frontmatter_dict(self) -> dict:
        """Convert to dictionary for YAML frontmatter."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "tags": self.tags,
            "project": self.project,
            "assignee": self.assignee,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_frontmatter(cls, metadata: dict, content: str, file_path: Path) -> "Task":
        """Create Task from frontmatter metadata and content."""
        return cls(
            id=metadata.get("id", uuid4().hex[:8]),
            title=metadata.get("title", "Untitled Task"),
            description=content,
            status=TaskStatus(metadata.get("status", "todo")),
            priority=TaskPriority(metadata.get("priority", "medium")),
            due_date=datetime.fromisoformat(metadata["due_date"])
            if metadata.get("due_date")
            else None,
            tags=metadata.get("tags", []),
            project=metadata.get("project"),
            assignee=metadata.get("assignee"),
            created_at=datetime.fromisoformat(metadata["created_at"])
            if "created_at" in metadata
            else datetime.now(),
            updated_at=datetime.fromisoformat(metadata["updated_at"])
            if "updated_at" in metadata
            else datetime.now(),
            completed_at=datetime.fromisoformat(metadata["completed_at"])
            if metadata.get("completed_at")
            else None,
            file_path=file_path,
        )

    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.due_date is None or self.status == TaskStatus.DONE:
            return False
        return datetime.now() > self.due_date

    def days_until_due(self) -> Optional[int]:
        """Calculate days until due date."""
        if self.due_date is None:
            return None
        delta = self.due_date - datetime.now()
        return delta.days


class MetadataIndex(BaseModel):
    """Index of all notes and tasks for fast searching."""

    notes: dict[str, dict] = Field(default_factory=dict)  # id -> metadata
    tasks: dict[str, dict] = Field(default_factory=dict)  # id -> metadata
    tags: dict[str, list[str]] = Field(default_factory=dict)  # tag -> [ids]
    projects: dict[str, list[str]] = Field(default_factory=dict)  # project -> [ids]
    categories: dict[str, list[str]] = Field(default_factory=dict)  # category -> [ids]
    assignees: dict[str, list[str]] = Field(default_factory=dict)  # assignee -> [task_ids]
    last_updated: datetime = Field(default_factory=datetime.now)

    def add_note(self, note: Note) -> None:
        """Add note to index."""
        # Cleanup old index entries if note exists
        if note.id in self.notes:
            old_data = self.notes[note.id]
            
            # Check project change
            old_project = old_data.get("project")
            if old_project and old_project != note.project:
                if old_project in self.projects and note.id in self.projects[old_project]:
                    self.projects[old_project].remove(note.id)
                    if not self.projects[old_project]:  # Clean up empty
                        del self.projects[old_project]

            # Check tags change
            old_tags = old_data.get("tags", [])
            for tag in old_tags:
                if tag not in note.tags:
                    if tag in self.tags and note.id in self.tags[tag]:
                        self.tags[tag].remove(note.id)
                        if not self.tags[tag]:  # Clean up empty
                            del self.tags[tag]
                            
            # Check category change
            old_category = old_data.get("category")
            if old_category and old_category != note.category:
                 if old_category in self.categories and note.id in self.categories[old_category]:
                    self.categories[old_category].remove(note.id)
                    if not self.categories[old_category]:
                        del self.categories[old_category]

        # Update metadata storage
        self.notes[note.id] = {
            "title": note.title,
            "note_type": note.note_type,
            "tags": note.tags,
            "category": note.category,
            "project": note.project,
            "file_path": str(note.file_path) if note.file_path else None,
            "extra": note.extra,
            "created_at": note.created_at.isoformat(),
        }

        # Update tag index
        for tag in note.tags:
            if tag not in self.tags:
                self.tags[tag] = []
            if note.id not in self.tags[tag]:
                self.tags[tag].append(note.id)

        # Update project index
        if note.project:
            if note.project not in self.projects:
                self.projects[note.project] = []
            if note.id not in self.projects[note.project]:
                self.projects[note.project].append(note.id)

        # Update category index
        if note.category not in self.categories:
            self.categories[note.category] = []
        if note.id not in self.categories[note.category]:
            self.categories[note.category].append(note.id)

        self.last_updated = datetime.now()

    def add_task(self, task: Task) -> None:
        """Add task to index."""
        # Cleanup old index entries if task exists
        if task.id in self.tasks:
            old_data = self.tasks[task.id]
            
            # Check project change
            old_project = old_data.get("project")
            if old_project and old_project != task.project:
                if old_project in self.projects and task.id in self.projects[old_project]:
                    self.projects[old_project].remove(task.id)
                    if not self.projects[old_project]:
                        del self.projects[old_project]
                        
            # Check assignee change
            old_assignee = old_data.get("assignee")
            if old_assignee and old_assignee != task.assignee:
                 if old_assignee in self.assignees and task.id in self.assignees[old_assignee]:
                    self.assignees[old_assignee].remove(task.id)
                    if not self.assignees[old_assignee]:
                        del self.assignees[old_assignee]

            # Check tags change
            old_tags = old_data.get("tags", [])
            for tag in old_tags:
                if tag not in task.tags:
                    if tag in self.tags and task.id in self.tags[tag]:
                        self.tags[tag].remove(task.id)
                        if not self.tags[tag]:
                            del self.tags[tag]

        # Update metadata storage
        self.tasks[task.id] = {
            "title": task.title,
            "status": task.status.value,
            "priority": task.priority.value,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "tags": task.tags,
            "project": task.project,
            "assignee": task.assignee,
            "file_path": str(task.file_path) if task.file_path else None,
            "created_at": task.created_at.isoformat(),
        }

        # Update tag index
        for tag in task.tags:
            if tag not in self.tags:
                self.tags[tag] = []
            if task.id not in self.tags[tag]:
                self.tags[tag].append(task.id)

        # Update project index
        if task.project:
            if task.project not in self.projects:
                self.projects[task.project] = []
            if task.id not in self.projects[task.project]:
                self.projects[task.project].append(task.id)

        # Update assignee index
        if task.assignee:
            if task.assignee not in self.assignees:
                self.assignees[task.assignee] = []
            if task.id not in self.assignees[task.assignee]:
                self.assignees[task.assignee].append(task.id)

        self.last_updated = datetime.now()

    def remove_note(self, note_id: str) -> None:
        """Remove note from index."""
        if note_id in self.notes:
            note_data = self.notes[note_id]

            # Remove from tag index
            for tag in note_data.get("tags", []):
                if tag in self.tags and note_id in self.tags[tag]:
                    self.tags[tag].remove(note_id)

            # Remove from project index
            project = note_data.get("project")
            if project and project in self.projects and note_id in self.projects[project]:
                self.projects[project].remove(note_id)

            # Remove from category index
            category = note_data.get("category", "general")
            if category in self.categories and note_id in self.categories[category]:
                self.categories[category].remove(note_id)

            del self.notes[note_id]
            self.last_updated = datetime.now()

    def remove_task(self, task_id: str) -> None:
        """Remove task from index."""
        if task_id in self.tasks:
            task_data = self.tasks[task_id]

            # Remove from tag index
            for tag in task_data.get("tags", []):
                if tag in self.tags and task_id in self.tags[tag]:
                    self.tags[tag].remove(task_id)

            # Remove from project index
            project = task_data.get("project")
            if project and project in self.projects and task_id in self.projects[project]:
                self.projects[project].remove(task_id)

            del self.tasks[task_id]
            self.last_updated = datetime.now()
