# Voice Assistant for Claude Code

A comprehensive voice-powered assistant that integrates:
- 🎤 **Grok STT** (Speech-to-Text) for voice input
- 🤖 **Grok-4** with MCP tools for intelligent responses
- 🔧 **Claude Code MCP** for code assistance
- 🔊 **Grok TTS** (Text-to-Speech) for voice output

## Architecture

```
User Speech → Grok STT → Grok-4 (with Claude Code MCP) → Grok TTS → Speaker
```

The assistant listens to your voice, transcribes it using Grok's STT API, sends the query to Grok-4 which can use Claude Code's MCP tools (like `ask_claude`, `list_processes`, `get_pr_comments`, etc.), and then speaks the response back to you using Grok's TTS API.

## Installation

### 1. Install python3 Dependencies

```bash
cd /home/green/code/claudia/claude_code_mcp/voice_client
pip install -r requirements.txt
```

### 2. Install PyAudio (System Dependencies)

**Ubuntu/Debian:**
```bash
sudo apt-get install portaudio19-dev python33-pyaudio
pip install pyaudio
```

**macOS:**
```bash
brew install portaudio
pip install pyaudio
```

**Windows:**
```bash
pip install pipwin
pipwin install pyaudio
```

### 3. Set Up Environment Variables

Create a `.env` file in the voice_client directory or use the existing one in the parent directory:

```bash
XAI_API_KEY=your_xai_api_key_here
```

## Usage

### Basic Voice Mode (Default)

```bash
python3 voice_assistant.py
```

This will:
1. Start listening for your voice
2. Transcribe your speech to text
3. Send it to Grok-4 with access to Claude Code MCP tools
4. Speak the response back to you

### Text-Only Mode (No Voice)

Perfect when you don't have a microphone/speaker or prefer typing:

```bash
python3 voice_assistant.py --text-only
```

This mode:
- Uses keyboard for input (type your questions)
- Displays responses as text on screen
- No PyAudio required
- Great for headless servers or quiet environments

### Hybrid Modes

**Text input, voice output:**
```bash
python3 voice_assistant.py --no-stt
```
Type your questions, hear the responses.

**Voice input, text output:**
```bash
python3 voice_assistant.py --no-tts
```
Speak your questions, read the responses on screen.

### Custom Voice

```bash
python3 voice_assistant.py --voice rex
```

Available voices: `ara` (default, female), `rex` (male), `sal`, `eve`, `una`, `leo`

### Custom MCP Server

If you're running the MCP server locally:

```bash
python3 voice_assistant.py --mcp-server http://localhost:6030/mcp
```

### Different Grok Model

```bash
python3 voice_assistant.py --model grok-4-1
```

### All Options

```bash
# Voice mode with all options
python3 voice_assistant.py \
  --mcp-server http://localhost:6030/mcp \
  --voice rex \
  --model grok-4-1-fast \
  --no-interim-stt

# Text-only mode (no microphone/speaker needed)
python3 voice_assistant.py --text-only

# Hybrid: Type input, hear output
python3 voice_assistant.py --no-stt --voice ara

# Hybrid: Speak input, read output
python3 voice_assistant.py --no-tts
```

### Command-Line Options

- `--text-only` - Disable both voice input and output (pure text mode)
- `--no-stt` - Disable voice input (use keyboard instead)
- `--no-tts` - Disable voice output (text only)
- `--voice <name>` - Choose TTS voice (ara, rex, sal, eve, una, leo)
- `--model <name>` - Choose Grok model (default: grok-4-1-fast)
- `--mcp-server <url>` - MCP server URL
- `--no-interim-stt` - Disable interim transcription results

## How It Works

### 1. Speech-to-Text (STT)

The assistant uses Grok's streaming STT API via WebSocket:
- Captures audio from your microphone using PyAudio
- Sends audio chunks to `wss://api.x.ai/v1/realtime/audio/transcriptions`
- Receives real-time transcripts (interim and final)
- Auto-stops after 2 seconds of silence

### 2. Grok-4 with MCP Tools

Uses the xAI SDK to create a chat with MCP tool access:
- Sends your transcribed query to Grok-4
- Grok-4 can call Claude Code MCP tools like:
  - `ask_claude(query)` - Ask Claude Code questions
  - `list_processes()` - List running processes
  - `get_process_logs(pid)` - Get process logs
  - `get_pr_comments(pr_number)` - Get PR comments
  - `switch_environment(name)` - Switch Claude Code environment
  - And many more (see main.py for full list)
- Streams the response in real-time

### 3. Text-to-Speech (TTS)

Converts the response to audio using Grok's streaming TTS API:
- Sends text to `wss://api.x.ai/v1/realtime/audio/speech`
- Receives audio chunks in real-time
- Plays audio immediately using PyAudio

## Example Conversation

```
🎤 Listening... (Speak now)
💭 What processes are running
✅ What processes are running

🤔 Asking Grok-4 (with Claude Code access)...

🔧 Calling tool: list_processes
   Args: {}

📝 Response:
There are currently 2 managed processes:
1. PID 12345 - Running the web server (runtime: 45.2s)
2. PID 12346 - Running the build script (runtime: 12.1s)

📊 Usage: 1523 tokens

🔊 Speaking response...
✅ Done speaking
```

## MCP Tools Available

The assistant has access to all Claude Code MCP tools:

### Claude Code Interaction
- `ask_claude(query)` - Ask Claude Code a question
- `get_status()` - Check if Claude is processing
- `pop_messages()` - Get Claude's intermediate messages

### Environment Management
- `list_environments()` - List all project environments
- `get_current_environment()` - Get current environment
- `switch_environment(name)` - Switch to a project
- `run_project(name)` - Run a project's script

### Process Management
- `run_cmd()` - Start run.sh in background
- `stop_cmd(pid)` - Stop a process
- `restart_cmd(pid)` - Restart a process
- `list_processes()` - List all processes
- `get_process_logs(pid, tail)` - Get process logs

### GitHub Integration
- `get_pr_comments(pr_number)` - Get PR comments
- `get_active_pr_comments()` - Get all active PR comments
- `get_pr_info(pr_number)` - Get PR information

### System
- `set_env(key, value)` - Set environment variable
- `get_env(key)` - Get environment variable
- `list_env()` - List all environment variables

## Troubleshooting

### PyAudio Installation Issues

**Linux:** If you get `portaudio.h not found`:
```bash
sudo apt-get install portaudio19-dev
```

**macOS:** If you get build errors:
```bash
brew install portaudio
pip install --global-option='build_ext' --global-option='-I/opt/homebrew/include' --global-option='-L/opt/homebrew/lib' pyaudio
```

### No Microphone Detected

Check available audio devices:
```python3
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    print(p.get_device_info_by_index(i))
```

### WebSocket Connection Errors

- Check your XAI_API_KEY is set correctly
- Ensure you have internet connectivity
- Verify the API endpoint is accessible

### MCP Server Not Responding

- Check if the MCP server is running: `curl https://dex-mcp.tunn.dev/mcp`
- If running locally, make sure it's on port 6030
- Verify the URL includes `/mcp` at the end

## Advanced Usage

### Custom Silence Threshold

Edit `voice_assistant.py` and change:
```python3
silence_threshold = 2.0  # seconds of silence before stopping
```

### Save Audio to File

Modify the `speak()` method to save audio:
```python3
import wave

# After collecting audio_bytes
with wave.open("output.wav", "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(self.tts_sample_rate)
    wf.writeframes(audio_bytes)
```

### Non-Interactive Mode

For single query:
```python3
assistant = VoiceAssistant()
transcript = await assistant.listen_once()
response = await assistant.ask_grok_with_mcp(transcript)
await assistant.speak(response)
```

## References

- [xAI Voice Examples](../xai-voice-examples-main/)
- [Claude Code MCP Server](../src/main.py)
- [xAI SDK Documentation](https://github.com/xai-org/xai-sdk-python3)
- [MCP Specification](https://spec.modelcontextprotocol.io/)

## License

Same as parent project.
