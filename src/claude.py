"""Claude SDK integration - Class-based architecture (no global state)."""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

import structlog

try:
    from claude_agent_sdk import (
        ClaudeAgent,
        ClaudeAgentOptions,
        Query,
        ResultMessage,
        ToolResultBlockContent,
    )
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False

log = structlog.get_logger()


@dataclass
class ClaudeMessage:
    """A message from Claude during processing."""
    content: str
    message_type: str
    timestamp: float = field(default_factory=time.time)
    raw: Any = None


class ClaudeSession:
    """Manages a Claude coding session with state encapsulated in the instance."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.running = False
        self.messages: List[ClaudeMessage] = []
        self.start_time: Optional[float] = None
        self.first_response: Optional[str] = None
        self._task: Optional[asyncio.Task] = None

    def is_running(self) -> bool:
        """Check if Claude is currently processing."""
        return self.running

    def pop_messages(self) -> List[ClaudeMessage]:
        """Get and clear all collected messages."""
        msgs = self.messages.copy()
        self.messages.clear()
        return msgs

    def get_status(self) -> dict:
        """Get current session status."""
        return {
            "running": self.running,
            "message_count": len(self.messages),
            "start_time": self.start_time,
            "elapsed": time.time() - self.start_time if self.start_time else None,
        }

    async def ask(self, query: str) -> str:
        """
        Send a query to Claude and return immediately with first response.
        Processing continues in background.
        """
        if not CLAUDE_SDK_AVAILABLE:
            return "Error: claude_agent_sdk not installed"

        if self.running:
            return "Claude is already processing a query. Wait for completion."

        self.running = True
        self.start_time = time.time()
        self.first_response = None
        self.messages.clear()

        log.info("claude.ask.started", query_preview=query[:100])

        # Start background task
        self._task = asyncio.create_task(self._process_query(query))

        # Wait for first response or timeout
        timeout = 30
        start_wait = time.time()
        while self.first_response is None and (time.time() - start_wait) < timeout:
            await asyncio.sleep(0.1)
            if not self.running:
                break

        if self.first_response:
            return f"{self.first_response}\n\n(Claude is still processing in background. Use get_status() to check.)"
        elif not self.running:
            return "Claude finished without response"
        else:
            return "Waiting for Claude response (processing in background)..."

    async def _process_query(self, query: str):
        """Background task to process Claude query."""
        try:
            options = ClaudeAgentOptions(
                stream_partial_assistant_message=True,
                bypass_permissions=True,
                cwd=self.working_dir,
            )

            agent = ClaudeAgent(options)

            async for message in agent.query(Query(query=query)):
                # Process message
                msg_content = self._extract_content(message)
                
                if msg_content:
                    claude_msg = ClaudeMessage(
                        content=msg_content,
                        message_type=type(message).__name__,
                        raw=message
                    )
                    self.messages.append(claude_msg)

                    # Set first response
                    if self.first_response is None:
                        self.first_response = msg_content
                        log.info("claude.first_response", preview=msg_content[:100])

                # Check for completion
                if isinstance(message, ResultMessage):
                    log.info("claude.completed", message_count=len(self.messages))
                    break

        except Exception as e:
            log.error("claude.error", error=str(e))
            self.messages.append(ClaudeMessage(
                content=f"Error: {str(e)}",
                message_type="error"
            ))
        finally:
            self.running = False
            elapsed = time.time() - (self.start_time or time.time())
            log.info("claude.session_ended", elapsed=f"{elapsed:.2f}s")

    def _extract_content(self, message) -> Optional[str]:
        """Extract readable content from a Claude message."""
        try:
            # Handle different message types
            if hasattr(message, 'message') and hasattr(message.message, 'content'):
                content = message.message.content
                if isinstance(content, list):
                    texts = []
                    for block in content:
                        if hasattr(block, 'text'):
                            texts.append(block.text)
                        elif hasattr(block, 'type') and block.type == 'tool_use':
                            texts.append(f"[Tool: {getattr(block, 'name', 'unknown')}]")
                    return ' '.join(texts) if texts else None
                return str(content) if content else None

            if isinstance(message, ResultMessage) and hasattr(message, 'subtype'):
                return f"[Result: {message.subtype}]"

            if hasattr(message, 'content'):
                if isinstance(message.content, ToolResultBlockContent):
                    return f"[Tool Result]"
                return str(message.content)

        except Exception as e:
            log.warning("claude.extract_failed", error=str(e))
        
        return None


# Default session (for backwards compatibility)
_default_session: Optional[ClaudeSession] = None


def get_default_session(working_dir: str = ".") -> ClaudeSession:
    """Get or create the default session."""
    global _default_session
    if _default_session is None:
        _default_session = ClaudeSession(working_dir)
    return _default_session


async def ask_claude_async(query: str, working_dir: str = ".") -> str:
    """Convenience function using default session."""
    session = get_default_session(working_dir)
    return await session.ask(query)
