"""
Claude SDK integration - Updated for claude_agent_sdk v0.1.13+
Uses ClaudeSDKClient instead of deprecated ClaudeAgent.
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

import structlog

log = structlog.get_logger()

# Check SDK availability  
try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        ResultMessage,
    )
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False


@dataclass
class ClaudeMessage:
    """A message from Claude during processing."""
    content: str
    message_type: str
    timestamp: float = field(default_factory=time.time)
    raw: Any = None


class ClaudeSession:
    """Manages a Claude coding session."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.running = False
        self.messages: List[ClaudeMessage] = []
        self.start_time: Optional[float] = None
        self.first_response: Optional[str] = None

    def is_running(self) -> bool:
        return self.running

    def pop_messages(self) -> List[ClaudeMessage]:
        msgs = self.messages.copy()
        self.messages.clear()
        return msgs

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "message_count": len(self.messages),
            "start_time": self.start_time,
            "elapsed": time.time() - self.start_time if self.start_time else None,
            "sdk_available": CLAUDE_SDK_AVAILABLE,
        }

    async def ask(self, query: str) -> str:
        """Send a query to Claude and return the response."""
        if not CLAUDE_SDK_AVAILABLE:
            return "Error: claude_agent_sdk not installed"

        if self.running:
            return "Claude is already processing a query."

        self.running = True
        self.start_time = time.time()
        self.first_response = None
        self.messages.clear()

        log.info("claude.ask.started", query_preview=query[:100])

        try:
            options = ClaudeAgentOptions(
                cwd=self.working_dir,
            )
            
            async with ClaudeSDKClient(options) as client:
                async for message in client.query(query):
                    content = self._extract_content(message)
                    
                    if content:
                        self.messages.append(ClaudeMessage(
                            content=content,
                            message_type=type(message).__name__,
                            raw=message
                        ))
                        
                        if self.first_response is None:
                            self.first_response = content
                            log.info("claude.first_response", preview=content[:100])
                    
                    if isinstance(message, ResultMessage):
                        break
            
            return self.first_response or "No response from Claude"
            
        except Exception as e:
            log.error("claude.error", error=str(e))
            return f"Error: {str(e)}"
        finally:
            self.running = False
            elapsed = time.time() - (self.start_time or time.time())
            log.info("claude.session_ended", elapsed=f"{elapsed:.2f}s")

    def _extract_content(self, message) -> Optional[str]:
        """Extract text content from a Claude message."""
        try:
            if hasattr(message, 'message') and hasattr(message.message, 'content'):
                content = message.message.content
                if isinstance(content, list):
                    texts = [b.text for b in content if hasattr(b, 'text')]
                    return ' '.join(texts) if texts else None
                return str(content) if content else None
            
            if hasattr(message, 'content'):
                return str(message.content)
                
        except Exception as e:
            log.warning("claude.extract_failed", error=str(e))
        return None


# Singleton
_default_session: Optional[ClaudeSession] = None


def get_default_session(working_dir: str = ".") -> ClaudeSession:
    global _default_session
    if _default_session is None:
        _default_session = ClaudeSession(working_dir)
    return _default_session
