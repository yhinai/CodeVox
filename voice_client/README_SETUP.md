# Voice Assistant - Setup Instructions

## ✅ Current Status

Your voice assistant is now **installed and ready to configure!**

- ✅ Virtual environment created
- ✅ All Python dependencies installed
- ✅ Text-only mode support added

## ⚠️ Action Required: Add Your XAI API Key

Before you can use the assistant, you need to add your xAI API key:

### Step 1: Get Your API Key

1. Go to https://console.x.ai/
2. Sign in (or create an account)
3. Navigate to API Keys
4. Create a new API key or copy your existing one

### Step 2: Add to .env File

Edit the file `/home/green/code/claudia/claude_code_mcp/.env` and replace:

```bash
XAI_API_KEY=your_key_here
```

With your actual key:

```bash
XAI_API_KEY=xai-abc123...
```

Or use this command:

```bash
# Replace YOUR_ACTUAL_KEY with your real key
echo "XAI_API_KEY=YOUR_ACTUAL_KEY" >> /home/green/code/claudia/claude_code_mcp/.env
```

## 🚀 Usage

Once your API key is set:

### Option 1: Use the launcher script (recommended)

```bash
cd /home/green/code/claudia/claude_code_mcp/voice_client

# Text-only mode (no microphone/speaker needed)
./run.sh --text-only

# Voice mode (requires microphone/speaker)
./run.sh

# Other options
./run.sh --help
```

### Option 2: Activate venv manually

```bash
cd /home/green/code/claudia/claude_code_mcp/voice_client
source venv/bin/activate

# Text-only mode
python3 voice_assistant.py --text-only

# Voice mode
python3 voice_assistant.py
```

## 🧪 Test Text Mode (Recommended First)

Start with text-only mode to test everything without needing audio:

```bash
cd /home/green/code/claudia/claude_code_mcp/voice_client
./run.sh --text-only
```

Then type your questions and press Enter!

Example interaction:
```
💬 Your message: list all environments
🤔 Asking Grok-4 (with Claude Code access)...
🔧 Calling tool: list_environments
📝 Response: [environment list here]
```

## 🎤 Voice Mode Setup (Optional)

If you want to use voice mode, you need PortAudio:

**Ubuntu/Debian:**
```bash
sudo apt-get install portaudio19-dev
```

**macOS:**
```bash
brew install portaudio
```

Then rebuild PyAudio in the venv:
```bash
source venv/bin/activate
pip uninstall pyaudio
pip install pyaudio
```

## 📚 Examples

After setting up your API key:

```bash
# Text-only mode (no voice)
./run.sh --text-only

# Type input, hear output
./run.sh --no-stt --voice rex

# Speak input, read output
./run.sh --no-tts

# Full voice mode
./run.sh --voice ara

# With custom MCP server
./run.sh --text-only --mcp-server http://localhost:6030/mcp

# Run demos
source venv/bin/activate
python3 text_mode_demo.py
```

## 🐛 Troubleshooting

### "Asking Grok-4..." hangs

This was your original issue. Possible causes:

1. **No API key** - Make sure XAI_API_KEY is set in .env
2. **Wrong API key** - Verify it's correct at https://console.x.ai
3. **Network issue** - Check internet connection
4. **MCP server down** - Try `curl https://dex-mcp.tunn.dev/mcp`

### Test API key is working

```bash
source venv/bin/activate
python3 -c "
import os
from dotenv import load_dotenv
from xai_sdk import Client

load_dotenv()
api_key = os.getenv('XAI_API_KEY')
if not api_key or api_key == 'your_key_here':
    print('❌ XAI_API_KEY not set or invalid')
else:
    print(f'✓ API key loaded (length: {len(api_key)})')
    try:
        client = Client(api_key=api_key)
        print('✓ Client created successfully')
    except Exception as e:
        print(f'❌ Error: {e}')
"
```

### Check dependencies

```bash
source venv/bin/activate
pip list | grep -E "(websockets|xai-sdk|dotenv)"
```

Should show:
- python-dotenv
- websockets
- xai-sdk

## 💡 Tips

1. **Start with text mode** - It's easier to debug and doesn't require audio hardware
2. **Use the launcher** - `./run.sh` automatically activates the venv
3. **Check the logs** - The assistant now shows detailed connection status
4. **Try local MCP** - If the remote MCP server is down, run it locally

## 📞 Getting Help

If you're still stuck:

1. Check that XAI_API_KEY is set correctly in .env
2. Try the test command above to verify API key
3. Try text-only mode first: `./run.sh --text-only`
4. Check https://console.x.ai/ for API status

## 🎉 Next Steps

Once working:

1. Try different queries: "list processes", "get PR comments", etc.
2. Explore the demos: `python3 text_mode_demo.py`
3. Try voice mode (if you have audio hardware)
4. Customize the MCP server URL for your setup

Happy coding! 🤖
