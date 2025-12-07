# Claude Code MCP - Lean Edition

A **minimal, elegant** MCP server for Claude Code with voice assistant capabilities.

```
╔══════════════════════════════════════════════════════════════╗
║  ✅ No Redis required                                        ║
║  ✅ Single pyproject.toml for all dependencies               ║
║  ✅ Unified CLI for voice assistant                          ║
║  ✅ Class-based architecture with structlog                  ║
╚══════════════════════════════════════════════════════════════╝
```

## Quick Start

```bash
# Install
pip install -e .

# Run MCP Server
python -m src.main

# Run Voice Assistant
XAI_API_KEY=your-key python -m client.main start --text-only
```

## Directory Structure

```
claude-code-mcp/
├── src/                    # MCP Server
│   ├── main.py             # FastMCP entry point (11 tools)
│   ├── config.py           # Pydantic settings
│   ├── claude.py           # Claude SDK (class-based)
│   ├── environment.py      # Environment management
│   ├── github.py           # GitHub PR tools
│   └── process.py          # Background process management
├── client/                 # Voice Assistant
│   ├── main.py             # Typer CLI
│   └── assistant.py        # VoiceAssistant class
├── pyproject.toml          # Dependencies
├── envs.json               # Project environments
└── .env.example            # Environment variables template
```

## MCP Tools (11)

| Tool | Description |
|------|-------------|
| `ask_coder` | Send query to Claude Code |
| `get_status` | Check if Claude is running |
| `pop_messages` | Get intermediate messages |
| `list_environments` | List project configs |
| `get_current_env` | Get active environment |
| `switch_environment` | Change environment |
| `run_cmd` | Start background process |
| `stop_cmd` | Stop process by PID |
| `restart_cmd` | Restart process |
| `get_pr_comments` | Fetch PR comments |
| `add_pr_comment_respond` | Reply to PR comment |

## Voice Assistant Modes

```bash
# Full voice (mic + speaker)
python -m client.main start

# Text only
python -m client.main start --text-only

# Type input, hear output
python -m client.main start --no-stt

# Speak input, read output
python -m client.main start --no-tts

# Different voice
python -m client.main start --voice rex
```

## Configuration

Create `.env` file:

```bash
XAI_API_KEY=your-xai-key
GH_TOKEN=your-github-token  # Optional
```

Edit `envs.json` for project environments:

```json
{
  "environments": {
    "myproject": {
      "name": "My Project",
      "path": "/path/to/project",
      "run_script": "npm run dev",
      "github_repo": "user/repo"
    }
  }
}
```

## Requirements

- Python 3.10+
- PyAudio (for voice): `brew install portaudio && pip install pyaudio`

## License

MIT
