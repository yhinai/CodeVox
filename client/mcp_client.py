"""MCP Client - Direct Python function calls to MCP tools."""

import json
import asyncio
from typing import Dict, List, Any, Optional
import structlog

log = structlog.get_logger()


class MCPClient:
    """Client that directly calls MCP tool functions from src module."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self._tools_loaded = False
        self._env_module = None
        self._process_module = None
        self._github_module = None
        self._claude_module = None
    
    def _ensure_loaded(self):
        """Lazy load the MCP modules."""
        if self._tools_loaded:
            return
        
        try:
            from src import environment as env_module
            from src import process as process_module
            from src import github as github_module
            from src import claude as claude_module
            
            self._env_module = env_module
            self._process_module = process_module
            self._github_module = github_module
            self._claude_module = claude_module
            self._tools_loaded = True
            log.info("mcp.modules.loaded")
        except ImportError as e:
            log.error("mcp.modules.import_error", error=str(e))
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Call a tool by name with the given arguments."""
        self._ensure_loaded()
        
        try:
            # Environment tools
            if tool_name == "list_environments":
                data = self._env_module.load_envs()
                envs = data.get("environments", {})
                return {"environments": list(envs.keys())}
            
            elif tool_name == "get_current_env":
                env_name, env_path = self._env_module.get_current_environment()
                if env_name:
                    return {"name": env_name, "path": env_path}
                # Fall back to sync detection
                env_name, env_data = self._env_module.get_current_environment_sync()
                return {"name": env_name, "path": env_data.get("path") if env_data else None}
            
            elif tool_name == "switch_environment":
                env_name = arguments.get("environment_name", "")
                env_data = self._env_module.get_environment_by_name(env_name)
                if env_data:
                    self._env_module.set_current_environment(env_name, env_data.get("path", ""))
                    return {"success": True, "environment": env_name}
                return {"success": False, "error": f"Environment '{env_name}' not found"}
            
            # Process tools
            elif tool_name == "run_cmd":
                env_name, env_path = self._env_module.get_current_environment()
                if env_path:
                    result = await self._process_module.run_process(
                        cmd="./run.sh",
                        cwd=env_path
                    )
                    return result
                return {"error": "No environment set"}
            
            elif tool_name == "stop_cmd":
                pid = arguments.get("pid", 0)
                force = arguments.get("force", False)
                result = await self._process_module.stop_process(pid, force)
                return result
            
            # Claude tools
            elif tool_name == "ask_coder":
                query = arguments.get("query", "")
                session = self._claude_module.ClaudeSession()
                result = await session.run_query(query)
                return {"response": result}
            
            elif tool_name == "get_status":
                session = self._claude_module.ClaudeSession()
                return {"running": session.is_running, "messages_count": len(session.messages)}
            
            # GitHub tools
            elif tool_name == "get_pr_comments":
                pr_number = arguments.get("pr_number", 0)
                env_name, _ = self._env_module.get_current_environment()
                envs = self._env_module.load_environments()
                env = envs.get(env_name, {})
                repo = env.get("repo", "")
                if repo:
                    comments = self._github_module.get_pr_comments(repo, pr_number)
                    return {"comments": comments}
                return {"error": "No repo configured for current environment"}
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            log.error("mcp.call_tool.error", tool=tool_name, error=str(e))
            return {"error": str(e)}


# Hardcoded tool definitions for the claude-code-mcp server
CLAUDE_CODE_MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_environments",
            "description": "List all available project environments",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_env",
            "description": "Get the current active environment",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "switch_environment",
            "description": "Switch to a different project environment",
            "parameters": {
                "type": "object",
                "properties": {
                    "environment_name": {"type": "string", "description": "Name of the environment to switch to"}
                },
                "required": ["environment_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_coder",
            "description": "Ask the Coding Agent a question and get a response",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The question or task for the Coding Agent"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "Check if Coding Agent is currently running",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_cmd",
            "description": "Start the run script for the current environment",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_cmd",
            "description": "Stop a running process by PID",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "Process ID to stop"},
                    "force": {"type": "boolean", "description": "Force kill with SIGKILL"}
                },
                "required": ["pid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pr_comments",
            "description": "Get all comments from a pull request",
            "parameters": {
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer", "description": "Pull request number"}
                },
                "required": ["pr_number"]
            }
        }
    }
]
