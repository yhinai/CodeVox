#!/usr/bin/env python3
"""
Example usage of the Voice Assistant in different modes
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from voice_assistant import VoiceAssistant


async def example_single_query():
    """Example: Single voice query"""
    print("\n=== Example: Single Voice Query ===\n")

    assistant = VoiceAssistant(voice="rex")

    # Listen to user
    print("Ask a question about your code...")
    query = await assistant.listen_once()

    if query:
        # Get response from Grok with Claude Code access
        response = await assistant.ask_grok_with_mcp(query)

        # Speak the response
        await assistant.speak(response)


async def example_text_query():
    """Example: Text query (no voice input)"""
    print("\n=== Example: Text Query ===\n")

    assistant = VoiceAssistant(voice="ara")

    # Direct text query
    query = "What processes are currently running?"
    print(f"Query: {query}\n")

    response = await assistant.ask_grok_with_mcp(query)

    # Speak the response
    await assistant.speak(response)


async def example_voice_to_text_only():
    """Example: Voice input, text output (no TTS)"""
    print("\n=== Example: Voice to Text Only ===\n")

    assistant = VoiceAssistant()

    print("Speak your question...")
    query = await assistant.listen_once()

    if query:
        response = await assistant.ask_grok_with_mcp(query)
        print(f"\nResponse (text only):\n{response}")


async def example_conversation():
    """Example: Full conversation mode"""
    print("\n=== Example: Full Conversation ===\n")

    assistant = VoiceAssistant(
        voice="rex",
        model="grok-4-1-fast",
    )

    # This will run the full conversation loop
    await assistant.conversation_loop()


async def example_claude_code_query():
    """Example: Specific Claude Code query"""
    print("\n=== Example: Claude Code Query ===\n")

    assistant = VoiceAssistant()

    # Ask Claude Code to do something
    query = """
    Can you list all the environments and tell me which one is currently active?
    Then show me if there are any running processes.
    """

    print(f"Query: {query}\n")
    response = await assistant.ask_grok_with_mcp(query)

    # Just print, don't speak (for this example)
    print(f"\nResponse:\n{response}")


async def example_github_pr_query():
    """Example: GitHub PR query"""
    print("\n=== Example: GitHub PR Query ===\n")

    assistant = VoiceAssistant()

    query = """
    Get the comments for all active pull requests in the current environment.
    Summarize any important feedback.
    """

    print(f"Query: {query}\n")
    response = await assistant.ask_grok_with_mcp(query)
    await assistant.speak(response)


async def example_environment_switch():
    """Example: Switch environment and run commands"""
    print("\n=== Example: Environment Management ===\n")

    assistant = VoiceAssistant()

    # Multi-step query
    query = """
    First, show me all available environments.
    Then switch to the 'voice_demo' environment if it exists.
    Then start the run.sh script for that environment.
    """

    print(f"Query: {query}\n")
    response = await assistant.ask_grok_with_mcp(query)

    print(f"\nResponse:\n{response}")


def main():
    """Main entry point - choose which example to run"""
    load_dotenv()

    examples = {
        "1": ("Single voice query", example_single_query),
        "2": ("Text query (no voice input)", example_text_query),
        "3": ("Voice to text only (no TTS)", example_voice_to_text_only),
        "4": ("Full conversation mode", example_conversation),
        "5": ("Claude Code query", example_claude_code_query),
        "6": ("GitHub PR query", example_github_pr_query),
        "7": ("Environment management", example_environment_switch),
    }

    print("\n" + "=" * 70)
    print("Voice Assistant Examples")
    print("=" * 70)
    print("\nChoose an example to run:\n")

    for key, (description, _) in examples.items():
        print(f"  {key}. {description}")

    print("\n  q. Quit")
    print()

    choice = input("Enter choice (1-7, or 'q'): ").strip()

    if choice.lower() == 'q':
        print("Goodbye!")
        return

    if choice in examples:
        description, example_func = examples[choice]
        print(f"\nRunning: {description}\n")

        try:
            asyncio.run(example_func())
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Invalid choice!")
        return main()


if __name__ == "__main__":
    main()
