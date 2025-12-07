"""
Claude Code Voice Client - Unified CLI
Single entry point for all voice assistant modes.
"""

import typer
from typing import Optional
import structlog
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import settings

app = typer.Typer(
    name="claude-voice",
    help="Claude Code Voice Assistant - Talk to AI with voice or text"
)

log = structlog.get_logger()


@app.command()
def start(
    text_only: bool = typer.Option(False, "--text-only", "-t", help="Text input and output only"),
    no_stt: bool = typer.Option(False, "--no-stt", help="Type input, hear output"),
    no_tts: bool = typer.Option(False, "--no-tts", help="Speak input, read output"),
    voice: str = typer.Option("ara", "--voice", "-v", help="TTS voice (ara, rex, sal, eve, una, leo)"),
    model: str = typer.Option("grok-4-1-fast", "--model", "-m", help="Grok model to use"),
    mcp_server: str = typer.Option(None, "--mcp", help="MCP server URL (defaults to MCP_BASE_URL from .env)"),
):
    """
    Start the voice assistant.
    
    Examples:
        client start                    # Full voice mode
        client start --text-only        # Text input/output
        client start --no-stt           # Type + hear
        client start --voice rex        # Different voice
    """
    from .assistant import VoiceAssistant
    
    # Use settings for MCP URL if not provided via CLI
    if mcp_server is None:
        mcp_server = settings.client_mcp_url
    
    # Get display URLs (base, mcp_endpoint)
    base_url, mcp_url = settings.client_display_urls
    
    # Determine mode
    if text_only:
        mode = "text-only"
    elif no_stt:
        mode = "no-stt"
    elif no_tts:
        mode = "no-tts"
    else:
        mode = "voice"
    
    log.info("client.starting", mode=mode, voice=voice, model=model)
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Claude Code Voice Assistant                        ║
╠══════════════════════════════════════════════════════════════╣
║  Mode: {mode:<52} ║
║  Voice: {voice:<51} ║
║  Model: {model:<51} ║
║  MCP Base: {base_url:<48} ║
║  MCP Endpoint: {mcp_url:<44} ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    assistant = VoiceAssistant(
        mode=mode,
        voice=voice,
        model=model,
        mcp_server=mcp_server
    )
    
    try:
        assistant.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")


@app.command()
def test():
    """Test audio devices and API connectivity."""
    import os
    
    api_key = os.getenv("XAI_API_KEY", "")
    
    print("🔍 Running diagnostics...\n")
    
    # Check API key
    if api_key:
        print(f"✅ XAI_API_KEY: Set ({len(api_key)} chars)")
    else:
        print("❌ XAI_API_KEY: Not set")
    
    # Check PyAudio
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        print(f"✅ PyAudio: Installed ({device_count} audio devices)")
        
        # List input devices
        print("\n📱 Audio Input Devices:")
        for i in range(device_count):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"   [{i}] {info['name']}")
        
        p.terminate()
    except ImportError:
        print("❌ PyAudio: Not installed (run: pip install pyaudio)")
    except Exception as e:
        print(f"⚠️  PyAudio: Error - {e}")
    
    print("\n✅ Diagnostics complete")


@app.command()
def devices():
    """List available audio devices."""
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        
        print("\n🎤 Input Devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                default = " (default)" if info.get('isDefault') else ""
                print(f"   [{i}] {info['name']}{default}")
        
        print("\n🔊 Output Devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                default = " (default)" if info.get('isDefault') else ""
                print(f"   [{i}] {info['name']}{default}")
        
        p.terminate()
    except ImportError:
        print("❌ PyAudio not installed. Run: pip install pyaudio")


if __name__ == "__main__":
    app()
