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
import requests

def cleanup():
    """Cleanup function called on exit."""
    print("🧹 Performing cleanup...")
    
    # Clean up webhook if it was set
    try:
        bot_token = os.getenv('BOT_TOKEN')
        if bot_token:
            webhook_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
            requests.post(webhook_url, timeout=10)
            print("🔗 Webhook cleaned up")
    except Exception as e:
        print(f"⚠️  Could not clean webhook: {e}")

def signal_handler(signum, frame):
    """Handle termination signals gracefully."""
    print(f"📡 Received signal {signum}, shutting down gracefully...")
    cleanup()
    sys.exit(0)

def clear_telegram_webhook():
    """Clear any existing Telegram webhook to avoid conflicts."""
    try:
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token:
            return False
            
        print("🔗 Clearing any existing Telegram webhook...")
        
        # Delete webhook
        webhook_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
        response = requests.post(webhook_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Telegram webhook cleared successfully")
            return True
        else:
            print(f"⚠️  Webhook deletion response: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error clearing webhook: {e}")
        return False

def wait_for_conflict_resolution(max_wait=30):
    """Wait for any existing bot conflicts to resolve."""
    print(f"⏳ Waiting up to {max_wait} seconds for any conflicts to resolve...")
    
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        return False
    
    for i in range(max_wait):
        try:
            # Test if we can get updates without conflict
            test_url = f"https://api.telegram.org/bot{bot_token}/getMe"
            response = requests.get(test_url, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ Bot API accessible after {i} seconds")
                return True
                
        except Exception as e:
            pass
            
        if i < max_wait - 1:  # Don't sleep on last iteration
            time.sleep(1)
    
    print(f"⚠️  Still potential conflicts after {max_wait} seconds")
    return False

def find_bot_processes():
    """Find running bot processes (Render-compatible)."""
    try:
        # In Render, we might not be able to see other container processes
        # So this is mainly for same-container process detection
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        bot_pids = []
        
        for line in result.stdout.split('\n'):
            if 'python' in line.lower() and 'bot.py' in line and 'grep' not in line:
                # Exclude our own render_start.py process
                if 'render_start.py' not in line:
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
        print("✅ No existing bot processes found in current container")

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
    
    # Stop any existing bots in current container
    stop_existing_bots()
    
    # Clear Telegram webhook to prevent conflicts with other instances
    clear_telegram_webhook()
    
    # Wait for any conflicts to resolve
    wait_for_conflict_resolution(15)
    
    # Verify bot.py exists
    if not os.path.exists('bot.py'):
        print("❌ bot.py not found!")
        sys.exit(1)
    
    print("📂 Found bot.py")
    
    # Start the bot with retry mechanism
    print("🎯 Starting bot process...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempt {attempt + 1}/{max_retries}")
            
            # Import and run the bot directly instead of subprocess
            # This works better in Render's container environment
            import bot
            print("✅ Bot module imported successfully")
            
            # Run the bot's main function
            bot.main()
            
            # If we reach here, the bot started successfully
            break
            
        except Exception as e:
            if "Conflict" in str(e) and attempt < max_retries - 1:
                print(f"⚠️  Conflict detected on attempt {attempt + 1}, retrying...")
                
                # Clear webhook again and wait longer
                clear_telegram_webhook()
                wait_time = (attempt + 1) * 10  # Exponential backoff
                print(f"⏳ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                
                # Reimport the bot module to reset its state
                if 'bot' in sys.modules:
                    del sys.modules['bot']
                
                continue
            else:
                print(f"❌ Error starting bot: {e}")
                import traceback
                traceback.print_exc()
                
                if attempt == max_retries - 1:
                    print("💥 All retry attempts failed")
                    sys.exit(1)
        
        except KeyboardInterrupt:
            print("🛑 Received keyboard interrupt")
            cleanup()
            break

if __name__ == '__main__':
    main() 