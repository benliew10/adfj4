#!/bin/bash

# Script to stop the Telegram bot

echo "🛑 Stopping Telegram bot..."

# Find and terminate existing bot processes
BOT_PIDS=$(pgrep -f "python.*bot\.py")

if [ ! -z "$BOT_PIDS" ]; then
    echo "📋 Found bot processes: $BOT_PIDS"
    
    # Try graceful termination first (SIGTERM)
    for pid in $BOT_PIDS; do
        if kill -TERM $pid 2>/dev/null; then
            echo "   ✅ Sent SIGTERM to process $pid"
        fi
    done
    
    # Wait for graceful shutdown
    sleep 3
    
    # Check if any processes are still running
    REMAINING_PIDS=$(pgrep -f "python.*bot\.py")
    
    if [ ! -z "$REMAINING_PIDS" ]; then
        echo "⚠️  Some processes still running, forcing termination..."
        # Force kill remaining processes (SIGKILL)
        for pid in $REMAINING_PIDS; do
            if kill -KILL $pid 2>/dev/null; then
                echo "   🔥 Force killed process $pid"
            fi
        done
    fi
    
    echo "✅ Bot stopped successfully"
else
    echo "ℹ️  No bot processes found running"
fi

# Additional cleanup
pkill -f "python.*telegram" 2>/dev/null && echo "   Cleaned up related processes"

echo "🏁 Stop script completed" 