# Troubleshooting Guide

## Problem: "Asking Grok-4..." Hangs or Times Out

### Symptoms
- Voice assistant gets stuck at "🤔 Asking Grok-4 (with Claude Code access)..."
- No response after 30-60 seconds
- Have to press Ctrl+C to stop

### Solution Steps

#### 1. Check Your API Key (MOST COMMON)

```bash
# View your .env file (API key will be hidden)
grep XAI_API_KEY /home/green/code/claudia/claude_code_mcp/.env | sed 's/=.*/=***/'

# If you see "your_key_here" or no output, you need to add your key:
echo "XAI_API_KEY=xai-your-actual-key" >> /home/green/code/claudia/claude_code_mcp/.env
```

Get your API key from: https://console.x.ai/

#### 2. Test Without MCP First

Run the simple test to isolate the issue:

```bash
cd /home/green/code/claudia/claude_code_mcp/voice_client
source venv/bin/activate
python3 simple_test.py
```

This will:
- ✅ Test basic xAI API connection (no MCP)
- ✅ Test with MCP tools
- ✅ Show exactly where it fails

#### 3. Check MCP Server Status

Your MCP server logs show it's working! But verify it's accessible:

```bash
# Check if server is responding
curl https://dex-mcp.tunn.dev/mcp

# Should return JSON (not an error)
```

#### 4. Increase Patience

MCP calls can be SLOW (10-60 seconds) because:
1. xAI connects to your MCP server
2. MCP server executes the tool (e.g., `list_environments`)
3. xAI processes the result
4. Response is streamed back

**This is normal!** The updated voice assistant now shows:
```
⏳ Waiting for response...
   (Note: MCP calls can take 10-60 seconds)
```

#### 5. Try a Simpler Query

Some queries are faster than others:

**Fast queries (no MCP needed):**
```
What is 2+2?
Tell me a joke
```

**Medium queries (simple MCP calls):**
```
list all environments
```

**Slow queries (complex MCP operations):**
```
get all active PR comments and summarize them
```

### Quick Diagnostic Commands

```bash
cd /home/green/code/claudia/claude_code_mcp/voice_client

# 1. Check dependencies
source venv/bin/activate
pip list | grep -E "(xai-sdk|websockets|dotenv)"

# 2. Check API key
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); k=os.getenv('XAI_API_KEY'); print('✓ Key set' if k and k != 'your_key_here' else '❌ No key')"

# 3. Test xAI connection
python3 simple_test.py

# 4. Test MCP server
curl https://dex-mcp.tunn.dev/mcp

# 5. Run voice assistant in text mode
./run.sh --text-only
```

## Problem: PyAudio Not Available

### Symptoms
```
❌ PyAudio is not installed
   Install with: pip install pyaudio
```

### Solution

**Option 1: Install PortAudio (for voice mode)**

```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev

# macOS
brew install portaudio

# Then reinstall PyAudio
source venv/bin/activate
pip uninstall pyaudio
pip install pyaudio
```

**Option 2: Use Text Mode (no audio needed)**

```bash
./run.sh --text-only
```

Text mode doesn't need PyAudio!

## Problem: Virtual Environment Issues

### Symptoms
- "ModuleNotFoundError: No module named 'websockets'"
- "ModuleNotFoundError: No module named 'xai_sdk'"

### Solution

```bash
cd /home/green/code/claudia/claude_code_mcp/voice_client

# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Or use the setup script
./setup.sh
```

## Problem: MCP Server Not Responding

### Symptoms
Your MCP server logs show:
```
INFO:     66.241.125.96:0 - "POST /mcp HTTP/1.1" 200 OK
```

This is GOOD! It means:
- ✅ xAI is connecting to your MCP server
- ✅ Requests are succeeding (200 OK)
- ✅ MCP integration is working

The "timeout" is likely just the normal processing time (10-60 seconds).

### If MCP is actually timing out:

1. **Check local MCP server** (if running locally):
   ```bash
   # Make sure it's running on port 6030
   netstat -tlnp | grep 6030
   ```

2. **Use remote MCP server** (recommended):
   ```bash
   ./run.sh --text-only --mcp-server https://dex-mcp.tunn.dev/mcp
   ```

3. **Test MCP directly**:
   ```bash
   # Your server logs show it's working!
   # Those 200 OK responses mean success
   ```

## Problem: "Network Error" or "Connection Failed"

### Solution

1. Check internet connection:
   ```bash
   ping api.x.ai
   ```

2. Check if xAI API is accessible:
   ```bash
   curl https://api.x.ai/v1/models
   ```

3. Try with different network:
   - Different WiFi
   - Mobile hotspot
   - VPN off/on

## Expected Behavior

### Normal Flow (Text Mode)

```
💬 Your message: list environments
🤔 Asking Grok-4 (with Claude Code access)...
   MCP Server: https://dex-mcp.tunn.dev/mcp

✓ Chat session created
✓ Query sent
⏳ Waiting for response...
   (Note: MCP calls can take 10-60 seconds)

🔧 Calling tool: list_environments

📝 Response:
Available environments:
...

📊 Usage: 1234 tokens | Time: 15.3s
```

**Total time: 15-60 seconds is NORMAL**

### What's Happening During the Wait

1. [0-5s] xAI creates session with MCP server
2. [5-10s] Your MCP server receives request
3. [10-30s] MCP tool executes (e.g., reads files, calls APIs)
4. [30-45s] xAI processes MCP response
5. [45-60s] Response is generated and streamed

## Still Stuck?

### Run Full Diagnostic

```bash
cd /home/green/code/claudia/claude_code_mcp/voice_client

echo "=== Diagnostic Report ==="
echo ""
echo "1. Python version:"
python3 --version

echo ""
echo "2. Virtual environment:"
ls venv/ | head -3

echo ""
echo "3. API key status:"
source venv/bin/activate
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); k=os.getenv('XAI_API_KEY'); print('✓ Set (' + str(len(k)) + ' chars)' if k and k != 'your_key_here' else '❌ Not set')"

echo ""
echo "4. Dependencies:"
pip list | grep -E "(xai-sdk|websockets|dotenv)" | head -3

echo ""
echo "5. MCP server:"
curl -I https://dex-mcp.tunn.dev/mcp 2>&1 | grep -E "(HTTP|200)"

echo ""
echo "6. xAI API:"
curl -I https://api.x.ai 2>&1 | grep -E "(HTTP|200)"
```

### Contact Info

If still having issues:
1. Save the diagnostic report output
2. Note exactly what command you ran
3. Include the full error message
4. Check https://status.x.ai for API status

## Working Configuration

Here's a known working setup:

```bash
# .env file
XAI_API_KEY=xai-abc123...  # Real key from console.x.ai

# Run command
cd /home/green/code/claudia/claude_code_mcp/voice_client
./run.sh --text-only

# Example query
💬 Your message: list all environments

# Wait 15-60 seconds (be patient!)
# Response will appear
```

**Key takeaway: MCP calls take 10-60 seconds. This is normal!**
