"""
Autonomous MCP Server - Golden Path Architecture
Clean entry point with dynamic tools.
"""
import json
import structlog
import uvicorn
from fastmcp import FastMCP

from .config import settings
from .engine import engine

# Logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
)
log = structlog.get_logger()

# Initialize MCP
mcp = FastMCP("claude-autonomous-mcp")


# =============================================================================
# DISCOVERY TOOLS
# =============================================================================

@mcp.tool()
def refresh_projects() -> str:
    """Scan the filesystem to discover Git projects in configured paths."""
    return engine.scan_projects(settings.search_paths_list)


@mcp.tool()
def list_projects() -> str:
    """List all discovered projects with their type and GitHub remote."""
    return engine.list_projects()


# =============================================================================
# EXECUTION TOOLS
# =============================================================================

@mcp.tool()
async def run_in_project(project_name: str, command: str) -> str:
    """
    Execute a shell command inside a discovered project.
    Example: run_in_project("my-app", "npm install")
    """
    return await engine.run_command(project_name, command)


@mcp.tool()
async def run_shell(command: str, cwd: str = "~") -> str:
    """
    Execute a raw shell command in any directory.
    Example: run_shell("ls -la", "~/code")
    """
    return await engine.run_raw(command, cwd)


@mcp.tool()
def get_process_stats() -> str:
    """Get system health stats and tracked background processes."""
    return engine.get_process_stats()


# =============================================================================
# GITHUB TOOLS
# =============================================================================

@mcp.tool()
async def github_api(method: str, endpoint: str, payload: str = "{}") -> str:
    """
    Universal GitHub API access. Constructs any API call dynamically.
    
    Examples:
    - github_api("GET", "/repos/owner/repo/pulls")
    - github_api("POST", "/repos/owner/repo/issues", '{"title": "Bug"}')
    - github_api("GET", "/user/repos")
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return "Error: Invalid JSON payload"
    
    result = await engine.call_github(method, endpoint, data, settings.GH_TOKEN)
    return json.dumps(result, indent=2)


# =============================================================================
# CLAUDE AGENT TOOLS
# =============================================================================

@mcp.tool()
async def ask_coder(query: str, project_name: str = "") -> str:
    """
    Query the Claude coding agent.
    Optionally specify a project to set the working directory.
    """
    if project_name and project_name in engine.projects:
        cwd = engine.projects[project_name].path
    else:
        cwd = "."
    return await engine.ask_claude(query, cwd)


# =============================================================================
# SERVER
# =============================================================================

def main():
    """Start the autonomous MCP server."""
    log.info("server.starting", url=settings.server_url)
    
    # Auto-scan on startup
    discovery_result = engine.scan_projects(settings.search_paths_list)
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Claude Autonomous MCP Server                       ║
╠══════════════════════════════════════════════════════════════╣
║  URL: {settings.mcp_endpoint:<53} ║
║  Tools: 7 (discovery, execution, github, claude)             ║
╠══════════════════════════════════════════════════════════════╣
║  {discovery_result.split(chr(10))[0]:<60} ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        mcp.http_app(),
        host=settings.HOST,
        port=settings.PORT,
        log_level="warning",
        ws="wsproto"
    )


if __name__ == "__main__":
    main()
