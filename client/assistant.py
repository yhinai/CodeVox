"""Voice Assistant - Core logic (refactored from voice_client/voice_assistant.py)"""

import asyncio
import json
import os
import base64
from typing import Optional
import structlog

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
        
        # Send to STT
        try:
            async with websockets.connect(
                "wss://api.x.ai/v1/realtime/audio/transcriptions",
                extra_headers={"Authorization": f"Bearer {self.api_key}"}
            ) as ws:
                # Send audio
                await ws.send(json.dumps({
                    "audio": base64.b64encode(audio_data).decode(),
                    "format": "wav",
                    "sample_rate": self.sample_rate
                }))
                
                # Get transcription
                response = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(response)
                return data.get("text", "")
                
        except Exception as e:
            log.error("stt.error", error=str(e))
            print(f"❌ STT Error: {e}")
            return input("💬 Type instead: ").strip()
    
    def _capture_audio(self, duration: float = 5.0) -> Optional[bytes]:
        """Capture audio from microphone."""
        try:
            import pyaudio
            import wave
            import io
            
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            frames = []
            for _ in range(int(self.sample_rate / self.chunk_size * duration)):
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Convert to WAV format
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(frames))
            
            return buffer.getvalue()
            
        except Exception as e:
            log.error("audio.capture.error", error=str(e))
            return None
    
    async def _ask_grok(self, query: str) -> Optional[str]:
        """Send query to Grok-4 with MCP tools."""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": query}],
                        "mcp": {"servers": [{"type": "url", "url": self.mcp_server}]}
                    }
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        log.error("grok.error", status=resp.status, error=error)
                        return f"Error: {resp.status}"
                    
                    data = await resp.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content")
                    
        except Exception as e:
            log.error("grok.error", error=str(e))
            return f"Error: {e}"
    
    async def _speak(self, text: str):
        """Convert text to speech and play."""
        try:
            import websockets
            import pyaudio
            
            async with websockets.connect(
                "wss://api.x.ai/v1/realtime/audio/speech",
                extra_headers={"Authorization": f"Bearer {self.api_key}"}
            ) as ws:
                await ws.send(json.dumps({
                    "text": text,
                    "voice": self.voice,
                    "format": "wav",
                    "sample_rate": self.sample_rate
                }))
                
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    output=True
                )
                
                async for message in ws:
                    if isinstance(message, bytes):
                        stream.write(message)
                
                stream.stop_stream()
                stream.close()
                p.terminate()
                
        except Exception as e:
            log.error("tts.error", error=str(e))
            print(f"⚠️ TTS Error: {e}")
