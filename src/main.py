"""
Claude Code MCP Server - Lean & Elegant
FastMCP server exposing Claude Code tools at http://localhost:6030
"""

import json
import structlog
from fastmcp import FastMCP
import uvicorn

from .config import settings
from .claude import get_default_session, ClaudeSession
from .environment import (
    load_envs,
    get_current_environment,
    set_current_environment,
    get_environment_by_name,
)
from .process import start_process, stop_process, list_all_processes, get_process_object
from .github import fetch_pr_comments, fetch_pr_info, respond_to_pr_comment

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
)
log = structlog.get_logger()

# Initialize MCP Server
mcp = FastMCP("claude-code-mcp")


# ============================================================================
# CLAUDE CODING TOOLS
# ============================================================================

@mcp.tool()
async def ask_coder(query: str) -> str:
    """Ask the Coding Agent a question and get a response."""
    log.info("tool.ask_coder", query_preview=query[:100])
    env_key, env_path = get_current_environment()
    session = get_default_session(env_path or ".")
    return await session.ask(query)


@mcp.tool()
def get_status() -> str:
    """Check if Coding Agent is currently running."""
    session = get_default_session()
    status = session.get_status()
    return json.dumps(status, indent=2)


@mcp.tool()
def pop_messages() -> str:
    """
    Get all intermediate messages from Coding Agent execution.
    
    IMPORTANT: Only call when user explicitly requests execution details.
    """
    session = get_default_session()
    messages = session.pop_messages()
    return json.dumps([
        {"content": m.content, "type": m.message_type, "timestamp": m.timestamp}
        for m in messages
    ], indent=2)


# ============================================================================
# ENVIRONMENT MANAGEMENT
# ============================================================================

@mcp.tool()
def list_environments() -> str:
    """List all available project environments."""
    data = load_envs()
    environments = data.get("environments", {})
    
    if not environments:
        return "No environments configured. Edit envs.json to add projects."
    
    lines = ["Available Environments:", "=" * 40]
    for key, env in environments.items():
        lines.append(f"\n• {key}")
        lines.append(f"  Path: {env.get('path', 'N/A')}")
        lines.append(f"  Run: {env.get('run_script', 'N/A')}")
        if env.get('github_repo'):
            lines.append(f"  GitHub: {env.get('github_repo')}")
        if env.get('active_prs'):
            prs = [f"#{p['pr_num']}" for p in env['active_prs']]
            lines.append(f"  PRs: {', '.join(prs)}")
    
    return "\n".join(lines)


@mcp.tool()
def get_current_env() -> str:
    """Get the current active environment."""
    env_key, env_path = get_current_environment()
    if env_key:
        env_data = get_environment_by_name(env_key)
        return json.dumps({"key": env_key, "path": env_path, "config": env_data}, indent=2)
    return "No environment currently set. Use switch_environment() to set one."


@mcp.tool()
def switch_environment(environment_name: str) -> str:
    """Switch to a different project environment."""
    log.info("tool.switch_environment", name=environment_name)
    
    env = get_environment_by_name(environment_name)
    if not env:
        available = list(load_envs().get("environments", {}).keys())
        return f"Environment '{environment_name}' not found. Available: {available}"
    
    path = env.get("path", ".")
    set_current_environment(environment_name, path)
    return f"Switched to environment: {environment_name} ({path})"


# ============================================================================
# PROCESS MANAGEMENT
# ============================================================================

@mcp.tool()
async def run_cmd() -> str:
    """Start the run script for the current environment."""
    env_key, env_path = get_current_environment()
    
    if not env_key:
        return "No environment set. Use switch_environment() first."
    
    env = get_environment_by_name(env_key)
    if not env:
        return f"Environment '{env_key}' not found"
    
    run_script = env.get("run_script")
    if not run_script:
        return f"No run_script configured for '{env_key}'"
    
    log.info("tool.run_cmd", env=env_key, script=run_script)
    pid = await start_process(run_script, env_path, env_key)
    return f"Started process PID: {pid}\nCommand: {run_script}\nLogs: {env_path}/run.log"


@mcp.tool()
async def stop_cmd(pid: int, force: bool = False) -> str:
    """Stop a running process by PID."""
    log.info("tool.stop_cmd", pid=pid, force=force)
    return await stop_process(pid, force)


@mcp.tool()
async def restart_cmd(pid: int) -> str:
    """Restart a process by stopping it and starting a new one."""
    log.info("tool.restart_cmd", pid=pid)
    
    # Get original process info
    proc = get_process_object(pid)
    if not proc:
        return f"Process {pid} not found"
    
    # Stop old process
    await stop_process(pid, force=True)
    
    # Start new process
    env_key, env_path = get_current_environment()
    if env_key:
        env = get_environment_by_name(env_key)
        run_script = env.get("run_script", "") if env else ""
        if run_script:
            new_pid = await start_process(run_script, env_path, env_key)
            return f"Stopped PID {pid}, started new PID {new_pid}"
    
    return f"Stopped PID {pid} but couldn't restart (no environment set)"


# ============================================================================
# GITHUB PR TOOLS
# ============================================================================

@mcp.tool()
def get_pr_comments(pr_number: int) -> str:
    """Get all comments from a pull request."""
    env_key, _ = get_current_environment()
    
    if not env_key:
        return "No environment set. Use switch_environment() first."
    
    env = get_environment_by_name(env_key)
    if not env:
        return f"Environment '{env_key}' not found"
    
    github_repo = env.get("github_repo")
    if not github_repo:
        return f"No github_repo configured for '{env_key}'"
    
    log.info("tool.get_pr_comments", repo=github_repo, pr=pr_number)
    result = fetch_pr_comments(github_repo, pr_number)
    return json.dumps(result, indent=2)


@mcp.tool()
def get_active_pr_comments() -> str:
    """Get comments from all active PRs in current environment."""
    env_key, _ = get_current_environment()
    
    if not env_key:
        return "No environment set. Use switch_environment() first."
    
    env = get_environment_by_name(env_key)
    if not env:
        return f"Environment '{env_key}' not found"
    
    github_repo = env.get("github_repo")
    active_prs = env.get("active_prs", [])
    
    if not github_repo:
        return f"No github_repo configured for '{env_key}'"
    
    if not active_prs:
        return f"No active PRs configured for '{env_key}'"
    
    all_comments = {}
    for pr in active_prs:
        pr_num = pr.get("pr_num")
        if pr_num:
            log.info("tool.get_active_pr_comments", repo=github_repo, pr=pr_num)
            all_comments[pr_num] = fetch_pr_comments(github_repo, pr_num)
    
    return json.dumps(all_comments, indent=2)


@mcp.tool()
def get_pr_info(pr_number: int) -> str:
    """Get detailed information about a pull request."""
    env_key, _ = get_current_environment()
    
    if not env_key:
        return "No environment set. Use switch_environment() first."
    
    env = get_environment_by_name(env_key)
    if not env:
        return f"Environment '{env_key}' not found"
    
    github_repo = env.get("github_repo")
    if not github_repo:
        return f"No github_repo configured for '{env_key}'"
    
    log.info("tool.get_pr_info", repo=github_repo, pr=pr_number)
    result = fetch_pr_info(github_repo, pr_number)
    return json.dumps(result, indent=2)


@mcp.tool()
def add_pr_comment_respond(pr_number: int, comment_id: int, body: str) -> str:
    """Reply to a specific PR review comment."""
    env_key, _ = get_current_environment()
    
    if not env_key:
        return "No environment set. Use switch_environment() first."
    
    env = get_environment_by_name(env_key)
    if not env:
        return f"Environment '{env_key}' not found"
    
    github_repo = env.get("github_repo")
    if not github_repo:
        return f"No github_repo configured for '{env_key}'"
    
    log.info("tool.add_pr_comment_respond", repo=github_repo, pr=pr_number, comment=comment_id)
    result = respond_to_pr_comment(github_repo, pr_number, comment_id, body)
    return json.dumps(result, indent=2)


# ============================================================================
# SERVER ENTRY POINT
# ============================================================================

def main():
    """Run the MCP server."""
    log.info("server.starting", host=settings.MCP_HOST, port=settings.MCP_PORT)
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Claude Code MCP Server - Lean Edition              ║
╠══════════════════════════════════════════════════════════════╣
║  URL: http://{settings.MCP_HOST}:{settings.MCP_PORT}                                  ║
║  Tools: 11 (coding, process, environment, github)            ║
║  Redis: Not required                                         ║
╚══════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(
        mcp.http_app(),
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
        log_level="warning"
    )


if __name__ == "__main__":
    main()
