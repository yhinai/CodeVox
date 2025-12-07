"""Voice Assistant - Core logic (refactored from voice_client/voice_assistant.py)"""

import asyncio
import json
import os
import base64
from typing import Optional
import structlog
from dotenv import load_dotenv

# Load .env file
load_dotenv()

log = structlog.get_logger()


class VoiceAssistant:
    """Voice assistant that integrates STT, TTS, and Grok-4 with MCP."""
    
    def __init__(
        self,
        mode: str = "voice",
        voice: str = "ara",
        model: str = "grok-4-1-fast",
        mcp_server: str = "https://dex-mcp.tunn.dev/mcp"
    ):
        self.mode = mode
        self.voice = voice
        self.model = model
        self.mcp_server = mcp_server
        self.api_key = os.getenv("XAI_API_KEY", "")
        
        # Audio settings
        self.sample_rate = 24000
        self.chunk_size = 1024
        
        # Conversation history for multi-turn context
        self.conversation_history = []
        self.system_prompt = """You are a helpful voice assistant with access to MCP (Model Context Protocol) tools.
When the user asks you to perform coding tasks, use the available MCP tools.
Be concise in responses since they will be spoken aloud.
Announce when you're using tools so the user knows what's happening."""
        
        if not self.api_key:
            raise ValueError("XAI_API_KEY environment variable not set")
    
    def run(self):
        """Run the voice assistant conversation loop."""
        asyncio.run(self._conversation_loop())
    
    async def _conversation_loop(self):
        """Main conversation loop."""
        print("\n🎙️ Assistant Ready! Say 'exit' or 'quit' to stop.\n")
        
        while True:
            try:
                # Get input
                if self.mode in ["text-only", "no-stt"]:
                    user_input = input("💬 Your message: ").strip()
                else:
                    user_input = await self._listen()
                
                if not user_input:
                    print("⚠️  No input detected, try again")
                    continue
                
                # Check for exit
                if user_input.lower() in ["exit", "quit", "bye", "goodbye"]:
                    print("👋 Goodbye!")
                    break
                
                print(f"✅ You said: {user_input}\n")
                
                # Get response from Grok
                print("🤔 Thinking...")
                response = await self._ask_grok(user_input)
                
                if not response:
                    print("❌ No response received")
                    continue
                
                # Output response
                if self.mode in ["text-only", "no-tts"]:
                    print(f"\n💬 Response:\n{response}\n")
                else:
                    print(f"\n💬 Response:\n{response}\n")
                    await self._speak(response)
                
                # Add to conversation history (keep last 10 turns)
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({"role": "assistant", "content": response})
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                
            except KeyboardInterrupt:
                print("\n⚠️ Interrupted")
                break
            except Exception as e:
                log.error("conversation.error", error=str(e))
                print(f"❌ Error: {e}")
    
    async def _listen(self) -> Optional[str]:
        """Capture audio and transcribe using STT."""
        try:
            import pyaudio
            import websockets
        except ImportError as e:
            print(f"❌ Missing dependency: {e}")
            return input("💬 Type instead: ").strip()
        
        print("🎤 Listening... (Speak now)")
        
        # Capture audio
        audio_data = self._capture_audio()
        if not audio_data:
            return None
        
        # Send to STT via REST API
        try:
            import aiohttp
            
            print("   Sending to STT...")
            
            # Create form data with audio file
            form_data = aiohttp.FormData()
            form_data.add_field('file', audio_data, filename='audio.wav', content_type='audio/wav')
            form_data.add_field('model', 'grok-2-vision-1212')  # STT model
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.x.ai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=form_data
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"   STT Response: {data}")
                        text = data.get("text", "")
                        return text if text else None
                    else:
                        error_text = await resp.text()
                        print(f"   STT Error ({resp.status}): {error_text[:200]}")
                        return input("💬 Type instead: ").strip()
                
        except Exception as e:
            log.error("stt.error", error=str(e))
            print(f"❌ STT Error: {e}")
            return input("💬 Type instead: ").strip()
            print(f"❌ STT Error: {e}")
            return input("💬 Type instead: ").strip()
    
    def _capture_audio(self, duration: float = 5.0) -> Optional[bytes]:
        """Capture audio from microphone with visual feedback."""
        try:
            import pyaudio
            import wave
            import io
            import struct
            import math
            
            p = pyaudio.PyAudio()
            
            # Use default input device
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            frames = []
            num_chunks = int(self.sample_rate / self.chunk_size * duration)
            
            print("   Recording: ", end="", flush=True)
            
            for i in range(num_chunks):
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
                
                # Show progress every 0.5 seconds
                if i % int(self.sample_rate / self.chunk_size / 2) == 0:
                    # Calculate audio level
                    samples = struct.unpack(f'{len(data)//2}h', data)
                    rms = math.sqrt(sum(s**2 for s in samples) / len(samples)) if samples else 0
                    level = min(int(rms / 1000), 10)
                    bar = "█" * level + "░" * (10 - level)
                    print(f"\r   Recording: [{bar}] {i * self.chunk_size / self.sample_rate:.1f}s ", end="", flush=True)
            
            print("✓")
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Check if we captured any audio
            if not frames:
                print("   ⚠️ No audio frames captured")
                return None
            
            # Convert to WAV format
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(frames))
            
            audio_bytes = buffer.getvalue()
            print(f"   Captured {len(audio_bytes)} bytes of audio")
            return audio_bytes
            
        except Exception as e:
            log.error("audio.capture.error", error=str(e))
            print(f"\n   ❌ Audio capture error: {e}")
            return None
    
    async def _ask_grok(self, query: str) -> Optional[str]:
        """Send query to Grok-4 with MCP tools and handle tool calling."""
        try:
            import aiohttp
            
            # Build messages with history
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history)
            messages.append({"role": "user", "content": query})
            
            async with aiohttp.ClientSession() as session:
                # Multi-turn loop to handle tool calls
                max_iterations = 10
                for iteration in range(max_iterations):
                    async with session.post(
                        "https://api.x.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "mcp": {"servers": [{"type": "url", "url": self.mcp_server}]}
                        }
                    ) as resp:
                        if resp.status != 200:
                            error = await resp.text()
                            log.error("grok.error", status=resp.status, error=error[:200])
                            return f"Error: {resp.status}"
                        
                        data = await resp.json()
                        choice = data.get("choices", [{}])[0]
                        message = choice.get("message", {})
                        finish_reason = choice.get("finish_reason", "")
                        
                        # Check for tool calls
                        tool_calls = message.get("tool_calls", [])
                        
                        if tool_calls:
                            # Display tool usage
                            for tool_call in tool_calls:
                                tool_name = tool_call.get("function", {}).get("name", "unknown")
                                tool_args = tool_call.get("function", {}).get("arguments", "{}")
                                print(f"   🔧 Tool: {tool_name}")
                                # Truncate long args
                                if len(tool_args) > 100:
                                    print(f"      Args: {tool_args[:100]}...")
                                else:
                                    print(f"      Args: {tool_args}")
                            
                            # Add assistant message with tool calls to conversation
                            messages.append(message)
                            
                            # The MCP server handles tool execution and returns results
                            # We continue the loop to get the final response
                            continue
                        
                        # No tool calls - return the content
                        content = message.get("content", "")
                        
                        # Handle thinking/reasoning if present
                        if message.get("reasoning_content"):
                            print(f"   💭 Reasoning: {message['reasoning_content'][:100]}...")
                        
                        return content if content else "No response"
                
                return "Max tool iterations reached"
                    
        except Exception as e:
            log.error("grok.error", error=str(e))
            return f"Error: {e}"
    
    async def _speak(self, text: str):
        """Convert text to speech and play using REST API."""
        try:
            import aiohttp
            import subprocess
            import tempfile
            import os
            
            print("   🔊 Generating speech...")
            
            # Use proper voice name capitalization
            voice_name = self.voice.capitalize()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.x.ai/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "input": text,
                        "voice": voice_name,
                        "response_format": "mp3"
                    }
                ) as resp:
                    if resp.status == 200:
                        audio_data = await resp.read()
                        print(f"   ✅ Got {len(audio_data)} bytes of audio")
                        
                        # Save to temp file and play with afplay (macOS)
                        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                            f.write(audio_data)
                            temp_path = f.name
                        
                        try:
                            # Use afplay on macOS for reliable MP3 playback
                            subprocess.run(['afplay', temp_path], check=True)
                        finally:
                            os.unlink(temp_path)
                    else:
                        error = await resp.text()
                        print(f"   ⚠️ TTS Error ({resp.status}): {error[:200]}")
                
        except Exception as e:
            log.error("tts.error", error=str(e))
            print(f"⚠️ TTS Error: {e}")


