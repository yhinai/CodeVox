"""
Claude Code Voice Client - Unified CLI
"""
import typer
import structlog

app = typer.Typer(
    name="voice",
    help="Claude Code Voice Assistant"
)

log = structlog.get_logger()


@app.command()
def start(
    text_only: bool = typer.Option(False, "--text-only", "-t", help="Text input/output only"),
    no_stt: bool = typer.Option(False, "--no-stt", help="Type input, hear output"),
    no_tts: bool = typer.Option(False, "--no-tts", help="Speak input, read output"),
    voice: str = typer.Option("ara", "--voice", "-v", help="TTS voice"),
    model: str = typer.Option("grok-4-1-fast", "--model", "-m", help="Grok model"),
    mcp_server: str = typer.Option(None, "--mcp", help="MCP server URL"),
):
    """Start the voice assistant."""
    from .assistant import VoiceAssistant
    
    # Determine mode
    if text_only:
        mode = "text-only"
    elif no_stt:
        mode = "no-stt"
    elif no_tts:
        mode = "no-tts"
    else:
        mode = "voice"
    
    # Get URL from settings if not provided
    if mcp_server is None:
        from src.config import settings
        mcp_server = settings.client_mcp_url
        base_url, mcp_url = settings.client_display_urls
    else:
        base_url = mcp_server.replace("/mcp", "")
        mcp_url = mcp_server
    
    log.info("client.starting", mode=mode, voice=voice, model=model)
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Claude Code Voice Assistant                        ║
╠══════════════════════════════════════════════════════════════╣
║  Mode: {mode:<52} ║
║  Voice: {voice:<51} ║
║  Model: {model:<51} ║
║  MCP: {mcp_url:<53} ║
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
    
    print("🔍 Diagnostics\n")
    
    if api_key:
        print(f"✅ XAI_API_KEY: Set ({len(api_key)} chars)")
    else:
        print("❌ XAI_API_KEY: Not set")
    
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        print(f"✅ PyAudio: {p.get_device_count()} devices")
        
        print("\n📱 Input Devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"   [{i}] {info['name']}")
        p.terminate()
    except ImportError:
        print("❌ PyAudio: Not installed")


@app.command()
def devices():
    """List audio devices."""
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        
        print("\n🎤 Input:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"   [{i}] {info['name']}")
        
        print("\n🔊 Output:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:
                print(f"   [{i}] {info['name']}")
        
        p.terminate()
    except ImportError:
        print("❌ PyAudio not installed")


if __name__ == "__main__":
    app()
