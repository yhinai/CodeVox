"""Process management for running background tasks"""

import asyncio
import json
import os
import time
from typing import Dict, Optional
from .environment import get_redis


# Keep process objects in memory (can't serialize to Redis)
_process_objects: Dict[int, asyncio.subprocess.Process] = {}


async def stream_process_output(pid: int, proc: asyncio.subprocess.Process, log_file_path: str):
    """Background task to capture process output"""
    r = await get_redis()

    def write_log(text: str):
        """Write to log file immediately with sync I/O"""
        with open(log_file_path, 'a', buffering=1) as f:  # Line buffered
            f.write(text)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

    try:
        # Write header
        write_log(f"\n{'=' * 70}\n")
        write_log(f"Process started: PID {pid}\n")
        write_log(f"Timestamp: {time.ctime()}\n")
        write_log(f"{'=' * 70}\n\n")

        # Read stdout
        if proc.stdout:
            async for line in proc.stdout:
                line_str = line.decode('utf-8', errors='replace')

                # Write to log file immediately
                write_log(f"[STDOUT] {line_str}")

                # Append log to Redis list
                log_entry = json.dumps({
                    'type': 'stdout',
                    'line': line_str.rstrip(),
                    'timestamp': time.time()
                })
                await r.rpush(f"process:{pid}:logs", log_entry)
                print(f"[PID:{pid}] {line_str.rstrip()}")

        # Wait for process to complete
        await proc.wait()

        # Read stderr if any
        if proc.stderr:
            stderr_data = await proc.stderr.read()
            if stderr_data:
                stderr_str = stderr_data.decode('utf-8', errors='replace')

                # Write to log file immediately
                write_log(f"[STDERR] {stderr_str}\n")

                log_entry = json.dumps({
                    'type': 'stderr',
                    'line': stderr_str,
                    'timestamp': time.time()
                })
                await r.rpush(f"process:{pid}:logs", log_entry)

        # Write footer
        write_log(f"\n{'=' * 70}\n")
        write_log(f"Process exited: PID {pid}\n")
        write_log(f"Exit code: {proc.returncode}\n")
        write_log(f"Timestamp: {time.ctime()}\n")
        write_log(f"{'=' * 70}\n\n")

        # Mark process as completed
        await r.hset(f"process:{pid}:info", "exit_code", proc.returncode)
        await r.hset(f"process:{pid}:info", "ended_at", time.time())
        print(f"[PID:{pid}] Exited with code {proc.returncode}")

    except Exception as e:
        print(f"[PID:{pid}] Error streaming output: {e}")
        write_log(f"\n[ERROR] {str(e)}\n")
        await r.hset(f"process:{pid}:info", "error", str(e))


async def start_process(command: str, cwd: str, env_key: Optional[str] = None) -> int:
    """
    Start a background process

    Args:
        command: Command to run
        cwd: Working directory
        env_key: Optional environment key for tracking

    Returns:
        PID of started process
    """
    global _process_objects
    r = await get_redis()

    # Start the process
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd
    )

    pid = proc.pid

    # Store process object in memory
    _process_objects[pid] = proc

    # Determine log file path
    log_file_path = os.path.join(cwd, "run.log")

    # Store process info in Redis
    await r.hset(f"process:{pid}:info", mapping={
        'cmd': command,
        'cwd': cwd,
        'started_at': time.time(),
        'pid': pid,
        'log_file': log_file_path,
        'env': env_key or os.path.basename(cwd)
    })

    # Start background task to stream output
    asyncio.create_task(stream_process_output(pid, proc, log_file_path))

    print(f"[PROCESS] Started PID: {pid}")
    return pid


async def stop_process(pid: int, force: bool = False) -> str:
    """
    Stop a running process

    Args:
        pid: Process ID to stop
        force: If True, use SIGKILL instead of SIGTERM

    Returns:
        Confirmation message
    """
    global _process_objects
    r = await get_redis()

    # Check if process exists
    if pid not in _process_objects:
        return f"Process {pid} not found"

    # Check if already stopped
    exit_code = await r.hget(f"process:{pid}:info", "exit_code")
    if exit_code is not None:
        return f"Process {pid} already stopped (exit code: {exit_code})"

    proc = _process_objects[pid]

    try:
        if force:
            proc.kill()
            return f"Sent SIGKILL to PID {pid}"
        else:
            proc.terminate()
            return f"Sent SIGTERM to PID {pid}"
    except Exception as e:
        return f"Error stopping process {pid}: {str(e)}"


async def list_all_processes() -> Dict[int, Dict]:
    """
    List all managed processes

    Returns:
        Dictionary mapping PIDs to process info
    """
    r = await get_redis()
    processes = {}

    # Get all process keys from Redis
    async for key in r.scan_iter("process:*:info"):
        pid = int(key.split(':')[1])
        info = await r.hgetall(f"process:{pid}:info")
        log_count = await r.llen(f"process:{pid}:logs")

        # Check if process is still alive
        is_alive = False
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            is_alive = True
        except OSError:
            pass

        processes[pid] = {
            **info,
            'log_count': log_count,
            'is_alive': is_alive
        }

    return processes


async def get_process_logs_data(pid: int, tail: Optional[int] = None) -> Optional[Dict]:
    """
    Get logs from a process by PID

    Args:
        pid: Process ID
        tail: Optional number of most recent lines to return (default: all)

    Returns:
        Dictionary with process info and logs, or None if not found
    """
    r = await get_redis()

    # Get process info from Redis
    proc_info = await r.hgetall(f"process:{pid}:info")
    if not proc_info:
        return None

    # Get logs from Redis
    log_count = await r.llen(f"process:{pid}:logs")

    if log_count == 0:
        return {
            'info': proc_info,
            'logs': [],
            'log_count': 0
        }

    # Get logs (with tail if specified)
    if tail:
        log_entries = await r.lrange(f"process:{pid}:logs", -tail, -1)
    else:
        log_entries = await r.lrange(f"process:{pid}:logs", 0, -1)

    # Parse log entries
    logs = [json.loads(entry) for entry in log_entries]

    return {
        'info': proc_info,
        'logs': logs,
        'log_count': log_count
    }


def get_process_object(pid: int) -> Optional[asyncio.subprocess.Process]:
    """Get process object by PID"""
    return _process_objects.get(pid)


def cleanup_process_object(pid: int):
    """Remove process object from memory"""
    if pid in _process_objects:
        del _process_objects[pid]
