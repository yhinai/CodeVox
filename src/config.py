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
    
    # Paths
    ENVS_FILE: Path = Path(__file__).parent.parent / "envs.json"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton instance
settings = Settings()
