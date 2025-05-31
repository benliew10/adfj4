#!/usr/bin/env python3
"""
Render Webhook-based bot startup script
Uses webhooks instead of polling to avoid conflicts completely
"""

import os
import sys
import signal
import atexit
import requests
from flask import Flask, request
import threading
import time

app = Flask(__name__)

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

def setup_webhook():
    """Set up webhook for the bot."""
    try:
        bot_token = os.getenv('BOT_TOKEN')
        render_service_url = os.getenv('RENDER_EXTERNAL_URL')
        
        if not bot_token:
            print("❌ BOT_TOKEN not found")
            return False
            
        if not render_service_url:
            print("❌ RENDER_EXTERNAL_URL not found")
            return False
        
        # Set webhook URL
        webhook_endpoint = f"{render_service_url}/webhook"
        telegram_webhook_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
        
        print(f"🔗 Setting webhook to: {webhook_endpoint}")
        
        response = requests.post(
            telegram_webhook_url,
            data={'url': webhook_endpoint},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print("✅ Webhook set successfully")
                return True
            else:
                print(f"❌ Webhook setup failed: {result}")
                return False
        else:
            print(f"❌ HTTP error setting webhook: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up webhook: {e}")
        return False

# Global bot instance
bot_instance = None

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook requests from Telegram."""
    try:
        if bot_instance:
            update_data = request.get_json()
            if update_data:
                # Process the update using the bot's dispatcher
                from telegram import Update
                update = Update.de_json(update_data, bot_instance.bot)
                bot_instance.dispatcher.process_update(update)
        
        return "OK", 200
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        return "Error", 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return "Bot is running", 200

@app.route('/', methods=['GET'])
def home():
    """Home endpoint."""
    return "Telegram Bot is running on Render", 200

def start_bot():
    """Initialize and start the bot."""
    global bot_instance
    
    try:
        # Import bot modules
        import bot
        from telegram.ext import Updater
        
        print("✅ Bot module imported successfully")
        
        # Create bot instance but don't start polling
        bot_token = os.getenv('BOT_TOKEN')
        updater = Updater(bot_token, use_context=True)
        
        # Set up handlers (import from main bot file)
        bot.register_handlers(updater.dispatcher)
        
        # Store bot instance globally
        bot_instance = updater
        
        print("✅ Bot initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing bot: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main startup function for Render with webhook."""
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(cleanup)
    
    print("🚀 Starting Telegram Bot with Webhook on Render...")
    print(f"🐍 Python version: {sys.version}")
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check environment
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("❌ BOT_TOKEN environment variable not set!")
        sys.exit(1)
    
    print("✅ BOT_TOKEN found")
    
    # Get port from environment (Render sets this)
    port = int(os.getenv('PORT', 10000))
    print(f"🌐 Using port: {port}")
    
    # Initialize bot
    if not start_bot():
        print("❌ Failed to initialize bot")
        sys.exit(1)
    
    # Set up webhook (with retry)
    webhook_setup = False
    for attempt in range(3):
        print(f"🔗 Setting up webhook (attempt {attempt + 1}/3)...")
        if setup_webhook():
            webhook_setup = True
            break
        else:
            if attempt < 2:
                print("⏳ Waiting 5 seconds before retry...")
                time.sleep(5)
    
    if not webhook_setup:
        print("⚠️  Could not set up webhook, falling back to polling...")
        # Fallback to polling mode
        try:
            if bot_instance:
                bot_instance.start_polling()
                print("✅ Started in polling mode")
        except Exception as e:
            print(f"❌ Polling fallback failed: {e}")
            sys.exit(1)
    
    # Start Flask server
    try:
        print(f"🌐 Starting Flask server on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"❌ Error starting Flask server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 