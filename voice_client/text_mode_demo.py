#!/usr/bin/env python3
"""
Demo script showing text-only mode usage
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from voice_assistant import VoiceAssistant


async def text_only_demo():
    """Demonstrate text-only mode (no voice)"""
    print("\n=== Text-Only Mode Demo ===\n")
    print("This mode is perfect when:")
    print("  - You don't have a microphone/speaker")
    print("  - You're in a quiet environment")
    print("  - PyAudio isn't available")
    print("  - You prefer typing over speaking\n")

    # Create assistant in text-only mode
    assistant = VoiceAssistant(
        enable_stt=False,  # No voice input
        enable_tts=False,  # No voice output
    )

    # Run conversation loop (will use keyboard input and screen output)
    await assistant.conversation_loop()


async def hybrid_demo():
    """Demonstrate hybrid modes"""
    print("\n=== Hybrid Mode Demo ===\n")

    choice = input("Choose mode:\n  1. Type input, hear output\n  2. Speak input, read output\nChoice (1-2): ")

    if choice == "1":
        print("\nMode: Text input → Voice output")
        assistant = VoiceAssistant(
            enable_stt=False,  # Type your questions
            enable_tts=True,   # Hear the responses
            voice="rex",
        )
    elif choice == "2":
        print("\nMode: Voice input → Text output")
        assistant = VoiceAssistant(
            enable_stt=True,   # Speak your questions
            enable_tts=False,  # Read the responses
        )
    else:
        print("Invalid choice!")
        return

    await assistant.conversation_loop()


async def single_text_query():
    """Single text query example"""
    print("\n=== Single Text Query ===\n")

    assistant = VoiceAssistant(
        enable_stt=False,
        enable_tts=False,
    )

    query = input("Enter your question: ")

    if query:
        print()
        response = await assistant.ask_grok_with_mcp(query)
        print(f"\n💬 Response:\n{response}\n")


def main():
    load_dotenv()

    print("\n" + "=" * 70)
    print("Text Mode Demos")
    print("=" * 70)
    print("\nChoose a demo:\n")
    print("  1. Text-only mode (no voice at all)")
    print("  2. Hybrid modes (mix of voice and text)")
    print("  3. Single text query")
    print("\n  q. Quit")
    print()

    choice = input("Enter choice (1-3, or 'q'): ").strip()

    if choice.lower() == 'q':
        print("Goodbye!")
        return

    try:
        if choice == "1":
            asyncio.run(text_only_demo())
        elif choice == "2":
            asyncio.run(hybrid_demo())
        elif choice == "3":
            asyncio.run(single_text_query())
        else:
            print("Invalid choice!")
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
