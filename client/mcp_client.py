"""
MCP Client - Dynamic tool discovery from server.
No hardcoded tools. Fetches capabilities at runtime.
"""
import json
import structlog
from typing import Any, Dict, List

log = structlog.get_logger()


class MCPClient:
    """Client that dynamically discovers and executes MCP tools."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self._tools_cache: List[Dict] = []
    
    async def get_adaptable_tools(self) -> List[Dict]:
        """
        Dynamically discover tools from the server.
        Returns tools in OpenAI/Grok function-calling format.
        """
        try:
            from fastmcp import Client
            
            async with Client(self.server_url) as client:
                tools = await client.list_tools()
                
                # Transform FastMCP schema -> OpenAI/Grok function schema
                self._tools_cache = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "No description",
                            "parameters": tool.inputSchema or {"type": "object", "properties": {}}
                        }
                    }
                    for tool in tools
                ]
                
                log.info("mcp.tools_discovered", count=len(self._tools_cache))
                return self._tools_cache
                
        except Exception as e:
            log.error("mcp.discovery_failed", error=str(e))
            return []
    
    @property
    def tools(self) -> List[Dict]:
        """Get cached tools (call get_adaptable_tools first)."""
        return self._tools_cache
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Execute a tool on the MCP server."""
        try:
            from fastmcp import Client
            
            async with Client(self.server_url) as client:
                result = await client.call_tool(tool_name, arguments)
                log.info("mcp.call_tool.success", tool=tool_name)
                
                # Parse FastMCP result format
                if hasattr(result, 'content') and result.content:
                    content = result.content
                    if isinstance(content, list) and len(content) > 0:
                        item = content[0]
                        if hasattr(item, 'text'):
                            text = item.text
                            try:
                                return json.loads(text)
                            except:
                                return {"result": text}
                        return {"result": str(item)}
                    return {"result": str(content)}
                return {"result": str(result)}
                
        except Exception as e:
            log.error("mcp.call_tool.error", tool=tool_name, error=str(e))
            return {"error": str(e)}
