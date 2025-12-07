"""
Environment Management - Singleton Class Pattern
No global variables. Clean, testable architecture.
"""
import json
import structlog
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import settings

log = structlog.get_logger()


class EnvironmentManager:
    """Manages project environments with clean state encapsulation."""
    
    def __init__(self):
        self._current_key: Optional[str] = None
        self._current_path: Optional[str] = None
    
    def load_envs(self) -> Dict:
        """Load environments from envs.json."""
        if not settings.ENVS_FILE.exists():
            return {"environments": {}}
        with open(settings.ENVS_FILE, 'r') as f:
            return json.load(f)
    
    def save_envs(self, data: Dict) -> None:
        """Save environments to envs.json."""
        with open(settings.ENVS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def set_current(self, env_key: str, path: str) -> None:
        """Set the current active environment."""
        self._current_key = env_key
        self._current_path = path
        log.info("environment.switched", key=env_key, path=path)
    
    def get_current(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current environment (key, path)."""
        return self._current_key, self._current_path
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get environment config by name."""
        data = self.load_envs()
        return data.get("environments", {}).get(name)
    
    def list_all(self) -> Dict:
        """List all environments."""
        return self.load_envs().get("environments", {})
    
    def create(self, name: str, path: str, run_script: str = "", 
               github_repo: str = "", description: str = "") -> str:
        """Create or update an environment configuration."""
        data = self.load_envs()
        
        data["environments"][name] = {
            "name": name,
            "path": path,
            "run_script": run_script,
            "github_repo": github_repo,
            "description": description
        }
        
        self.save_envs(data)
        log.info("environment.created", name=name, path=path)
        return f"Environment '{name}' configured at {path}"


# Singleton instance
env_manager = EnvironmentManager()


# Public API functions (for tool registration)
def list_environments() -> str:
    """List all available project environments."""
    environments = env_manager.list_all()
    
    if not environments:
        return "No environments configured. Use create_environment() to add one."
    
    lines = ["Available Environments:", "=" * 40]
    for key, env in environments.items():
        lines.append(f"\n• {key}")
        lines.append(f"  Path: {env.get('path', 'N/A')}")
        lines.append(f"  Run: {env.get('run_script', 'N/A')}")
        if env.get('github_repo'):
            lines.append(f"  GitHub: {env.get('github_repo')}")
    
    return "\n".join(lines)


def get_current_env() -> str:
    """Get the current active environment."""
    import json
    env_key, env_path = env_manager.get_current()
    if env_key:
        env_data = env_manager.get_by_name(env_key)
        return json.dumps({"key": env_key, "path": env_path, "config": env_data}, indent=2)
    return "No environment currently set. Use switch_environment() to set one."


def switch_environment(environment_name: str) -> str:
    """Switch to a different project environment."""
    env = env_manager.get_by_name(environment_name)
    if not env:
        available = list(env_manager.list_all().keys())
        return f"Environment '{environment_name}' not found. Available: {available}"
    
    path = env.get("path", ".")
    env_manager.set_current(environment_name, path)
    return f"Switched to environment: {environment_name} ({path})"


def create_environment(name: str, path: str, run_script: str = "") -> str:
    """Create or update a project environment configuration."""
    return env_manager.create(name, path, run_script)


# Backwards compatibility
def get_current_environment() -> Tuple[Optional[str], Optional[str]]:
    return env_manager.get_current()

def set_current_environment(env_key: str, path: str) -> None:
    env_manager.set_current(env_key, path)

def get_environment_by_name(env_name: str) -> Optional[Dict]:
    return env_manager.get_by_name(env_name)

def load_envs() -> Dict:
    return env_manager.load_envs()
