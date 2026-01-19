"""AI provider abstraction layer."""

from abc import ABC, abstractmethod
from typing import List

from brain.models import Task


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    def generate_tags(self, content: str, max_tags: int = 5) -> List[str]:
        """Generate tags for content.

        Args:
            content: Text content to analyze
            max_tags: Maximum number of tags to generate

        Returns:
            List of suggested tags
        """
        pass

    @abstractmethod
    def summarize(self, content: str, max_length: int = 200) -> str:
        """Summarize content.

        Args:
            content: Text content to summarize
            max_length: Maximum length of summary

        Returns:
            Summary text
        """
        pass

    @abstractmethod
    def suggest_focus(self, tasks: List[Task]) -> str:
        """Suggest which tasks to focus on.

        Args:
            tasks: List of tasks to analyze

        Returns:
            Focus suggestion text
        """
        pass

    @abstractmethod
    def extract_tasks(self, content: str) -> List[str]:
        """Extract potential tasks from content.

        Args:
            content: Text content to analyze

        Returns:
            List of extracted task descriptions
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the AI provider is available and configured.

        Returns:
            True if available, False otherwise
        """
        pass
