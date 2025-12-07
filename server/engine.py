"""
Engine - The Brain: Discovery, Process Management, GitHub, Claude
v3.1 - Smart command inference, deep discovery, metadata extraction, process cleanup
"""
import os
import re
import asyncio
import time
import json
import atexit
import structlog
import aiohttp
from pathlib import Path
import dataclasses
from dataclasses import dataclass
from typing import Dict, List, Optional

log = structlog.get_logger()


@dataclass
class Project:
    """Discovered project with smart metadata."""
    name: str
    path: str
    type: str
    git_remote: Optional[str] = None
    description: Optional[str] = None
    suggested_cmd: Optional[str] = None


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
    """Core engine with smart discovery and process management."""
    
    def __init__(self):
        self.projects: Dict[str, Project] = {}
        self.processes: Dict[int, ProcessInfo] = {}
        # Register cleanup on shutdown
        atexit.register(self._cleanup_sync)
    
    # =========================================================================
    # PROJECT DISCOVERY - Smart, Deep, with Metadata
    # =========================================================================
    
    def scan_projects(self, search_paths: List[Path], max_depth: int = 3) -> str:
        """Recursively find Git projects with smart metadata extraction."""
        self.projects.clear()
        found = []
        
        for base in search_paths:
            if not base.exists():
                continue
            
            # Walk with depth limit, skip hidden/vendor folders
            for root, dirs, _ in os.walk(base):
                # Skip hidden and vendor directories
                dirs[:] = [d for d in dirs if not d.startswith('.') 
                          and d not in {'venv', 'node_modules', '__pycache__', 'dist', 'build'}]
                
                path = Path(root)
                try:
                    depth = len(path.relative_to(base).parts)
                except ValueError:
                    continue
                    
                if depth > max_depth:
                    dirs.clear()  # Don't go deeper
                    continue
                
                if (path / ".git").exists():
                    proj = self._analyze_project(path)
                    self.projects[proj.name] = proj
                    found.append(proj)
                    dirs.clear()  # Don't scan inside git repos
        
        log.info("discovery.complete", count=len(found))
        
        lines = [f"Discovered {len(found)} projects:"]
        for p in found:
            cmd_info = f" → {p.suggested_cmd}" if p.suggested_cmd else ""
            lines.append(f"  • {p.name} ({p.type}){cmd_info}")
        
        return "\n".join(lines)
    
    def _analyze_project(self, path: Path) -> Project:
        """Deep analysis: type, remote, description, run command."""
        ptype = self._detect_type(path)
        return Project(
            name=path.name,
            path=str(path.absolute()),
            type=ptype,
            git_remote=self._get_git_remote(path),
            description=self._get_description(path, ptype),
            suggested_cmd=self._suggest_command(path, ptype)
        )
    
    def _detect_type(self, path: Path) -> str:
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
        if (path / "Dockerfile").exists():
            return "docker"
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
    
    def _get_description(self, path: Path, ptype: str) -> Optional[str]:
        """Read project description from config files."""
        try:
            if ptype == "node" and (path / "package.json").exists():
                data = json.loads((path / "package.json").read_text())
                return data.get("description")
            
            if ptype == "python" and (path / "pyproject.toml").exists():
                content = (path / "pyproject.toml").read_text()
                if 'description = "' in content:
                    return content.split('description = "')[1].split('"')[0]
        except Exception:
            pass
        return None
    
    def _suggest_command(self, path: Path, ptype: str) -> Optional[str]:
        """Intelligently suggest the best run command."""
        try:
            if ptype == "node" and (path / "package.json").exists():
                scripts = json.loads((path / "package.json").read_text()).get("scripts", {})
                if "dev" in scripts:
                    return "npm run dev"
                if "start" in scripts:
                    return "npm start"
                if "build" in scripts:
                    return "npm run build"
            
            if ptype == "python":
                if (path / "manage.py").exists():
                    return "python manage.py runserver"
                if (path / "main.py").exists():
                    return "python main.py"
                if (path / "app.py").exists():
                    return "python app.py"
            
            if ptype == "rust":
                return "cargo run"
            
            if ptype == "go":
                return "go run ."
            
            if ptype == "make":
                return "make"
            
            if ptype == "docker":
                return "docker-compose up"
                
        except Exception:
            pass
        return None
    
    def list_projects_data(self) -> List[Dict]:
        """Return list of projects as dictionaries (for JSON API)."""
        # Convert Path objects to strings for JSON serialization
        results = []
        for p in self.projects.values():
            d = dataclasses.asdict(p)
            d['path'] = str(d['path'])
            results.append(d)
        return results

    def list_projects(self) -> str:
        """List all discovered projects with metadata."""
        if not self.projects:
            return "No projects found. Run refresh_projects() first."
        
        lines = ["Available Projects:", "=" * 50]
        for name, p in self.projects.items():
            lines.append(f"\n• {name} ({p.type})")
            lines.append(f"  Path: {p.path}")
            if p.git_remote:
                lines.append(f"  GitHub: {p.git_remote}")
            if p.description:
                lines.append(f"  Description: {p.description[:60]}...")
            if p.suggested_cmd:
                lines.append(f"  Run: {p.suggested_cmd}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # COMMAND EXECUTION - Smart with auto-run support
    # =========================================================================
    
    async def run_command(self, project_name: str, command: str) -> str:
        """Execute command in project context. Use 'run' for suggested command."""
        if project_name not in self.projects:
            return f"Project '{project_name}' not found. Run refresh_projects() first."
        
        project = self.projects[project_name]
        
        # Smart: if user just says "run", use suggested command
        if command.lower() in ("run", "start", "dev"):
            if project.suggested_cmd:
                command = project.suggested_cmd
                log.info("exec.smart", using=command)
            else:
                return f"No suggested command for '{project_name}'. Specify a command."
        
        cwd = project.path
        log.info("exec.start", project=project_name, cmd=command)
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.processes[proc.pid] = ProcessInfo(
                pid=proc.pid,
                cmd=command,
                project=project_name,
                started_at=time.time()
            )
            
            # Quick timeout for immediate feedback
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
                self.processes[proc.pid].status = "finished"
                self.processes[proc.pid].exit_code = proc.returncode
                output = stdout.decode().strip() or stderr.decode().strip()
                return f"✅ PID {proc.pid} exited ({proc.returncode}):\n{output[:2000]}"
            except asyncio.TimeoutError:
                self.processes[proc.pid].status = "background"
                return f"🚀 Running in background (PID {proc.pid}). Use get_process_stats() to monitor."
                
        except Exception as e:
            log.error("exec.failed", error=str(e))
            return f"❌ Failed: {str(e)}"
    
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
            
        except asyncio.TimeoutError:
            return "⏱️ Command timed out (60s)"
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def get_process_stats(self) -> str:
        """Get system stats and tracked processes."""
        try:
            import psutil
            stats = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": round(psutil.virtual_memory().percent, 1),
                "tracked_processes": len(self.processes),
                "running": sum(1 for p in self.processes.values() if p.status == "background")
            }
        except ImportError:
            stats = {"error": "psutil not installed"}
        
        lines = [json.dumps(stats, indent=2), "", "Tracked Processes:"]
        for pid, info in self.processes.items():
            runtime = time.time() - info.started_at
            lines.append(f"  PID {pid}: {info.cmd[:40]} [{info.status}] ({runtime:.0f}s)")
        
        return "\n".join(lines)
    
    async def stop_process(self, pid: int) -> str:
        """Stop a tracked process."""
        try:
            import psutil
            if pid not in self.processes:
                return f"PID {pid} not tracked"
            
            p = psutil.Process(pid)
            p.terminate()
            self.processes[pid].status = "terminated"
            return f"✅ Terminated PID {pid}"
        except Exception as e:
            return f"❌ Failed to stop {pid}: {e}"
    
    def _cleanup_sync(self):
        """Synchronous cleanup for atexit."""
        try:
            import psutil
            for pid, info in self.processes.items():
                if info.status == "background":
                    try:
                        p = psutil.Process(pid)
                        p.terminate()
                        log.info("cleanup.terminated", pid=pid)
                    except Exception:
                        pass
        except ImportError:
            pass
    
    # =========================================================================
    # GITHUB API
    # =========================================================================
    
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
                    return await resp.json()
                except Exception:
                    return {"status": resp.status, "text": await resp.text()}
    
    # =========================================================================
    # CLAUDE AGENT
    # =========================================================================
    
    async def ask_claude(self, query: str, working_dir: str = ".") -> str:
        """Query Claude coding agent."""
        try:
            from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, ResultMessage, AssistantMessage
        except ImportError:
            return "Error: claude_agent_sdk not installed"
        
        log.info("claude.ask", query=query[:100])
        
        try:
            options = ClaudeAgentOptions(cwd=os.path.expanduser(working_dir))
            
            async with ClaudeSDKClient(options) as client:
                await client.query(query)
                
                response = None
                async for message in client.receive_messages():
                    if isinstance(message, AssistantMessage) and message.content:
                        texts = [b.text for b in message.content if hasattr(b, 'text')]
                        if texts:
                            response = ' '.join(texts)
                    
                    if isinstance(message, ResultMessage):
                        break
                
                return response or "No response from Claude"
                
        except Exception as e:
            log.error("claude.error", error=str(e))
            return f"Error: {str(e)}"


# Singleton
engine = Engine()
