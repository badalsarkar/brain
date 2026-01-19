"""Git integration utilities for brain."""

import subprocess
from pathlib import Path
from typing import Optional

from git import Repo, InvalidGitRepositoryError
from git.exc import GitCommandError
from gitdb.exc import BadName

from brain.config import get_config


class GitManager:
    """Manage git operations for brain."""

    def __init__(self, repo_path: Optional[Path] = None):
        """Initialize git manager.

        Args:
            repo_path: Path to git repository. Defaults to data directory.
        """
        self.repo_path = repo_path or get_config().brain_data_dir
        self.repo: Optional[Repo] = None
        self._init_repo()

    def _init_repo(self) -> None:
        """Initialize or open git repository."""
        try:
            self.repo = Repo(self.repo_path)
        except InvalidGitRepositoryError:
            # Not a git repo, initialize if auto-commit is enabled
            config = get_config()
            if config.git_auto_commit:
                self.repo = Repo.init(self.repo_path)
                self._create_gitignore()
                self.commit("Initial commit - brain setup")

    def _create_gitignore(self) -> None:
        """Create .gitignore file in the data directory."""
        gitignore_path = self.repo_path / ".gitignore"
        if not gitignore_path.exists():
            gitignore_content = """# Brainflow metadata
.brain/
"""
            gitignore_path.write_text(gitignore_content)

    def is_repo(self) -> bool:
        """Check if directory is a git repository."""
        return self.repo is not None

    def commit(self, message: str, files: Optional[list[Path]] = None) -> bool:
        """Commit changes to git.

        Args:
            message: Commit message
            files: Specific files to commit. If None, commits all changes.

        Returns:
            True if commit was successful, False otherwise
        """
        if not self.repo:
            return False

        try:
            # Add files
            if files:
                self.repo.index.add([str(f.relative_to(self.repo_path)) for f in files])
            else:
                self.repo.git.add(A=True)

            # Check if there are changes to commit
            # Handle case when there are no commits yet (no HEAD)
            try:
                has_changes = bool(self.repo.index.diff("HEAD") or self.repo.untracked_files)
            except (GitCommandError, BadName):
                # No HEAD yet, check if there are any files staged
                has_changes = bool(self.repo.untracked_files)

            if not has_changes:
                return False

            # Commit
            self.repo.index.commit(message)
            return True
        except GitCommandError as e:
            print(f"Git commit failed: {e}")
            return False

    def auto_commit(self, message: str, files: Optional[list[Path]] = None) -> bool:
        """Auto-commit if enabled in config.

        Args:
            message: Commit message
            files: Specific files to commit

        Returns:
            True if commit was successful or auto-commit disabled, False on error
        """
        config = get_config()
        if not config.git_auto_commit:
            return True

        return self.commit(message, files)

    def status(self) -> str:
        """Get git status.

        Returns:
            Git status output
        """
        if not self.repo:
            return "Not a git repository"

        try:
            return self.repo.git.status()
        except GitCommandError as e:
            return f"Error getting status: {e}"

    def has_changes(self) -> bool:
        """Check if there are uncommitted changes.

        Returns:
            True if there are changes, False otherwise
        """
        if not self.repo:
            return False

        return bool(self.repo.index.diff(None) or self.repo.untracked_files)

    def sync(self) -> tuple[bool, str]:
        """Sync with remote (pull and push).

        Returns:
            Tuple of (success, message)
        """
        if not self.repo:
            return False, "Not a git repository"

        try:
            # Check if remote exists
            if not self.repo.remotes:
                return False, "No remote configured"

            origin = self.repo.remotes.origin

            # Pull changes
            origin.pull()

            # Push changes
            origin.push()

            return True, "Synced successfully"
        except GitCommandError as e:
            return False, f"Sync failed: {e}"


# Global git manager instance
_git_manager: Optional[GitManager] = None


def get_git_manager() -> GitManager:
    """Get the global git manager instance."""
    global _git_manager
    if _git_manager is None:
        _git_manager = GitManager()
    return _git_manager
