"""
Engine - The Brain: Discovery, Process Management, GitHub, Claude
Combines all core functionality in one efficient module.
"""
import os
import re
import asyncio
import time
import json
import structlog
import aiohttp
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

log = structlog.get_logger()


@dataclass
class Project:
    """Discovered project metadata."""
    name: str
    path: str
    type: str  # python, node, rust, go, unknown
    git_remote: Optional[str] = None


@dataclass
class ProcessInfo:
    """Running process metadata."""
    pid: int
    cmd: str
    project: str
    started_at: float
    status: str = "running"
    exit_code: Optional[int] = None


class Engine:
    """Core engine for discovery, execution, and API calls."""
    
    def __init__(self):
        self.projects: Dict[str, Project] = {}
        self.processes: Dict[int, ProcessInfo] = {}
    
    # -------------------------------------------------------------------------
    # Project Discovery
    # -------------------------------------------------------------------------
    
    def scan_projects(self, search_paths: List[Path]) -> str:
        """Recursively find Git projects and identify their type."""
        self.projects.clear()
        found = []
        
        for base_path in search_paths:
            if not base_path.exists():
                continue
            
            # Scan depth 1 (e.g., ~/code/project_a)
            for item in base_path.iterdir():
                if item.is_dir() and (item / ".git").exists():
                    ptype = self._detect_project_type(item)
                    remote = self._get_git_remote(item)
                    
                    proj = Project(
                        name=item.name,
                        path=str(item.absolute()),
                        type=ptype,
                        git_remote=remote
                    )
                    self.projects[proj.name] = proj
                    found.append(f"{proj.name} ({ptype})")
        
        log.info("discovery.complete", count=len(found))
        return f"Discovered {len(found)} projects:\n" + "\n".join(f"  • {p}" for p in found)
    
    def _detect_project_type(self, path: Path) -> str:
        """Detect project type from config files."""
        if (path / "package.json").exists():
            return "node"
        if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
            return "python"
        if (path / "Cargo.toml").exists():
            return "rust"
        if (path / "go.mod").exists():
            return "go"
        if (path / "Makefile").exists():
            return "make"
        return "unknown"
    
    def _get_git_remote(self, path: Path) -> Optional[str]:
        """Extract 'owner/repo' from git config."""
        try:
            config_path = path / ".git" / "config"
            if config_path.exists():
                content = config_path.read_text()
                match = re.search(r'github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$', content, re.MULTILINE)
                return match.group(1) if match else None
        except Exception:
            pass
        return None
    
    def list_projects(self) -> str:
        """List all discovered projects."""
        if not self.projects:
            return "No projects found. Run refresh_projects() first."
        
        lines = ["Available Projects:", "=" * 40]
        for name, p in self.projects.items():
            lines.append(f"• {name}")
            lines.append(f"  Type: {p.type}")
            lines.append(f"  Path: {p.path}")
            if p.git_remote:
                lines.append(f"  GitHub: {p.git_remote}")
        return "\n".join(lines)
    
    # -------------------------------------------------------------------------
    # Command Execution
    # -------------------------------------------------------------------------
    
    async def run_command(self, project_name: str, command: str) -> str:
        """Execute a shell command in a project's context."""
        if project_name not in self.projects:
            return f"Project '{project_name}' not found. Run refresh_projects() first."
        
        cwd = self.projects[project_name].path
        log.info("exec.start", project=project_name, cmd=command)
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Track process
            self.processes[proc.pid] = ProcessInfo(
                pid=proc.pid,
                cmd=command,
                project=project_name,
                started_at=time.time()
            )
            
            # Wait for completion (with timeout for long commands)
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            except asyncio.TimeoutError:
                self.processes[proc.pid].status = "running (background)"
                return f"PID {proc.pid} started in background. Use get_process_stats() to check."
            
            # Update status
            self.processes[proc.pid].status = "finished"
            self.processes[proc.pid].exit_code = proc.returncode
            
            output = stdout.decode().strip() or stderr.decode().strip()
            result = f"✅ PID {proc.pid} exited with code {proc.returncode}\n"
            result += f"Output:\n{output[:3000]}"  # Truncate large output
            return result
            
        except Exception as e:
            log.error("exec.failed", error=str(e))
            return f"❌ Execution failed: {str(e)}"
    
    async def run_raw(self, command: str, cwd: str = ".") -> str:
        """Execute a raw shell command in any directory."""
        log.info("exec.raw", cmd=command, cwd=cwd)
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=os.path.expanduser(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            output = stdout.decode().strip() or stderr.decode().strip()
            return f"Exit code: {proc.returncode}\n{output[:3000]}"
            
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def get_process_stats(self) -> str:
        """Get system stats and tracked processes."""
        try:
            import psutil
            stats = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "tracked_processes": len(self.processes),
                "running": sum(1 for p in self.processes.values() if "running" in p.status)
            }
        except ImportError:
            stats = {"error": "psutil not installed"}
        
        lines = [json.dumps(stats, indent=2), "", "Tracked Processes:"]
        for pid, info in self.processes.items():
            lines.append(f"  PID {pid}: {info.cmd[:50]} [{info.status}]")
        
        return "\n".join(lines)
    
    # -------------------------------------------------------------------------
    # GitHub API
    # -------------------------------------------------------------------------
    
    async def call_github(self, method: str, endpoint: str, data: dict = None, token: str = None) -> dict:
        """Universal GitHub API caller."""
        if not token:
            return {"error": "No GH_TOKEN configured"}
        
        url = f"https://api.github.com/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "claude-code-mcp"
        }
        
        log.info("github.call", method=method, endpoint=endpoint)
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method.upper(), url, headers=headers, json=data) as resp:
                try:
                    result = await resp.json()
                    return result
                except Exception:
                    return {"status": resp.status, "text": await resp.text()}
    
    # -------------------------------------------------------------------------
    # Claude Agent
    # -------------------------------------------------------------------------
    
    async def ask_claude(self, query: str, working_dir: str = ".") -> str:
        """Query Claude coding agent."""
        try:
            from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage
        except ImportError:
            return "Error: claude_agent_sdk not installed. Run: pip install claude-agent-sdk"
        
        log.info("claude.ask", query=query[:100])
        
        try:
            options = ClaudeAgentOptions(cwd=os.path.expanduser(working_dir))
            
            async with ClaudeSDKClient(options) as client:
                await client.query(query)
                
                response = None
                async for message in client.receive_messages():
                    if hasattr(message, 'message') and hasattr(message.message, 'content'):
                        content = message.message.content
                        if isinstance(content, list):
                            texts = [b.text for b in content if hasattr(b, 'text')]
                            if texts:
                                response = ' '.join(texts)
                                break
                    if isinstance(message, ResultMessage):
                        break
                
                return response or "No response from Claude"
                
        except Exception as e:
            log.error("claude.error", error=str(e))
            return f"Error: {str(e)}"


# Singleton
engine = Engine()
