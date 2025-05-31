#!/usr/bin/env python3
"""
Render-specific bot startup script
Handles cloud deployment requirements and graceful shutdowns
"""

import os
import sys
import time
import signal
import subprocess
import atexit

def cleanup():
    """Cleanup function called on exit."""
    print("🧹 Performing cleanup...")

def signal_handler(signum, frame):
    """Handle termination signals gracefully."""
    print(f"📡 Received signal {signum}, shutting down gracefully...")
    cleanup()
    sys.exit(0)

def find_bot_processes():
    """Find running bot processes (Render-compatible)."""
    try:
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

def stop_existing_bots():
    """Stop any existing bot processes."""
    print("🔍 Checking for existing bot processes...")
    
    bot_pids = find_bot_processes()
    
    if bot_pids:
        print(f"🛑 Found existing bot processes: {bot_pids}")
        
        for pid in bot_pids:
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"   ✅ Sent SIGTERM to process {pid}")
            except OSError as e:
                print(f"   ⚠️  Could not terminate process {pid}: {e}")
        
        # Wait for graceful shutdown
        time.sleep(3)
        
        # Force kill any remaining processes
        remaining = find_bot_processes()
        for pid in remaining:
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"   🔥 Force killed process {pid}")
            except OSError:
                pass
    else:
        print("✅ No existing bot processes found")

def main():
    """Main startup function for Render."""
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(cleanup)
    
    print("🚀 Starting Telegram Bot on Render...")
    print(f"🐍 Python version: {sys.version}")
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check environment
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("❌ BOT_TOKEN environment variable not set!")
        sys.exit(1)
    
    print("✅ BOT_TOKEN found")
    
    # Stop any existing bots
    stop_existing_bots()
    
    # Verify bot.py exists
    if not os.path.exists('bot.py'):
        print("❌ bot.py not found!")
        sys.exit(1)
    
    print("📂 Found bot.py")
    
    # Start the bot directly (no subprocess in Render)
    print("🎯 Starting bot process...")
    
    try:
        # Import and run the bot directly instead of subprocess
        # This works better in Render's container environment
        import bot
        print("✅ Bot module imported successfully")
        
        # Run the bot's main function
        bot.main()
        
    except KeyboardInterrupt:
        print("🛑 Received keyboard interrupt")
        cleanup()
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main() 