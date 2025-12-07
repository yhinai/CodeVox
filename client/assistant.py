"""
Voice Assistant - Clean architecture with dynamic tool discovery.
Uses AudioCapture for VAD and MCPClient for dynamic tools.
"""
import asyncio
import json
import os
from typing import Optional, List, Dict
import structlog
from dotenv import load_dotenv

from .mcp_client import MCPClient
from .audio import AudioCapture

load_dotenv()
log = structlog.get_logger()


class VoiceAssistant:
    """Voice assistant with STT, TTS, and dynamic MCP tool execution."""
    
    def __init__(
        self,
        mode: str = "voice",
        voice: str = "ara",
        model: str = "grok-4-1-fast",
        mcp_server: str = None
    ):
        self.mode = mode
        self.voice = voice
        self.model = model
        self.api_key = os.getenv("XAI_API_KEY", "")
        
        # Use config for default URL
        if mcp_server is None:
            from server.config import settings
            mcp_server = settings.mcp_endpoint
        
        self.mcp_client = MCPClient(mcp_server)
        self.audio = AudioCapture()
        self.tools: List[Dict] = []
        self.conversation_history: List[Dict] = []
        
        self.system_prompt = """You are a helpful voice assistant with access to coding tools.
When the user asks you to perform tasks, use the available function tools.
Be concise since responses will be spoken aloud."""
        
        if not self.api_key:
            raise ValueError("XAI_API_KEY environment variable not set")
    
    def run(self):
        """Run the assistant."""
        asyncio.run(self._main_loop())
    
    async def _main_loop(self):
        """Main conversation loop."""
        # Discover tools dynamically
        print("🔌 Connecting to MCP Server...")
        self.tools = await self.mcp_client.get_adaptable_tools()
        print(f"⚡ Loaded {len(self.tools)} tools dynamically\n")
        
        print("🎙️ Assistant Ready! Say 'exit' or 'quit' to stop.\n")
        
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
                
                if user_input.lower() in ["exit", "quit", "bye", "goodbye"]:
                    print("👋 Goodbye!")
                    break
                
                print(f"✅ You said: {user_input}\n")
                
                # Get response
                print("🤔 Thinking...")
                response = await self._ask_grok(user_input)
                
                if not response:
                    print("❌ No response received")
                    continue
                
                # Output
                print(f"\n💬 Response:\n{response}\n")
                if self.mode not in ["text-only", "no-tts"]:
                    await self._speak(response)
                
                # Update history
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({"role": "assistant", "content": response})
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                
            except KeyboardInterrupt:
                print("\n⚠️ Interrupted")
                break
            except Exception as e:
                log.error("assistant.error", error=str(e))
                print(f"❌ Error: {e}")
    
    async def _listen(self) -> Optional[str]:
        """Capture and transcribe audio."""
        audio_data = self.audio.capture()
        if not audio_data:
            return None
        
        try:
            import aiohttp
            
            print("   Sending to STT...")
            form_data = aiohttp.FormData()
            form_data.add_field('file', audio_data, filename='audio.wav', content_type='audio/wav')
            form_data.add_field('model', 'grok-2-vision-1212')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.x.ai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=form_data
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("text", "") or None
                    else:
                        print(f"   STT Error: {resp.status}")
                        return input("💬 Type instead: ").strip()
                        
        except Exception as e:
            log.error("stt.error", error=str(e))
            return input("💬 Type instead: ").strip()
    
    async def _ask_grok(self, query: str) -> Optional[str]:
        """Query Grok with dynamic tool execution."""
        try:
            import aiohttp
            
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_history)
            messages.append({"role": "user", "content": query})
            
            async with aiohttp.ClientSession() as session:
                for iteration in range(5):
                    payload = {
                        "model": self.model,
                        "messages": messages,
                        "tools": self.tools
                    }
                    
                    print(f"   📡 Calling Grok API (iteration {iteration + 1})...")
                    
                    async with session.post(
                        "https://api.x.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json=payload
                    ) as resp:
                        if resp.status != 200:
                            error = await resp.text()
                            return f"Error: {resp.status}"
                        
                        data = await resp.json()
                        choice = data.get("choices", [{}])[0]
                        message = choice.get("message", {})
                        tool_calls = message.get("tool_calls", [])
                        
                        if tool_calls:
                            messages.append(message)
                            
                            for tool_call in tool_calls:
                                tool_name = tool_call.get("function", {}).get("name", "")
                                tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                                
                                print(f"   🔧 Tool: {tool_name}")
                                try:
                                    tool_args = json.loads(tool_args_str)
                                except:
                                    tool_args = {}
                                
                                result = await self.mcp_client.call_tool(tool_name, tool_args)
                                result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                                
                                print(f"      ✅ Result: {result_str[:100]}...")
                                
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.get("id", ""),
                                    "content": result_str
                                })
                            continue
                        
                        return message.get("content", "No response")
                
                return "Max iterations reached"
                
        except Exception as e:
            log.error("grok.error", error=str(e))
            return f"Error: {e}"
    
    async def _speak(self, text: str):
        """Text to speech."""
        try:
            import aiohttp
            import subprocess
            import tempfile
            
            print("   🔊 Generating speech...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.x.ai/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "input": text,
                        "voice": self.voice.capitalize(),
                        "response_format": "mp3"
                    }
                ) as resp:
                    if resp.status == 200:
                        audio = await resp.read()
                        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                            f.write(audio)
                            temp_path = f.name
                        
                        try:
                            subprocess.run(['afplay', temp_path], check=True)
                        finally:
                            os.unlink(temp_path)
                    else:
                        print(f"   ⚠️ TTS Error: {resp.status}")
                        
        except Exception as e:
            log.error("tts.error", error=str(e))
