#!/bin/bash
# Run script for Claude Code MCP Server or Client

set -e

cd "$(dirname "$0")"

case "$1" in
    server)
        echo "Starting MCP Server..."
        python -m src.main
        ;;
    client)
        shift  # Remove 'client' from args, pass rest to typer
        echo "Starting Voice Client..."
        python -m client.main start "$@"
        ;;
    *)
        echo "Usage: ./run.sh <server|client> [options]"
        echo ""
        echo "Commands:"
        echo "  server              Start the MCP server"
        echo "  client [options]    Start the voice client"
        echo ""
        echo "Client options:"
        echo "  --text-only, -t     Text input and output only"
        echo "  --no-stt            Type input, hear output"
        echo "  --no-tts            Speak input, read output"
        echo "  --voice, -v NAME    TTS voice (ara, rex, sal, eve, una, leo)"
        echo "  --model, -m NAME    Grok model to use"
        echo "  --mcp URL           MCP server URL (defaults to .env)"
        exit 1
        ;;
esac
