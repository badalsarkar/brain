"""Anthropic provider implementation."""

from typing import List

from anthropic import Anthropic

from brainflow.ai import AIProvider
from brainflow.config import get_config
from brainflow.models import Task


class AnthropicProvider(AIProvider):
    """Anthropic (Claude) implementation of AI provider."""

    def __init__(self):
        """Initialize Anthropic provider."""
        config = get_config()
        self.api_key = config.anthropic_api_key
        self.model = config.anthropic_model
        self.client = None

        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)

    def is_available(self) -> bool:
        """Check if Anthropic is available."""
        return self.client is not None

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Call Anthropic API.

        Args:
            system_prompt: System message
            user_prompt: User message

        Returns:
            API response text
        """
        if not self.client:
            return ""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            print(f"Anthropic API error: {e}")
            return ""

    def generate_tags(self, content: str, max_tags: int = 5) -> List[str]:
        """Generate tags using Claude."""
        system_prompt = (
            "You are a helpful assistant that generates relevant tags for text content. "
            f"Generate up to {max_tags} concise, lowercase tags separated by commas."
        )
        user_prompt = f"Generate tags for this content:\n\n{content[:1000]}"

        response = self._call_api(system_prompt, user_prompt)
        if not response:
            return []

        # Parse comma-separated tags
        tags = [tag.strip().lower() for tag in response.split(",")]
        return tags[:max_tags]

    def summarize(self, content: str, max_length: int = 200) -> str:
        """Summarize content using Claude."""
        system_prompt = (
            "You are a helpful assistant that creates concise summaries. "
            f"Create a summary of maximum {max_length} characters."
        )
        user_prompt = f"Summarize this content:\n\n{content}"

        return self._call_api(system_prompt, user_prompt)

    def suggest_focus(self, tasks: List[Task]) -> str:
        """Suggest focus using Claude."""
        if not tasks:
            return "No tasks to analyze."

        # Format tasks for the prompt
        task_list = []
        for task in tasks:
            due_info = f"Due: {task.due_date.strftime('%Y-%m-%d')}" if task.due_date else "No due date"
            task_list.append(
                f"- [{task.priority.value.upper()}] {task.title} ({due_info}) - {task.status.value}"
            )

        tasks_text = "\n".join(task_list)

        system_prompt = (
            "You are a productivity assistant. Analyze the given tasks and suggest "
            "which ones to focus on based on priority, due dates, and status. "
            "Provide actionable advice in 2-3 sentences."
        )
        user_prompt = f"Here are my current tasks:\n\n{tasks_text}\n\nWhat should I focus on?"

        return self._call_api(system_prompt, user_prompt)

    def extract_tasks(self, content: str) -> List[str]:
        """Extract tasks using Claude."""
        system_prompt = (
            "You are a helpful assistant that extracts actionable tasks from text. "
            "Return only the task descriptions, one per line, without numbering or bullets."
        )
        user_prompt = f"Extract actionable tasks from this content:\n\n{content}"

        response = self._call_api(system_prompt, user_prompt)
        if not response:
            return []

        # Split by newlines and clean up
        tasks = [line.strip() for line in response.split("\n") if line.strip()]
        return tasks
