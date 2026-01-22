"""Configuration management for brain."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class BrainConfig(BaseSettings):
    """Brainflow configuration with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Data directory
    brain_data_dir: Path = Field(
        default_factory=lambda: Path.home() / "Documents" / "brain"
    )

    # AI Provider settings
    ai_provider: str = Field(default="ollama", description="AI provider: openai, anthropic, ollama")

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"

    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-sonnet-20240229"

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama2"

    # Git settings
    git_auto_commit: bool = True

    # Default organization
    default_tags: list[str] = Field(default_factory=list)
    default_category: str = "general"

    @property
    def notes_dir(self) -> Path:
        """Directory for notes."""
        return self.brain_data_dir / "notes"

    @property
    def tasks_dir(self) -> Path:
        """Directory for tasks."""
        return self.brain_data_dir / "tasks"

    @property
    def projects_dir(self) -> Path:
        """Directory for project metadata."""
        return self.brain_data_dir / "projects"

    @property
    def metadata_dir(self) -> Path:
        """Directory for metadata."""
        return self.brain_data_dir / ".brain"

    @property
    def index_file(self) -> Path:
        """Path to index file."""
        return self.metadata_dir / "index.json"

    @property
    def config_file(self) -> Path:
        """User config file path."""
        return Path.home() / ".config" / "brainflow" / "config.yaml"

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.brain_data_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def save_config(self) -> None:
        """Save current configuration to user config file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        config_data = {
            "brain_data_dir": str(self.brain_data_dir),
            "ai_provider": self.ai_provider,
            "git_auto_commit": self.git_auto_commit,
            "default_tags": self.default_tags,
            "default_category": self.default_category,
        }
        with open(self.config_file, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)

    @classmethod
    def load_config(cls) -> "BrainConfig":
        """Load configuration from file and environment."""
        config = cls()

        # Load from user config file if it exists
        if config.config_file.exists():
            with open(config.config_file) as f:
                user_config = yaml.safe_load(f) or {}

            # Update with user config, converting paths to Path objects
            for key, value in user_config.items():
                if hasattr(config, key):
                    # Convert string paths to Path objects
                    if key == "brain_data_dir" and isinstance(value, str):
                        value = Path(value)
                    setattr(config, key, value)

        return config


# Global config instance
_config: Optional[BrainConfig] = None


def get_config() -> BrainConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = BrainConfig.load_config()
    return _config


def reload_config() -> BrainConfig:
    """Reload configuration from files and environment."""
    global _config
    _config = BrainConfig.load_config()
    return _config
