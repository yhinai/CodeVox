#!/bin/bash
set -e

PID_FILE=".mcp.pid"
LOG_FILE="server.log"

case "$1" in
    server)
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "⚠️  Server already running (PID $(cat $PID_FILE))"
            exit 1
        fi
        echo "🚀 Starting Autonomous MCP Server v3.1..."
        nohup python -m server.main > $LOG_FILE 2>&1 &
        echo $! > $PID_FILE
        sleep 2
        if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "✅ Active (PID $(cat $PID_FILE))"
            echo "   Logs: tail -f $LOG_FILE"
            echo "   URL:  http://127.0.0.1:6030/mcp"
        else
            echo "❌ Failed. Check $LOG_FILE"
            rm -f "$PID_FILE"
        fi
        ;;
    stop)
        if [ -f "$PID_FILE" ]; then
            kill $(cat "$PID_FILE") 2>/dev/null || true
            rm -f "$PID_FILE"
            echo "🛑 Stopped"
        else
            lsof -ti :6030 | xargs kill -9 2>/dev/null || true
            echo "🛑 Stopped (by port)"
        fi
        ;;
    restart)
        $0 stop && sleep 1 && $0 server
        ;;
    logs)
        tail -f $LOG_FILE
        ;;
    client)
        shift
        python -m client.main start "$@"
        ;;
    *)
        echo "Usage: $0 {server|stop|restart|logs|client}"
        ;;
esac
