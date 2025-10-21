import { wsClients, addConnectionLog } from './state.js';
import { MCP_PROVIDERS } from './config.js';

// Broadcast message to all connected WebSocket clients
export function broadcast(message: any): void {
  const data = JSON.stringify(message);
  wsClients.forEach(ws => {
    if (ws.readyState === 1) { // OPEN
      ws.send(data);
    }
  });
}

// Add log entry and broadcast to clients
export function addLog(message: string, type: 'info' | 'error' | 'success' = 'info'): void {
  const timestamp = new Date().toISOString().substr(11, 8);
  const logEntry = `[${timestamp}] ${message}`;
  addConnectionLog(logEntry);

  console.log(logEntry);

  broadcast({
    type: 'log',
    data: { message: logEntry, type }
  });
}

// Get providers with their availability status
export function getProvidersWithStatus() {
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
