"""MCP Client using FastMCP Python client."""

import json
from typing import Dict, List, Any, Optional
import structlog

log = structlog.get_logger()


class MCPClient:
    """Client that uses FastMCP to connect to MCP servers."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self._client = None
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Call a tool on the MCP server using FastMCP Client."""
        try:
            from fastmcp import Client
            
            client = Client(self.server_url)
            async with client:
                result = await client.call_tool(tool_name, arguments)
                log.info("mcp.call_tool.raw_result", result=str(result)[:200])
                
                # FastMCP returns a CallToolResult with content list
                if hasattr(result, 'content') and result.content:
                    content = result.content
                    if isinstance(content, list) and len(content) > 0:
                        item = content[0]
                        if hasattr(item, 'text'):
                            text = item.text
                            # Try to parse as JSON, otherwise return as string
                            try:
                                return json.loads(text)
                            except:
                                return {"result": text}
                        return {"result": str(item)}
                    return {"result": str(content)}
                elif hasattr(result, 'data'):
                    return result.data if result.data else {"result": "OK"}
                else:
                    return {"result": str(result)}
                    
        except Exception as e:
            log.error("mcp.call_tool.error", tool=tool_name, error=str(e))
            return {"error": str(e)}
    
    async def list_tools(self) -> List[Dict]:
        """List available tools from the MCP server."""
        try:
            from fastmcp import Client
            
            client = Client(self.server_url)
            async with client:
                tools = await client.list_tools()
                return [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": t.inputSchema if hasattr(t, 'inputSchema') else {"type": "object", "properties": {}}
                        }
                    }
                    for t in tools
                ]
        except Exception as e:
            log.error("mcp.list_tools.error", error=str(e))
            return []


# Hardcoded tool definitions as fallback
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
