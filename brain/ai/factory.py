"""AI provider factory."""

from typing import Optional

from brain.ai import AIProvider
from brain.ai.openai_provider import OpenAIProvider
from brain.ai.anthropic_provider import AnthropicProvider
from brain.ai.ollama_provider import OllamaProvider
from brain.config import get_config


class NoOpProvider(AIProvider):
    """No-op provider when AI is not configured."""

    def is_available(self) -> bool:
        return False

    def generate_tags(self, content: str, max_tags: int = 5) -> list[str]:
        return []

    def summarize(self, content: str, max_length: int = 200) -> str:
        return ""

    def suggest_focus(self, tasks: list) -> str:
        return "AI provider not configured."

    def extract_tasks(self, content: str) -> list[str]:
        return []


def create_ai_provider() -> AIProvider:
    """Create AI provider based on configuration.

    Returns:
        Configured AI provider instance
    """
    config = get_config()
    provider_name = config.ai_provider.lower()

    if provider_name == "openai":
        provider = OpenAIProvider()
        if provider.is_available():
            return provider
        print("Warning: OpenAI provider not available (check API key)")

    elif provider_name == "anthropic":
        provider = AnthropicProvider()
        if provider.is_available():
            return provider
        print("Warning: Anthropic provider not available (check API key)")

    elif provider_name == "ollama":
        provider = OllamaProvider()
        if provider.is_available():
            return provider
        print("Warning: Ollama provider not available (is Ollama running?)")

    else:
        print(f"Warning: Unknown AI provider '{provider_name}'")

    # Fallback to no-op provider
    return NoOpProvider()


# Global AI provider instance
_ai_provider: Optional[AIProvider] = None


def get_ai_provider() -> AIProvider:
    """Get the global AI provider instance."""
    global _ai_provider
    if _ai_provider is None:
        _ai_provider = create_ai_provider()
    return _ai_provider
