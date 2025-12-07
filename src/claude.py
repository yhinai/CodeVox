"""Claude SDK integration for agent interactions"""

import asyncio
import time
from typing import List, Dict
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, AssistantMessage, TextBlock
from .discord_client import send_to_discord


# Global state for tracking Claude execution
_claude_running = False
_claude_messages: List[Dict] = []  # Stack of intermediate messages
_claude_start_time = None


async def get_claude_client():
    """Create a new Claude SDK client for each request"""
    options = ClaudeAgentOptions(
        include_partial_messages=True,  # Enable streaming to capture intermediate messages
        permission_mode='bypassPermissions'  # Never ask for permission - auto-approve all actions
    )
    return ClaudeSDKClient(options=options)


async def process_claude_query(query: str, first_message_event: asyncio.Event):
    """Background task to process Claude's full response"""
    global _claude_running, _claude_messages, _claude_start_time

    try:
        client = await get_claude_client()

        async with client:
            # Send query to Claude
            await client.query(query)

            # Collect the response
            async for msg in client.receive_response():
                print(f"[DEBUG] Received message type: {type(msg).__name__}")

                # Extract text from AssistantMessage
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            message_text = block.text
                            # Add to message stack
                            msg_entry = {
                                "type": "assistant",
                                "text": message_text,
                                "timestamp": time.time() - _claude_start_time
                            }
                            _claude_messages.append(msg_entry)
                            print(f"[DEBUG] Added assistant message: {message_text[:100]}...")

                            # Signal that first message is ready
                            if not first_message_event.is_set():
                                first_message_event.set()

                            # Send to Discord
                            await send_to_discord(f"🤖 **Claude**: {message_text}")

                # Get final result
                elif isinstance(msg, ResultMessage):
                    result_text = str(msg.result) if msg.result else None
                    if result_text:
                        msg_entry = {
                            "type": "result",
                            "text": result_text,
                            "timestamp": time.time() - _claude_start_time
                        }
                        _claude_messages.append(msg_entry)
                        print(f"[DEBUG] Added result message")

                        # Signal that first message is ready (if we get result first)
                        if not first_message_event.is_set():
                            first_message_event.set()

                        # Send to Discord
                        await send_to_discord(f"✅ **Result**: {result_text}")

    except Exception as e:
        print(f"Error in background Claude processing: {e}")
        error_entry = {
            "type": "error",
            "text": str(e),
            "timestamp": time.time() - _claude_start_time
        }
        _claude_messages.append(error_entry)
        # Signal event even on error
        if not first_message_event.is_set():
            first_message_event.set()
    finally:
        # Clear running status
        global _claude_running
        _claude_running = False
        print("[DEBUG] Claude background processing completed")


async def ask_claude_async(query: str) -> str:
    """
    Ask Claude Code a question and get a response

    Args:
        query: The question or prompt to send to Claude Code

    Returns:
        Claude Code's first response with a note about background processing
    """
    global _claude_running, _claude_messages, _claude_start_time

    # Set running status
    _claude_running = True
    _claude_messages = []  # Clear message stack
    _claude_start_time = time.time()

    # Event to signal when first message is ready
    first_message_event = asyncio.Event()

    # Start background processing task
    asyncio.create_task(process_claude_query(query, first_message_event))

    try:
        # Wait for first message (with timeout)
        await asyncio.wait_for(first_message_event.wait(), timeout=30.0)

        # Get the first message from the stack
        if _claude_messages:
            first_msg = _claude_messages[0]
            first_text = first_msg.get("text", "")
            note = "\n\n---\n⚙️ Claude is still working in the background. Use pop_messages() to see progress."
            return first_text + note
        else:
            note = "\n\n---\n⚙️ Claude is working in the background. Use pop_messages() to see progress."
            return "Claude is processing your request..." + note

    except asyncio.TimeoutError:
        print("[DEBUG] Timeout waiting for first message")
        note = "\n\n---\n⚙️ Claude is working in the background. Use pop_messages() to see progress."
        return "Claude is processing your request (taking longer than expected)..." + note


def get_claude_status() -> bool:
    """Check if Claude Code is currently running"""
    global _claude_running
    return _claude_running


def get_claude_messages() -> List[Dict]:
    """Get all intermediate messages from Claude Code execution"""
    global _claude_messages
    return _claude_messages.copy()
