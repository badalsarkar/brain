# Brain

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
   brain init
   ```

2. **Configure AI provider** (optional):
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Create your first note:**
   ```bash
   brain note "My first note with some content"
   ```

4. **Create a task:**
   ```bash
   brain task create "Finish project documentation ~tmrw ^high"
   ```

5. **Check your focus view:**
   ```bash
   brain focus
   ```

## Configuration

Brain can be configured via:
- Environment variables (`.env` file)
- Config file (`~/.config/brain/config.yaml`)

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
brain note "Quick thought"

# Interactive mode
brain note --interactive

# From stdin (pipe from other commands)
echo "Note content" | brain note --from-stdin

# List notes
brain notes list
brain notes list --tags work,important
brain notes list --project myproject

# Search notes
brain notes search "keyword"

# Show note
brain notes show <note-id>

# Edit note
brain notes edit <note-id>

# Delete note
brain notes delete <note-id>
```

### Tasks

```bash
# Create task
brain task create "Do something ~tmrw ^high"

# Interactive mode
brain task create -i

# Batch create
brain task create -b "Task one" "Task two ^high"

# List tasks
brain task list
brain task list --status todo
brain task list --project myproject

# Time-based views
brain task today
brain task week

# Mark as done
brain task done <task-id>

# Show task details
brain task show <task-id>
```

### Focus & Productivity

```bash
# Show focus dashboard (with AI suggestions)
brain focus

# Show without AI
brain focus --no-ai

# Show productivity stats
brain stats
```

### Utilities

```bash
# Show configuration
brain config

# Sync with git remote
brain sync
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
└── .brain/
    └── index.json
```

All files are human-readable and git-friendly!

## Examples

### Daily Workflow

```bash
# Morning: Check what to focus on
brain focus

# Capture a quick idea
brain note "Idea: Add dark mode to the app" --tags idea,feature

# Add a task from a meeting
brain task create "Review PR #123 ~today ^high @backend"

# End of day: Mark tasks as done
brain tasks done abc123

# Check stats
brain stats
```

### Using AI Features

```bash
# Auto-tag notes (enabled by default)
brain note "Meeting notes about the new authentication system..."
# AI will automatically suggest tags like: meeting, authentication, security

# Get AI focus suggestions
brain focus
# AI analyzes your tasks and suggests what to prioritize

# Extract tasks from notes
brain note "TODO: Update docs, fix bug in login, write tests"
# AI can extract these as separate tasks
```

### Git Integration

All changes are automatically committed (if `GIT_AUTO_COMMIT=true`):

```bash
brain note "Important note"
# Automatically commits: "Add/update note: Important note"

# Manual sync with remote
brain sync
```

## Development

Run tests:
```bash
pytest tests/ -v
```

Format code:
```bash
black brain/
```

Type checking:
```bash
mypy brain/
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please open an issue or PR.
