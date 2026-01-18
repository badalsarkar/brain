# Brainflow

Terminal-based note-taking and work management system with AI integration.

## Features

- **📝 Quick Note Capture**: Capture thoughts instantly from the command line
- **✅ Task Management**: Time-based task prioritization (today, this week, overdue)
- **🎯 Focus View**: AI-powered dashboard showing what to work on
- **🤖 AI Integration**: Swappable AI providers (OpenAI, Anthropic, Ollama)
  - Auto-tagging
  - Content summarization
  - Focus suggestions
  - Task extraction from notes
- **💾 Git Integration**: Automatic version control for all your notes and tasks
- **🔍 Powerful Search**: Search by tags, categories, projects, or content
- **📊 Productivity Stats**: Track your progress and completion rates

## Installation

```bash
cd /home/bsarkar/Documents/code/brain
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Quick Start

1. **Initialize your workspace:**
   ```bash
   brainflow init
   ```

2. **Configure AI provider** (optional):
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Create your first note:**
   ```bash
   brainflow note "My first note with some content"
   ```

4. **Create a task:**
   ```bash
   brainflow task "Finish project documentation" --due tomorrow --priority high
   ```

5. **Check your focus view:**
   ```bash
   brainflow focus
   ```

## Configuration

Brainflow can be configured via:
- Environment variables (`.env` file)
- Config file (`~/.config/brainflow/config.yaml`)

### AI Providers

**Ollama (Local Models - Default):**
```bash
# Install Ollama: https://ollama.ai
ollama pull llama2
export AI_PROVIDER=ollama
```

**OpenAI:**
```bash
export AI_PROVIDER=openai
export OPENAI_API_KEY=your-key-here
```

**Anthropic (Claude):**
```bash
export AI_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your-key-here
```

## Usage

### Notes

```bash
# Quick capture
brainflow note "Quick thought"

# Interactive mode
brainflow note --interactive

# From stdin (pipe from other commands)
echo "Note content" | brainflow note --from-stdin

# List notes
brainflow notes list
brainflow notes list --tags work,important
brainflow notes list --project myproject

# Search notes
brainflow notes search "keyword"

# Show note
brainflow notes show <note-id>

# Edit note
brainflow notes edit <note-id>

# Delete note
brainflow notes delete <note-id>
```

### Tasks

```bash
# Create task
brainflow task "Do something" --due tomorrow --priority high

# Interactive mode
brainflow task --interactive

# List tasks
brainflow tasks list
brainflow tasks list --status todo
brainflow tasks list --project myproject

# Time-based views
brainflow tasks today
brainflow tasks week

# Mark as done
brainflow tasks done <task-id>

# Show task details
brainflow tasks show <task-id>
```

### Focus & Productivity

```bash
# Show focus dashboard (with AI suggestions)
brainflow focus

# Show without AI
brainflow focus --no-ai

# Show productivity stats
brainflow stats
```

### Utilities

```bash
# Show configuration
brainflow config

# Sync with git remote
brainflow sync
```

## File Organization

Notes and tasks are stored as markdown files with YAML frontmatter:

```
~/Documents/brain/
├── notes/
│   └── 2024/
│       └── 01/
│           └── 15/
│               └── my-note-abc123.md
├── tasks/
│   ├── todo/
│   │   └── my-task-def456.md
│   ├── in-progress/
│   └── done/
└── .brainflow/
    └── index.json
```

All files are human-readable and git-friendly!

## Examples

### Daily Workflow

```bash
# Morning: Check what to focus on
brainflow focus

# Capture a quick idea
brainflow note "Idea: Add dark mode to the app" --tags idea,feature

# Add a task from a meeting
brainflow task "Review PR #123" --due today --priority high --project backend

# End of day: Mark tasks as done
brainflow tasks done abc123

# Check stats
brainflow stats
```

### Using AI Features

```bash
# Auto-tag notes (enabled by default)
brainflow note "Meeting notes about the new authentication system..."
# AI will automatically suggest tags like: meeting, authentication, security

# Get AI focus suggestions
brainflow focus
# AI analyzes your tasks and suggests what to prioritize

# Extract tasks from notes
brainflow note "TODO: Update docs, fix bug in login, write tests"
# AI can extract these as separate tasks
```

### Git Integration

All changes are automatically committed (if `GIT_AUTO_COMMIT=true`):

```bash
brainflow note "Important note"
# Automatically commits: "Add/update note: Important note"

# Manual sync with remote
brainflow sync
```

## Development

Run tests:
```bash
pytest tests/ -v
```

Format code:
```bash
black brainflow/
```

Type checking:
```bash
mypy brainflow/
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please open an issue or PR.
