"""Environment and system management - No Redis required."""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import settings


# In-memory state (replaces Redis)
_current_env_key: Optional[str] = None
_current_env_path: Optional[str] = None


def load_envs() -> Dict:
    """Load environments from envs.json (read-only)."""
    if not settings.ENVS_FILE.exists():
        return {"environments": {}}
    with open(settings.ENVS_FILE, 'r') as f:
        return json.load(f)


def set_current_environment(env_key: str, path: str) -> None:
    """Store current environment in memory."""
    global _current_env_key, _current_env_path
    _current_env_key = env_key
    _current_env_path = path
    print(f"[ENV] Set current environment: {env_key} -> {path}")


def get_current_environment() -> Tuple[Optional[str], Optional[str]]:
    """Get current environment from memory."""
    return _current_env_key, _current_env_path


def get_environment_by_name(env_name: str) -> Optional[Dict]:
    """Get environment configuration by name."""
    data = load_envs()
    environments = data.get("environments", {})
    return environments.get(env_name)


def get_current_environment_sync() -> Tuple[Optional[str], Optional[Dict]]:
    """Get current working directory and matching environment if any."""
    cwd = os.getcwd()
    data = load_envs()
    environments = data.get("environments", {})

    # Check if current directory matches any environment
    for key, env in environments.items():
        if env.get('path') == cwd:
            return key, env

    return None, None
