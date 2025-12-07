#!/usr/bin/env python3
"""
Test script to verify individual components work correctly
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from voice_assistant import VoiceAssistant


async def test_stt():
    """Test speech-to-text"""
    print("\n" + "=" * 70)
    print("Testing Speech-to-Text")
    print("=" * 70)

    assistant = VoiceAssistant()

    print("\nSpeak something to test STT...")
    transcript = await assistant.listen_once()

    if transcript:
        print(f"✓ STT works! Transcribed: {transcript}")
        return True
    else:
        print("✗ STT failed - no transcript received")
        return False


async def test_mcp():
    """Test MCP connection to Claude Code"""
    print("\n" + "=" * 70)
    print("Testing MCP Connection to Claude Code")
    print("=" * 70)

    assistant = VoiceAssistant()

    print("\nAsking a simple question via MCP...")
    response = await assistant.ask_grok_with_mcp("List all available environments")

    if response and len(response) > 0:
        print(f"✓ MCP works! Response received ({len(response)} chars)")
        return True
    else:
        print("✗ MCP failed - no response received")
        return False


async def test_tts():
    """Test text-to-speech"""
    print("\n" + "=" * 70)
    print("Testing Text-to-Speech")
    print("=" * 70)

    assistant = VoiceAssistant()

    test_text = "Hello! This is a test of the text to speech system."
    print(f"\nSpeaking: {test_text}")

    audio_bytes = await assistant.speak(test_text)

    if audio_bytes and len(audio_bytes) > 0:
        print(f"✓ TTS works! Generated {len(audio_bytes)} bytes of audio")
        return True
    else:
        print("✗ TTS failed - no audio generated")
        return False


async def test_all():
    """Run all tests"""
    load_dotenv()

    # Check API key
    if not os.getenv("XAI_API_KEY"):
        print("✗ XAI_API_KEY not found in environment")
        print("  Please set it in .env file")
        return False

    print("\n🧪 Running Voice Assistant Component Tests\n")

    results = {}

    # Test each component
    try:
        results['stt'] = await test_stt()
    except Exception as e:
        print(f"✗ STT test failed with error: {e}")
        results['stt'] = False

    try:
        results['mcp'] = await test_mcp()
    except Exception as e:
        print(f"✗ MCP test failed with error: {e}")
        results['mcp'] = False

    try:
        results['tts'] = await test_tts()
    except Exception as e:
        print(f"✗ TTS test failed with error: {e}")
        results['tts'] = False

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Speech-to-Text: {'✓ PASS' if results.get('stt') else '✗ FAIL'}")
    print(f"MCP Connection: {'✓ PASS' if results.get('mcp') else '✗ FAIL'}")
    print(f"Text-to-Speech: {'✓ PASS' if results.get('tts') else '✗ FAIL'}")

    all_passed = all(results.values())
    print("\n" + ("✓ All tests passed!" if all_passed else "✗ Some tests failed"))

    return all_passed


async def quick_test():
    """Quick test - just check if components are importable"""
    print("\n🧪 Quick Component Check\n")

    try:
        import pyaudio
        print("✓ PyAudio is available")
    except ImportError:
        print("✗ PyAudio not found - install with: pip install pyaudio")
        print("  (May also need: sudo apt-get install portaudio19-dev)")

    try:
        import websockets
        print("✓ websockets is available")
    except ImportError:
        print("✗ websockets not found - install with: pip install websockets")

    try:
        from xai_sdk import Client
        print("✓ xai-sdk is available")
    except ImportError:
        print("✗ xai-sdk not found - install with: pip install xai-sdk")

    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("XAI_API_KEY")
        if api_key:
            print(f"✓ XAI_API_KEY is set (length: {len(api_key)})")
        else:
            print("✗ XAI_API_KEY not found in environment")
    except ImportError:
        print("✗ python-dotenv not found - install with: pip install python-dotenv")

    print("\n✓ Quick check complete")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test voice assistant components")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test - just check if libraries are installed"
    )
    parser.add_argument(
        "--stt-only",
        action="store_true",
        help="Test only speech-to-text"
    )
    parser.add_argument(
        "--mcp-only",
        action="store_true",
        help="Test only MCP connection"
    )
    parser.add_argument(
        "--tts-only",
        action="store_true",
        help="Test only text-to-speech"
    )

    args = parser.parse_args()

    try:
        if args.quick:
            asyncio.run(quick_test())
        elif args.stt_only:
            asyncio.run(test_stt())
        elif args.mcp_only:
            asyncio.run(test_mcp())
        elif args.tts_only:
            asyncio.run(test_tts())
        else:
            asyncio.run(test_all())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
