# Claude Code MCP Repository - Complete Analysis

---

## System Architecture Overview

```mermaid
graph TB
    subgraph "User Interfaces"
        Voice["🎤 Voice Assistant<br/>voice_client/"]
        Web["🌐 Web Agent<br/>xai-voice-examples/"]
        Phone["📞 Telephony<br/>Twilio Integration"]
    end
    
    subgraph "AI Layer"
        Grok["🤖 Grok-4<br/>xAI API"]
        Claude["🧠 Claude Code<br/>claude_agent_sdk"]
    end
    
    subgraph "MCP Server (Port 6030)"
        MCP["FastMCP Server<br/>src/main.py"]
        Tools["11 MCP Tools"]
    end
    
    subgraph "Infrastructure"
        Redis["📦 Redis<br/>State Management"]
        GitHub["🐙 GitHub API<br/>PR Comments"]
        Discord["💬 Discord<br/>Notifications"]
    end
    
    Voice --> Grok
    Web --> Grok
    Phone --> Grok
    Grok --> MCP
    MCP --> Claude
    MCP --> Redis
    MCP --> GitHub
    MCP --> Discord
```

---

## 1. Core MCP Server (`src/`)

### Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Grok as Grok-4 (xAI)
    participant MCP as MCP Server
    participant Claude as Claude Code
    participant Redis
    participant GH as GitHub

    User->>Grok: Voice/Text Query
    Grok->>MCP: Call ask_coder(query)
    MCP->>Claude: Send to Claude SDK
    Claude-->>MCP: Streaming Response
    MCP->>Redis: Store Messages
    MCP-->>Grok: Return Response
    Grok-->>User: Speak/Display Result
    
    Note over MCP,GH: Optional: PR Operations
    Grok->>MCP: Call get_pr_comments(pr_num)
    MCP->>GH: Fetch via PyGithub
    GH-->>MCP: PR Data
    MCP-->>Grok: JSON Response
```

---

### [main.py](file:///Users/alhinai/project/claude-code-mcp/src/main.py) - FastMCP Server

**Purpose**: Central HTTP server exposing Claude Code tools via MCP protocol.

```mermaid
graph LR
    subgraph "MCP Tools (11 total)"
        A[ask_coder] --> B[get_status]
        B --> C[pop_messages]
        
        D[list_environments] --> E[get_current_environment]
        E --> F[switch_environment]
        
        G[run_cmd] --> H[stop_cmd]
        H --> I[restart_cmd]
        
        J[get_pr_comments] --> K[get_active_pr_comments]
        K --> L[get_pr_info]
        L --> M[add_pr_comment_respond]
    end
```

| Tool | Arguments | Returns |
|------|-----------|---------|
| `ask_coder` | `query: str` | First response + background note |
| `get_status` | — | `bool` (is running) |
| `pop_messages` | — | JSON with all messages |
| `list_environments` | — | Formatted environment list |
| `switch_environment` | `environment_name: str` | Confirmation |
| `run_cmd` | — | PID of started process |
| `stop_cmd` | `pid: int, force: bool` | Confirmation |
| `restart_cmd` | `pid: int` | New PID |
| `get_pr_comments` | `pr_number: int` | JSON with comments |
| `get_pr_info` | `pr_number: int` | JSON with PR metadata |
| `add_pr_comment_respond` | `pr_number, comment_id, body` | JSON with reply |

---

### [claude.py](file:///Users/alhinai/project/claude-code-mcp/src/claude.py) - Claude SDK Integration

**Purpose**: Manages communication with Claude Code using the agent SDK.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Running: ask_claude_async()
    Running --> WaitingForFirst: Start background task
    WaitingForFirst --> CollectingMessages: First message received
    CollectingMessages --> CollectingMessages: More messages
    CollectingMessages --> Completed: ResultMessage received
    Completed --> Idle: Reset state
    
    WaitingForFirst --> Timeout: 30s timeout
    Timeout --> Idle
```

**Key Features**:
- `bypassPermissions` mode - auto-approves all Claude actions
- Background task pattern - returns immediately with first message
- Global message stack for `pop_messages()` retrieval
- Discord notification integration

---

### [process.py](file:///Users/alhinai/project/claude-code-mcp/src/process.py) - Process Management

**Purpose**: Run scripts in background, capture logs to Redis and filesystem.

```mermaid
flowchart TD
    A[start_process] --> B[Create subprocess]
    B --> C[Store in Redis<br/>process:PID:info]
    C --> D[Background stream task]
    D --> E{Read stdout}
    E -->|Data| F[Write to run.log]
    F --> G[Push to Redis<br/>process:PID:logs]
    G --> E
    E -->|EOF| H[Set exit_code]
    H --> I[Process complete]
```

**Redis Keys**:
- `process:{pid}:info` - Hash with cmd, cwd, started_at, exit_code
- `process:{pid}:logs` - List of JSON log entries

---

### [github.py](file:///Users/alhinai/project/claude-code-mcp/src/github.py) - GitHub Integration

**Purpose**: Fetch and respond to PR comments using PyGithub.

| Function | Description |
|----------|-------------|
| `fetch_review_comments()` | Code-line comments (position-based) |
| `fetch_issue_comments()` | General PR discussion |
| `fetch_pr_comments()` | Combined: both types |
| `fetch_pr_info()` | Full PR metadata (title, body, status, labels) |
| `respond_to_pr_comment()` | Create reply to review comment |

---

### [environment.py](file:///Users/alhinai/project/claude-code-mcp/src/environment.py) - Environment Config

**Purpose**: Load project environments from `envs.json`, manage Redis state.

```mermaid
graph LR
    A[envs.json] --> B[load_envs]
    B --> C{Environment}
    C --> D[name]
    C --> E[path]
    C --> F[run_script]
    C --> G[github_repo]
    C --> H[active_prs]
```

---

## 2. Voice Client (`voice_client/`)

### Voice Pipeline

```mermaid
flowchart LR
    subgraph Input
        Mic[🎤 Microphone]
    end
    
    subgraph "Speech-to-Text"
        STT[WebSocket<br/>wss://api.x.ai/v1/realtime/audio/transcriptions]
    end
    
    subgraph "Processing"
        Grok[Grok-4<br/>+ MCP Tools]
    end
    
    subgraph "Text-to-Speech"
        TTS[WebSocket<br/>wss://api.x.ai/v1/realtime/audio/speech]
    end
    
    subgraph Output
        Speaker[🔊 Speaker]
    end
    
    Mic --> STT
    STT --> Grok
    Grok --> TTS
    TTS --> Speaker
```

### [voice_assistant.py](file:///Users/alhinai/project/claude-code-mcp/voice_client/voice_assistant.py)

**Class: `VoiceAssistant`**

| Method | Purpose |
|--------|---------|
| `listen_once()` | Capture audio, send to STT, return transcript |
| `ask_grok_with_mcp()` | Send query to Grok-4 with MCP tool access |
| `speak()` | Convert text to speech via TTS WebSocket |
| `conversation_loop()` | Main loop: Listen → Process → Speak |

**Modes**:
```
python voice_assistant.py              # Full voice
python voice_assistant.py --text-only  # Text I/O
python voice_assistant.py --no-stt     # Type + Speak
python voice_assistant.py --no-tts     # Listen + Read
```

---

## 3. Voice Demos (`voice-demo-hackathon/`)

### [demo.py](file:///Users/alhinai/project/claude-code-mcp/voice-demo-hackathon/demo.py) - TTS with Voice Cloning

```mermaid
flowchart LR
    A[Input Text] --> B[voice_file.m4a]
    B --> C[Base64 Encode]
    C --> D[POST /text-to-speech/generate]
    D --> E[output.mp3]
```

### [demo_podcast.py](file:///Users/alhinai/project/claude-code-mcp/voice-demo-hackathon/demo_podcast.py) - Multi-Speaker

```mermaid
flowchart TD
    A[Define Speakers] --> B[Steve: steve-jobs.m4a]
    A --> C[Grant: grant.m4a]
    B --> D[Script with Turns]
    C --> D
    D --> E[POST /generate-podcast]
    E --> F[podcast.mp3]
```

---

## 4. xAI Examples (`xai-voice-examples-main/`)

### Architecture Comparison

````carousel
```mermaid
graph TB
    subgraph "WebSocket Architecture"
        B1[Browser] <-->|WebSocket| B2[Backend<br/>Python/Node.js]
        B2 <-->|WebSocket| B3[xAI API]
    end
```
<!-- slide -->
```mermaid
graph TB
    subgraph "WebRTC Architecture"
        R1[Browser] <-->|DataChannel| R2[Server<br/>Node.js]
        R2 <-->|WebSocket| R3[xAI API]
    end
```
<!-- slide -->
```mermaid
graph TB
    subgraph "Telephony Architecture"
        T1[Phone] <-->|SIP| T2[Twilio]
        T2 <-->|WebSocket| T3[Server]
        T3 <-->|WebSocket| T4[xAI API]
    end
```
````

### Directory Structure

| Path | Type | Description |
|------|------|-------------|
| `examples/agent/web/client/` | React + Vite | Browser frontend |
| `examples/agent/web/xai/backend-python/` | FastAPI | WebSocket proxy |
| `examples/agent/web/xai/backend-nodejs/` | Express | WebSocket proxy |
| `examples/agent/webrtc/server/` | Node.js | WebRTC relay server |
| `examples/agent/telephony/xai/` | Node.js | Twilio integration |
| `examples/stt/python/` | Python | Audio → Text |
| `examples/tts/python/` | Python | Text → Audio |

---

## 5. Configuration

### [envs.json](file:///Users/alhinai/project/claude-code-mcp/envs.json)

```json
{
  "environments": {
    "default": {
      "name": "Project Name",
      "path": "/path/to/project",
      "run_script": "bash run.sh",
      "github_repo": "owner/repo",
      "active_prs": [{"pr_num": 1, "branch_name": "feature"}]
    }
  },
  "current_env": ""
}
```

---

## 6. Requirements Summary

```mermaid
graph TD
    subgraph "MCP Server"
        M1[Python 3.10+]
        M2[Redis Server]
        M3[fastmcp, uvicorn, redis]
        M4[PyGithub, discord.py]
        M5[claude_agent_sdk]
    end
    
    subgraph "Voice Client"
        V1[xai-sdk]
        V2[websockets]
        V3[pyaudio + portaudio]
    end
    
    subgraph "Environment Variables"
        E1[XAI_API_KEY ★]
        E2[GH_TOKEN]
        E3[DISCORD_TOKEN]
        E4[REDIS_HOST]
    end
```

---

## Quick Start Commands

```bash
# 1. MCP Server
redis-server &
cd src && python main.py

# 2. Voice Assistant
cd voice_client
export XAI_API_KEY="your-key"
python voice_assistant.py

# 3. xAI Examples
cd xai-voice-examples-main/examples/tts/python
./start.sh
```
