#!/bin/bash
set -e

# Configuration
PID_FILE=".mcp_server.pid"
LOG_FILE="server.log"

function start_server {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat $PID_FILE)
        if ps -p $OLD_PID > /dev/null 2>&1; then
            echo "Server already running (PID $OLD_PID). Stop it first."
            exit 1
        else
            rm $PID_FILE
        fi
    fi
    
    echo "Starting Autonomous MCP Server..."
    source .venv/bin/activate 2>/dev/null || true
    nohup python -m server.main > $LOG_FILE 2>&1 &
    echo $! > $PID_FILE
    
    sleep 2
    if ps -p $(cat $PID_FILE) > /dev/null 2>&1; then
        echo "✅ Server active (PID $(cat $PID_FILE))"
        echo "   Logs: $LOG_FILE"
        echo "   URL: http://127.0.0.1:6030/mcp"
    else
        echo "❌ Server failed to start. Check $LOG_FILE"
        rm -f $PID_FILE
        exit 1
    fi
}

function stop_server {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat $PID_FILE)
        echo "Stopping PID $PID..."
        kill $PID 2>/dev/null || true
        rm -f $PID_FILE
        echo "✅ Stopped."
    else
        # Try to kill by port
        lsof -ti :6030 | xargs kill -9 2>/dev/null || true
        echo "Server stopped."
    fi
}

function show_logs {
    if [ -f "$LOG_FILE" ]; then
        tail -50 $LOG_FILE
    else
        echo "No log file found."
    fi
}

case "$1" in
    server)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 1
        start_server
        ;;
    logs)
        show_logs
        ;;
    client)
        shift
        source .venv/bin/activate 2>/dev/null || true
        python -m client.main start "$@"
        ;;
    *)
        echo "Usage: ./run.sh [server | stop | restart | logs | client]"
        echo ""
        echo "Commands:"
        echo "  server   Start MCP server in background"
        echo "  stop     Stop running server"
        echo "  restart  Restart server"
        echo "  logs     View server logs"
        echo "  client   Start voice client"
        ;;
esac
