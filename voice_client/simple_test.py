#!/usr/bin/env python3
"""
Simple test to verify xAI SDK works with MCP
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment
load_dotenv()

def test_sync():
    """Test synchronous (non-streaming) mode"""
    print("\n" + "=" * 70)
    print("Testing xAI SDK with MCP (Non-streaming)")
    print("=" * 70)

    # Check API key
    api_key = os.getenv("XAI_API_KEY")
    if not api_key or api_key == "your_key_here":
        print("\n❌ XAI_API_KEY not set properly in .env")
        print("   Please edit /home/green/code/claudia/claude_code_mcp/.env")
        print("   and add your actual API key from https://console.x.ai/")
        return False

    print(f"\n✓ API key loaded (length: {len(api_key)})")

    try:
        from xai_sdk import Client
        from xai_sdk.chat import user
        from xai_sdk.tools import mcp

        print("✓ xai_sdk imported")

        # Create client
        client = Client(api_key=api_key)
        print("✓ Client created")

        # Test without MCP first
        print("\n--- Test 1: Simple query (no MCP) ---")
        chat = client.chat.create(model="grok-4-1-fast")
        chat.append(user("Say 'hello' in one word"))

        print("Sending query...")
        response = chat.sample()
        print(f"✓ Response: {response.content}")

        # Test with MCP
        print("\n--- Test 2: With MCP tools ---")
        mcp_url = "https://dex-mcp.tunn.dev/mcp"
        print(f"MCP Server: {mcp_url}")

        chat2 = client.chat.create(
            model="grok-4-1-fast",
            tools=[mcp(server_url=mcp_url)],
        )
        print("✓ Chat with MCP created")

        chat2.append(user("List all available environments using the MCP tools"))
        print("✓ Query added")

        print("\nSending query with MCP...")
        print("(This may take 10-30 seconds...)")

        # Non-streaming sample with timeout
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError("Request timed out after 60 seconds")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(60)  # 60 second timeout

        try:
            response2 = chat2.sample()
            signal.alarm(0)  # Cancel alarm

            print(f"\n✓ Success!")
            print(f"Response: {response2.content[:200]}...")

            if response2.tool_calls:
                print(f"\nTool calls made: {len(response2.tool_calls)}")
                for tc in response2.tool_calls:
                    print(f"  - {tc.function.name}")

            return True

        except TimeoutError as e:
            signal.alarm(0)
            print(f"\n❌ {e}")
            print("\nThis could mean:")
            print("  1. Network is slow")
            print("  2. MCP server is not responding")
            print("  3. xAI API is having issues")
            return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_timeout():
    """Test with explicit timeout using asyncio"""
    print("\n" + "=" * 70)
    print("Testing with asyncio timeout")
    print("=" * 70)

    async def run_test():
        from xai_sdk import AsyncClient
        from xai_sdk.chat import user
        from xai_sdk.tools import mcp

        api_key = os.getenv("XAI_API_KEY")
        client = AsyncClient(api_key=api_key)

        chat = client.chat.create(
            model="grok-4-1-fast",
            tools=[mcp(server_url="https://dex-mcp.tunn.dev/mcp")],
        )

        chat.append(user("What environments are available?"))

        print("\nSending query (30 second timeout)...")

        try:
            # Use asyncio timeout
            response = await asyncio.wait_for(
                chat.sample(),
                timeout=30.0
            )

            print(f"✓ Success: {response.content[:200]}...")
            return True

        except asyncio.TimeoutError:
            print("❌ Timed out after 30 seconds")
            return False

    try:
        return asyncio.run(run_test())
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    print("\n🧪 Simple MCP Test Suite\n")

    # Test 1: Synchronous
    success1 = test_sync()

    if not success1:
        print("\n" + "=" * 70)
        print("Basic test failed. Check:")
        print("  1. XAI_API_KEY is set correctly in .env")
        print("  2. Internet connection is working")
        print("  3. https://api.x.ai is accessible")
        print("=" * 70)
        return

    # Test 2: With timeout
    print("\n")
    success2 = test_with_timeout()

    if success1 and success2:
        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        print("\nYou can now use the voice assistant:")
        print("  ./run.sh --text-only")
    else:
        print("\n" + "=" * 70)
        print("⚠️  Some tests failed")
        print("=" * 70)
        print("\nThe MCP integration may be slow or timing out.")
        print("Try increasing timeouts or check MCP server status.")


if __name__ == "__main__":
    main()
