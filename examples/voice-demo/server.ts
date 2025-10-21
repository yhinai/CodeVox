// Load environment variables from .env file
import dotenv from 'dotenv';
dotenv.config();

// Debug environment loading
console.log('🔧 Environment variable debug:');
console.log(`   OPENAI_API_KEY: ${process.env.OPENAI_API_KEY ? 'Set ✅' : 'Not set ❌'}`);
console.log(`   .env file path: ${process.cwd()}/.env`);

import express from 'express';
import { createServer } from 'http';
import { createServer as createHttpsServer } from 'https';
import { readFileSync } from 'fs';
import { WebSocketServer } from 'ws';
import { WebRTCBridgeServer } from '@gillinghammer/realtime-mcp-core';
import type { WebRTCBridgeConfig } from '@gillinghammer/realtime-mcp-core';
import cors from 'cors';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const PORT = parseInt(process.env.PORT || '8085');
const HOST = process.env.HOST || 'localhost';
const USE_HTTPS = process.env.USE_HTTPS === 'true' || false;

// Validate required environment variables
if (!process.env.OPENAI_API_KEY) {
  console.error('\n❌ ERROR: Missing required environment variable');
  console.error('📝 Please create a .env file in the project root with:');
  console.error('   OPENAI_API_KEY=sk-proj-your-api-key-here');
  console.error('   HUBSPOT_TOKEN=your-hubspot-token-here (optional)');
  console.error('\n🔗 Get your OpenAI API key from: https://platform.openai.com/api-keys');
  process.exit(1);
}

// MCP Provider Configurations
interface MCPProvider {
  id: string;
  name: string;
  description: string;
  icon: string;
  config: WebRTCBridgeConfig['mcp'];
  instructions: string;
  requiredEnvVars: string[];
  voiceCommands: string[];
}

const MCP_PROVIDERS: MCPProvider[] = [
  {
    id: 'claudecode',
    name: 'Claude Code Controller',
    description: 'Control Claude Code SDK operations including session management, code queries, and environment switching',
    icon: '🤖',
    config: {
      command: '/home/green/py312/bin/python3',
      args: ['/home/green/code/claudia/main.py'],
      env: {},
      timeout: 60000, // Increased timeout for code operations
    },
    instructions: `You are a helpful Claude Code assistant. You can help users with:
- Creating and managing sessions for stateful operations
- Running Claude Code queries to write, read, and analyze code
- Managing environments and switching between projects
- Executing bash scripts and getting git diffs
- Storing and retrieving data in sessions
- Incrementing counters and tracking operations

IMPORTANT: Keep ALL responses under 2000 characters. Be concise and conversational for voice. When Claude Code returns results, summarize the key points briefly. Focus on what was accomplished rather than reading entire code outputs.`,
    requiredEnvVars: [],
    voiceCommands: [
      'Create a new session called test',
      'List all my sessions',
      'Ask Claude to write a hello world function in Python',
      'Get the server status',
      'Show me the git diff',
      'List available environments'
    ]
  }
];

// Global state
let activeBridge: WebRTCBridgeServer | null = null;
let currentProvider: string | null = null;
let discoveredTools: any[] = [];
let isConnecting = false;
let connectionLogs: string[] = [];
let wsClients: Set<any> = new Set();

// Express app
const app = express();
app.use(cors());
app.use(express.json());

// Create HTTP or HTTPS server for WebSocket
let httpServer;
if (USE_HTTPS) {
  try {
    const httpsOptions = {
      key: readFileSync(join(process.cwd(), 'certs', 'key.pem')),
      cert: readFileSync(join(process.cwd(), 'certs', 'cert.pem'))
    };
    httpServer = createHttpsServer(httpsOptions, app);
    console.log('🔒 HTTPS enabled');
  } catch (error: any) {
    console.error('❌ Failed to load SSL certificates, falling back to HTTP:', error?.message || error);
    httpServer = createServer(app);
  }
} else {
  httpServer = createServer(app);
}

const wss = new WebSocketServer({ server: httpServer });

// WebSocket for real-time updates
wss.on('connection', (ws) => {
  wsClients.add(ws);
  
  // Send current state
  ws.send(JSON.stringify({
    type: 'state',
    data: {
      providers: getProvidersWithStatus(),
      currentProvider,
      discoveredTools,
      isConnecting,
      logs: connectionLogs.slice(-50) // Last 50 log entries
    }
  }));
  
  ws.on('close', () => {
    wsClients.delete(ws);
  });
});

// Broadcast to all WebSocket clients
function broadcast(message: any) {
  const data = JSON.stringify(message);
  wsClients.forEach(ws => {
    if (ws.readyState === 1) { // OPEN
      ws.send(data);
    }
  });
}

// Add log entry and broadcast
function addLog(message: string, type: 'info' | 'error' | 'success' = 'info') {
  const timestamp = new Date().toISOString().substr(11, 8);
  const logEntry = `[${timestamp}] ${message}`;
  connectionLogs.push(logEntry);
  
  // Keep only last 100 entries
  if (connectionLogs.length > 100) {
    connectionLogs = connectionLogs.slice(-100);
  }
  
  console.log(logEntry);
  
  broadcast({
    type: 'log',
    data: { message: logEntry, type }
  });
}

function getProvidersWithStatus() {
  return MCP_PROVIDERS.map(provider => {
    const missingEnvVars = provider.requiredEnvVars.filter(envVar => !process.env[envVar]);
    return {
      ...provider,
      available: missingEnvVars.length === 0,
      missingEnvVars,
      config: undefined // Don't expose config in API
    };
  });
}

// API Routes
app.get('/api/providers', (req, res) => {
  res.json({
    providers: getProvidersWithStatus(),
    currentProvider,
    discoveredTools,
    isConnecting
  });
});

app.post('/api/connect/:providerId', async (req, res) => {
  const { providerId } = req.params;
  
  if (isConnecting) {
    return res.status(400).json({ error: 'Connection in progress' });
  }
  
  try {
    const provider = MCP_PROVIDERS.find(p => p.id === providerId);
    if (!provider) {
      return res.status(404).json({ error: 'Provider not found' });
    }
    
    // Check required environment variables
    const missingEnvVars = provider.requiredEnvVars.filter(envVar => !process.env[envVar]);
    if (missingEnvVars.length > 0) {
      return res.status(400).json({ 
        error: 'Missing required environment variables',
        missingEnvVars 
      });
    }
    
    isConnecting = true;
    discoveredTools = [];
    
    broadcast({
      type: 'state',
      data: { isConnecting: true, discoveredTools: [] }
    });
    
    console.log('\n🎯 ===== STARTING CONNECTION =====');
    addLog(`🚀 Starting connection to ${provider.name}...`, 'info');
    
    // Stop current bridge if running
    if (activeBridge) {
      addLog(`🛑 Stopping current bridge (${currentProvider})`, 'info');
      await activeBridge.stop();
      activeBridge = null;
    }
    
    // Create bridge config without WebRTC server (we'll handle that separately)
    const bridgeConfig: WebRTCBridgeConfig = {
      openai: {
        apiKey: process.env.OPENAI_API_KEY!,
        model: 'gpt-4o-realtime-preview-2024-12-17',
        voice: 'alloy',
        instructions: provider.instructions,
      },
      mcp: provider.config,
      server: {
        port: PORT + 100, // Use a different port to avoid conflicts
        host: HOST,
        cors: true,
      },
      debug: {
        enabled: process.env.DEBUG === 'true',
        logTools: false, // Disable verbose tool logging during connection
        logFunctionCalls: process.env.DEBUG_FUNCTIONS === 'true',
      },
    };
    
    addLog(`🔧 Creating WebRTC bridge on port ${PORT + 100}...`, 'info');
    activeBridge = new WebRTCBridgeServer(bridgeConfig);
    
    addLog(`🚀 Starting bridge server...`, 'info');
    await activeBridge.start();
    
    // Get tools from the MCP API after connection
    try {
      const toolsResponse = await fetch(`http://${HOST}:${PORT + 100}/tools`);
      if (toolsResponse.ok) {
        const toolsData = await toolsResponse.json();
        discoveredTools = toolsData.tools || [];
        addLog(`✅ Connected! Discovered ${discoveredTools.length} tools`, 'success');
      } else {
        addLog(`⚠️ Connected but couldn't fetch tools`, 'info');
      }
    } catch (error) {
      addLog(`⚠️ Connected but couldn't fetch tools: ${error}`, 'info');
    }
    
    currentProvider = providerId;
    isConnecting = false;
    
    // Broadcast the updated state
    broadcast({
      type: 'state',
      data: { 
        currentProvider: providerId,
        discoveredTools,
        isConnecting: false
      }
    });
    
    addLog(`🎙️ Voice interface ready at http://${HOST}:${PORT + 100}/demo`, 'success');
    console.log('🎯 ===== CONNECTION SUCCESSFUL =====\n');

    res.json({
      success: true,
      provider: provider.name,
      tools: discoveredTools,
      voiceUrl: `http://${HOST}:${PORT + 100}/demo`,
      bridgeUrl: `http://${HOST}:${PORT + 100}`
    });
    
  } catch (error) {
    isConnecting = false;
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    const fullError = error instanceof Error ? error.stack : error;
    
    // Log to both our system and stderr for visibility
    addLog(`❌ CRITICAL ERROR: Failed to connect to ${providerId}`, 'error');
    addLog(`💥 Error details: ${errorMessage}`, 'error');
    console.error('\n🚨 ===== CONNECTION ERROR =====');
    console.error(`Provider: ${providerId}`);
    console.error(`Error: ${errorMessage}`);
    console.error(`Full stack:`, fullError);
    console.error('🚨 =============================\n');
    
    broadcast({
      type: 'state',
      data: { isConnecting: false }
    });
    
    res.status(500).json({ 
      error: 'Failed to start bridge',
      message: errorMessage,
      provider: providerId
    });
  }
});

app.post('/api/disconnect', async (req, res) => {
  try {
    if (activeBridge) {
      addLog(`🛑 Disconnecting from ${currentProvider}...`, 'info');
      await activeBridge.stop();
      activeBridge = null;
    }
    
    currentProvider = null;
    discoveredTools = [];
    isConnecting = false;
    
    broadcast({
      type: 'state',
      data: {
        currentProvider: null,
        discoveredTools: [],
        isConnecting: false
      }
    });
    
    addLog(`✅ Disconnected successfully`, 'success');
    
    res.json({ success: true });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    addLog(`❌ Disconnect failed: ${errorMessage}`, 'error');
    res.status(500).json({ error: errorMessage });
  }
});

app.get('/api/status', (req, res) => {
  res.json({
    currentProvider,
    discoveredTools,
    isConnecting,
    bridgeRunning: activeBridge?.isServerRunning() || false,
    bridgeUrl: activeBridge ? `http://${HOST}:${PORT + 100}` : null,
    logs: connectionLogs.slice(-20)
  });
});

// Serve static files (for audio)
app.use('/static', express.static('.'));

// Serve the main interface
app.get('/', (req, res) => {
  res.send(getMainHTML());
});

// Graceful shutdown
process.on('SIGINT', async () => {
  console.log('\n🛑 Shutting down gracefully...');
  if (activeBridge) {
    await activeBridge.stop();
  }
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\n🛑 Shutting down gracefully...');
  if (activeBridge) {
    await activeBridge.stop();
  }
  process.exit(0);
});

// Start the server
httpServer.listen(PORT, HOST, () => {
  const protocol = USE_HTTPS ? 'https' : 'http';
  console.log('\n🎙️ Realtime MCP Voice Demo');
  console.log('============================');
  console.log(`🌐 Interface: ${protocol}://${HOST}:${PORT}`);
  if (USE_HTTPS) {
    console.log('🔒 Running with HTTPS (self-signed certificate)');
    console.log('⚠️  You may need to accept the security warning in your browser');
  }
  console.log('\n📋 Available Providers:');
  
  MCP_PROVIDERS.forEach(provider => {
    const missingEnvVars = provider.requiredEnvVars.filter(envVar => !process.env[envVar]);
    const status = missingEnvVars.length === 0 ? '✅' : '❌';
    console.log(`   ${status} ${provider.icon} ${provider.name}`);
    if (missingEnvVars.length > 0) {
      console.log(`      Missing: ${missingEnvVars.join(', ')}`);
    }
  });
  
  console.log('\n🚀 Ready! Open the interface to get started.');
});

function getMainHTML(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎙️ Realtime MCP Voice Demo</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #fafbfc;
            min-height: 100vh;
            color: #2c3e50;
            padding: 24px;
            line-height: 1.5;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            text-align: left;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .header h1 {
            font-size: 1.875rem;
            margin-bottom: 4px;
            font-weight: 600;
            color: #1a202c;
            letter-spacing: -0.025em;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 300px 1fr 400px;
            gap: 24px;
            margin-bottom: 24px;
            height: calc(60vh);
        }

        .terminal-section {
            margin-top: 24px;
            height: calc(30vh);
        }

        /* Mobile and Tablet Responsive Styles */
        @media (max-width: 1200px) {
            .main-content {
                grid-template-columns: 250px 1fr 350px;
            }
        }

        @media (max-width: 992px) {
            body {
                padding: 16px;
            }

            .header h1 {
                font-size: 1.5rem;
            }

            .main-content {
                grid-template-columns: 1fr;
                grid-template-rows: auto auto auto;
                height: auto;
                gap: 16px;
            }

            .panel.provider-panel {
                height: auto;
                order: 1;
            }

            .panel:nth-child(2) {
                order: 3;
                height: 400px;
            }

            .panel.file-explorer {
                order: 2;
                height: 300px;
            }

            .terminal-section {
                height: 300px;
            }
        }

        @media (max-width: 768px) {
            body {
                padding: 12px;
            }

            .header {
                margin-bottom: 20px;
                padding-bottom: 16px;
            }

            .header h1 {
                font-size: 1.25rem;
            }

            .header p {
                font-size: 14px;
            }

            .panel {
                padding: 16px;
            }

            .btn {
                padding: 12px 16px;
                font-size: 16px;
                min-height: 44px;
            }

            .control-buttons {
                flex-direction: column;
            }

            .control-buttons .btn {
                width: 100%;
            }

            .provider-select {
                padding: 14px 16px;
                font-size: 16px;
                min-height: 44px;
            }

            .transcript-item.user {
                margin-left: 8px;
            }

            .transcript-item.assistant {
                margin-right: 8px;
            }

            .message.user {
                margin-left: 8px;
            }

            .message.assistant {
                margin-right: 8px;
            }
        }

        @media (max-width: 480px) {
            body {
                padding: 8px;
            }

            .header h1 {
                font-size: 1.125rem;
            }

            .panel {
                padding: 12px;
            }

            .panel h2 {
                font-size: 1rem;
            }

            .thinking-indicator {
                bottom: 16px;
                right: 16px;
                padding: 10px 16px;
                font-size: 14px;
            }

            .modal-content,
            .tool-response-content {
                width: 95%;
                margin: 10% auto;
                padding: 16px;
            }

            .file-explorer,
            .panel:nth-child(2) {
                height: 250px;
            }

            .terminal-section {
                height: 250px;
            }
        }
        
        .panel {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        .panel.provider-panel {
            height: 634px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }
        
        .panel h2 {
            margin: 0 0 20px 0;
            font-size: 1.125rem;
            font-weight: 600;
            color: #1a202c;
            padding-bottom: 12px;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .panel.transcript-panel {
            height: 634px;
            display: flex;
            flex-direction: column;
        }
        
        .provider-section h2 {
            margin-bottom: 20px;
            color: #1a202c;
            font-size: 1.125rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .provider-select {
            width: 100%;
            padding: 12px 16px;
            border: 1px solid #d1d5db;
            border-radius: 4px;
            font-size: 14px;
            background: white;
            color: #374151;
            margin-bottom: 12px;
        }
        
        .provider-select:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        
        .control-buttons {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }
        
        .btn {
            padding: 8px 16px;
            border: 1px solid transparent;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        
        .btn-primary {
            background: #3b82f6;
            color: white;
            border-color: #3b82f6;
        }
        
        .btn-primary:hover:not(:disabled) {
            background: #2563eb;
            border-color: #2563eb;
        }
        
        .btn-secondary {
            background: white;
            color: #374151;
            border-color: #d1d5db;
        }
        
        .btn-secondary:hover:not(:disabled) {
            background: #f9fafb;
            border-color: #9ca3af;
        }
        
        .btn-danger {
            background: #ef4444;
            color: white;
            border-color: #ef4444;
        }
        
        .btn-danger:hover:not(:disabled) {
            background: #dc2626;
            border-color: #dc2626;
        }
        
        .btn:disabled {
            background: #f3f4f6;
            color: #9ca3af;
            border-color: #e5e7eb;
            cursor: not-allowed;
        }
        
        .provider-info {
            background: #f8fafc;
            padding: 16px;
            border-radius: 4px;
            border: 1px solid #e2e8f0;
            margin-bottom: 16px;
            display: none;
        }
        
        .provider-info.active {
            display: block;
        }
        
        .status {
            padding: 12px 16px;
            border-radius: 4px;
            margin-bottom: 16px;
            font-weight: 500;
            font-size: 14px;
            border: 1px solid transparent;
        }
        
        .status.connected {
            background: #f0fdf4;
            color: #166534;
            border-color: #bbf7d0;
        }
        
        .status.connecting {
            background: #fffbeb;
            color: #92400e;
            border-color: #fed7aa;
        }
        
        .status.disconnected {
            background: #fef2f2;
            color: #991b1b;
            border-color: #fecaca;
        }
        

        

        

        

        
        .voice-status {
            font-weight: 600;
            margin: 10px 0;
        }
        
        .voice-status.connecting {
            color: #856404;
        }
        
        .voice-status.connected {
            color: #155724;
        }
        
        .voice-status.listening {
            color: #2196f3;
            background: rgba(33, 150, 243, 0.1);
            animation: pulse 2s infinite;
        }
        
        .voice-status.paused {
            color: #9e9e9e;
            background: rgba(158, 158, 158, 0.1);
        }
        
        .voice-status.error {
            color: #721c24;
        }
        
        .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .voice-commands {
            margin-top: 12px;
            text-align: left;
        }
        
        .voice-commands h4 {
            margin-bottom: 8px;
            color: #374151;
            font-size: 14px;
            font-weight: 500;
        }
        
        .voice-commands ul {
            list-style: none;
            padding: 0;
        }
        
        .voice-commands li {
            background: #f1f5f9;
            border: 1px solid #e2e8f0;
            padding: 8px 12px;
            margin-bottom: 4px;
            border-radius: 4px;
            font-style: italic;
            color: #64748b;
            font-size: 13px;
        }
        
        .available-tools {
            margin-top: 16px;
        }
        
        .available-tools h4 {
            margin-bottom: 8px;
            color: #374151;
            font-size: 14px;
            font-weight: 500;
        }
        
        .tools-list-inline {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        
        .tool-item-inline {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            color: #64748b;
            border-left: 3px solid #3b82f6;
        }
        
        .tool-item-inline .tool-name {
            font-weight: 600;
            color: #374151;
            font-size: 13px;
        }
        
        .conversation {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 16px;
            margin-top: 16px;
            max-height: 300px;
            overflow-y: auto;
            text-align: left;
        }
        
        .message {
            margin-bottom: 12px;
            padding: 12px 16px;
            border-radius: 4px;
            border: 1px solid transparent;
        }
        
        .message.user {
            background: #eff6ff;
            border-color: #dbeafe;
            margin-left: 24px;
        }
        
        .message.assistant {
            background: #f0fdf4;
            border-color: #bbf7d0;
            margin-right: 24px;
        }
        
        .message.system {
            background: #f8fafc;
            border-color: #e2e8f0;
            color: #64748b;
            font-size: 13px;
        }
        
        .message-sender {
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            margin-bottom: 4px;
            letter-spacing: 0.05em;
        }
        
        /* Modal styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.4);
        }
        
        .modal-content {
            background-color: white;
            margin: 5% auto;
            padding: 24px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            width: 90%;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .modal-title {
            font-size: 1.125rem;
            font-weight: 600;
            color: #1a202c;
        }
        
        .close {
            color: #9ca3af;
            font-size: 24px;
            font-weight: bold;
            cursor: pointer;
            border: none;
            background: none;
            padding: 4px;
        }
        
        .close:hover {
            color: #374151;
        }
        
        /* Transcript panel */
        .transcript {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 16px;
            flex: 1;
            overflow-y: auto;
            scroll-behavior: smooth;
        }
        
        .transcript-item {
            margin-bottom: 16px;
            padding: 12px 16px;
            border-radius: 4px;
            border: 1px solid transparent;
            font-size: 14px;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        
        .transcript-item.user {
            background: #eff6ff;
            border-color: #dbeafe;
            margin-left: 24px;
            margin-right: 0;
        }
        
        .transcript-item.assistant {
            background: #f0fdf4;
            border-color: #bbf7d0;
            margin-right: 24px;
            margin-left: 0;
        }
        
        .transcript-item.tool {
            background: #f8fafc;
            border-color: #e2e8f0;
            margin-left: 12px;
            margin-right: 12px;
            font-size: 13px;
        }
        
        .transcript-sender {
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            margin-bottom: 4px;
            letter-spacing: 0.05em;
        }
        
        .tool-call-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }
        
        .tool-name {
            font-weight: 600;
            color: #374151;
        }
        
        .tool-status {
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
        }
        
        .tool-status.starting {
            background: #fed7aa;
            color: #92400e;
        }
        
        .tool-status.success {
            background: #bbf7d0;
            color: #166534;
        }
        
        .tool-status.error {
            background: #fecaca;
            color: #991b1b;
        }
        
        .tool-args {
            color: #64748b;
            font-size: 12px;
            margin-top: 4px;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        
        /* Tool response modal */
        .tool-response-modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.4);
        }
        
        .tool-response-content {
            background-color: white;
            margin: 5% auto;
            padding: 24px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            width: 90%;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .tool-response-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .tool-response-title {
            font-size: 1.125rem;
            font-weight: 600;
            color: #1a202c;
        }
        
        .tool-response-body {
            font-family: 'SF Mono', Monaco, Inconsolata, 'Roboto Mono', monospace;
            font-size: 13px;
            line-height: 1.5;
        }
        
        .tool-response-section {
            margin-bottom: 16px;
        }
        
        .tool-response-section h4 {
            margin-bottom: 8px;
            color: #374151;
            font-size: 14px;
            font-weight: 600;
        }
        
        .tool-response-json {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 12px;
            white-space: pre-wrap;
            overflow-x: auto;
        }

        /* VSCode-like Code Editor */
        .code-editor {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.5;
            padding: 16px;
            overflow: auto;
            border-radius: 4px;
            height: 100%;
        }

        .code-editor pre {
            margin: 0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .code-line {
            display: block;
            padding: 0 4px;
        }

        .code-line:hover {
            background: #2a2a2a;
        }

        .file-explorer {
            background: #252526;
            color: #cccccc;
            overflow-y: auto;
            height: 100%;
        }

        .file-item {
            padding: 6px 12px;
            cursor: pointer;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .file-item:hover {
            background: #2a2d2e;
        }

        .file-item.active {
            background: #37373d;
            color: #ffffff;
        }

        .file-icon {
            font-size: 16px;
        }

        .thinking-indicator {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #3b82f6;
            color: white;
            padding: 12px 24px;
            border-radius: 24px;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
            display: none;
            align-items: center;
            gap: 12px;
            font-weight: 500;
            z-index: 1000;
            animation: slideIn 0.3s ease;
        }

        .thinking-indicator.active {
            display: flex;
        }

        @keyframes slideIn {
            from {
                transform: translateY(100px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        .thinking-spinner {
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        .audio-permission-notice {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(59, 130, 246, 0.95);
            color: white;
            padding: 24px 32px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            display: none;
            z-index: 2000;
            text-align: center;
            max-width: 90%;
        }

        .audio-permission-notice.active {
            display: block;
        }

        .audio-permission-notice h3 {
            margin: 0 0 12px 0;
            font-size: 1.25rem;
        }

        .audio-permission-notice p {
            margin: 0 0 16px 0;
            font-size: 1rem;
        }

        .audio-permission-notice button {
            background: white;
            color: #3b82f6;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }

        @media (max-width: 768px) {
            .audio-permission-notice {
                padding: 20px 24px;
            }

            .audio-permission-notice h3 {
                font-size: 1.125rem;
            }

            .audio-permission-notice p {
                font-size: 0.875rem;
            }
        }

        /* Terminal Output */
        .terminal {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13px;
            padding: 16px;
            overflow-y: auto;
            height: 100%;
            border-radius: 4px;
        }

        .terminal-line {
            margin: 2px 0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .terminal-line.error {
            color: #f48771;
        }

        .terminal-line.success {
            color: #89d185;
        }

        .terminal-line.info {
            color: #75beff;
        }

        .terminal-line.tool {
            color: #dcdcaa;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>MCP Voice Interface</h1>
            <p>Connect to MCP providers and start voice conversations</p>
        </div>
        
        <div class="main-content">
            <div class="panel file-explorer">
                <h2 style="padding: 12px; margin: 0; border-bottom: 1px solid #3e3e42; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #cccccc;">Explorer</h2>
                <div id="fileList">
                    <div class="file-item active">
                        <span class="file-icon">📄</span>
                        <span>main.py</span>
                    </div>
                    <div class="file-item">
                        <span class="file-icon">📄</span>
                        <span>session_data.json</span>
                    </div>
                    <div class="file-item">
                        <span class="file-icon">📄</span>
                        <span>output.txt</span>
                    </div>
                </div>
            </div>

            <div class="panel" style="background: #1e1e1e; padding: 0;">
                <div style="background: #252526; padding: 8px 16px; border-bottom: 1px solid #3e3e42; display: flex; align-items: center; gap: 8px;">
                    <span style="color: #cccccc; font-size: 13px;">main.py</span>
                    <span style="color: #858585; font-size: 11px; margin-left: auto;">Python</span>
                </div>
                <div id="codeEditor" class="code-editor">
                    <pre><code># Waiting for code from Claude Code SDK...</code></pre>
                </div>
            </div>

            <div class="panel provider-panel provider-section" style="display: flex; flex-direction: column;">
                <h2>Voice Control</h2>
                
                <select id="providerSelect" class="provider-select">
                    <option value="">Select a provider...</option>
                </select>
                
                <div class="control-buttons">
                    <button id="requestMicBtn" class="btn btn-primary" style="width: 100%; margin-bottom: 8px;">
                        🎤 Request Microphone Access
                    </button>
                </div>

                <div class="control-buttons">
                    <button id="connectBtn" class="btn btn-primary" disabled>
                        Connect
                    </button>
                    <button id="disconnectBtn" class="btn btn-danger" disabled>
                        Disconnect
                    </button>
                </div>

                <div id="connectionStatus" class="status disconnected">
                    Disconnected - select a provider and click Connect to start voice chat
                </div>

                <div id="microphoneStatus" style="margin-top: 12px; padding: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 13px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span id="micIcon">🎤</span>
                        <span id="micText">Microphone: Not requested</span>
                    </div>
                </div>

                <div id="audioPlayerContainer" style="margin-top: 12px; padding: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px;">
                    <div style="font-size: 12px; font-weight: 600; margin-bottom: 8px; color: #374151;">🔊 Audio Output</div>
                    <audio id="remoteAudio" controls playsinline webkit-playsinline style="width: 100%; height: 40px;"></audio>
                    <div id="audioLevel" style="margin-top: 8px; height: 6px; background: #e2e8f0; border-radius: 3px;">
                        <div id="audioLevelBar" style="height: 100%; width: 0%; background: #10b981; border-radius: 3px; transition: width 0.1s;"></div>
                    </div>
                    <div id="audioStats" style="margin-top: 6px; font-size: 12px; color: #64748b; font-weight: 500;">Waiting for connection...</div>
                </div>
                
                <div id="providerInfo" class="provider-info">
                    <h3 id="providerName"></h3>
                    <p id="providerDescription"></p>
                    <div id="providerStatus"></div>
                    
                    <div class="voice-commands">
                        <h4>Try saying:</h4>
                        <ul id="voiceCommands"></ul>
                    </div>
                    
                    <div id="availableTools" class="available-tools">
                        <h4>Available Tools:</h4>
                        <div id="toolsList" class="tools-list-inline">
                            <p style="color: #9ca3af; font-style: italic; font-size: 13px;">
                                Connect to see available tools
                            </p>
                        </div>
                    </div>
                </div>
                
                <div id="voiceInterface" style="display: none;">
                </div>
            </div>
            
            </div>
        </div>

        <!-- Terminal Output Section -->
        <div class="panel terminal-section" style="background: #1e1e1e; padding: 0;">
            <div style="background: #252526; padding: 8px 16px; border-bottom: 1px solid #3e3e42; display: flex; align-items: center; gap: 8px;">
                <span style="color: #cccccc; font-size: 13px;">Terminal Output</span>
                <button id="clearTerminal" class="btn btn-secondary" style="margin-left: auto; padding: 4px 12px; font-size: 12px;">Clear</button>
            </div>
            <div id="terminal" class="terminal">
                <div class="terminal-line info">Claude Code Terminal - Ready</div>
            </div>
        </div>

        <!-- Environment Logs Section -->
        <div class="panel" style="background: #1e1e1e; padding: 0; margin-top: 24px;">
            <div style="background: #252526; padding: 8px 16px; border-bottom: 1px solid #3e3e42; display: flex; align-items: center; gap: 8px;">
                <span style="color: #cccccc; font-size: 13px;">📝 Voice Transcript</span>
            </div>
            <div id="envLogs" class="terminal" style="max-height: 300px;">
                <div class="terminal-line info">Your conversation will appear here</div>
            </div>
        </div>
    </div>

    <!-- Thinking Indicator -->
    <div id="thinkingIndicator" class="thinking-indicator">
        <div class="thinking-spinner"></div>
        <span>Claude is thinking...</span>
    </div>

    <!-- Audio Permission Notice (iOS) -->
    <div id="audioPermissionNotice" class="audio-permission-notice">
        <h3>🔊 Enable Audio</h3>
        <p>Tap the button below to enable audio playback</p>
        <button id="enableAudioBtn">Enable Audio</button>
    </div>

    <!-- Audio element for thinking sound -->
    <audio id="thinkingSound" src="/static/thinking.mp3" loop></audio>



    <!-- Tool Response Modal -->
    <div id="toolResponseModal" class="tool-response-modal">
        <div class="tool-response-content">
            <div class="tool-response-header">
                <h3 class="tool-response-title" id="toolResponseTitle">Tool Response</h3>
                <button class="close" id="closeToolResponseModal">&times;</button>
            </div>
            <div class="tool-response-body" id="toolResponseBody">
                <!-- Tool response details will be populated here -->
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let currentState = {
            providers: [],
            currentProvider: null,
            discoveredTools: [],
            isConnecting: false
        };
        
        // Voice chat state
        let pc = null;
        let dataChannel = null;
        let conversation = null;
        let isVoiceConnected = false;
        let isVoiceConnecting = false; // Track if connection is in progress
        let userHasSpoken = false;
        let currentAssistantResponse = null;
        let microphoneStream = null; // Store microphone stream
        let microphoneGranted = false; // Track if microphone access is granted
        let globalAudioContext = null; // Store audio context globally for iOS
        
        // Configuration - bridge port is embedded from server
        const BRIDGE_PORT = ${PORT + 100};
        
        function initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(\`\${protocol}//\${window.location.host}\`);
            
            ws.onopen = () => {
                console.log('WebSocket connected');
            };
            
            ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                
                if (message.type === 'state') {
                    Object.assign(currentState, message.data);
                    updateUI();
                }
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected, reconnecting...');
                setTimeout(initWebSocket, 1000);
            };
        }
        

        
        async function loadProviders() {
            try {
                const response = await fetch('/api/providers');
                const data = await response.json();
                Object.assign(currentState, data);
                updateUI();
            } catch (error) {
                console.error('Failed to load providers:', error);
            }
        }
        
        function updateUI() {
            updateProviderSelect();
            updateConnectionStatus();
            updateToolsList();
        }
        
        function updateProviderSelect() {
            const select = document.getElementById('providerSelect');
            const currentValue = select.value;

            select.innerHTML = '<option value="">Select an MCP provider...</option>';

            currentState.providers.forEach(provider => {
                const option = document.createElement('option');
                option.value = provider.id;
                option.textContent = provider.icon + ' ' + provider.name;
                if (!provider.available) {
                    option.textContent += ' (Setup Required)';
                    option.disabled = true;
                }
                select.appendChild(option);
            });
            
            if (currentState.currentProvider) {
                select.value = currentState.currentProvider;
                showProviderInfo(currentState.currentProvider);
            } else if (currentValue) {
                select.value = currentValue;
                showProviderInfo(currentValue);
            }
        }
        
        function showProviderInfo(providerId) {
            const provider = currentState.providers.find(p => p.id === providerId);
            if (!provider) return;
            
            const info = document.getElementById('providerInfo');
            const connectBtn = document.getElementById('connectBtn');
            
            document.getElementById('providerName').textContent = \`\${provider.icon} \${provider.name}\`;
            document.getElementById('providerDescription').textContent = provider.description;
            
            const statusEl = document.getElementById('providerStatus');
            if (provider.available) {
                statusEl.innerHTML = '<span style="color: #16a34a;">Ready to connect</span>';
                connectBtn.disabled = currentState.isConnecting || currentState.currentProvider === providerId;
            } else {
                statusEl.innerHTML = \`<span style="color: #dc2626;">Missing: \${provider.missingEnvVars.join(', ')}</span>\`;
                connectBtn.disabled = true;
            }
            
            const commandsList = document.getElementById('voiceCommands');
            commandsList.innerHTML = '';
            provider.voiceCommands.slice(0, 3).forEach(cmd => {
                const li = document.createElement('li');
                li.textContent = \`"\${cmd}"\`;
                commandsList.appendChild(li);
            });
            
            info.classList.add('active');
        }
        
        function updateConnectionStatus() {
            const statusEl = document.getElementById('connectionStatus');
            const connectBtn = document.getElementById('connectBtn');
            const disconnectBtn = document.getElementById('disconnectBtn');
            const voiceInterface = document.getElementById('voiceInterface');
            
            if (currentState.isConnecting) {
                statusEl.className = 'status connecting';
                statusEl.innerHTML = '<span class="loading-spinner"></span> Connecting and starting voice chat...';
                connectBtn.disabled = true;
                disconnectBtn.disabled = true;
            } else if (currentState.currentProvider) {
                const provider = currentState.providers.find(p => p.id === currentState.currentProvider);
                statusEl.className = 'status connected';
                statusEl.innerHTML = \`Voice chat active with \${provider?.name} - you can speak now!\`;
                connectBtn.disabled = true;
                disconnectBtn.disabled = false;
                
                // Show voice interface and auto-start voice chat
                voiceInterface.style.display = 'block';
                
                // Auto-start voice chat after MCP connection
                if (!isVoiceConnected) {
                    setTimeout(() => startVoiceChat(), 500);
                }
            } else {
                statusEl.className = 'status disconnected';
                statusEl.innerHTML = 'Disconnected - select a provider and click Connect to start voice chat';
                connectBtn.disabled = !document.getElementById('providerSelect').value;
                disconnectBtn.disabled = true;
                voiceInterface.style.display = 'none';
                
                // Cleanup voice connection
                if (pc) {
                    pc.close();
                    pc = null;
                    isVoiceConnected = false;
                    isVoiceConnecting = false;
                    userHasSpoken = false;
                }
            }
        }
        
        function updateToolsList() {
            const toolsList = document.getElementById('toolsList');
            
            if (currentState.discoveredTools.length === 0) {
                toolsList.innerHTML = '<p style="color: #9ca3af; font-style: italic; font-size: 13px;">Connect to see available tools</p>';
                return;
            }
            
            toolsList.innerHTML = '';
            currentState.discoveredTools.forEach(tool => {
                const toolItem = document.createElement('div');
                toolItem.className = 'tool-item-inline';
                toolItem.title = tool.description || 'No description available';
                
                const toolName = document.createElement('div');
                toolName.className = 'tool-name';
                toolName.textContent = tool.name;
                
                toolItem.appendChild(toolName);
                toolsList.appendChild(toolItem);
            });
        }
        
        // Request microphone access (for iPhone - needs user gesture)
        async function requestMicrophoneAccess() {
            const micStatus = document.getElementById('microphoneStatus');
            const micText = document.getElementById('micText');
            const micIcon = document.getElementById('micIcon');
            const requestBtn = document.getElementById('requestMicBtn');

            try {
                if (micStatus && micText && micIcon) {
                    micText.textContent = 'Requesting microphone access...';
                    micIcon.textContent = '🎤';
                    micStatus.style.background = '#fffbeb';
                    micStatus.style.borderColor = '#fed7aa';
                }

                addTerminalLine('Requesting microphone access...', 'info');

                // Request microphone - try with full constraints first
                let stream;
                try {
                    stream = await navigator.mediaDevices.getUserMedia({
                        audio: {
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true,
                            sampleRate: 24000
                        }
                    });
                    addTerminalLine('Microphone granted with full constraints', 'success');
                } catch (err) {
                    // Fallback to simple constraints for iOS
                    console.log('Full constraints failed, trying simple audio:', err);
                    stream = await navigator.mediaDevices.getUserMedia({
                        audio: true
                    });
                    addTerminalLine('Microphone granted with simple constraints', 'success');
                }

                // Store the stream globally
                microphoneStream = stream;
                microphoneGranted = true;

                const audioTrack = stream.getTracks()[0];
                console.log('Audio track settings:', audioTrack.getSettings());
                addTerminalLine('Audio track: ' + audioTrack.label, 'success');

                // Update UI
                if (micStatus && micText && micIcon) {
                    micIcon.textContent = '🎤✅';
                    micText.textContent = 'Microphone: Ready!';
                    micStatus.style.background = '#f0fdf4';
                    micStatus.style.borderColor = '#bbf7d0';
                }

                // Update button
                if (requestBtn) {
                    requestBtn.textContent = '✅ Microphone Ready';
                    requestBtn.disabled = true;
                    requestBtn.style.background = '#10b981';
                    requestBtn.style.borderColor = '#10b981';
                }

                // For iPhone: Initialize audio context (requires user gesture)
                try {
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    globalAudioContext = new AudioContext();

                    console.log('Audio context created, state:', globalAudioContext.state);

                    // Resume audio context (required on iOS)
                    if (globalAudioContext.state === 'suspended') {
                        await globalAudioContext.resume();
                    }

                    console.log('Audio context state after resume:', globalAudioContext.state);
                    addTerminalLine('Audio context initialized (' + globalAudioContext.state + ')', 'success');
                } catch (err) {
                    console.log('Audio context init:', err.message);
                    addTerminalLine('Audio context init failed: ' + err.message, 'error');
                }

                return true;
            } catch (error) {
                console.error('Microphone access denied:', error);
                addTerminalLine('Microphone access denied: ' + error.message, 'error');

                if (micStatus && micText && micIcon) {
                    micIcon.textContent = '🎤❌';
                    micText.textContent = 'Microphone: Access denied';
                    micStatus.style.background = '#fef2f2';
                    micStatus.style.borderColor = '#fecaca';
                }

                alert('Microphone access is required for voice chat. Please grant permission and try again.');
                return false;
            }
        }

        // Voice chat functions
        async function startVoiceChat() {
            if (!currentState.currentProvider) return;

            // Prevent multiple simultaneous connection attempts
            if (isVoiceConnected) {
                console.log('Voice chat already connected, skipping');
                return;
            }

            if (isVoiceConnecting) {
                console.log('Voice connection already in progress, skipping');
                return;
            }

            if (pc && pc.connectionState !== 'closed') {
                console.log('PeerConnection exists and not closed, skipping');
                return;
            }

            // Mark as connecting
            isVoiceConnecting = true;
            addTerminalLine('Starting voice connection...', 'info');

            // Show microphone status
            const micStatus = document.getElementById('microphoneStatus');
            const micText = document.getElementById('micText');
            const micIcon = document.getElementById('micIcon');
            if (micStatus) {
                micStatus.style.display = 'block';
                micText.textContent = 'Requesting microphone access...';
                micIcon.textContent = '🎤';
            }

            try {
                // Check if mediaDevices is supported
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    throw new Error('Browser does not support audio input. Please use a modern browser with HTTPS or localhost.');
                }

                // Get ephemeral API key
                const sessionResponse = await fetch(\`http://localhost:\${BRIDGE_PORT}/session\`);
                if (!sessionResponse.ok) {
                    throw new Error('Failed to get session key');
                }
                const session = await sessionResponse.json();

                // Use stored microphone stream if available, otherwise request it
                let stream;
                if (microphoneStream && microphoneGranted) {
                    stream = microphoneStream;
                    addTerminalLine('Using pre-authorized microphone', 'success');
                } else {
                    // Get microphone access FIRST (before creating peer connection)
                    // Note: iOS Safari requires simpler audio constraints
                    try {
                        // Try with full constraints first
                        stream = await navigator.mediaDevices.getUserMedia({
                            audio: {
                                echoCancellation: true,
                                noiseSuppression: true,
                                autoGainControl: true,
                                sampleRate: 24000 // Optimized for OpenAI Realtime API
                            }
                        });
                        addTerminalLine('Microphone access granted with full constraints', 'success');
                    } catch (err) {
                        // Fallback to simple constraints for iOS
                        console.log('Full constraints failed, trying simple audio:', err);
                        stream = await navigator.mediaDevices.getUserMedia({
                            audio: true
                        });
                        addTerminalLine('Microphone access granted with simple constraints', 'success');
                    }

                    // Store for future use
                    microphoneStream = stream;
                    microphoneGranted = true;
                }

                const audioTrack = stream.getTracks()[0];
                console.log('Audio track settings:', audioTrack.getSettings());
                addTerminalLine('Audio track added: ' + audioTrack.label, 'info');

                // Update microphone status
                if (micStatus && micText && micIcon) {
                    if (audioTrack.enabled && !audioTrack.muted) {
                        micIcon.textContent = '🎤✅';
                        micText.textContent = 'Microphone: Active and ready';
                        micStatus.style.background = '#f0fdf4';
                        micStatus.style.borderColor = '#bbf7d0';
                    } else {
                        micIcon.textContent = '🎤⚠️';
                        micText.textContent = 'Microphone: May not be working';
                        micStatus.style.background = '#fffbeb';
                        micStatus.style.borderColor = '#fed7aa';
                    }
                }

                // Monitor track state
                audioTrack.onended = () => {
                    console.log('Audio track ended');
                    addTerminalLine('Microphone disconnected', 'error');
                    if (micStatus && micText && micIcon) {
                        micIcon.textContent = '🎤❌';
                        micText.textContent = 'Microphone: Disconnected';
                        micStatus.style.background = '#fef2f2';
                        micStatus.style.borderColor = '#fecaca';
                    }
                };

                audioTrack.onmute = () => {
                    console.log('Audio track muted');
                    addTerminalLine('Microphone muted', 'error');
                    if (micStatus && micText && micIcon) {
                        micIcon.textContent = '🎤🔇';
                        micText.textContent = 'Microphone: Muted';
                        micStatus.style.background = '#fffbeb';
                        micStatus.style.borderColor = '#fed7aa';
                    }
                };

                audioTrack.onunmute = () => {
                    console.log('Audio track unmuted');
                    addTerminalLine('Microphone unmuted', 'success');
                    if (micStatus && micText && micIcon) {
                        micIcon.textContent = '🎤✅';
                        micText.textContent = 'Microphone: Active';
                        micStatus.style.background = '#f0fdf4';
                        micStatus.style.borderColor = '#bbf7d0';
                    }
                };

                // Check if track is actually enabled
                console.log('Audio track enabled:', audioTrack.enabled);
                console.log('Audio track muted:', audioTrack.muted);
                console.log('Audio track readyState:', audioTrack.readyState);

                if (!audioTrack.enabled || audioTrack.muted) {
                    addTerminalLine('Warning: Microphone may not be working properly', 'error');
                } else {
                    addTerminalLine('Microphone is active and ready', 'success');
                }

                // NOW set up WebRTC connection (after we have the stream)
                pc = new RTCPeerConnection();

                // Monitor connection state
                pc.onconnectionstatechange = () => {
                    console.log('WebRTC connection state:', pc.connectionState);
                    addTerminalLine('WebRTC state: ' + pc.connectionState, 'info');
                };

                pc.oniceconnectionstatechange = () => {
                    console.log('ICE connection state:', pc.iceConnectionState);
                    addTerminalLine('ICE state: ' + pc.iceConnectionState, 'info');
                };

                // Add microphone track BEFORE creating offer
                pc.addTrack(audioTrack, stream);

                // Set up audio element to play remote audio from the model
                // Use the visible audio player
                const audioEl = document.getElementById('remoteAudio');

                if (!audioEl) {
                    throw new Error('Audio element not found');
                }

                audioEl.autoplay = true;
                // Don't set playsinline here - will be set when stream is attached
                // Don't set muted=false here - iOS requires starting muted
                audioEl.volume = 1.0; // Maximum volume (will be muted initially)

                // Log audio element state
                console.log('Audio element created:', {
                    autoplay: audioEl.autoplay,
                    playsInline: audioEl.playsInline,
                    muted: audioEl.muted,
                    volume: audioEl.volume
                });

                pc.ontrack = e => {
                    console.log('Received remote audio track');
                    console.log('Remote stream tracks:', e.streams[0].getTracks());

                    // NEW iOS FIX: Use Web Audio API as primary playback method
                    // Audio element is secondary (for UI/controls only)

                    // Set up audio element for UI/controls
                    audioEl.playsInline = true;
                    audioEl.setAttribute('playsinline', 'true');
                    audioEl.setAttribute('webkit-playsinline', 'true');

                    // DON'T mute - let Web Audio API handle playback
                    audioEl.muted = false;  // Changed: was true
                    audioEl.volume = 1.0;
                    audioEl.srcObject = e.streams[0];

                    // CRITICAL FOR iOS: Set up Web Audio API routing FIRST
                    // This must happen before audio element plays
                    try {
                        if (globalAudioContext) {
                            console.log('🎧 Setting up Web Audio API playback for iOS...');
                            const remoteSource = globalAudioContext.createMediaStreamSource(e.streams[0]);
                            remoteSource.connect(globalAudioContext.destination);
                            console.log('✅ Web Audio API: Remote audio connected to speakers');
                            addTerminalLine('Web Audio API playback enabled', 'success');

                            // Store for monitoring
                            window.remoteAudioSource = remoteSource;
                        } else {
                            console.warn('⚠️ globalAudioContext not available - Web Audio routing skipped');
                        }
                    } catch (err) {
                        console.error('❌ Failed to set up Web Audio routing:', err);
                        addTerminalLine('Web Audio routing failed: ' + err.message, 'error');
                    }

                    // Update UI to show we're connected
                    const audioStats = document.getElementById('audioStats');
                    if (audioStats) {
                        audioStats.textContent = 'Connected - Listening for AI audio...';
                        audioStats.style.color = '#10b981';
                        console.log('✅ Updated audioStats UI');
                    } else {
                        console.error('❌ audioStats element not found');
                    }

                    // Start monitoring remote audio levels (for visualization only now)
                    if (window.monitorRemoteAudio && !window.remoteAudioSource) {
                        console.log('Calling monitorRemoteAudio for visualization...');
                        window.monitorRemoteAudio(e.streams[0]);
                    } else if (window.remoteAudioSource) {
                        console.log('Remote audio already routed via Web Audio API');
                    } else {
                        console.error('❌ monitorRemoteAudio not available');
                    }

                    // Log remote audio track details
                    const remoteTrack = e.streams[0].getAudioTracks()[0];
                    if (remoteTrack) {
                        console.log('Remote audio track:', {
                            label: remoteTrack.label,
                            enabled: remoteTrack.enabled,
                            muted: remoteTrack.muted,
                            readyState: remoteTrack.readyState
                        });
                    }

                    // Monitor audio element events
                    audioEl.onloadedmetadata = () => {
                        console.log('Audio metadata loaded');
                        addTerminalLine('Audio stream metadata loaded', 'info');
                    };

                    audioEl.onplay = () => {
                        console.log('✅ Audio element started playing');
                        addTerminalLine('Audio element ready (Web Audio API handling playback)', 'success');
                        // Note: Actual audio playback is handled by Web Audio API
                        // Audio element is just for UI/controls
                    };

                    audioEl.onpause = () => {
                        console.log('Audio element paused');
                        addTerminalLine('Audio element paused', 'error');
                    };

                    audioEl.onerror = (err) => {
                        console.error('Audio element error:', err);
                        addTerminalLine('Audio element error: ' + err, 'error');
                    };

                    // iOS requires a user gesture to play audio
                    // Try to play and handle the promise
                    const playPromise = audioEl.play();
                    if (playPromise !== undefined) {
                        playPromise
                            .then(() => {
                                console.log('Audio playback started successfully');
                                console.log('Audio element state after play:', {
                                    paused: audioEl.paused,
                                    currentTime: audioEl.currentTime,
                                    volume: audioEl.volume,
                                    muted: audioEl.muted
                                });
                                addTerminalLine('Audio playback started', 'success');
                            })
                            .catch(error => {
                                console.error('Audio playback failed:', error);
                                addTerminalLine('Audio playback failed - tap to enable', 'error');

                                // Show the audio permission notice
                                const notice = document.getElementById('audioPermissionNotice');
                                const enableBtn = document.getElementById('enableAudioBtn');

                                if (notice) {
                                    notice.classList.add('active');
                                }

                                // For iOS, we need to retry play on user interaction
                                const retryPlay = () => {
                                    audioEl.play()
                                        .then(() => {
                                            console.log('Audio playback started after user interaction');
                                            addTerminalLine('Audio playback enabled', 'success');

                                            // Hide the notice
                                            if (notice) {
                                                notice.classList.remove('active');
                                            }
                                        })
                                        .catch(e => console.log('Retry failed:', e));
                                };

                                // Handle button click
                                if (enableBtn) {
                                    enableBtn.addEventListener('click', retryPlay, { once: true });
                                }

                                // Also handle any tap/click on the document
                                document.addEventListener('touchstart', retryPlay, { once: true });
                                document.addEventListener('click', retryPlay, { once: true });
                            });
                    }
                };

                // Add visual feedback for microphone activity (helps debug iOS issues)
                try {
                    // Use global audio context if available, otherwise create new one
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    const audioContext = globalAudioContext || new AudioContext();

                    // If we created a new one, store it
                    if (!globalAudioContext) {
                        globalAudioContext = audioContext;
                    }

                    // Make sure it's running (critical for iOS)
                    if (audioContext.state === 'suspended') {
                        await audioContext.resume();
                        console.log('Audio context resumed, state:', audioContext.state);
                    }

                    const analyser = audioContext.createAnalyser();
                    const microphone = audioContext.createMediaStreamSource(stream);
                    microphone.connect(analyser);
                    analyser.fftSize = 256;
                    const bufferLength = analyser.frequencyBinCount;
                    const dataArray = new Uint8Array(bufferLength);

                    let lastSoundTime = 0;
                    const checkAudioLevel = () => {
                        analyser.getByteFrequencyData(dataArray);
                        const average = dataArray.reduce((a, b) => a + b) / bufferLength;

                        // If we detect sound, log it (helps debug)
                        if (average > 10) {
                            const now = Date.now();
                            if (now - lastSoundTime > 2000) { // Log every 2 seconds max
                                console.log('Microphone activity detected, level:', average);
                                addTerminalLine('🎤 Speaking detected (level: ' + Math.round(average) + ')', 'success');
                                lastSoundTime = now;
                            }
                        }

                        if (isVoiceConnected) {
                            requestAnimationFrame(checkAudioLevel);
                        }
                    };
                    checkAudioLevel();

                    // Also monitor REMOTE audio (what we should hear from OpenAI)
                    const monitorRemoteAudio = (remoteStream) => {
                        try {
                            console.log('🎧 Setting up remote audio monitoring (visualization only)...');
                            addTerminalLine('Setting up remote audio level visualization', 'info');

                            const remoteAnalyser = audioContext.createAnalyser();

                            // Use existing source if available (already connected to destination)
                            // Otherwise create new source BUT don't connect to destination (duplicate)
                            const remoteSource = window.remoteAudioSource || audioContext.createMediaStreamSource(remoteStream);
                            remoteSource.connect(remoteAnalyser);

                            // DON'T connect to destination - already done in ontrack handler
                            console.log('✅ Remote audio analyser set up for visualization');

                            remoteAnalyser.fftSize = 256;
                            const remoteBufferLength = remoteAnalyser.frequencyBinCount;
                            const remoteDataArray = new Uint8Array(remoteBufferLength);

                            const audioLevelBar = document.getElementById('audioLevelBar');
                            const audioStats = document.getElementById('audioStats');

                            // Update stats immediately to show we're monitoring
                            if (audioStats) {
                                audioStats.textContent = 'Monitoring... Level: 0';
                            }

                            let lastRemoteSoundTime = 0;
                            const checkRemoteAudioLevel = () => {
                                remoteAnalyser.getByteFrequencyData(remoteDataArray);
                                const average = remoteDataArray.reduce((a, b) => a + b) / remoteBufferLength;

                                // Update visual level indicator
                                if (audioLevelBar) {
                                    audioLevelBar.style.width = Math.min(100, average) + '%';
                                }

                                if (audioStats) {
                                    audioStats.textContent = \`Level: \${Math.round(average)} | \${average > 10 ? '🔊 Audio detected' : '🔇 Silent'}\`;
                                }

                                // If we detect sound from OpenAI, log it
                                if (average > 10) {
                                    const now = Date.now();
                                    if (now - lastRemoteSoundTime > 2000) {
                                        console.log('🔊 Remote audio detected, level:', average);
                                        addTerminalLine('🔊 AI is speaking (level: ' + Math.round(average) + ')', 'success');
                                        lastRemoteSoundTime = now;
                                    }
                                }

                                if (isVoiceConnected) {
                                    requestAnimationFrame(checkRemoteAudioLevel);
                                }
                            };
                            checkRemoteAudioLevel();
                        } catch (err) {
                            console.error('Remote audio monitoring failed:', err);
                            addTerminalLine('Remote audio monitoring failed: ' + err.message, 'error');
                        }
                    };

                    // Store the monitor function to call when we get the remote track
                    window.monitorRemoteAudio = monitorRemoteAudio;
                } catch (err) {
                    console.log('Audio monitoring not available:', err);
                }

                // Create data channel for events
                dataChannel = pc.createDataChannel("oai-events");
                dataChannel.onmessage = handleVoiceMessage;

                // Configure session when data channel opens
                dataChannel.onopen = () => {
                    console.log('Data channel opened, readyState:', dataChannel.readyState);
                    addTerminalLine('Data channel connected', 'success');

                    // Wait a brief moment to ensure channel is fully ready
                    setTimeout(() => {
                        if (dataChannel && dataChannel.readyState === 'open') {
                            // Default session config optimized for voice interactions
                            const defaultSessionConfig = {
                                modalities: ['text', 'audio'],
                                voice: 'alloy',
                                tool_choice: 'auto',
                                max_response_output_tokens: 500, // Limit response length (roughly 2000 chars)
                                // Voice interface optimizations
                                speed: 1.2, // Optimal speed - fast but not hurried
                                temperature: 0.7, // Slightly lower for more consistent, professional responses
                                input_audio_transcription: {
                                    model: 'whisper-1' // Enable transcription for better UX
                                },
                                turn_detection: {
                                    type: 'server_vad',
                                    threshold: 0.5,
                                    prefix_padding_ms: 300,
                                    silence_duration_ms: 400, // Slightly faster response time
                                    create_response: true,
                                    interrupt_response: true,
                                },
                            };

                            // Use default config with ability to override specific settings
                            const sessionConfig = {
                                ...defaultSessionConfig,
                                // Any voice demo specific overrides can go here
                                // For example: speed: 1.0, // Override default speed if needed
                            };

                            console.log('🔧 Sending session config:', sessionConfig);

                            try {
                                dataChannel.send(JSON.stringify({
                                    type: 'session.update',
                                    session: sessionConfig
                                }));
                                addTerminalLine('Session configured successfully', 'success');
                                console.log('✅ Session config sent');
                            } catch (err) {
                                console.error('Failed to send session config:', err);
                                addTerminalLine('Failed to configure session: ' + err.message, 'error');
                            }
                        } else {
                            console.error('Data channel not ready');
                            addTerminalLine('Data channel not ready', 'error');
                        }
                    }, 100); // 100ms delay to ensure channel is stable
                };

                // Connect to OpenAI Realtime API - create offer AFTER adding tracks
                addTerminalLine('Creating WebRTC offer...', 'info');
                const offer = await pc.createOffer();

                console.log('PC state before setLocalDescription:', pc.signalingState);
                addTerminalLine('PC signaling state: ' + pc.signalingState, 'info');

                await pc.setLocalDescription(offer);
                console.log('PC state after setLocalDescription:', pc.signalingState);
                addTerminalLine('Local description set, state: ' + pc.signalingState, 'success');

                // Wait for ICE gathering to complete or timeout
                if (pc.iceGatheringState !== 'complete') {
                    await new Promise((resolve) => {
                        const timeout = setTimeout(resolve, 5000); // 5 second timeout
                        pc.onicegatheringstatechange = () => {
                            console.log('ICE gathering state:', pc.iceGatheringState);
                            if (pc.iceGatheringState === 'complete') {
                                clearTimeout(timeout);
                                resolve();
                            }
                        };
                    });
                }
                addTerminalLine('ICE gathering complete', 'success');

                addTerminalLine('Connecting to OpenAI Realtime API...', 'info');
                const response = await fetch(\`https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17\`, {
                    method: "POST",
                    body: pc.localDescription.sdp,
                    headers: {
                        Authorization: \`Bearer \${session.client_secret.value}\`,
                        "Content-Type": "application/sdp"
                    }
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error('Failed to connect to OpenAI: ' + response.status + ' - ' + errorText);
                }

                const answerSdp = await response.text();
                addTerminalLine('Received answer from OpenAI', 'success');

                // Check if pc still exists
                if (!pc) {
                    throw new Error('PeerConnection was closed or destroyed');
                }

                console.log('PC state before setRemoteDescription:', pc.signalingState);

                // Make sure we're in the right state
                if (pc.signalingState !== 'have-local-offer') {
                    throw new Error('Invalid signaling state for setRemoteDescription: ' + pc.signalingState);
                }

                const answer = new RTCSessionDescription({ type: "answer", sdp: answerSdp });
                await pc.setRemoteDescription(answer);

                console.log('PC state after setRemoteDescription:', pc.signalingState);
                addTerminalLine('Remote description set - connection complete!', 'success');

                isVoiceConnected = true;
                isVoiceConnecting = false;

            } catch (error) {
                console.error('Voice chat error:', error);
                isVoiceConnecting = false; // Reset on error

                // Display user-friendly error message
                const statusEl = document.getElementById('status');
                if (statusEl) {
                    statusEl.className = 'status disconnected';
                    statusEl.innerHTML = '❌ Voice Error: ' + error.message;
                }

                // Add to transcript
                addTranscriptMessage('system', 'Voice chat failed: ' + error.message);
                addTerminalLine('Voice chat error: ' + error.message, 'error');

                // Cleanup on error
                if (pc) {
                    pc.close();
                    pc = null;
                }
                isVoiceConnected = false;
            }
        }
        
        function handleVoiceMessage(event) {
            try {
                const data = JSON.parse(event.data);

                // Log ALL messages to debug what we're receiving
                console.log('📨 Received message type:', data.type);

                // Log specific important events
                if (data.type.includes('audio') || data.type.includes('response')) {
                    console.log('🔍 Audio/Response event:', data);
                }

                // Handle different message types
                if (data.type === 'session.updated') {
                    console.log('✅ Session updated:', data.session);
                    addTerminalLine('Session updated - modalities: ' + (data.session?.modalities || 'unknown'), 'success');
                } else if (data.type === 'session.created') {
                    console.log('✅ Session created:', data.session);
                    addTerminalLine('Session created - modalities: ' + (data.session?.modalities || 'unknown'), 'success');
                } else if (data.type === 'conversation.item.input_audio_transcription.completed') {
                    currentAssistantResponse = null; // Reset for new conversation
                    userHasSpoken = true;
                    addTranscriptMessage('user', data.transcript);
                } else if (data.type === 'response.created') {
                    currentAssistantResponse = null; // Reset for new response
                } else if (data.type === 'response.audio.delta') {
                    // Assistant is speaking - pause thinking sound
                    const sound = document.getElementById('thinkingSound');
                    if (sound && !sound.paused) {
                        sound.pause();
                    }
                } else if (data.type === 'response.text.delta') {
                    // Collect text deltas but don't add to transcript yet
                    if (userHasSpoken) {
                        if (!currentAssistantResponse) {
                            currentAssistantResponse = '';
                        }
                        currentAssistantResponse += data.delta;
                    }
                } else if (data.type === 'response.text.done') {
                    // Add complete AI text response to transcript
                    if (userHasSpoken && currentAssistantResponse) {
                        addTranscriptMessage('assistant', currentAssistantResponse);
                        currentAssistantResponse = null;
                    }
                } else if (data.type === 'response.function_call_arguments.done') {
                    // Add small delay to ensure user transcription is processed first
                    setTimeout(() => handleFunctionCall(data), 100);
                } else if (data.type === 'conversation.item.created') {
                    // Skip - we handle AI responses through response.text.done and response.audio_transcript.done
                } else if (data.type === 'response.audio_transcript.delta') {
                    // Assistant is speaking - pause thinking sound
                    const sound = document.getElementById('thinkingSound');
                    if (sound && !sound.paused) {
                        sound.pause();
                    }
                    // Collect audio transcript deltas but don't add to transcript yet
                    if (userHasSpoken) {
                        if (!currentAssistantResponse) {
                            currentAssistantResponse = '';
                        }
                        currentAssistantResponse += data.delta;
                    }
                } else if (data.type === 'response.audio_transcript.done') {
                    // Add complete AI audio transcript to transcript
                    if (userHasSpoken && currentAssistantResponse) {
                        addTranscriptMessage('assistant', currentAssistantResponse);
                        currentAssistantResponse = null;
                    }
                } else if (data.type === 'response.audio.done' || data.type === 'response.done') {
                    // Response finished - safe to resume thinking sound if still processing
                    // (will be stopped by handleFunctionCall when tool completes)
                }
            } catch (error) {
                console.error('Error handling voice message:', error);
            }
        }
        
        async function handleFunctionCall(functionCallData) {
            try {
                const { call_id, name, arguments: args } = functionCallData;

                // Only show thinking indicator and play sound for Claude Code operations
                const isClaudeCodeOperation = name.includes('claude') || name.includes('session') ||
                                             name.includes('git') || name.includes('bash') ||
                                             name.includes('env') || name.includes('data') ||
                                             name.includes('counter') || name.includes('status');

                if (isClaudeCodeOperation) {
                    showThinking(true);
                }

                // Log to terminal
                const parsedArgs = JSON.parse(args);
                addTerminalLine('$ Calling tool: ' + name, 'tool');
                if (Object.keys(parsedArgs).length > 0) {
                    addTerminalLine('  Args: ' + JSON.stringify(parsedArgs).substring(0, 100) + '...', 'info');
                }

                // Bridge server now handles function name mapping automatically
                // Just send the OpenAI function name directly

                // Call the MCP tool via our bridge server
                const response = await fetch(\`http://localhost:\${BRIDGE_PORT}/mcp\`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        id: Date.now(),
                        method: 'tools/call',
                        params: {
                            name: name, // Bridge server handles the mapping
                            arguments: parsedArgs
                        }
                    })
                });
                
                const result = await response.json();

                // Hide thinking indicator and stop sound (only if it was shown)
                if (isClaudeCodeOperation) {
                    showThinking(false);
                }

                if (result.error) {
                    addTerminalLine('✗ Error: ' + result.error.message, 'error');
                    throw new Error(result.error.message);
                }

                // Log success to terminal
                addTerminalLine('✓ Tool completed successfully', 'success');

                // Log key result info
                if (result.result && result.result.result) {
                    const resultPreview = String(result.result.result).substring(0, 150);
                    addTerminalLine('  Output: ' + resultPreview + '...', 'info');
                }

                // Update code editor if this was a code-related operation
                if (result.result) {
                    updateCodeEditor(result.result, name);

                    // If there was a git diff, try to fetch and display the changed file
                    if (result.result.git_tracked || result.result.has_changes) {
                        setTimeout(() => fetchAndDisplayChangedFile(), 1000);
                    }
                }

                // Add tool call to transcript with response
                addToolCallToTranscript(name, parsedArgs, result.result, 'success');

                // Extract Claude's response text to send back
                let claudeResponse = '';
                if (result.result) {
                    if (typeof result.result === 'object') {
                        // For claude_query, extract the actual response text
                        if (result.result.result) {
                            claudeResponse = result.result.result;
                        } else if (result.result.success) {
                            claudeResponse = JSON.stringify(result.result, null, 2);
                        } else {
                            claudeResponse = JSON.stringify(result.result);
                        }
                    } else {
                        claudeResponse = String(result.result);
                    }
                }

                // Send the result back to OpenAI via the data channel
                if (dataChannel && dataChannel.readyState === 'open') {
                    dataChannel.send(JSON.stringify({
                        type: 'conversation.item.create',
                        item: {
                            type: 'function_call_output',
                            call_id: call_id,
                            output: claudeResponse || JSON.stringify(result.result)
                        }
                    }));

                    // Trigger AI to generate a response with the function results
                    setTimeout(() => {
                        if (dataChannel && dataChannel.readyState === 'open') {
                            dataChannel.send(JSON.stringify({
                                type: 'response.create',
                                response: {
                                    modalities: ['text', 'audio']
                                }
                            }));
                        }
                    }, 100);
                } else {
                    console.error('Cannot send function result: data channel not open');
                    addTerminalLine('Data channel disconnected', 'error');
                }
                
            } catch (error) {
                console.error('Function call error:', error);

                // Hide thinking indicator on error (always, in case it was shown)
                showThinking(false);

                // Log error to terminal
                addTerminalLine('✗ Function call failed: ' + error.message, 'error');

                // Add error to transcript
                try {
                    const errorArgs = functionCallData.arguments ? JSON.parse(functionCallData.arguments) : {};
                    addToolCallToTranscript(name, errorArgs, { error: error.message }, 'error');
                } catch (parseError) {
                    addToolCallToTranscript(name, { raw: functionCallData.arguments }, { error: error.message }, 'error');
                }

                // Send error back to OpenAI
                if (dataChannel && dataChannel.readyState === 'open') {
                    dataChannel.send(JSON.stringify({
                        type: 'conversation.item.create',
                        item: {
                            type: 'function_call_output',
                            call_id: functionCallData.call_id,
                            output: JSON.stringify({ error: error.message })
                        }
                    }));
                }
            }
        }

        // Thinking indicator functions
        function showThinking(show) {
            const indicator = document.getElementById('thinkingIndicator');
            const sound = document.getElementById('thinkingSound');

            if (show) {
                indicator.classList.add('active');
                sound.play().catch(e => console.log('Audio play failed:', e));
            } else {
                indicator.classList.remove('active');
                sound.pause();
                sound.currentTime = 0;
            }
        }

        // Code editor update function
        function updateCodeEditor(result, toolName) {
            const codeEditor = document.getElementById('codeEditor');

            // Try to extract code from the result
            let code = '';
            if (typeof result === 'object') {
                // Look for git diff first
                if (result.git_diff && result.git_diff !== '(no changes)' && result.git_diff !== '(git diff unavailable)') {
                    code = '# Git Diff:\\n' + result.git_diff;
                }
                // Then look for the actual result
                else if (result.result) {
                    code = result.result;
                } else {
                    code = JSON.stringify(result, null, 2);
                }
            } else if (typeof result === 'string') {
                code = result;
            }

            // Update the code editor
            codeEditor.innerHTML = '<pre><code>' + escapeHtml(code) + '</code></pre>';
        }

        async function fetchAndDisplayChangedFile() {
            try {
                // Try to get git diff from the MCP server
                const response = await fetch(\`http://localhost:\${BRIDGE_PORT}/mcp\`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        id: Date.now(),
                        method: 'tools/call',
                        params: {
                            name: 'get_git_diff_tool',
                            arguments: {}
                        }
                    })
                });

                const result = await response.json();
                if (result.result && result.result.git_diff) {
                    const codeEditor = document.getElementById('codeEditor');
                    codeEditor.innerHTML = '<pre><code>' + escapeHtml('# Recent Changes:\\n\\n' + result.result.git_diff) + '</code></pre>';
                }
            } catch (error) {
                console.log('Could not fetch git diff:', error);
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Terminal functions
        function addTerminalLine(text, type = 'info') {
            const terminal = document.getElementById('terminal');
            if (!terminal) {
                console.log('Terminal not found:', text);
                return;
            }

            const line = document.createElement('div');
            line.className = 'terminal-line ' + type;

            const timestamp = new Date().toLocaleTimeString();
            line.textContent = '[' + timestamp + '] ' + text;

            terminal.appendChild(line);

            // Auto-scroll to bottom
            terminal.scrollTop = terminal.scrollHeight;

            // Keep only last 100 lines
            while (terminal.children.length > 100) {
                terminal.removeChild(terminal.firstChild);
            }
        }

        // Clear terminal
        document.addEventListener('DOMContentLoaded', () => {
            const clearBtn = document.getElementById('clearTerminal');
            if (clearBtn) {
                clearBtn.addEventListener('click', () => {
                    const terminal = document.getElementById('terminal');
                    terminal.innerHTML = '<div class="terminal-line info">Claude Code Terminal - Ready</div>';
                });
            }
        });

        // Environment logs functions
        async function loadEnvLogs() {
            try {
                const logsDiv = document.getElementById('envLogs');
                if (!logsDiv) return;

                // Just show a message that logs would be fetched via MCP
                logsDiv.innerHTML = '<div class="terminal-line info">Environment logs feature - speak to Claude to fetch logs</div>';
                addTerminalLine('To view logs, say: "Show me the environment logs"', 'info');
            } catch (error) {
                console.error('Error loading logs:', error);
                addTerminalLine('Failed to load environment logs: ' + error.message, 'error');
            }
        }

        function displayLogs(logs) {
            const logsDiv = document.getElementById('envLogs');
            if (!logsDiv) return;

            logsDiv.innerHTML = '';

            if (!logs || logs.length === 0) {
                logsDiv.innerHTML = '<div class="terminal-line info">No logs available</div>';
                return;
            }

            logs.forEach(log => {
                const line = document.createElement('div');
                line.className = 'terminal-line';

                const time = new Date(log.timestamp).toLocaleString();
                const operation = log.operation;
                const dataStr = JSON.stringify(log.data, null, 2);

                line.textContent = '[' + time + '] ' + operation + ': ' + dataStr.substring(0, 200);
                logsDiv.appendChild(line);
            });

            logsDiv.scrollTop = logsDiv.scrollHeight;
        }

        // No longer needed - removed refresh and clear logs buttons

        function addTranscriptMessage(sender, message) {
            // Skip system messages about function calls - they only go to the tool calls in transcript
            if (sender === 'system' && (message.includes('Executing') || message.includes('Calling function') || message.includes('Tool completed'))) {
                return;
            }
            
            const transcript = document.getElementById('transcript');
            
            if (!transcript) {
                return;
            }
            
            // Remove placeholder text if it exists
            if (transcript.children.length === 1 && transcript.children[0].tagName === 'P') {
                transcript.innerHTML = '';
            }
            
            const messageDiv = document.createElement('div');
            messageDiv.className = \`transcript-item \${sender}\`;
            
            const senderDiv = document.createElement('div');
            senderDiv.className = 'transcript-sender';
            senderDiv.textContent = sender === 'user' ? 'YOU' : sender === 'assistant' ? 'AI' : 'SYSTEM';
            
            const contentDiv = document.createElement('div');
            contentDiv.textContent = message;
            
            messageDiv.appendChild(senderDiv);
            messageDiv.appendChild(contentDiv);
            transcript.appendChild(messageDiv);
            
            // Auto-scroll to bottom
            setTimeout(() => {
                transcript.scrollTop = transcript.scrollHeight;
            }, 10);
        }
        
        function addToolCallToTranscript(toolName, args = null, response = null, type = 'starting') {
            const transcript = document.getElementById('transcript');
            if (!transcript) {
                console.log('Transcript not found');
                return;
            }

            // Remove placeholder text if it exists
            if (transcript.children.length === 1 && transcript.children[0].tagName === 'P') {
                transcript.innerHTML = '';
            }
            
            const item = document.createElement('div');
            item.className = 'transcript-item tool';
            
            const headerDiv = document.createElement('div');
            headerDiv.className = 'tool-call-header';
            
            const toolNameSpan = document.createElement('span');
            toolNameSpan.className = 'tool-name';
            toolNameSpan.textContent = toolName;
            
            const statusSpan = document.createElement('span');
            statusSpan.className = \`tool-status \${type}\`;
            statusSpan.textContent = type === 'success' ? 'SUCCEEDED' : type === 'error' ? 'FAILED' : type.toUpperCase();
            
            headerDiv.appendChild(toolNameSpan);
            headerDiv.appendChild(statusSpan);
            
            item.appendChild(headerDiv);
            
            // Add simplified args preview
            if (args && Object.keys(args).length > 0) {
                const argsDiv = document.createElement('div');
                argsDiv.className = 'tool-args';
                
                const argsPreview = Object.entries(args)
                    .slice(0, 2) // Show first 2 args
                    .map(([key, value]) => {
                        const stringValue = typeof value === 'string' ? value : JSON.stringify(value);
                        const truncated = stringValue.length > 30 ? stringValue.substring(0, 30) + '...' : stringValue;
                        return \`\${key}: \${truncated}\`;
                    })
                    .join(', ');
                
                argsDiv.textContent = argsPreview;
                item.appendChild(argsDiv);
            }
            
            // Store the response data for modal
            item.setAttribute('data-response', JSON.stringify({ args, response }));
            
            transcript.appendChild(item);
            
            // Auto-scroll to bottom
            setTimeout(() => {
                transcript.scrollTop = transcript.scrollHeight;
            }, 10);
            
            // Keep only last 50 transcript items
            while (transcript.children.length > 50) {
                transcript.removeChild(transcript.firstChild);
            }
        }
        
        function openToolResponseModal(toolName, args, response) {
            const modal = document.getElementById('toolResponseModal');
            const title = document.getElementById('toolResponseTitle');
            const body = document.getElementById('toolResponseBody');
            
            title.textContent = \`Tool Response: \${toolName}\`;
            
            let content = '';
            
            if (args && Object.keys(args).length > 0) {
                content += \`
                    <div class="tool-response-section">
                        <h4>Arguments</h4>
                        <div class="tool-response-json">\${JSON.stringify(args, null, 2)}</div>
                    </div>
                \`;
            }
            
            if (response) {
                content += \`
                    <div class="tool-response-section">
                        <h4>Response</h4>
                        <div class="tool-response-json">\${JSON.stringify(response, null, 2)}</div>
                    </div>
                \`;
            }
            
            body.innerHTML = content;
            modal.style.display = 'block';
        }

        // Removed streaming functions - now using complete responses only
        
        // Event listeners
        document.getElementById('requestMicBtn').addEventListener('click', async () => {
            await requestMicrophoneAccess();
        });

        document.getElementById('providerSelect').addEventListener('change', (e) => {
            if (e.target.value) {
                showProviderInfo(e.target.value);
            } else {
                document.getElementById('providerInfo').classList.remove('active');
                document.getElementById('connectBtn').disabled = true;
            }
        });
        
        document.getElementById('connectBtn').addEventListener('click', async () => {
            const providerId = document.getElementById('providerSelect').value;
            if (!providerId) return;
            
            try {
                const response = await fetch(\`/api/connect/\${providerId}\`, {
                    method: 'POST'
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    alert(\`Connection failed: \${error.message}\`);
                }
            } catch (error) {
                alert(\`Connection failed: \${error.message}\`);
            }
        });
        
        document.getElementById('disconnectBtn').addEventListener('click', async () => {
            try {
                const response = await fetch('/api/disconnect', {
                    method: 'POST'
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    alert(\`Disconnect failed: \${error.error}\`);
                }
            } catch (error) {
                alert(\`Disconnect failed: \${error.message}\`);
            }
        });
        

        
        // Tool response modal functionality
        document.getElementById('closeToolResponseModal').addEventListener('click', () => {
            document.getElementById('toolResponseModal').style.display = 'none';
        });

        // Close modal when clicking outside
        window.addEventListener('click', (event) => {
            const toolResponseModal = document.getElementById('toolResponseModal');
            
            if (event.target === toolResponseModal) {
                toolResponseModal.style.display = 'none';
            }
        });
        
        // Initialize
        // conversation variable is no longer needed - using transcript directly
        
        loadProviders();
        initWebSocket();
    </script>
</body>
</html>`;
} 