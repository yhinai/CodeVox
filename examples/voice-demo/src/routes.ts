import type { Express, Request, Response } from 'express';
import { WebRTCBridgeServer } from '@gillinghammer/realtime-mcp-core';
import type { WebRTCBridgeConfig } from '@gillinghammer/realtime-mcp-core';
import {
  activeBridge,
  currentProvider,
  discoveredTools,
  isConnecting,
  connectionLogs,
  setActiveBridge,
  setCurrentProvider,
  setDiscoveredTools,
  setIsConnecting
} from './state.js';
import { getProvidersWithStatus, addLog, broadcast } from './utils.js';
import { MCP_PROVIDERS, PORT, HOST } from './config.js';

export function setupRoutes(app: Express): void {
  // Get providers and current state
  app.get('/api/providers', (req: Request, res: Response) => {
    res.json({
      providers: getProvidersWithStatus(),
      currentProvider,
      discoveredTools,
      isConnecting
    });
  });

  // Connect to a provider
  app.post('/api/connect/:providerId', async (req: Request, res: Response) => {
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

      setIsConnecting(true);
      setDiscoveredTools([]);

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
        setActiveBridge(null);
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
      const bridge = new WebRTCBridgeServer(bridgeConfig);
      setActiveBridge(bridge);

      addLog(`🚀 Starting bridge server...`, 'info');
      await bridge.start();

      // Get tools from the MCP API after connection
      try {
        const toolsResponse = await fetch(`http://${HOST}:${PORT + 100}/tools`);
        if (toolsResponse.ok) {
          const toolsData = await toolsResponse.json();
          setDiscoveredTools(toolsData.tools || []);
          addLog(`✅ Connected! Discovered ${discoveredTools.length} tools`, 'success');
        } else {
          addLog(`⚠️ Connected but couldn't fetch tools`, 'info');
        }
      } catch (error) {
        addLog(`⚠️ Connected but couldn't fetch tools: ${error}`, 'info');
      }

      setCurrentProvider(providerId);
      setIsConnecting(false);

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
      setIsConnecting(false);
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

  // Disconnect from current provider
  app.post('/api/disconnect', async (req: Request, res: Response) => {
    try {
      if (activeBridge) {
        addLog(`🛑 Disconnecting from ${currentProvider}...`, 'info');
        await activeBridge.stop();
        setActiveBridge(null);
      }

      setCurrentProvider(null);
      setDiscoveredTools([]);
      setIsConnecting(false);

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

  // Get current status
  app.get('/api/status', (req: Request, res: Response) => {
    res.json({
      currentProvider,
      discoveredTools,
      isConnecting,
      bridgeRunning: activeBridge?.isServerRunning() || false,
      bridgeUrl: activeBridge ? `http://${HOST}:${PORT + 100}` : null,
      logs: connectionLogs.slice(-20)
    });
  });
}
