"""
Server Configuration - Minimal Pydantic Settings
Auto-expands paths and handles local vs tunnel URLs.
"""
from pydantic_settings import BaseSettings
from typing import Optional, List
from pathlib import Path


class Settings(BaseSettings):
    # API Keys
    XAI_API_KEY: str = ""
    GH_TOKEN: Optional[str] = None
    
    # Server Binding
    HOST: str = "127.0.0.1"
    PORT: int = 6030
    
    # Optional override
    MCP_BASE_URL: Optional[str] = None
    
    # Discovery - Comma-separated paths to scan
    SEARCH_PATHS: str = "~/code,~/projects,~/dev"
    
    @property
    def search_paths_list(self) -> List[Path]:
        """Expand ~ and return list of Paths."""
        return [Path(p.strip()).expanduser() for p in self.SEARCH_PATHS.split(",")]
    
    @property
    def mcp_endpoint(self) -> str:
        if self.MCP_BASE_URL:
            return f"{self.MCP_BASE_URL.rstrip('/')}/mcp"
        return f"http://{self.HOST}:{self.PORT}/mcp"
    
    @property 
    def server_url(self) -> str:
        if self.MCP_BASE_URL:
            return self.MCP_BASE_URL.rstrip('/')
        return f"http://{self.HOST}:{self.PORT}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
