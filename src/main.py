"""
Claude Code MCP Server - Clean Architecture
Minimal entry point with modular tool registration.
"""
import json
import structlog
from fastmcp import FastMCP
import uvicorn

from .config import settings
from .claude import get_default_session
from . import environment
from . import process
from . import github

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
mcp = FastMCP("claude-code-mcp")


# ============================================================================
# CODING TOOLS
# ============================================================================

@mcp.tool()
async def ask_coder(query: str) -> str:
    """Ask the Coding Agent a question and get a response."""
    log.info("tool.ask_coder", query_preview=query[:100])
    env_key, env_path = environment.get_current_environment()
    session = get_default_session(env_path or ".")
    return await session.ask(query)


@mcp.tool()
def get_status() -> str:
    """Check if Coding Agent is currently running."""
    session = get_default_session()
    return json.dumps(session.get_status(), indent=2)


@mcp.tool()
def pop_messages() -> str:
    """Get all intermediate messages from Coding Agent execution."""
    session = get_default_session()
    messages = session.pop_messages()
    return json.dumps([
        {"content": m.content, "type": m.message_type, "timestamp": m.timestamp}
        for m in messages
    ], indent=2)


# ============================================================================
# ENVIRONMENT TOOLS (from module)
# ============================================================================

mcp.tool()(environment.list_environments)
mcp.tool()(environment.get_current_env)
mcp.tool()(environment.switch_environment)
mcp.tool()(environment.create_environment)


# ============================================================================
# PROCESS TOOLS (from module)
# ============================================================================

mcp.tool()(process.run_cmd)
mcp.tool()(process.stop_cmd)
mcp.tool()(process.restart_cmd)


# ============================================================================
# GITHUB TOOLS
# ============================================================================

@mcp.tool()
def get_pr_comments(pr_number: int) -> str:
    """Get all comments from a pull request."""
    env_key, _ = environment.get_current_environment()
    if not env_key:
        return "No environment set. Use switch_environment() first."
    
    env = environment.get_environment_by_name(env_key)
    if not env or not env.get("github_repo"):
        return f"No github_repo configured for '{env_key}'"
    
    result = github.fetch_pr_comments(env["github_repo"], pr_number)
    return json.dumps(result, indent=2)


@mcp.tool()
def get_pr_info(pr_number: int) -> str:
    """Get detailed information about a pull request."""
    env_key, _ = environment.get_current_environment()
    if not env_key:
        return "No environment set. Use switch_environment() first."
    
    env = environment.get_environment_by_name(env_key)
    if not env or not env.get("github_repo"):
        return f"No github_repo configured for '{env_key}'"
    
    result = github.fetch_pr_info(env["github_repo"], pr_number)
    return json.dumps(result, indent=2)


@mcp.tool()
def add_pr_comment_respond(pr_number: int, comment_id: int, body: str) -> str:
    """Reply to a specific PR review comment."""
    env_key, _ = environment.get_current_environment()
    if not env_key:
        return "No environment set. Use switch_environment() first."
    
    env = environment.get_environment_by_name(env_key)
    if not env or not env.get("github_repo"):
        return f"No github_repo configured for '{env_key}'"
    
    result = github.respond_to_pr_comment(env["github_repo"], pr_number, comment_id, body)
    return json.dumps(result, indent=2)


# ============================================================================
# SERVER
# ============================================================================

def main():
    """Run the MCP server."""
    log.info("server.starting", url=settings.server_public_url)
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Claude Code MCP Server                             ║
╠══════════════════════════════════════════════════════════════╣
║  URL: {settings.server_public_url:<53} ║
║  Tools: 12 (coding, process, environment, github)            ║
╚══════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(
        mcp.http_app(),
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        log_level="warning",
        ws="wsproto"
    )


if __name__ == "__main__":
    main()
