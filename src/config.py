"""Centralized configuration using Pydantic Settings."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # xAI API
    XAI_API_KEY: str = ""
    
    # GitHub
    GH_TOKEN: Optional[str] = None
    
    # Discord (optional)
    DISCORD_TOKEN: Optional[str] = None
    DISCORD_CHANNEL_ID: Optional[str] = None
    
    # MCP Server
    MCP_HOST: str = "127.0.0.1"  # Secure default: localhost only
    MCP_PORT: int = 6030
    MCP_BASE_URL: Optional[str] = None  # Base URL for MCP (e.g., http://127.0.0.1:6030 or https://dex-mcp.tunn.dev)
    
    # Paths
    ENVS_FILE: Path = Path(__file__).parent.parent / "envs.json"
    
    @property
    def is_local_deployment(self) -> bool:
        """Check if this is a local deployment (localhost/127.0.0.1)."""
        if self.MCP_BASE_URL:
            return "127.0.0.1" in self.MCP_BASE_URL or "localhost" in self.MCP_BASE_URL
        return True  # Default to local
    
    @property
    def server_bind_url(self) -> str:
        """
        URL the server should bind to.
        - Local: http://127.0.0.1:6030 (bind directly)
        - Remote: Behind a proxy, so still bind to local, but serve at /mcp
        """
        return f"http://{self.MCP_HOST}:{self.MCP_PORT}"
    
    @property
    def server_public_url(self) -> str:
        """
        Public URL the server is accessible at.
        - Local: http://127.0.0.1:6030
        - Remote: https://dex-mcp.tunn.dev/mcp
        """
        if self.MCP_BASE_URL:
            if self.is_local_deployment:
                return self.MCP_BASE_URL
            else:
                # Remote deployment: append /mcp
                return f"{self.MCP_BASE_URL.rstrip('/')}/mcp"
        return self.server_bind_url
    
    @property
    def client_mcp_url(self) -> str:
        """
        URL the client should use to connect to MCP.
        Always use the /mcp endpoint.
        - Local: http://127.0.0.1:6030/mcp
        - Remote: https://dex-mcp.tunn.dev/mcp
        """
        if self.MCP_BASE_URL:
            return f"{self.MCP_BASE_URL.rstrip('/')}/mcp"
        return f"{self.server_bind_url}/mcp"
    
    @property
    def client_display_urls(self) -> tuple:
        """
        URLs to display in client UI (base, mcp_endpoint).
        - Local: (http://127.0.0.1:6030, http://127.0.0.1:6030/mcp)
        - Remote: (https://dex-mcp.tunn.dev, https://dex-mcp.tunn.dev/mcp)
        """
        if self.MCP_BASE_URL:
            base = self.MCP_BASE_URL.rstrip('/')
            return (base, f"{base}/mcp")
        base = self.server_bind_url
        return (base, f"{base}/mcp")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton instance
settings = Settings()
