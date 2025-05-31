#!/bin/bash

# Script to safely restart the Telegram bot
# This ensures no conflicts with existing bot instances

echo "🔍 Checking for existing bot processes..."

# Find and terminate existing bot processes
BOT_PIDS=$(pgrep -f "python.*bot\.py" | head -10)

if [ ! -z "$BOT_PIDS" ]; then
    echo "📋 Found existing bot processes: $BOT_PIDS"
    echo "🛑 Terminating existing bot processes..."
    
    # Try graceful termination first (SIGTERM)
    for pid in $BOT_PIDS; do
        if kill -TERM $pid 2>/dev/null; then
            echo "   ✅ Sent SIGTERM to process $pid"
        fi
    done
    
    # Wait a moment for graceful shutdown
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
        sleep 1
    fi
    
    echo "✅ All existing bot processes terminated"
else
    echo "✅ No existing bot processes found"
fi

# Additional cleanup: kill any python processes that might be related
echo "🧹 Performing additional cleanup..."
pkill -f "python.*telegram" 2>/dev/null && echo "   Killed telegram-related processes"

# Wait a moment to ensure everything is cleaned up
sleep 2

echo "🚀 Starting new bot instance..."

# Start the new bot
if [ -f "bot.py" ]; then
    echo "📂 Found bot.py, starting bot..."
    nohup python bot.py > bot.log 2>&1 &
    BOT_PID=$!
    echo "✅ Bot started with PID: $BOT_PID"
    echo "📝 Logs are being written to bot.log"
    
    # Wait a moment and check if the bot is still running
    sleep 3
    if kill -0 $BOT_PID 2>/dev/null; then
        echo "🎉 Bot is running successfully!"
        echo "📊 To monitor logs: tail -f bot.log"
        echo "🛑 To stop bot: kill $BOT_PID"
    else
        echo "❌ Bot failed to start. Check bot.log for errors."
        tail -10 bot.log
    fi
else
    echo "❌ bot.py not found in current directory"
    exit 1
fi 