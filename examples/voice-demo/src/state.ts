import type { WebRTCBridgeServer } from '@gillinghammer/realtime-mcp-core';
import type { WebSocket } from 'ws';

// Global application state
export let activeBridge: WebRTCBridgeServer | null = null;
export let currentProvider: string | null = null;
export let discoveredTools: any[] = [];
export let isConnecting = false;
export let connectionLogs: string[] = [];
export let wsClients: Set<WebSocket> = new Set();

// State setters
export function setActiveBridge(bridge: WebRTCBridgeServer | null): void {
  activeBridge = bridge;
}

export function setCurrentProvider(provider: string | null): void {
  currentProvider = provider;
}

export function setDiscoveredTools(tools: any[]): void {
  discoveredTools = tools;
}

export function setIsConnecting(connecting: boolean): void {
  isConnecting = connecting;
}

export function addConnectionLog(message: string): void {
  connectionLogs.push(message);
  // Keep only last 100 logs
  if (connectionLogs.length > 100) {
    connectionLogs = connectionLogs.slice(-100);
  }
}

export function clearConnectionLogs(): void {
  connectionLogs = [];
}

export function addWsClient(client: WebSocket): void {
  wsClients.add(client);
}

export function removeWsClient(client: WebSocket): void {
  wsClients.delete(client);
}
