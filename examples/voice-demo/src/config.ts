import type { WebRTCBridgeConfig } from '@gillinghammer/realtime-mcp-core';

// Server configuration
export const PORT = parseInt(process.env.PORT || '8085');
export const HOST = process.env.HOST || 'localhost';
export const USE_HTTPS = process.env.USE_HTTPS === 'true' || false;

// MCP Provider interface
export interface MCPProvider {
  id: string;
  name: string;
  description: string;
  icon: string;
  config: WebRTCBridgeConfig['mcp'];
  instructions: string;
  requiredEnvVars: string[];
  voiceCommands: string[];
}

// MCP Provider configurations
export const MCP_PROVIDERS: MCPProvider[] = [
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

// Validate required environment variables
export function validateEnvironment(): void {
  if (!process.env.OPENAI_API_KEY) {
    console.error('\n❌ ERROR: Missing required environment variable');
    console.error('📝 Please create a .env file in the project root with:');
    console.error('   OPENAI_API_KEY=sk-proj-your-api-key-here');
    console.error('   HUBSPOT_TOKEN=your-hubspot-token-here (optional)');
    console.error('\n🔗 Get your OpenAI API key from: https://platform.openai.com/api-keys');
    process.exit(1);
  }
}
