"""Ollama provider implementation for local models."""

from typing import List

import ollama

from brain.ai import AIProvider
from brain.config import get_config
from brain.models import Task


class OllamaProvider(AIProvider):
    """Ollama implementation for local AI models."""

    def __init__(self):
        """Initialize Ollama provider."""
        config = get_config()
        self.host = config.ollama_host
        self.model = config.ollama_model
        self.client = None

        try:
            # Test connection
            ollama.list()
            self.client = ollama
        except Exception:
            pass

    def is_available(self) -> bool:
        """Check if Ollama is available."""
        return self.client is not None

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Call Ollama API.

        Args:
            system_prompt: System message
            user_prompt: User message

        Returns:
            API response text
        """
        if not self.client:
            return ""

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response["message"]["content"]
        except Exception as e:
            print(f"Ollama API error: {e}")
            return ""

    def generate_tags(self, content: str, max_tags: int = 5) -> List[str]:
        """Generate tags using Ollama."""
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
        """Summarize content using Ollama."""
        system_prompt = (
            "You are a helpful assistant that creates concise summaries. "
            f"Create a summary of maximum {max_length} characters."
        )
        user_prompt = f"Summarize this content:\n\n{content}"

        return self._call_api(system_prompt, user_prompt)

    def suggest_focus(self, tasks: List[Task]) -> str:
        """Suggest focus using Ollama."""
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
        """Extract tasks using Ollama."""
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
