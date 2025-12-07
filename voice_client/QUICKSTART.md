# Quick Start Guide

Get up and running with the Voice Assistant in 5 minutes!

## 1. Install Dependencies

```bash
cd /home/green/code/claudia/claude_code_mcp/voice_client

# Run setup script
./setup.sh

# Or manually:
pip install -r requirements.txt
```

## 2. Set Up Environment

Make sure you have `XAI_API_KEY` in your `.env` file:

```bash
# If not already set, add to parent .env:
echo "XAI_API_KEY=your_key_here" >> ../.env
```

## 3. Test Components

Quick check to verify everything is installed:

```bash
python test_components.py --quick
```

Full test (requires microphone and speaker):

```bash
python test_components.py
```

## 4. Run the Assistant

### Voice Mode (Default)

```bash
python voice_assistant.py
```

Then just speak! The assistant will:
1. Listen to your voice
2. Send it to Grok-4 with Claude Code access
3. Speak the response back

### Text-Only Mode (No Voice)

Don't have a microphone or speaker? No problem!

```bash
python voice_assistant.py --text-only
```

Type your questions and read the responses. Perfect for:
- Systems without audio hardware
- Quiet environments
- When PyAudio isn't available
- Preference for typing over speaking

### Hybrid Modes

```bash
# Type questions, hear responses
python voice_assistant.py --no-stt

# Speak questions, read responses
python voice_assistant.py --no-tts
```

### Examples

Try different modes:

```bash
python example_usage.py      # Original examples
python text_mode_demo.py     # Text mode demos
```

## What Can You Ask?

### Code-Related Questions

- "What processes are running?"
- "List all environments"
- "Show me the logs for process 12345"
- "Switch to the voice demo environment"

### GitHub PR Questions

- "Get comments for PR number 42"
- "Show me all active pull requests"
- "Summarize the feedback on the latest PR"

### Claude Code Integration

- "Ask Claude to refactor the main function"
- "Have Claude review the changes in src/main.py"
- "Tell Claude to add error handling to the API endpoints"

### Environment Management

- "What's the current environment?"
- "Switch to the frontend project"
- "Run the development server"

## Troubleshooting

### No audio input/output

```bash
# Check if PyAudio is installed
python -c "import pyaudio; print('PyAudio OK')"

# Install system dependencies
sudo apt-get install portaudio19-dev  # Ubuntu/Debian
brew install portaudio                # macOS
```

### MCP server not responding

```bash
# Test the MCP server directly
curl https://dex-mcp.tunn.dev/mcp

# Or if running locally:
curl http://localhost:6030/mcp
```

### API key issues

```bash
# Check if API key is set
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Key:', os.getenv('XAI_API_KEY')[:10] + '...' if os.getenv('XAI_API_KEY') else 'NOT SET')"
```

## Architecture Diagram

```
┌─────────────┐
│   User      │
│  Speaks     │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│   Grok STT API      │
│   (WebSocket)       │
│  wss://api.x.ai/... │
└──────┬──────────────┘
       │ Transcript
       ▼
┌─────────────────────────────┐
│      Grok-4 Model           │
│   (with MCP Tools)          │
│                             │
│  ┌───────────────────────┐  │
│  │  Claude Code MCP      │  │
│  │  - ask_claude()       │  │
│  │  - list_processes()   │  │
│  │  - get_pr_comments()  │  │
│  │  - switch_env()       │  │
│  │  - etc.               │  │
│  └───────────────────────┘  │
└──────┬──────────────────────┘
       │ Response
       ▼
┌─────────────────────┐
│   Grok TTS API      │
│   (WebSocket)       │
│  wss://api.x.ai/... │
└──────┬──────────────┘
       │ Audio
       ▼
┌─────────────┐
│   Speaker   │
│  (PyAudio)  │
└─────────────┘
```

## Next Steps

- Read the [full README](README.md) for detailed documentation
- Check out [example_usage.py](example_usage.py) for more examples
- Explore the [reference implementations](../xai-voice-examples-main/)
- Review the [MCP tools](../src/main.py) available

## Common Commands

```bash
# Voice mode (default)
python voice_assistant.py

# Text-only mode (no voice)
python voice_assistant.py --text-only

# Hybrid: type input, hear output
python voice_assistant.py --no-stt --voice rex

# Hybrid: speak input, read output
python voice_assistant.py --no-tts

# Local MCP server
python voice_assistant.py --mcp-server http://localhost:6030/mcp

# Test individual components
python test_components.py --quick      # Quick library check
python test_components.py --stt-only   # Test just speech-to-text
python test_components.py --tts-only   # Test just text-to-speech
python test_components.py --mcp-only   # Test just MCP connection

# Run examples
python example_usage.py                # Original examples
python text_mode_demo.py              # Text mode demos
```

## Tips

1. **Speak clearly** - The STT works best with clear, natural speech
2. **Pause briefly** - The system auto-detects 2 seconds of silence to end input
3. **Be specific** - More specific questions get better answers
4. **Use commands** - Say "exit", "quit", or "goodbye" to stop
5. **Check logs** - If something fails, check the output for error messages

## Support

- Issues: [GitHub Issues](https://github.com/anthropics/claude-code/issues)
- Documentation: [Claude Code Docs](https://docs.anthropic.com/claude-code)
- xAI SDK: [xAI SDK Docs](https://github.com/xai-org/xai-sdk-python)

Happy voice coding! 🎤🤖
