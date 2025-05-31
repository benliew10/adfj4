#!/usr/bin/env python3
"""
Bot Process Manager
Handles starting, stopping, and restarting the Telegram bot to prevent conflicts.
"""

import os
import sys
import time
import signal
import subprocess
import psutil
import argparse
from typing import List

def find_bot_processes() -> List[int]:
    """Find all running bot processes."""
    bot_pids = []
    
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            # Look for Python processes running bot.py
            if 'python' in cmdline.lower() and 'bot.py' in cmdline:
                bot_pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    return bot_pids

def stop_bot_processes(graceful_timeout: int = 5) -> bool:
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
        except OSError:
            print(f"   ⚠️  Could not send SIGTERM to process {pid}")
    
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
            except OSError:
                print(f"   ❌ Could not kill process {pid}")
        
        time.sleep(1)
        
        # Final check
        final_pids = find_bot_processes()
        if final_pids:
            print(f"❌ Failed to stop processes: {final_pids}")
            return False
    
    print("✅ All bot processes stopped successfully")
    return True

def start_bot() -> bool:
    """Start the bot."""
    print("🚀 Starting new bot instance...")
    
    if not os.path.exists('bot.py'):
        print("❌ bot.py not found in current directory")
        return False
    
    try:
        # Start the bot in background
        process = subprocess.Popen(
            [sys.executable, 'bot.py'],
            stdout=open('bot.log', 'w'),
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

def restart_bot() -> bool:
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
        
        for pid in bot_pids:
            try:
                proc = psutil.Process(pid)
                print(f"   PID {pid}: CPU={proc.cpu_percent():.1f}%, Memory={proc.memory_info().rss/1024/1024:.1f}MB")
                print(f"   Started: {time.ctime(proc.create_time())}")
            except Exception:
                print(f"   PID {pid}: Could not get process info")
    else:
        print("❌ Bot is not running")

def main():
    parser = argparse.ArgumentParser(description='Telegram Bot Process Manager')
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