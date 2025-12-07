"""Process management for running background tasks - No Redis required."""

import asyncio
import json
import os
import time
import aiofiles
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProcessInfo:
    """Information about a running process."""
    pid: int
    cmd: str
    cwd: str
    started_at: float
    env: str = ""
    exit_code: Optional[int] = None
    ended_at: Optional[float] = None


@dataclass
class LogEntry:
    """A single log entry."""
    type: str  # 'stdout' or 'stderr'
    line: str
    timestamp: float


# In-memory state (replaces Redis)
_process_objects: Dict[int, asyncio.subprocess.Process] = {}
_process_info: Dict[int, ProcessInfo] = {}
_process_logs: Dict[int, List[LogEntry]] = {}


async def stream_process_output(pid: int, proc: asyncio.subprocess.Process, log_file_path: str):
    """Background task to capture process output."""
    
    async def write_log(text: str):
        """Write to log file asynchronously."""
        async with aiofiles.open(log_file_path, 'a') as f:
            await f.write(text)
    
    try:
        # Write header
        await write_log(f"\n{'=' * 70}\n")
        await write_log(f"Process started: PID {pid}\n")
        await write_log(f"Timestamp: {time.ctime()}\n")
        await write_log(f"{'=' * 70}\n\n")

        # Read stdout
        if proc.stdout:
            async for line in proc.stdout:
                line_str = line.decode('utf-8', errors='replace')
                
                # Write to log file
                await write_log(f"[STDOUT] {line_str}")
                
                # Store in memory
                _process_logs.setdefault(pid, []).append(
                    LogEntry(type='stdout', line=line_str.rstrip(), timestamp=time.time())
                )
                print(f"[PID:{pid}] {line_str.rstrip()}")

        # Wait for process to complete
        await proc.wait()

        # Read stderr if any
        if proc.stderr:
            stderr_data = await proc.stderr.read()
            if stderr_data:
                stderr_str = stderr_data.decode('utf-8', errors='replace')
                await write_log(f"[STDERR] {stderr_str}\n")
                _process_logs.setdefault(pid, []).append(
                    LogEntry(type='stderr', line=stderr_str, timestamp=time.time())
                )

        # Write footer
        await write_log(f"\n{'=' * 70}\n")
        await write_log(f"Process exited: PID {pid}\n")
        await write_log(f"Exit code: {proc.returncode}\n")
        await write_log(f"Timestamp: {time.ctime()}\n")
        await write_log(f"{'=' * 70}\n\n")

        # Mark process as completed
        if pid in _process_info:
            _process_info[pid].exit_code = proc.returncode
            _process_info[pid].ended_at = time.time()
        print(f"[PID:{pid}] Exited with code {proc.returncode}")

    except Exception as e:
        print(f"[PID:{pid}] Error streaming output: {e}")
        await write_log(f"\n[ERROR] {str(e)}\n")


async def start_process(command: str, cwd: str, env_key: Optional[str] = None) -> int:
    """Start a background process."""
    # Start the process
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd
    )

    pid = proc.pid
    
    # Store process object
    _process_objects[pid] = proc
    
    # Store process info
    _process_info[pid] = ProcessInfo(
        pid=pid,
        cmd=command,
        cwd=cwd,
        started_at=time.time(),
        env=env_key or os.path.basename(cwd)
    )
    
    # Initialize logs
    _process_logs[pid] = []
    
    # Determine log file path
    log_file_path = os.path.join(cwd, "run.log")

    # Start background task to stream output
    asyncio.create_task(stream_process_output(pid, proc, log_file_path))

    print(f"[PROCESS] Started PID: {pid}")
    return pid


async def stop_process(pid: int, force: bool = False) -> str:
    """Stop a running process."""
    if pid not in _process_objects:
        return f"Process {pid} not found"

    # Check if already stopped
    info = _process_info.get(pid)
    if info and info.exit_code is not None:
        return f"Process {pid} already stopped (exit code: {info.exit_code})"

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
    """List all managed processes."""
    processes = {}

    for pid, info in _process_info.items():
        # Check if process is still alive
        is_alive = False
        try:
            os.kill(pid, 0)
            is_alive = True
        except OSError:
            pass

        processes[pid] = {
            'cmd': info.cmd,
            'cwd': info.cwd,
            'started_at': info.started_at,
            'env': info.env,
            'exit_code': info.exit_code,
            'ended_at': info.ended_at,
            'log_count': len(_process_logs.get(pid, [])),
            'is_alive': is_alive
        }

    return processes


async def get_process_logs_data(pid: int, tail: Optional[int] = None) -> Optional[Dict]:
    """Get logs from a process by PID."""
    if pid not in _process_info:
        return None

    info = _process_info[pid]
    logs = _process_logs.get(pid, [])

    if tail:
        logs = logs[-tail:]

    return {
        'info': {
            'cmd': info.cmd,
            'cwd': info.cwd,
            'started_at': info.started_at,
            'env': info.env,
            'exit_code': info.exit_code
        },
        'logs': [{'type': l.type, 'line': l.line, 'timestamp': l.timestamp} for l in logs],
        'log_count': len(_process_logs.get(pid, []))
    }


def get_process_object(pid: int) -> Optional[asyncio.subprocess.Process]:
    """Get process object by PID."""
    return _process_objects.get(pid)


def cleanup_process_object(pid: int):
    """Remove process object from memory."""
    _process_objects.pop(pid, None)
    _process_info.pop(pid, None)
    _process_logs.pop(pid, None)
