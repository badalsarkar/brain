"""Project management operations."""

from datetime import datetime
from typing import Optional

from brain.models import Project, ProjectStatus
from brain.storage import get_storage
from brain.utils import parse_date


def create_project(
    name: str,
    description: str = "",
    end_date: Optional[str] = None,
) -> Project:
    """Create a new project.

    Args:
        name: Project name
        description: Project description
        end_date: Optional end date (string)

    Returns:
        Created project
    """
    storage = get_storage()
    
    # Canonicalize name
    name = storage.get_canonical_project(name)
    
    # Check if project metadata already exists
    existing = storage.get_project(name)
    if existing:
        # Update existing metadata if needed or raise?
        # User said "create a new project", let's assume update description/date if already exists
        # or maybe we should return it?
        # Standard behavior for "create" in this app seems to be "upsert" or just overwrite.
        project = existing
        if description:
            project.description = description
        if end_date:
            project.end_date = parse_date(end_date)
    else:
        parsed_end_date = None
        if end_date:
            parsed_end_date = parse_date(end_date)
            
        project = Project(
            name=name,
            description=description,
            end_date=parsed_end_date
        )

    # Save to storage
    storage.save_project(project)
    
    return project


def get_project(name: str) -> Optional[Project]:
    """Get project by name."""
    storage = get_storage()
    return storage.get_project(name)


def set_project_status(name: str, status: str) -> Optional[Project]:
    """Set a project's status.

    Args:
        name: Project name
        status: New status value (active, archived, completed)

    Returns:
        Updated project or None if not found/created
    """
    storage = get_storage()
    canonical = storage.get_canonical_project(name)

    project = storage.get_project(canonical)
    if not project:
        # Create metadata if project exists in index but has no metadata file
        if canonical in storage.index.projects:
            project = Project(name=canonical)
        else:
            return None

    project.status = ProjectStatus(status)
    storage.save_project(project)
    return project
