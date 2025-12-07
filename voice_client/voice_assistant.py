#!/usr/bin/env python3
"""
Comprehensive Voice Assistant Client
Integrates Grok STT → Grok-4 with Claude Code MCP → Grok TTS

This client allows you to:
1. Speak your questions/commands (STT)
2. Send them to Grok-4 which can use Claude Code MCP tools
3. Hear the response via TTS
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import websockets
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import mcp

# PyAudio is optional - only needed for audio I/O
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    pyaudio = None


class VoiceAssistant:
    """
    Voice Assistant that combines STT, Grok-4 with MCP, and TTS
    """

    def __init__(
        self,
        mcp_server_url: str = "https://dex-mcp.tunn.dev/mcp",
        voice: str = "ara",
        model: str = "grok-4-1-fast",
        enable_interim_stt: bool = True,
        stt_sample_rate: int = 16000,
        tts_sample_rate: int = 24000,
        enable_stt: bool = True,
        enable_tts: bool = True,
    ):
        self.mcp_server_url = mcp_server_url
        self.voice = voice
        self.model = model
        self.enable_interim_stt = enable_interim_stt
        self.stt_sample_rate = stt_sample_rate
        self.tts_sample_rate = tts_sample_rate
        self.enable_stt = enable_stt
        self.enable_tts = enable_tts

        # Get API key
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY not found in environment variables")

        # Initialize xAI client for chat
        self.xai_client = Client(api_key=self.api_key)

        # STT state
        self.stt_running = False
        self.final_transcript = ""
        self.current_interim = ""

        # WebSocket URLs
        base_url = os.getenv("BASE_URL", "https://api.x.ai/v1")
        self.ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
        self.stt_uri = f"{self.ws_base}/realtime/audio/transcriptions"
        self.tts_uri = f"{self.ws_base}/realtime/audio/speech"

        # Determine mode
        mode = "text-only" if not (enable_stt or enable_tts) else "voice" if (enable_stt and enable_tts) else "hybrid"

        print("🤖 Voice Assistant initialized")
        print(f"   Mode: {mode}")
        print(f"   Model: {self.model}")
        if self.enable_tts:
            print(f"   Voice: {self.voice}")
        if not self.enable_stt:
            print(f"   Input: Text (keyboard)")
        if not self.enable_tts:
            print(f"   Output: Text (screen)")
        print(f"   MCP Server: {self.mcp_server_url}")

    def get_text_input(self) -> str:
        """
        Get text input from keyboard (alternative to voice input).
        """
        try:
            print("\n💬 Your message: ", end="", flush=True)
            text = input().strip()
            return text
        except (EOFError, KeyboardInterrupt):
            return ""

    async def get_input(self) -> str:
        """
        Get input from user - either via voice (STT) or text (keyboard).
        """
        if self.enable_stt:
            return await self.listen_once()
        else:
            return await asyncio.to_thread(self.get_text_input)

    async def listen_once(self) -> str:
        """
        Listen to user speech and return the transcribed text.
        Returns when user pauses or stops speaking.
        """
        if not PYAUDIO_AVAILABLE:
            print("❌ PyAudio is not installed. Install with: pip install pyaudio")
            return ""

        print("\n🎤 Listening... (Speak now)")

        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Initialize PyAudio
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.stt_sample_rate,
            input=True,
            frames_per_buffer=1024,
        )

        self.final_transcript = ""
        self.current_interim = ""
        self.stt_running = True

        # Track silence to auto-stop
        silence_start = None
        silence_threshold = 2.0  # seconds of silence before stopping
        last_transcript_time = time.time()

        try:
            async with websockets.connect(self.stt_uri, additional_headers=headers) as websocket:
                # Send config
                config_message = {
                    "type": "config",
                    "data": {
                        "encoding": "linear16",
                        "sample_rate_hertz": self.stt_sample_rate,
                        "enable_interim_results": self.enable_interim_stt,
                    },
                }
                await websocket.send(json.dumps(config_message))

                # Create tasks for sending and receiving
                send_task = asyncio.create_task(self._send_audio_stt(websocket, stream))
                recv_task = asyncio.create_task(
                    self._receive_transcripts(websocket, silence_threshold)
                )

                # Wait for either task to complete
                done, pending = await asyncio.wait(
                    [send_task, recv_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Cancel remaining tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        except Exception as e:
            print(f"❌ STT Error: {e}")
        finally:
            self.stt_running = False
            stream.stop_stream()
            stream.close()
            p.terminate()

        transcript = self.final_transcript.strip()
        if transcript:
            print(f"✅ You said: {transcript}\n")
        else:
            print("⚠️  No speech detected\n")

        return transcript

    async def _send_audio_stt(self, websocket, stream):
        """Send audio chunks to STT WebSocket."""
        try:
            while self.stt_running:
                audio_data = await asyncio.to_thread(
                    stream.read, 1024, exception_on_overflow=False
                )
                audio_b64 = base64.b64encode(audio_data).decode("utf-8")

                audio_message = {
                    "type": "audio",
                    "data": {"audio": audio_b64},
                }
                await websocket.send(json.dumps(audio_message))

        except Exception as e:
            if self.stt_running:
                print(f"❌ Error sending audio: {e}")
                self.stt_running = False

    async def _receive_transcripts(self, websocket, silence_threshold: float):
        """Receive and process transcripts from STT WebSocket."""
        last_transcript_time = time.time()

        try:
            while self.stt_running:
                # Check for silence timeout
                if time.time() - last_transcript_time > silence_threshold:
                    if self.final_transcript:  # Only stop if we got something
                        print("\n⏸️  Silence detected, stopping...")
                        self.stt_running = False
                        break

                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    data = json.loads(response)

                    if data.get("data", {}).get("type") == "speech_recognized":
                        transcript_data = data["data"]["data"]
                        transcript = transcript_data.get("transcript", "")
                        is_final = transcript_data.get("is_final", False)

                        if transcript:
                            last_transcript_time = time.time()

                        if is_final:
                            self.final_transcript += transcript + " "
                            self.current_interim = ""
                            print(f"\r✅ {transcript}")
                        else:
                            self.current_interim = transcript
                            print(f"\r💭 {transcript}", end="", flush=True)

                except asyncio.TimeoutError:
                    continue

        except websockets.exceptions.ConnectionClosedOK:
            pass
        except Exception as e:
            if self.stt_running:
                print(f"❌ Error receiving transcripts: {e}")
                self.stt_running = False

    async def ask_grok_with_mcp(self, query: str) -> str:
        """
        Send query to Grok-4 with MCP access to Claude Code.
        Returns the response text.
        """
        print(f"🤔 Asking Grok-4 (with Claude Code access)...")
        print(f"   MCP Server: {self.mcp_server_url}")
        print()

        # Create chat with MCP tool
        try:
            chat = self.xai_client.chat.create(
                model=self.model,
                tools=[mcp(server_url=self.mcp_server_url)],
            )
            print("✓ Chat session created")
        except Exception as e:
            print(f"❌ Failed to create chat: {e}")
            return f"Error creating chat session: {str(e)}"

        try:
            chat.append(user(query))
            print("✓ Query sent")
        except Exception as e:
            print(f"❌ Failed to send query: {e}")
            return f"Error sending query: {str(e)}"

        # Stream the response
        response_text = ""
        is_thinking = True

        try:
            print("⏳ Waiting for response...\n")
            print("   (Note: MCP calls can take 10-60 seconds)\n")

            start_time = time.time()
            last_activity = start_time

            for response, chunk in chat.stream():
                # Update activity time
                last_activity = time.time()

                # Show tool calls
                for tool_call in chunk.tool_calls:
                    print(f"🔧 Calling tool: {tool_call.function.name}")
                    if tool_call.function.arguments:
                        args = tool_call.function.arguments
                        if len(args) > 100:
                            args = args[:100] + "..."
                        print(f"   Args: {args}")

                # Show thinking
                if response.usage.reasoning_tokens and is_thinking:
                    print(f"\r💭 Thinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)

                # Show response
                if chunk.content and is_thinking:
                    print("\n\n📝 Response:")
                    is_thinking = False

                if chunk.content and not is_thinking:
                    print(chunk.content, end="", flush=True)
                    response_text += chunk.content

            print("\n")

            # Show usage stats and timing
            elapsed = time.time() - start_time
            if response.usage:
                print(f"📊 Usage: {response.usage.total_tokens} tokens | Time: {elapsed:.1f}s")
            else:
                print(f"⏱️  Total time: {elapsed:.1f}s")

            return response_text

        except KeyboardInterrupt:
            print("\n⚠️  Interrupted by user")
            raise
        except TimeoutError as e:
            elapsed = time.time() - start_time
            print(f"\n❌ Request timed out after {elapsed:.1f}s")
            return f"The request timed out. The MCP server might be slow or unresponsive."
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Error after {elapsed:.1f}s: {e}")
            return f"Sorry, I encountered an error: {str(e)}"

    async def speak(self, text: str, play_audio: bool = True) -> bytes:
        """
        Convert text to speech using Grok TTS.
        Optionally play the audio in real-time.
        Returns the audio bytes.

        If TTS is disabled, just prints the text.
        """
        if not text:
            return b""

        # If TTS is disabled, just print the text
        if not self.enable_tts:
            print(f"\n💬 Response:\n{text}\n")
            return b""

        print(f"🔊 Speaking response...\n")

        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Initialize audio playback if needed
        audio_stream = None
        p = None
        if play_audio:
            if not PYAUDIO_AVAILABLE:
                print("⚠️  PyAudio not available - skipping playback")
                play_audio = False
            else:
                p = pyaudio.PyAudio()
                audio_stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.tts_sample_rate,
                    output=True,
                )

        audio_bytes = b""

        try:
            async with websockets.connect(self.tts_uri, additional_headers=headers) as websocket:
                # Send config
                config_message = {"type": "config", "data": {"voice_id": self.voice}}
                await websocket.send(json.dumps(config_message))

                # Send text
                text_message = {
                    "type": "text_chunk",
                    "data": {"text": text, "is_last": True},
                }
                await websocket.send(json.dumps(text_message))

                # Receive and play audio
                while True:
                    try:
                        response = await websocket.recv()
                        data = json.loads(response)

                        audio_b64 = data["data"]["data"]["audio"]
                        is_last = data["data"]["data"].get("is_last", False)

                        # Decode audio
                        chunk_bytes = base64.b64decode(audio_b64)
                        audio_bytes += chunk_bytes

                        # Play audio in real-time
                        if play_audio and audio_stream and len(chunk_bytes) > 0:
                            await asyncio.to_thread(audio_stream.write, chunk_bytes)

                        if is_last:
                            break

                    except websockets.exceptions.ConnectionClosedOK:
                        break

        except Exception as e:
            print(f"❌ TTS Error: {e}")
        finally:
            if audio_stream:
                audio_stream.stop_stream()
                audio_stream.close()
            if p:
                p.terminate()

        print("✅ Done speaking\n")
        return audio_bytes

    async def conversation_loop(self):
        """
        Main conversation loop: Listen → Process → Speak
        """
        print("\n" + "=" * 70)
        if self.enable_stt and self.enable_tts:
            print("🎙️  Voice Assistant Ready!")
        elif not self.enable_stt and not self.enable_tts:
            print("💬 Text Assistant Ready!")
        else:
            print("🔀 Hybrid Assistant Ready!")
        print("=" * 70)
        print("\nCommands:")
        if self.enable_stt:
            print("  - Speak your question/command after the prompt")
        else:
            print("  - Type your question/command and press Enter")
        print("  - Say/type 'exit' or 'quit' to stop")
        print("  - Press Ctrl+C to interrupt\n")

        while True:
            try:
                # 1. Get input from user (voice or text)
                transcript = await self.get_input()

                if not transcript:
                    print("⚠️  No input detected, try again\n")
                    continue

                # Check for exit commands
                if transcript.lower().strip() in ["exit", "quit", "goodbye", "stop"]:
                    print("👋 Goodbye!")
                    if self.enable_tts:
                        await self.speak("Goodbye!")
                    break

                # 2. Ask Grok-4 with MCP access
                response = await self.ask_grok_with_mcp(transcript)

                # 3. Speak the response
                if response:
                    await self.speak(response)

            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Error in conversation loop: {e}")
                continue


def main():
    """Main entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Voice Assistant with Grok STT/TTS and Claude Code MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic voice mode (default)
  python voice_assistant.py

  # Text-only mode (no voice input or output)
  python voice_assistant.py --text-only

  # Text input, voice output
  python voice_assistant.py --no-stt

  # Voice input, text output
  python voice_assistant.py --no-tts

  # Custom voice
  python voice_assistant.py --voice rex

  # Custom MCP server
  python voice_assistant.py --mcp-server http://localhost:6030/mcp

  # Different Grok model
  python voice_assistant.py --model grok-4-1

Available voices:
  ara - Female voice (default)
  rex - Male voice
  sal - Voice
  eve - Female voice
  una - Female voice
  leo - Male voice
        """,
    )

    parser.add_argument(
        "--mcp-server",
        default="https://dex-mcp.tunn.dev/mcp",
        help="MCP server URL for Claude Code integration",
    )
    parser.add_argument(
        "--voice",
        default="ara",
        choices=["ara", "rex", "sal", "eve", "una", "leo"],
        help="TTS voice (default: ara)",
    )
    parser.add_argument(
        "--model",
        default="grok-4-1-fast",
        help="Grok model to use (default: grok-4-1-fast)",
    )
    parser.add_argument(
        "--no-interim-stt",
        action="store_true",
        help="Disable interim STT results",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Disable both voice input and output (text mode)",
    )
    parser.add_argument(
        "--no-stt",
        action="store_true",
        help="Disable voice input (use keyboard instead)",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable voice output (text only)",
    )

    args = parser.parse_args()

    # Handle text-only mode
    enable_stt = not (args.text_only or args.no_stt)
    enable_tts = not (args.text_only or args.no_tts)

    try:
        assistant = VoiceAssistant(
            mcp_server_url=args.mcp_server,
            voice=args.voice,
            model=args.model,
            enable_interim_stt=not args.no_interim_stt,
            enable_stt=enable_stt,
            enable_tts=enable_tts,
        )

        asyncio.run(assistant.conversation_loop())

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
