from fastmcp import FastMCP
import uvicorn
import os
import json
import subprocess
import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv

# Import from our modules
from .environment import (
    load_envs,
    get_redis,
    clear_redis,
    set_current_environment,
    get_current_environment,
    get_environment_by_name,
    get_current_environment_sync
)
from .process import (
    start_process,
    stop_process,
    list_all_processes,
    get_process_logs_data,
    cleanup_process_object
)
from .discord_client import init_discord_client, send_to_discord
from .claude import ask_claude_async, get_claude_status, get_claude_messages
from .github import fetch_pr_comments, fetch_pr_info, respond_to_pr_comment

# Load environment variables from .env file
load_dotenv()

# Create FastMCP server WITHOUT authentication for now
mcp = FastMCP("claude-code-chat")

# Environment configuration file path
ENVS_FILE = Path(__file__).parent.parent / "envs.json"


@mcp.tool()
async def ask_coder(query: str) -> str:
    """Ask Coding Agent a question and get a response

    Args:
        query: The question or prompt to send to Coding Agent

    Returns:
        Coding Agent's first response with a note about background processing
    """
    print(f"\n[API CALL] ask_coder - Query: {query[:100]}{'...' if len(query) > 100 else ''}")
    return await ask_claude_async(query)


@mcp.tool()
def get_status() -> bool:
    """Check if Coding Agent is currently running

    Returns:
        True if Coding Agent is still processing, False otherwise
    """
    print(f"[API CALL] get_status")
    return get_claude_status()


@mcp.tool()
def pop_messages() -> str:
    """Get all intermediate messages from Coding Agent execution

    IMPORTANT: Do not call this tool unless the user explicitly asks for messages or execution details.
    This should only be used when the user specifically requests to see intermediate messages.

    Returns:
        JSON string containing all messages collected during Coding Agent execution,
        including message type, text, and timestamp (seconds since start)
    """
    print(f"[API CALL] pop_messages")
    messages = get_claude_messages()

    if not messages:
        return json.dumps({
            "status": "no messages",
            "messages": []
        }, indent=2)

    return json.dumps({
        "status": "success",
        "message_count": len(messages),
        "messages": messages
    }, indent=2)


@mcp.tool()
def list_environments() -> str:
    """List all available project environments from envs.json

    Returns:
        List of all project environments with their details
    """
    print(f"[API CALL] list_environments")
    data = load_envs()
    environments = data.get("environments", {})

    if not environments:
        return "No environments configured in envs.json"

    result = "Available environments:\n\n"
    for key, env in environments.items():
        result += f"• {key}\n"
        result += f"  Name: {env.get('name', 'N/A')}\n"
        result += f"  Path: {env.get('path', 'N/A')}\n"
        if env.get('description'):
            result += f"  Description: {env['description']}\n"
        if env.get('run_script'):
            result += f"  Run script: {env['run_script']}\n"
        if env.get('github_repo'):
            result += f"  GitHub repo: {env['github_repo']}\n"
        if env.get('active_prs'):
            result += f"  Active PRs: {env['active_prs']}\n"
        result += "\n"

    return result.strip()


@mcp.tool()
def get_current_environment() -> str:
    """Get the current working directory and matching environment if any

    Returns:
        Current working directory and environment information
    """
    print(f"[API CALL] get_current_environment")
    cwd = os.getcwd()
    env_key, env = get_current_environment_sync()

    result = f"Current directory: {cwd}\n"
    if env:
        result += f"\nMatches environment: {env_key}\n"
        result += f"Name: {env.get('name', 'N/A')}\n"
        if env.get('description'):
            result += f"Description: {env['description']}\n"
        if env.get('github_repo'):
            result += f"GitHub repo: {env['github_repo']}\n"
        if env.get('active_prs'):
            result += f"Active PRs: {json.dumps(env['active_prs'])}\n"
    else:
        result += "\nNo matching environment found"

    return result


@mcp.tool()
async def switch_environment(environment_name: str) -> str:
    """Switch Coding Agent's working directory to a specific project environment

    Args:
        environment_name: The name/key of the environment to switch to

    Returns:
        Confirmation message with new working directory
    """
    print(f"[API CALL] switch_environment - Environment: {environment_name}")
    data = load_envs()
    environments = data.get("environments", {})

    if environment_name not in environments:
        available = ", ".join(environments.keys())
        return f"Environment '{environment_name}' not found. Available: {available}"

    env = environments[environment_name]
    path = env.get('path')

    if not path:
        return f"Environment '{environment_name}' has no path configured"

    if not os.path.exists(path):
        return f"Path does not exist: {path}"

    os.chdir(path)

    # Save environment to Redis
    await set_current_environment(environment_name, path)

    result = f"Switched to environment: {env.get('name', environment_name)}\n"
    result += f"Working directory: {path}"

    return result


@mcp.tool()
async def run_cmd() -> int:
    """Start run.sh script in the background and log its output for the current environment

    Returns:
        PID of the started process
    """
    try:
        # Use current working directory
        cwd = os.getcwd()

        # Check if we're in a configured environment
        env_key, env = get_current_environment_sync()

        # Use run_script from environment if available, otherwise default to run.sh
        if env and env.get('run_script'):
            command = f"bash {env['run_script']}"
        else:
            # Default to run.sh in the working directory
            command = "bash run.sh"

        print(f"[API CALL] run_cmd - Command: {command}, CWD: {cwd}")

        # Start the process
        pid = await start_process(command, cwd, env_key)
        return pid

    except Exception as e:
        print(f"[API CALL] Error starting process: {e}")
        raise


@mcp.tool()
async def stop_cmd(pid: int, force: bool = False) -> str:
    """Stop a running process

    Args:
        pid: Process ID to stop
        force: If True, use SIGKILL instead of SIGTERM

    Returns:
        Confirmation message
    """
    print(f"[API CALL] stop_cmd - PID: {pid}, Force: {force}")
    return await stop_process(pid, force)


@mcp.tool()
async def restart_cmd(pid: int) -> int:
    """Restart a process (stop and start with same run.sh script)

    Args:
        pid: Process ID to restart

    Returns:
        PID of the new process
    """
    r = await get_redis()

    print(f"[API CALL] restart_cmd - PID: {pid}")

    # Get the working directory before stopping
    proc_info = await r.hgetall(f"process:{pid}:info")
    if not proc_info:
        raise ValueError(f"Process {pid} not found")

    cwd = proc_info.get('cwd', os.getcwd())

    # Stop if running
    exit_code = await r.hget(f"process:{pid}:info", "exit_code")
    if exit_code is None:
        await stop_process(pid, force=False)
        # Wait a bit for graceful shutdown
        await asyncio.sleep(1)

    # Remove old process entry
    cleanup_process_object(pid)

    # Clear Redis data for this process
    await r.delete(f"process:{pid}:info")
    await r.delete(f"process:{pid}:logs")

    # Change to the same directory and start new process
    original_cwd = os.getcwd()
    try:
        os.chdir(cwd)
        env_key, env = get_current_environment_sync()

        # Use run_script from environment if available, otherwise default to run.sh
        if env and env.get('run_script'):
            command = f"bash {env['run_script']}"
        else:
            command = "bash run.sh"

        new_pid = await start_process(command, cwd, env_key)
        return new_pid
    finally:
        os.chdir(original_cwd)


@mcp.tool()
def get_pr_comments(pr_number: int, include_outdated: bool = False) -> str:
    """Get PR comments for a specific PR number from the current environment

    Args:
        pr_number: Pull request number
        include_outdated: If True, include outdated review comments

    Returns:
        JSON string with PR comments
    """
    # Get current environment
    env_key, env = get_current_environment_sync()
    if not env:
        return json.dumps({"error": "Not in a configured environment. Please switch to an environment first using switch_environment."}, indent=2)

    print(f"[API CALL] get_pr_comments - PR: {pr_number}, Env: {env_key}")

    # Get github_repo from environment
    github_repo = env.get('github_repo')
    if not github_repo:
        return json.dumps({"error": f"Environment has no github_repo configured"}, indent=2)

    try:
        comments = fetch_pr_comments(github_repo, pr_number, include_outdated)
        return json.dumps(comments, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def get_active_pr_comments(include_outdated: bool = False) -> str:
    """Get comments for all active PRs in the current environment

    Args:
        include_outdated: If True, include outdated review comments

    Returns:
        JSON string with all active PR comments
    """
    # Get current environment
    env_key, env = get_current_environment_sync()
    if not env:
        return json.dumps({"error": "Not in a configured environment. Please switch to an environment first using switch_environment."}, indent=2)

    print(f"[API CALL] get_active_pr_comments - Env: {env_key}")

    # Get github_repo and active_prs from environment
    github_repo = env.get('github_repo')
    active_prs = env.get('active_prs', [])

    if not github_repo:
        return json.dumps({"error": f"Environment has no github_repo configured"}, indent=2)

    if not active_prs:
        return json.dumps({
            "environment": env_key,
            "github_repo": github_repo,
            "active_prs": [],
            "message": "No active PRs configured"
        }, indent=2)

    # Fetch comments for each active PR
    all_pr_data = []
    for pr_info in active_prs:
        pr_num = pr_info.get('pr_num')
        branch_name = pr_info.get('branch_name')

        try:
            comments = fetch_pr_comments(github_repo, pr_num, include_outdated)
            all_pr_data.append({
                "pr_number": pr_num,
                "branch_name": branch_name,
                "comments": comments
            })
        except Exception as e:
            all_pr_data.append({
                "pr_number": pr_num,
                "branch_name": branch_name,
                "error": str(e)
            })

    return json.dumps({
        "environment": env_key,
        "github_repo": github_repo,
        "prs": all_pr_data
    }, indent=2)


@mcp.tool()
def get_pr_info_tool(pr_number: int) -> str:
    """Get PR information including title, description, status, etc. from the current environment

    Args:
        pr_number: Pull request number

    Returns:
        JSON string with PR information
    """
    # Get current environment
    env_key, env = get_current_environment_sync()
    if not env:
        return json.dumps({"error": "Not in a configured environment. Please switch to an environment first using switch_environment."}, indent=2)

    print(f"[API CALL] get_pr_info - PR: {pr_number}, Env: {env_key}")

    # Get github_repo from environment
    github_repo = env.get('github_repo')
    if not github_repo:
        return json.dumps({"error": f"Environment has no github_repo configured"}, indent=2)

    try:
        pr_info = fetch_pr_info(github_repo, pr_number)
        if pr_info is None:
            return json.dumps({"error": "Failed to fetch PR info"}, indent=2)
        return json.dumps(pr_info, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def add_pr_comment_respond(pr_number: int, comment_id: int, response_body: str) -> str:
    """Respond to a PR review comment from the current environment

    Args:
        pr_number: Pull request number
        comment_id: ID of the review comment to respond to
        response_body: The text of the response

    Returns:
        JSON string with the created reply information
    """
    # Get current environment
    env_key, env = get_current_environment_sync()
    if not env:
        return json.dumps({"error": "Not in a configured environment. Please switch to an environment first using switch_environment."}, indent=2)

    print(f"[API CALL] add_pr_comment_respond - PR: {pr_number}, Comment ID: {comment_id}, Env: {env_key}")

    # Get github_repo from environment
    github_repo = env.get('github_repo')
    if not github_repo:
        return json.dumps({"error": f"Environment has no github_repo configured"}, indent=2)

    try:
        reply_info = respond_to_pr_comment(github_repo, pr_number, comment_id, response_body)
        if reply_info is None:
            return json.dumps({"error": "Failed to create reply"}, indent=2)
        return json.dumps({"success": True, "reply": reply_info}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


async def startup():
    """Initialize services on startup"""
    # Clear Redis on startup
    await clear_redis()

    # Initialize Discord client if configured
    await init_discord_client()


if __name__ == "__main__":
    print("Starting Claude Code MCP Server on 0.0.0.0:6030")
    print("=" * 70)
    print("Server URL: https://dex-mcp.tunn.dev/mcp")
    print("=" * 70)
    print("\nNOTE: OAuth is DISABLED due to FastMCP bugs with Claude.ai")
    print("\nTo connect from Claude.ai:")
    print("  1. Go to Settings > Integrations")
    print("  2. Click 'Add custom connector'")
    print("  3. Enter URL: https://dex-mcp.tunn.dev/mcp")
    print("     ^^^^ IMPORTANT: Include the /mcp at the end!\n")

    # Get MCP app (without OAuth)
    app = mcp.http_app()

    # Initialize Discord on startup
    @app.on_event("startup")
    async def on_startup():
        await startup()

    # Run with uvicorn, disabling websockets
    uvicorn.run(app, host="0.0.0.0", port=6030, ws="none")
