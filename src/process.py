"""
Process Management - Singleton Class Pattern
No global variables. Clean, testable architecture.
"""
import asyncio
import time
import os
import aiofiles
import structlog
from dataclasses import dataclass
from typing import Dict, List, Optional

log = structlog.get_logger()


@dataclass
class ProcessInfo:
    """Information about a managed process."""
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
    type: str
    line: str
    timestamp: float


class ProcessManager:
    """Manages background processes with clean state encapsulation."""
    
    def __init__(self):
        self._processes: Dict[int, asyncio.subprocess.Process] = {}
        self._info: Dict[int, ProcessInfo] = {}
        self._logs: Dict[int, List[LogEntry]] = {}
    
    async def start(self, command: str, cwd: str, env_key: str = "") -> int:
        """Start a background process."""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        pid = proc.pid
        self._processes[pid] = proc
        self._info[pid] = ProcessInfo(
            pid=pid,
            cmd=command,
            cwd=cwd,
            started_at=time.time(),
            env=env_key or os.path.basename(cwd)
        )
        self._logs[pid] = []
        
        # Start log streaming
        log_path = os.path.join(cwd, "run.log")
        asyncio.create_task(self._stream_output(pid, proc, log_path))
        
        log.info("process.started", pid=pid, cmd=command)
        return pid
    
    async def stop(self, pid: int, force: bool = False) -> str:
        """Stop a running process."""
        if pid not in self._processes:
            return f"Process {pid} not found"
        
        info = self._info.get(pid)
        if info and info.exit_code is not None:
            return f"Process {pid} already stopped (exit code: {info.exit_code})"
        
        proc = self._processes[pid]
        try:
            if force:
                proc.kill()
                return f"Sent SIGKILL to PID {pid}"
            else:
                proc.terminate()
                return f"Sent SIGTERM to PID {pid}"
        except Exception as e:
            return f"Error stopping {pid}: {e}"
    
    async def list_all(self) -> Dict[int, Dict]:
        """List all managed processes."""
        result = {}
        for pid, info in self._info.items():
            is_alive = False
            try:
                os.kill(pid, 0)
                is_alive = True
            except OSError:
                pass
            
            result[pid] = {
                'cmd': info.cmd,
                'cwd': info.cwd,
                'started_at': info.started_at,
                'env': info.env,
                'exit_code': info.exit_code,
                'is_alive': is_alive
            }
        return result
    
    def get_process(self, pid: int) -> Optional[asyncio.subprocess.Process]:
        """Get process object by PID."""
        return self._processes.get(pid)
    
    async def _stream_output(self, pid: int, proc: asyncio.subprocess.Process, log_path: str):
        """Background task to stream process output."""
        async def write_log(text: str):
            async with aiofiles.open(log_path, 'a') as f:
                await f.write(text)
        
        try:
            await write_log(f"\n{'='*70}\nProcess started: PID {pid} at {time.ctime()}\n{'='*70}\n\n")
            
            if proc.stdout:
                async for line in proc.stdout:
                    line_str = line.decode('utf-8', errors='replace')
                    await write_log(f"[STDOUT] {line_str}")
                    self._logs.setdefault(pid, []).append(
                        LogEntry(type='stdout', line=line_str.rstrip(), timestamp=time.time())
                    )
            
            await proc.wait()
            
            if proc.stderr:
                stderr = await proc.stderr.read()
                if stderr:
                    await write_log(f"[STDERR] {stderr.decode()}\n")
            
            await write_log(f"\n{'='*70}\nProcess exited: {proc.returncode}\n{'='*70}\n")
            
            if pid in self._info:
                self._info[pid].exit_code = proc.returncode
                self._info[pid].ended_at = time.time()
                
        except Exception as e:
            log.error("process.stream_error", pid=pid, error=str(e))


# Singleton instance
process_manager = ProcessManager()


# Public API functions (for tool registration)
async def run_cmd() -> str:
    """Start the run script for the current environment."""
    from .environment import env_manager
    
    env_key, env_path = env_manager.get_current()
    if not env_key:
        return "No environment set. Use switch_environment() first."
    
    env = env_manager.get_by_name(env_key)
    if not env:
        return f"Environment '{env_key}' not found"
    
    run_script = env.get("run_script")
    if not run_script:
        return f"No run_script configured for '{env_key}'"
    
    pid = await process_manager.start(run_script, env_path, env_key)
    return f"Started process PID: {pid}\nCommand: {run_script}\nLogs: {env_path}/run.log"


async def stop_cmd(pid: int, force: bool = False) -> str:
    """Stop a running process by PID."""
    return await process_manager.stop(pid, force)


async def restart_cmd(pid: int) -> str:
    """Restart a process by stopping it and starting a new one."""
    from .environment import env_manager
    
    proc = process_manager.get_process(pid)
    if not proc:
        return f"Process {pid} not found"
    
    await process_manager.stop(pid, force=True)
    
    env_key, env_path = env_manager.get_current()
    if env_key:
        env = env_manager.get_by_name(env_key)
        run_script = env.get("run_script", "") if env else ""
        if run_script:
            new_pid = await process_manager.start(run_script, env_path, env_key)
            return f"Stopped PID {pid}, started new PID {new_pid}"
    
    return f"Stopped PID {pid} but couldn't restart (no environment set)"


# Backwards compatibility
async def start_process(command: str, cwd: str, env_key: Optional[str] = None) -> int:
    return await process_manager.start(command, cwd, env_key or "")

async def stop_process(pid: int, force: bool = False) -> str:
    return await process_manager.stop(pid, force)

async def list_all_processes() -> Dict[int, Dict]:
    return await process_manager.list_all()

def get_process_object(pid: int) -> Optional[asyncio.subprocess.Process]:
    return process_manager.get_process(pid)
