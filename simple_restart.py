#!/usr/bin/env python3
"""
Simple Bot Process Manager (No external dependencies)
Handles starting, stopping, and restarting the Telegram bot to prevent conflicts.
"""

import os
import sys
import time
import signal
import subprocess
import argparse

def find_bot_processes():
    """Find all running bot processes using ps command."""
    try:
        # Use ps to find processes
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        bot_pids = []
        
        for line in result.stdout.split('\n'):
            if 'python' in line.lower() and 'bot.py' in line and 'grep' not in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        bot_pids.append(pid)
                    except ValueError:
                        continue
        
        return bot_pids
    except Exception as e:
        print(f"Error finding processes: {e}")
        return []

def stop_bot_processes(graceful_timeout=5):
    """Stop all bot processes."""
    print("🛑 Stopping existing bot processes...")
    
    bot_pids = find_bot_processes()
    
    if not bot_pids:
        print("ℹ️  No bot processes found running")
        return True
    
    print(f"📋 Found bot processes: {bot_pids}")
    
    # Try graceful termination first
    for pid in bot_pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"   ✅ Sent SIGTERM to process {pid}")
        except OSError as e:
            print(f"   ⚠️  Could not send SIGTERM to process {pid}: {e}")
    
    # Wait for graceful shutdown
    print(f"⏳ Waiting {graceful_timeout} seconds for graceful shutdown...")
    time.sleep(graceful_timeout)
    
    # Check for remaining processes
    remaining_pids = find_bot_processes()
    
    if remaining_pids:
        print("⚠️  Some processes still running, forcing termination...")
        for pid in remaining_pids:
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"   🔥 Force killed process {pid}")
            except OSError as e:
                print(f"   ❌ Could not kill process {pid}: {e}")
        
        time.sleep(1)
        
        # Final check
        final_pids = find_bot_processes()
        if final_pids:
            print(f"❌ Failed to stop processes: {final_pids}")
            return False
    
    print("✅ All bot processes stopped successfully")
    return True

def start_bot():
    """Start the bot."""
    print("🚀 Starting new bot instance...")
    
    if not os.path.exists('bot.py'):
        print("❌ bot.py not found in current directory")
        return False
    
    try:
        # Start the bot in background
        with open('bot.log', 'w') as log_file:
            process = subprocess.Popen(
                [sys.executable, 'bot.py'],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
        
        print(f"✅ Bot started with PID: {process.pid}")
        print("📝 Logs are being written to bot.log")
        
        # Wait a moment and check if the bot is still running
        time.sleep(3)
        
        if process.poll() is None:
            print("🎉 Bot is running successfully!")
            print("📊 To monitor logs: tail -f bot.log")
            print(f"🛑 To stop bot: kill {process.pid}")
            return True
        else:
            print("❌ Bot failed to start. Check bot.log for errors.")
            try:
                with open('bot.log', 'r') as f:
                    lines = f.readlines()
                    print("Last 10 lines of log:")
                    for line in lines[-10:]:
                        print(f"   {line.rstrip()}")
            except Exception:
                pass
            return False
    
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        return False

def restart_bot():
    """Restart the bot (stop then start)."""
    print("🔄 Restarting bot...")
    
    if not stop_bot_processes():
        print("❌ Failed to stop existing processes")
        return False
    
    # Wait a moment before starting
    time.sleep(2)
    
    return start_bot()

def check_bot_status():
    """Check if bot is running."""
    bot_pids = find_bot_processes()
    
    if bot_pids:
        print(f"✅ Bot is running with PID(s): {bot_pids}")
        
        # Try to get basic process info
        for pid in bot_pids:
            try:
                # Check if process is still alive
                os.kill(pid, 0)  # This doesn't kill, just checks if process exists
                print(f"   PID {pid}: Process is alive")
            except OSError:
                print(f"   PID {pid}: Process not found (might be zombie)")
    else:
        print("❌ Bot is not running")

def main():
    parser = argparse.ArgumentParser(description='Simple Telegram Bot Process Manager')
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status'], 
                       help='Action to perform')
    
    args = parser.parse_args()
    
    if args.action == 'start':
        # Check if already running
        if find_bot_processes():
            print("⚠️  Bot is already running. Use 'restart' to restart or 'stop' to stop.")
            return
        start_bot()
    
    elif args.action == 'stop':
        stop_bot_processes()
    
    elif args.action == 'restart':
        restart_bot()
    
    elif args.action == 'status':
        check_bot_status()

if __name__ == '__main__':
    main() 