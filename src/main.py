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
from .github import fetch_pr_comments, fetch_pr_info

# Load environment variables from .env file
load_dotenv()

# Create FastMCP server WITHOUT authentication for now
mcp = FastMCP("claude-code-chat")

# Environment configuration file path
ENVS_FILE = Path(__file__).parent.parent / "envs.json"


@mcp.tool()
async def ask_claude(query: str) -> str:
    """Ask Claude Code a question and get a response

    Args:
        query: The question or prompt to send to Claude Code

    Returns:
        Claude Code's first response with a note about background processing
    """
    print(f"\n[API CALL] ask_claude - Query: {query[:100]}{'...' if len(query) > 100 else ''}")
    return await ask_claude_async(query)


@mcp.tool()
def get_status() -> bool:
    """Check if Claude Code is currently running

    Returns:
        True if Claude is still processing, False otherwise
    """
    print(f"[API CALL] get_status")
    return get_claude_status()


@mcp.tool()
def pop_messages() -> str:
    """Get all intermediate messages from Claude Code execution

    Returns:
        JSON string containing all messages collected during Claude execution,
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
def set_env(key: str, value: str) -> str:
    """Set an environment variable

    Args:
        key: The environment variable name
        value: The value to set

    Returns:
        Confirmation message
    """
    print(f"[API CALL] set_env - Key: {key}")
    os.environ[key] = value
    return f"Set environment variable {key}='{value}'"


@mcp.tool()
def get_env(key: str) -> str:
    """Get an environment variable

    Args:
        key: The environment variable name

    Returns:
        The environment variable value or error message
    """
    print(f"[API CALL] get_env - Key: {key}")
    value = os.getenv(key)
    if value is None:
        return f"Environment variable '{key}' is not set"
    return f"{key}='{value}'"


@mcp.tool()
def list_env() -> str:
    """List all environment variables

    Returns:
        List of all environment variables
    """
    print(f"[API CALL] list_env")
    env_vars = dict(os.environ)
    if not env_vars:
        return "No environment variables set"

    # Format as key=value pairs
    formatted = "\n".join(f"{k}={v}" for k, v in sorted(env_vars.items()))
    return f"Environment variables:\n{formatted}"


@mcp.tool()
def delete_env(key: str) -> str:
    """Delete an environment variable

    Args:
        key: The environment variable name to delete

    Returns:
        Confirmation message
    """
    print(f"[API CALL] delete_env - Key: {key}")
    if key in os.environ:
        del os.environ[key]
        return f"Deleted environment variable '{key}'"
    return f"Environment variable '{key}' does not exist"


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
    """Switch Claude Code's working directory to a specific project environment

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
def run_project(environment_name: str) -> str:
    """Execute the run script for a specific project environment

    Args:
        environment_name: The name/key of the environment whose script to run

    Returns:
        Output from the run script
    """
    print(f"[API CALL] run_project - Environment: {environment_name}")
    data = load_envs()
    environments = data.get("environments", {})

    if environment_name not in environments:
        available = ", ".join(environments.keys())
        return f"Environment '{environment_name}' not found. Available: {available}"

    env = environments[environment_name]
    run_script = env.get('run_script')

    if not run_script:
        return f"Environment '{environment_name}' has no run script configured"

    if not os.path.exists(run_script):
        return f"Run script does not exist: {run_script}"

    try:
        # Run the script in the environment's directory
        path = env.get('path', os.path.dirname(run_script))
        result = subprocess.run(
            [run_script],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30
        )

        output = f"Executed: {run_script}\n"
        output += f"Exit code: {result.returncode}\n\n"

        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"

        return output
    except subprocess.TimeoutExpired:
        return f"Script execution timed out after 30 seconds: {run_script}"
    except Exception as e:
        return f"Error running script: {str(e)}"


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
async def debug_redis() -> str:
    """Debug tool to see all Redis keys and their values

    Returns:
        All Redis keys related to processes
    """
    print(f"[API CALL] debug_redis")
    r = await get_redis()

    result = "Redis Debug Information:\n\n"

    # Get all keys
    all_keys = []
    async for key in r.scan_iter("*"):
        all_keys.append(key)

    if not all_keys:
        return "No keys found in Redis"

    result += f"Total keys: {len(all_keys)}\n\n"

    # Group by process
    process_keys = {}
    other_keys = []

    for key in sorted(all_keys):
        if key.startswith("process:"):
            parts = key.split(":")
            if len(parts) >= 2:
                proc_name = parts[1]
                if proc_name not in process_keys:
                    process_keys[proc_name] = []
                process_keys[proc_name].append(key)
        else:
            other_keys.append(key)

    # Show process keys
    if process_keys:
        result += "Process Keys:\n"
        for proc_name, keys in process_keys.items():
            result += f"\n  Process: {proc_name}\n"
            for key in keys:
                if ":info" in key:
                    info = await r.hgetall(key)
                    result += f"    {key}: {info}\n"
                elif ":logs" in key:
                    log_count = await r.llen(key)
                    result += f"    {key}: {log_count} entries\n"
                else:
                    value = await r.get(key)
                    result += f"    {key}: {value}\n"

    # Show other keys
    if other_keys:
        result += "\nOther Keys:\n"
        for key in other_keys:
            value = await r.get(key)
            result += f"  {key}: {value}\n"

    return result


@mcp.tool()
def find_process_children(pid: int) -> str:
    """Find all child processes of a given PID using ps

    Args:
        pid: Parent process ID

    Returns:
        List of child processes
    """
    print(f"[API CALL] find_process_children - PID: {pid}")

    try:
        result = subprocess.run(
            ['ps', '--ppid', str(pid), '-o', 'pid,cmd', '--no-headers'],
            capture_output=True,
            text=True
        )

        if result.returncode != 0 or not result.stdout.strip():
            return f"No child processes found for PID {pid}"

        return f"Child processes of PID {pid}:\n{result.stdout}"
    except Exception as e:
        return f"Error finding children of PID {pid}: {e}"


@mcp.tool()
async def list_processes() -> str:
    """List all managed processes and their status

    Returns:
        List of all processes with their PIDs and details
    """
    print(f"[API CALL] list_processes")
    processes = await list_all_processes()

    if not processes:
        return "No processes being managed"

    result = "Managed processes:\n\n"
    for pid in sorted(processes.keys()):
        info = processes[pid]

        result += f"PID {pid}"
        result += " [ALIVE]" if info['is_alive'] else " [DEAD]"
        result += "\n"
        result += f"  Command: {info.get('cmd', 'N/A')}\n"
        result += f"  Environment: {info.get('env', 'N/A')}\n"
        result += f"  Working dir: {info.get('cwd', 'N/A')}\n"

        if 'exit_code' in info:
            started_at = float(info.get('started_at', 0))
            ended_at = float(info.get('ended_at', 0))
            result += f"  Status: Stopped (exit code: {info['exit_code']})\n"
            result += f"  Runtime: {ended_at - started_at:.1f}s\n"
        else:
            started_at = float(info.get('started_at', time.time()))
            runtime = time.time() - started_at
            result += f"  Status: Running\n"
            result += f"  Runtime: {runtime:.1f}s\n"

        if info['log_count'] > 0:
            result += f"  Logs: {info['log_count']} lines ✓\n"
        else:
            result += f"  Logs: 0 lines (no output yet)\n"
        result += "\n"

    return result.strip()


@mcp.tool()
async def get_process_logs(pid: int, tail: int = None) -> str:
    """Get logs from a process by PID

    Args:
        pid: Process ID
        tail: Optional number of most recent lines to return (default: all)

    Returns:
        Process logs as formatted text
    """
    print(f"[API CALL] get_process_logs - PID: {pid}, Tail: {tail}")

    data = await get_process_logs_data(pid, tail)
    if not data:
        return f"Process {pid} not found"

    proc_info = data['info']
    logs = data['logs']

    if not logs:
        status = "stopped" if 'exit_code' in proc_info else "running"
        return f"No logs yet for process {pid} (status: {status})"

    # Format logs
    result = f"Logs for PID {pid}:\n"
    result += f"Command: {proc_info.get('cmd', 'N/A')}\n"
    result += f"Environment: {proc_info.get('env', 'N/A')}\n"
    started_at = float(proc_info.get('started_at', 0))
    result += f"Started: {time.ctime(started_at)}\n"

    if 'exit_code' in proc_info:
        result += f"Exit code: {proc_info['exit_code']}\n"

    result += "\n" + "=" * 70 + "\n\n"

    for log_entry in logs:
        log_type = log_entry.get('type', 'stdout')
        line = log_entry.get('line', '')
        prefix = "[STDERR]" if log_type == 'stderr' else "[STDOUT]"
        result += f"{prefix} {line}\n"

    return result


@mcp.tool()
def get_pr_comments(pr_number: int, environment_name: str = None, include_outdated: bool = False) -> str:
    """Get PR comments for a specific PR number

    Args:
        pr_number: Pull request number
        environment_name: Optional environment name to get github_repo from. If not provided, uses current environment.
        include_outdated: If True, include outdated review comments

    Returns:
        JSON string with PR comments
    """
    print(f"[API CALL] get_pr_comments - PR: {pr_number}, Env: {environment_name}")

    # Get environment
    if environment_name:
        env = get_environment_by_name(environment_name)
        if not env:
            return json.dumps({"error": f"Environment '{environment_name}' not found"}, indent=2)
    else:
        env_key, env = get_current_environment_sync()
        if not env:
            return json.dumps({"error": "Not in a configured environment. Please specify environment_name or switch to an environment."}, indent=2)

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
def get_active_pr_comments(environment_name: str = None, include_outdated: bool = False) -> str:
    """Get comments for all active PRs in an environment

    Args:
        environment_name: Optional environment name. If not provided, uses current environment.
        include_outdated: If True, include outdated review comments

    Returns:
        JSON string with all active PR comments
    """
    print(f"[API CALL] get_active_pr_comments - Env: {environment_name}")

    # Get environment
    if environment_name:
        env = get_environment_by_name(environment_name)
        env_key = environment_name
        if not env:
            return json.dumps({"error": f"Environment '{environment_name}' not found"}, indent=2)
    else:
        env_key, env = get_current_environment_sync()
        if not env:
            return json.dumps({"error": "Not in a configured environment. Please specify environment_name or switch to an environment."}, indent=2)

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
def get_pr_info_tool(pr_number: int, environment_name: str = None) -> str:
    """Get PR information including title, description, status, etc.

    Args:
        pr_number: Pull request number
        environment_name: Optional environment name to get github_repo from. If not provided, uses current environment.

    Returns:
        JSON string with PR information
    """
    print(f"[API CALL] get_pr_info - PR: {pr_number}, Env: {environment_name}")

    # Get environment
    if environment_name:
        env = get_environment_by_name(environment_name)
        if not env:
            return json.dumps({"error": f"Environment '{environment_name}' not found"}, indent=2)
    else:
        env_key, env = get_current_environment_sync()
        if not env:
            return json.dumps({"error": "Not in a configured environment. Please specify environment_name or switch to an environment."}, indent=2)

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
