"""Environment configuration management"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
import redis.asyncio as redis


# Environment configuration file path
ENVS_FILE = Path(__file__).parent.parent / "envs.json"

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Redis client for state management
_redis_client = None


def load_envs() -> Dict:
    """Load environments from envs.json (read-only)"""
    if not ENVS_FILE.exists():
        return {"environments": {}}
    with open(ENVS_FILE, 'r') as f:
        return json.load(f)


async def get_redis():
    """Get Redis client instance"""
    global _redis_client
    if _redis_client is None:
        _redis_client = await redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
    return _redis_client


async def clear_redis():
    """Clear all Redis data on startup"""
    r = await get_redis()
    await r.flushdb()
    print("[REDIS] Cleared all data")


async def set_current_environment(env_key: str, path: str):
    """Store current environment in Redis"""
    r = await get_redis()
    await r.set("current_env:key", env_key)
    await r.set("current_env:path", path)
    print(f"[REDIS] Set current environment: {env_key} -> {path}")


async def get_current_environment() -> Tuple[Optional[str], Optional[str]]:
    """Get current environment from Redis"""
    r = await get_redis()
    env_key = await r.get("current_env:key")
    path = await r.get("current_env:path")
    return env_key, path


def get_environment_by_name(env_name: str) -> Optional[Dict]:
    """Get environment configuration by name"""
    data = load_envs()
    environments = data.get("environments", {})
    return environments.get(env_name)


def get_current_environment_sync() -> Tuple[Optional[str], Optional[Dict]]:
    """Get current working directory and matching environment if any (synchronous)"""
    cwd = os.getcwd()
    data = load_envs()
    environments = data.get("environments", {})

    # Check if current directory matches any environment
    for key, env in environments.items():
        if env.get('path') == cwd:
            return key, env

    return None, None
