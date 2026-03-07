# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/path/to/test_file.py::test_name -v

# Format code (line length: 100)
black brain/

# Lint
ruff check brain/

# Type checking
mypy brain/
```

## Architecture

**brain** is a CLI tool (`brain.cli:main`) built with Click + Rich for terminal UI. Data lives in `~/Documents/brain/` (configurable via `BRAIN_DATA_DIR`).

### Data Flow

1. **CLI** (`cli.py`) — Click commands delegate to domain modules (`notes.py`, `tasks.py`, `projects.py`, `focus.py`)
2. **Domain modules** call **Storage** (`storage.py`) for persistence
3. **Storage** writes markdown files with YAML frontmatter and maintains a JSON index (`~/.../brain/.brain/index.json`) for fast lookups; also calls `GitManager` for auto-commits
4. **AI** (`brain/ai/`) provides optional enrichment — `factory.py` exposes a singleton `get_ai_provider()` that returns the configured provider (openai/anthropic/ollama) or a `NoOpProvider` fallback

### Key Modules

- `models.py` — Pydantic models: `Note`, `Task`, `Project`, `MetadataIndex`. All have `to_frontmatter_dict()` / `from_frontmatter()` for serialization.
- `storage.py` — `Storage` class: reads/writes markdown files; notes organized as `notes/YYYY/MM/DD/title-id.md`, tasks as `tasks/<status>/title-id.md`
- `config.py` — `BrainConfig` (pydantic-settings): reads from `.env` and `~/.config/brain/config.yaml`; key env vars: `AI_PROVIDER`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_HOST`, `GIT_AUTO_COMMIT`
- `git_utils.py` — wraps GitPython for auto-committing changes to the data directory
- `focus.py` — dashboard combining task priority logic + AI suggestions

### Adding a New AI Provider

Implement the `AIProvider` ABC from `brain/ai/__init__.py` (methods: `is_available`, `generate_tags`, `summarize`, `suggest_focus`, `extract_tasks`), then register it in `factory.py`.
