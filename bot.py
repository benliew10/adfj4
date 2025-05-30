import logging
import os
import re
import json
import time
import random
import threading
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta

from telegram import Update, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from telegram.error import NetworkError, TimedOut, RetryAfter

import db

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
TOKEN = os.getenv("BOT_TOKEN", "8087490170:AAGkIL_s_NywMN0z6uyx7Jty6r66Ej9SfS0")

# Group IDs
# Moving from single group to multiple groups
GROUP_A_IDS = set()  # Set of Group A chat IDs
GROUP_B_IDS = set()  # Set of Group B chat IDs

# Legacy variables for backward compatibility
GROUP_A_ID = -4687450746  # Using negative ID for group chats
GROUP_B_ID = -1002648811668  # New supergroup ID from migration message

# Initialize default groups if needed
if not GROUP_A_IDS:
    GROUP_A_IDS.add(GROUP_A_ID)
if not GROUP_B_IDS:
    GROUP_B_IDS.add(GROUP_B_ID)

# Admin system
GLOBAL_ADMINS = set([5962096701, 1844353808, 7997704196, 5965182828])  # Global admins with full permissions
GROUP_ADMINS = {}  # Format: {chat_id: set(user_ids)} - Group-specific admins

# Message forwarding control
FORWARDING_ENABLED = False  # Controls if messages can be forwarded from Group B to Group A

# Paths for persistent storage
FORWARDED_MSGS_FILE = "forwarded_msgs.json"
GROUP_B_RESPONSES_FILE = "group_b_responses.json"
GROUP_A_IDS_FILE = "group_a_ids.json"
GROUP_B_IDS_FILE = "group_b_ids.json"
GROUP_ADMINS_FILE = "group_admins.json"
PENDING_CUSTOM_AMOUNTS_FILE = "pending_custom_amounts.json"
SETTINGS_FILE = "bot_settings.json"
GROUP_B_PERCENTAGES_FILE = "group_b_percentages.json"
GROUP_B_CLICK_MODE_FILE = "group_b_click_mode.json"

# Message IDs mapping for forwarded messages
forwarded_msgs: Dict[str, Dict] = {}

# Store Group B responses for each image
group_b_responses: Dict[str, str] = {}

# Store pending requests that need approval
pending_requests: Dict[int, Dict] = {}

# Store pending custom amount approvals from Group B
pending_custom_amounts: Dict[int, Dict] = {}  # Format: {message_id: {img_id, amount, responder, original_msg_id}}

# Store Group B percentage settings for image distribution
group_b_percentages: Dict[int, int] = {}  # Format: {group_b_id: percentage}

# Store Group B click mode settings - True means single-click mode, False means default mode
group_b_click_mode: Dict[int, bool] = {}  # Format: {group_b_id: is_click_mode}

# Store scheduled message deletions
scheduled_deletions: Dict[str, Any] = {}  # Format: {deletion_id: job_info}

# Function to safely send messages with retry logic
def safe_send_message(context, chat_id, text, reply_to_message_id=None, max_retries=3, retry_delay=2):
    """Send a message with retry logic to handle network errors."""
    for attempt in range(max_retries):
        try:
            return context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=reply_to_message_id
            )
        except (NetworkError, TimedOut, RetryAfter) as e:
            logger.warning(f"Network error on attempt {attempt+1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                # Increase delay for next retry
                retry_delay *= 1.5
            else:
                logger.error(f"Failed to send message after {max_retries} attempts")
                raise

# Function to safely reply to a message with retry logic
def safe_reply_text(update, text, max_retries=3, retry_delay=2):
    """Reply to a message with retry logic to handle network errors."""
    for attempt in range(max_retries):
        try:
            return update.message.reply_text(text)
        except (NetworkError, TimedOut, RetryAfter) as e:
            logger.warning(f"Network error on attempt {attempt+1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                # Increase delay for next retry
                retry_delay *= 1.5
            else:
                logger.error(f"Failed to reply to message after {max_retries} attempts")
                # Just log the error but don't crash the handler
                return None

# Function to save all configuration data
def save_config_data():
    """Save all configuration data to files."""
    # Save Group A IDs
    try:
        with open(GROUP_A_IDS_FILE, 'w') as f:
            json.dump(list(GROUP_A_IDS), f, indent=2)
            logger.info(f"Saved {len(GROUP_A_IDS)} Group A IDs to file")
    except Exception as e:
        logger.error(f"Error saving Group A IDs: {e}")
    
    # Save Group B IDs
    try:
        with open(GROUP_B_IDS_FILE, 'w') as f:
            json.dump(list(GROUP_B_IDS), f, indent=2)
            logger.info(f"Saved {len(GROUP_B_IDS)} Group B IDs to file")
    except Exception as e:
        logger.error(f"Error saving Group B IDs: {e}")
    
    # Save Group Admins
    try:
        # Convert sets to lists for JSON serialization
        admins_json = {str(chat_id): list(user_ids) for chat_id, user_ids in GROUP_ADMINS.items()}
        with open(GROUP_ADMINS_FILE, 'w') as f:
            json.dump(admins_json, f, indent=2)
            logger.info(f"Saved group admins to file")
    except Exception as e:
        logger.error(f"Error saving group admins: {e}")
    
    # Save Bot Settings
    try:
        settings = {
            "forwarding_enabled": FORWARDING_ENABLED
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
            logger.info(f"Saved bot settings to file")
    except Exception as e:
        logger.error(f"Error saving bot settings: {e}")
    
    # Save Group B Percentages
    try:
        with open(GROUP_B_PERCENTAGES_FILE, 'w') as f:
            json.dump(group_b_percentages, f, indent=2)
            logger.info(f"Saved Group B percentages to file")
    except Exception as e:
        logger.error(f"Error saving Group B percentages: {e}")
    
    # Save Group B Click Mode Settings
    try:
        with open(GROUP_B_CLICK_MODE_FILE, 'w') as f:
            json.dump(group_b_click_mode, f, indent=2)
            logger.info(f"Saved Group B click mode settings to file")
    except Exception as e:
        logger.error(f"Error saving Group B click mode settings: {e}")

# Function to load all configuration data
def load_config_data():
    """Load all configuration data from files."""
    global GROUP_A_IDS, GROUP_B_IDS, GROUP_ADMINS, FORWARDING_ENABLED, group_b_percentages, group_b_click_mode
    
    # Load Group A IDs
    if os.path.exists(GROUP_A_IDS_FILE):
        try:
            with open(GROUP_A_IDS_FILE, 'r') as f:
                # Convert all IDs to integers
                GROUP_A_IDS = set(int(x) for x in json.load(f))
                logger.info(f"Loaded {len(GROUP_A_IDS)} Group A IDs from file")
        except Exception as e:
            logger.error(f"Error loading Group A IDs: {e}")
    
    # Load Group B IDs
    if os.path.exists(GROUP_B_IDS_FILE):
        try:
            with open(GROUP_B_IDS_FILE, 'r') as f:
                # Convert all IDs to integers
                GROUP_B_IDS = set(int(x) for x in json.load(f))
                logger.info(f"Loaded {len(GROUP_B_IDS)} Group B IDs from file")
        except Exception as e:
            logger.error(f"Error loading Group B IDs: {e}")
    
    # Load Group Admins
    if os.path.exists(GROUP_ADMINS_FILE):
        try:
            with open(GROUP_ADMINS_FILE, 'r') as f:
                admins_json = json.load(f)
                # Convert keys back to integers and values back to sets
                GROUP_ADMINS = {int(chat_id): set(user_ids) for chat_id, user_ids in admins_json.items()}
                logger.info(f"Loaded group admins from file")
        except Exception as e:
            logger.error(f"Error loading group admins: {e}")
    
    # Load Bot Settings
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                FORWARDING_ENABLED = settings.get("forwarding_enabled", False)
                logger.info(f"Loaded bot settings: forwarding_enabled={FORWARDING_ENABLED}")
        except Exception as e:
            logger.error(f"Error loading bot settings: {e}")
    
    # Load Group B Percentages
    if os.path.exists(GROUP_B_PERCENTAGES_FILE):
        try:
            with open(GROUP_B_PERCENTAGES_FILE, 'r') as f:
                percentages_json = json.load(f)
                # Convert keys back to integers
                group_b_percentages = {int(group_id): percentage for group_id, percentage in percentages_json.items()}
                logger.info(f"Loaded Group B percentages from file: {group_b_percentages}")
        except Exception as e:
            logger.error(f"Error loading Group B percentages: {e}")
            group_b_percentages = {}
    
    # Load Group B Click Mode Settings
    if os.path.exists(GROUP_B_CLICK_MODE_FILE):
        try:
            with open(GROUP_B_CLICK_MODE_FILE, 'r') as f:
                click_mode_json = json.load(f)
                # Convert keys back to integers
                group_b_click_mode = {int(group_id): is_click_mode for group_id, is_click_mode in click_mode_json.items()}
                logger.info(f"Loaded Group B click mode settings from file: {group_b_click_mode}")
        except Exception as e:
            logger.error(f"Error loading Group B click mode settings: {e}")
            group_b_click_mode = {}

# Check if user is a global admin
def is_global_admin(user_id):
    """Check if user is a global admin."""
    return user_id in GLOBAL_ADMINS

# Check if user is a group admin for a specific chat
def is_group_admin(user_id, chat_id):
    """Check if user is a group admin for a specific chat."""
    # Global admins are also group admins
    if is_global_admin(user_id):
        return True
    
    # Check if user is in the group admin list for this chat
    return chat_id in GROUP_ADMINS and user_id in GROUP_ADMINS.get(chat_id, set())

# Add group admin
def add_group_admin(user_id, chat_id):
    """Add a user as a group admin for a specific chat."""
    if chat_id not in GROUP_ADMINS:
        GROUP_ADMINS[chat_id] = set()
    
    GROUP_ADMINS[chat_id].add(user_id)
    save_config_data()
    logger.info(f"Added user {user_id} as group admin for chat {chat_id}")

# Load persistent data on startup
def load_persistent_data():
    global forwarded_msgs, group_b_responses, pending_custom_amounts
    
    # Load forwarded_msgs
    if os.path.exists(FORWARDED_MSGS_FILE):
        try:
            with open(FORWARDED_MSGS_FILE, 'r') as f:
                forwarded_msgs = json.load(f)
                logger.info(f"Loaded {len(forwarded_msgs)} forwarded messages from file")
        except Exception as e:
            logger.error(f"Error loading forwarded messages: {e}")
    
    # Load group_b_responses
    if os.path.exists(GROUP_B_RESPONSES_FILE):
        try:
            with open(GROUP_B_RESPONSES_FILE, 'r') as f:
                group_b_responses = json.load(f)
                logger.info(f"Loaded {len(group_b_responses)} Group B responses from file")
        except Exception as e:
            logger.error(f"Error loading Group B responses: {e}")
    
    # Load pending_custom_amounts
    if os.path.exists(PENDING_CUSTOM_AMOUNTS_FILE):
        try:
            with open(PENDING_CUSTOM_AMOUNTS_FILE, 'r') as f:
                # Convert string keys back to integers
                data = json.load(f)
                pending_custom_amounts = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded {len(pending_custom_amounts)} pending custom amounts from file")
        except Exception as e:
            logger.error(f"Error loading pending custom amounts: {e}")
    
    # Load configuration data
    load_config_data()

# Save persistent data
def save_persistent_data():
    # Save forwarded_msgs
    try:
        with open(FORWARDED_MSGS_FILE, 'w') as f:
            json.dump(forwarded_msgs, f, indent=2)
            logger.info(f"Saved {len(forwarded_msgs)} forwarded messages to file")
    except Exception as e:
        logger.error(f"Error saving forwarded messages: {e}")
    
    # Save group_b_responses
    try:
        with open(GROUP_B_RESPONSES_FILE, 'w') as f:
            json.dump(group_b_responses, f, indent=2)
            logger.info(f"Saved {len(group_b_responses)} Group B responses to file")
    except Exception as e:
        logger.error(f"Error saving Group B responses: {e}")
    
    # Save pending_custom_amounts
    try:
        with open(PENDING_CUSTOM_AMOUNTS_FILE, 'w') as f:
            json.dump(pending_custom_amounts, f, indent=2)
            logger.info(f"Saved {len(pending_custom_amounts)} pending custom amounts to file")
    except Exception as e:
        logger.error(f"Error saving pending custom amounts: {e}")

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    is_admin = is_global_admin(user_id)
    
    welcome_message = "欢迎使用TLG群组管理机器人！"
    
    # Show admin controls if user is admin and in private chat
    if is_admin and update.effective_chat.type == "private":
        admin_controls = (
            "\n\n管理员控制:\n"
            "• 开启转发 - 开启群B到群A的消息转发\n"
            "• 关闭转发 - 关闭群B到群A的消息转发\n"
            "• 转发状态 - 切换转发状态\n"
            "• /debug - 显示当前状态信息"
        )
        welcome_message += admin_controls
    
    update.message.reply_text(welcome_message)

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    user_id = update.message.from_user.id
    
    help_text = """
🤖 *Telegram Image Management Bot*

*Basic Commands:*
/start - Start the bot
/help - Show this help message
/images - List all images and their statuses

*Admin Commands:*
/setimage <number> - Set an image with a number (reply to an image)

*How it works:*
1. Send a number in Group A to get a random open image
2. The bot forwards the image to Group B
3. Users in Group B can reopen images with the + button
"""

    if is_global_admin(user_id):
        help_text += """
*Global Admin Commands:*
/setgroupbpercent <group_b_id> <percentage> - Set percentage chance (0-100) for a Group B
/resetgroupbpercent - Reset all Group B percentages to normal
/listgroupbpercent - List all Group B percentage settings
/debug - Debug information
/dreset - Reset all image statuses
"""

    update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

def set_image(update: Update, context: CallbackContext) -> None:
    """Set an image with a number."""
    # Check if admin (can be customized)
    if update.effective_chat.type != "private":
        return
    
    # Check if replying to an image
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        update.message.reply_text("Please reply to an image with this command.")
        return
    
    # Check if number provided
    if not context.args:
        update.message.reply_text("Please provide a number for this image.")
        return
    
    try:
        number = int(context.args[0])
    except ValueError:
        update.message.reply_text("Please provide a valid number.")
        return
    
    # Get the file_id of the image
    file_id = update.message.reply_to_message.photo[-1].file_id
    image_id = f"img_{len(db.get_all_images()) + 1}"
    
    if db.add_image(image_id, number, file_id):
        update.message.reply_text(f"Image set with number {number} and status 'open'.")
    else:
        update.message.reply_text("Failed to set image. It might already exist.")

def list_images(update: Update, context: CallbackContext) -> None:
    """List all available images with their statuses and associated Group B."""
    user_id = update.effective_user.id
    
    # Only allow admins
    if not is_global_admin(user_id):
        update.message.reply_text("Only global admins can use this command.")
        return
    
    images = db.get_all_images()
    if not images:
        update.message.reply_text("No images available.")
        return
    
    # Format the list of images
    image_list = []
    for img in images:
        status = img['status']
        number = img['number']
        image_id = img['image_id']
        
        # Get Group B ID from metadata if available
        group_b_id = "none"
        if 'metadata' in img and isinstance(img['metadata'], dict):
            group_b_id = img['metadata'].get('source_group_b_id', "none")
        
        image_list.append(f"🔢 Group: {number} | 🆔 ID: {image_id} | ⚡ Status: {status} | 🔸 Group B: {group_b_id}")
    
    # Join the list with newlines
    message = "📋 Available Images:\n\n" + "\n\n".join(image_list)
    
    # Add instructions for updating Group B association
    message += "\n\n🔄 To update Group B association:\n/setimagegroup <image_id> <group_b_id>"
    
    update.message.reply_text(message)

# Define a helper function for consistent Group B mapping
def get_group_b_for_image(image_id, metadata=None):
    """Get the consistent Group B ID for an image."""
    # If metadata has a source_group_b_id and it's valid, use it
    if isinstance(metadata, dict) and 'source_group_b_id' in metadata:
        try:
            # Convert to int to ensure consistent comparison
            source_group_b_id = int(metadata['source_group_b_id'])
            
            # Check if source_group_b_id is valid - all Group B IDs are already integers
            if source_group_b_id in GROUP_B_IDS or source_group_b_id == GROUP_B_ID:
                logger.info(f"Using existing Group B mapping for image {image_id}: {source_group_b_id}")
                return source_group_b_id
            else:
                logger.warning(f"Source Group B ID {source_group_b_id} is not in valid Group B IDs: {GROUP_B_IDS}")
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting source_group_b_id to int: {e}. Metadata: {metadata}")
    
    # Create a deterministic mapping
    # Use a hash of the image ID to ensure the same image always goes to the same Group B
    image_hash = hash(image_id)
    
    # Get available Group B IDs
    available_group_bs = list(GROUP_B_IDS) if GROUP_B_IDS else [GROUP_B_ID]
    
    # Deterministically select a Group B based on image hash
    if available_group_bs:
        selected_index = abs(image_hash) % len(available_group_bs)
        target_group_b_id = available_group_bs[selected_index]  # Already an integer
        
        logger.info(f"Created deterministic mapping for image {image_id} to Group B {target_group_b_id}")
        
        # Save this mapping for future use
        updated_metadata = metadata.copy() if isinstance(metadata, dict) else {}
        updated_metadata['source_group_b_id'] = target_group_b_id
        db.update_image_metadata(image_id, json.dumps(updated_metadata))
        logger.info(f"Saved Group B mapping to image metadata: {updated_metadata}")
        
        return target_group_b_id
    else:
        logger.error("No available Group B IDs!")
        # Default to GROUP_B_ID if no other options
        return GROUP_B_ID

def handle_group_a_message(update: Update, context: CallbackContext) -> None:
    """Handle messages in Group A."""
    # Add debug logging
    chat_id = update.effective_chat.id
    logger.info(f"Received message in chat ID: {chat_id}")
    logger.info(f"GROUP_A_IDS: {GROUP_A_IDS}, GROUP_B_IDS: {GROUP_B_IDS}")
    logger.info(f"Is chat in Group A: {int(chat_id) in GROUP_A_IDS or int(chat_id) == GROUP_A_ID}")
    logger.info(f"Is chat in Group B: {int(chat_id) in GROUP_B_IDS or int(chat_id) == GROUP_B_ID}")
    
    # Check if this chat is a Group A - ensure we're comparing integers
    if int(chat_id) not in GROUP_A_IDS and int(chat_id) != GROUP_A_ID:
        logger.info(f"Message received in non-Group A chat: {chat_id}")
        return
    
    # Get message text
    text = update.message.text.strip()
    logger.info(f"Received message: {text}")
    
    # Skip messages that start with "+"
    if text.startswith("+"):
        logger.info("Message starts with '+', skipping")
        return
    
    # Match any of the formats:
    # - Just a number
    # - number+群 or number 群
    # - 群+number or 群 number
    # - 微信+number or 微信 number 
    # - number+微信 or number 微信
    # - 微信群+number or 微信群 number
    # - number+微信群 or number 微信群
    patterns = [
        r'^(\d+)$',  # Just a number
        r'^(\d+)\s*群$',  # number+群
        r'^群\s*(\d+)$',  # 群+number
        r'^微信\s*(\d+)$',  # 微信+number
        r'^(\d+)\s*微信$',  # number+微信
        r'^微信群\s*(\d+)$',  # 微信群+number
        r'^(\d+)\s*微信群$',  # number+微信群
        r'^微信\s*群\s*(\d+)$',  # 微信 群 number (with spaces)
        r'^(\d+)\s*微信\s*群$'   # number 微信 群 (with spaces)
    ]
    
    amount = None
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            amount = match.group(1)
            logger.info(f"Matched pattern '{pattern}' with amount: {amount}")
            break
    
    if not amount:
        logger.info("Message doesn't match any accepted format")
        return
    
    # Check if the number is between 20 and 5000 (inclusive)
    try:
        amount_int = int(amount)
        if amount_int < 20 or amount_int > 5000:
            logger.info(f"Number {amount} is outside the allowed range (20-5000).")
            return
    except ValueError:
        logger.info(f"Invalid number format: {amount}")
        return
    
    # Rest of the function remains unchanged
    # Check if we have any images
    images = db.get_all_images()
    if not images:
        logger.info("No images found in database - remaining silent")
        return
        
    # For now, just log that this is a Group A message
    logger.info("Group A message handling completed")

def handle_approval(update: Update, context: CallbackContext) -> None:
    """Handle approval messages (reply with '1')."""
    # Check if the message is "1"
    if update.message.text != "1":
        return
    
    # Check if replying to a message
    if not update.message.reply_to_message:
        return
    
    # Check if replying to a bot message
    if update.message.reply_to_message.from_user.id != context.bot.id:
        return
    
    logger.info("Approval message detected")
    
    # Get the pending request
    request_msg_id = update.message.reply_to_message.message_id
    
    if request_msg_id in pending_requests:
        # Get request info
        request = pending_requests[request_msg_id]
        amount = request['amount']
        
        logger.info(f"Found pending request: {request}")
        
        # Get a random open image
        image = db.get_random_open_image()
        if not image:
            update.message.reply_text("No open images available.")
            return
        
        logger.info(f"Selected image: {image['image_id']}")
        
        # Send the image
        try:
            # Get the image and its metadata
            image = db.get_image_by_id(image['image_id'])
            metadata = image.get('metadata', {}) if image else {}
            
            # Get the proper Group B ID for this image
            target_group_b_id = get_group_b_for_image(image['image_id'], metadata)
            
            # First send the image to Group A
            sent_msg = update.message.reply_photo(
                photo=image['file_id'],
                caption=f"🌟 群: {image['number']} 🌟"
            )
            logger.info(f"Image sent to Group A with message_id: {sent_msg.message_id}")
            
            # Then forward to Group B
            # Check click mode for this Group B
            click_mode = is_click_mode_enabled(target_group_b_id)
            
            # Create buttons based on click mode
            if click_mode:
                # Single button mode
                keyboard = [
                    [InlineKeyboardButton("解除", callback_data=f"release_{image['image_id']}")]
                ]
            else:
                # Default mode with multiple buttons
                keyboard = [
                    [
                        InlineKeyboardButton(f"+{amount}", callback_data=f"verify_{image['image_id']}_{amount}"),
                        InlineKeyboardButton("+0", callback_data=f"verify_{image['image_id']}_0")
                    ]
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            forwarded = context.bot.send_message(
                chat_id=target_group_b_id,
                text=f"💰 金额：{amount}\n🔢 群：{image['number']}\n\n❌ 如果会员10分钟没进群请回复0",
                reply_markup=reply_markup
            )
            logger.info(f"Message forwarded to Group B with message_id: {forwarded.message_id}")
            
            # Store mapping between original and forwarded message
            forwarded_msgs[image['image_id']] = {
                'group_a_msg_id': sent_msg.message_id,
                'group_a_chat_id': update.effective_chat.id,
                'group_b_msg_id': forwarded.message_id,
                'group_b_chat_id': target_group_b_id,
                'image_id': image['image_id'],
                'amount': amount,  # Store the original amount
                'number': str(image['number']),  # Store the image number as string
                'original_user_id': request['user_id'],  # Store original user for more robust tracking
                'original_message_id': request['original_message_id']  # Store the original message ID to reply to
            }
            
            logger.info(f"Stored message mapping: {forwarded_msgs[image['image_id']]}")
            
            # Save persistent data
            save_persistent_data()
            
            # Set image status to closed
            db.set_image_status(image['image_id'], "closed")
            logger.info(f"Image {image['image_id']} status set to closed")
            
            # Remove the pending request
            del pending_requests[request_msg_id]
        except Exception as e:
            logger.error(f"Error forwarding to Group B: {e}")
            update.message.reply_text(f"发送至Group B失败: {e}")
    else:
        logger.info(f"No pending request found for message ID: {request_msg_id}")

def handle_set_group_a(update: Update, context: CallbackContext) -> None:
    """Handle setting a group as Group A."""
    global dispatcher
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if user is a global admin
    if not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to set group as Group A but is not a global admin")
        update.message.reply_text("只有全局管理员可以设置群聊类型。")
        return
    
    # Add this chat to Group A - ensure we're storing as integer
    GROUP_A_IDS.add(int(chat_id))
    save_config_data()
    
    # Reload handlers to pick up the new group
    if dispatcher:
        register_handlers(dispatcher)
    
    logger.info(f"Group {chat_id} set as Group A by user {user_id}")
    # Notification removed

def handle_set_group_b(update: Update, context: CallbackContext) -> None:
    """Handle setting a group as Group B."""
    global dispatcher
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if user is a global admin
    if not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to set group as Group B but is not a global admin")
        update.message.reply_text("只有全局管理员可以设置群聊类型。")
        return
    
    # Add this chat to Group B - ensure we're storing as integer
    GROUP_B_IDS.add(int(chat_id))
    save_config_data()
    
    # Reload handlers to pick up the new group
    if dispatcher:
        register_handlers(dispatcher)
    
    logger.info(f"Group {chat_id} set as Group B by user {user_id}")
    # Notification removed

def handle_promote_group_admin(update: Update, context: CallbackContext) -> None:
    """Handle promoting a user to group admin."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if user is a global admin
    if not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to promote a group admin but is not a global admin")
        return
    
    # Check if replying to a user
    if not update.message.reply_to_message:
        update.message.reply_text("请回复要设置为操作人的用户消息。")
        return
    
    # Get the user to promote
    target_user_id = update.message.reply_to_message.from_user.id
    target_user_name = update.message.reply_to_message.from_user.first_name
    
    # Add the user as a group admin
    add_group_admin(target_user_id, chat_id)
    
    update.message.reply_text(f"👑 已将用户 {target_user_name} 设置为群操作人。")
    logger.info(f"User {target_user_id} promoted to group admin in chat {chat_id} by user {user_id}")

def handle_set_group_image(update: Update, context: CallbackContext) -> None:
    """Handle setting an image for a specific group number."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    logger.info(f"Image setting attempt in chat {chat_id} by user {user_id}")
    
    # Debug registered Group B chats
    logger.info(f"Current Group B chats: {GROUP_B_IDS}")
    
    # Check if this is a Group B chat
    if chat_id not in GROUP_B_IDS:
        logger.warning(f"User tried to set image in non-Group B chat: {chat_id}")
        update.message.reply_text("此群聊未设置为需方群 (Group B)，请联系全局管理员设置。")
        return
    
    # Debug admin status
    is_admin = is_group_admin(user_id, chat_id)
    is_global = is_global_admin(user_id)
    logger.info(f"User {user_id} is group admin: {is_admin}, is global admin: {is_global}")
    
    # Debug group admins for this chat
    if chat_id in GROUP_ADMINS:
        logger.info(f"Group admins for chat {chat_id}: {GROUP_ADMINS[chat_id]}")
    else:
        logger.info(f"No group admins registered for chat {chat_id}")
    
    # For testing, allow all users to set images temporarily
    allow_all_users = False  # Set to True for debugging
    
    # Check if user is a group admin or global admin
    if not allow_all_users and not is_group_admin(user_id, chat_id) and not is_global_admin(user_id):
        logger.warning(f"User {user_id} tried to set image but is not an admin")
        update.message.reply_text("只有群操作人可以设置图片。请联系管理员。")
        return
    
    # Check if message has a photo
    if not update.message.photo:
        logger.warning(f"No photo in message")
        update.message.reply_text("请发送一张图片并备注'设置群 {number}'。")
        return
    
    # Debug caption
    caption = update.message.caption or ""
    logger.info(f"Caption: '{caption}'")
    
    # Extract group number from message text
    match = re.search(r'设置群\s*(\d+)', caption)
    if not match:
        logger.warning(f"Caption doesn't match pattern: '{caption}'")
        update.message.reply_text("请使用正确的格式：设置群 {number}")
        return
    
    group_number = match.group(1)
    logger.info(f"Setting image for group {group_number}")
    
    # Get the file_id of the image
    file_id = update.message.photo[-1].file_id
    image_id = f"img_{int(time.time())}"  # Use timestamp for unique ID
    
    # Store which Group B chat this image came from
    source_group_b_id = int(chat_id)  # Explicitly convert to int to ensure consistent type
    logger.info(f"Setting image source Group B ID: {source_group_b_id}")
    
    # Find a target Group A for this Group B
    target_group_a_id = None
    
    # First, check if we have a specific Group A that corresponds to this Group B
    # For simplicity, we'll use the first Group A in the list
    if GROUP_A_IDS:
        target_group_a_id = next(iter(GROUP_A_IDS))
    else:
        target_group_a_id = GROUP_A_ID
    
    logger.info(f"Setting image target Group A ID: {target_group_a_id}")
    
    # Debug image data
    logger.info(f"Image data - ID: {image_id}, file_id: {file_id}, group: {group_number}")
    logger.info(f"Source Group B: {source_group_b_id}, Target Group A: {target_group_a_id}")
    
    # Save the image with additional metadata
    try:
        # Store the metadata in a separate JSON field - make sure source_group_b_id is explicitly an int
        metadata_dict = {
            'source_group_b_id': source_group_b_id,
            'target_group_a_id': target_group_a_id
        }
        
        # Convert to JSON string
        metadata = json.dumps(metadata_dict)
        
        logger.info(f"Saving image with metadata: {metadata}")
        
        success = db.add_image(image_id, int(group_number), file_id, metadata=metadata)
        if success:
            # Double check that the image was set correctly
            saved_image = db.get_image_by_id(image_id)
            if saved_image and 'metadata' in saved_image:
                logger.info(f"Verified image metadata: {saved_image['metadata']}")
            
            logger.info(f"Successfully added image {image_id} for group {group_number}")
            update.message.reply_text(f"✅ 已设置群聊为{group_number}群")
        else:
            logger.error(f"Failed to add image {image_id} for group {group_number}")
            update.message.reply_text("设置图片失败，该图片可能已存在。请重试。")
    except Exception as e:
        logger.error(f"Exception when adding image: {e}")
        update.message.reply_text(f"设置图片时出错: {str(e)}")

def handle_custom_amount(update: Update, context: CallbackContext, img_id, msg_data, number) -> None:
    """Handle custom amount that needs approval."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.username or update.effective_user.first_name
    custom_message = update.message.text
    message_id = update.message.message_id
    reply_to_message_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None
    
    logger.info(f"Custom amount detected: {number}")
    
    # Store the custom amount approval with more detailed info
    pending_custom_amounts[message_id] = {
        'img_id': img_id,
        'amount': number,
        'responder': user_id,
        'responder_name': user_name,
        'original_msg_id': message_id,  # The ID of the message with the custom amount
        'reply_to_msg_id': reply_to_message_id,  # The ID of the message being replied to
        'message_text': custom_message,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save updated responses
    save_persistent_data()
    
    # Create mention tags for global admins
    admin_mentions = ""
    for admin_id in GLOBAL_ADMINS:
        try:
            # Get admin chat member info to get username or first name
            admin_user = context.bot.get_chat_member(chat_id, admin_id).user
            admin_name = admin_user.username or admin_user.first_name
            admin_mentions += f"@{admin_name} "
        except Exception as e:
            logger.error(f"Error getting admin info for ID {admin_id}: {e}")
    
    # Send notification in Group B about pending approval, including admin mentions
    notification_text = f"👤 用户 {user_name} 提交的自定义金额 +{number} 需要全局管理员确认 {admin_mentions}"
    update.message.reply_text(notification_text)
    
    # No longer sending confirmation to user
    
    # Notify all global admins about the pending approval
    for admin_id in GLOBAL_ADMINS:
        try:
            # Try to send private message to global admin
            original_amount = msg_data.get('amount')
            group_number = msg_data.get('number')
            
            notification_text = (
                f"🔔 需要审批:\n"
                f"👤 用户 {user_name} (ID: {user_id}) 在群 B 提交了自定义金额:\n"
                f"💰 原始金额: {original_amount}\n"
                f"💲 自定义金额: {number}\n"
                f"🔢 群号: {group_number}\n\n"
                f"✅ 审批方式:\n"
                f"1️⃣ 直接回复此消息并输入\"同意\"或\"确认\"\n"
                f"2️⃣ 或在群 B 找到用户发送的自定义金额消息（例如: +{number}）并回复\"同意\"或\"确认\""
            )
            
            # Attempt to send notification to admin
            context.bot.send_message(
                chat_id=admin_id,
                text=notification_text
            )
            logger.info(f"Sent approval notification to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

# Add this new function to handle global admin approvals
def handle_custom_amount_approval(update: Update, context: CallbackContext) -> None:
    """Handle global admin approval of custom amount."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if user is a global admin
    if not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to approve custom amount but is not a global admin")
        return
    
    # Check if this is a reply and contains "同意" or "确认"
    if not update.message.reply_to_message or not any(word in update.message.text for word in ["同意", "确认"]):
        return
    
    logger.info(f"Global admin {user_id} approval attempt detected")
    
    # If we're in a private chat, this is likely a reply to the notification
    # So we need to find the latest pending custom amount
    if update.effective_chat.type == "private":
        logger.info("Approval in private chat detected, finding most recent pending custom amount")
        
        if not pending_custom_amounts:
            logger.info("No pending custom amounts found")
            update.message.reply_text("没有待审批的自定义金额。")
            return
        
        # Find the most recent pending custom amount
        most_recent_msg_id = max(pending_custom_amounts.keys())
        approval_data = pending_custom_amounts[most_recent_msg_id]
        
        logger.info(f"Found most recent pending custom amount: {approval_data}")
        
        # Process the approval
        process_custom_amount_approval(update, context, most_recent_msg_id, approval_data)
        return
    
    # If we're in a group chat, check if this is a reply to a custom amount message
    reply_msg_id = update.message.reply_to_message.message_id
    logger.info(f"Checking if message {reply_msg_id} has a pending approval")
    
    # Debug all pending custom amounts to check what's stored
    logger.info(f"All pending custom amounts: {pending_custom_amounts}")
    
    # First, check if the message being replied to is directly in pending_custom_amounts
    if reply_msg_id in pending_custom_amounts:
        logger.info(f"Found direct match for message {reply_msg_id}")
        approval_data = pending_custom_amounts[reply_msg_id]
        process_custom_amount_approval(update, context, reply_msg_id, approval_data)
        return
    
    # If not, search through all pending approvals
    for msg_id, data in pending_custom_amounts.items():
        logger.info(f"Checking pending approval {msg_id} with data {data}")
        
        # Check if any of the stored message IDs match
        if (data.get('original_msg_id') == reply_msg_id or 
            str(data.get('original_msg_id')) == str(reply_msg_id) or
            data.get('reply_to_msg_id') == reply_msg_id or
            str(data.get('reply_to_msg_id')) == str(reply_msg_id)):
            
            logger.info(f"Found matching pending approval through message ID comparison: {msg_id}")
            process_custom_amount_approval(update, context, msg_id, data)
            return
    
    # If we still can't find it, try checking the message content
    reply_message_text = update.message.reply_to_message.text if update.message.reply_to_message.text else ""
    for msg_id, data in pending_custom_amounts.items():
        custom_amount = data.get('amount')
        if f"+{custom_amount}" in reply_message_text:
            logger.info(f"Found matching pending approval through message content: {msg_id}")
            process_custom_amount_approval(update, context, msg_id, data)
            return
    
    logger.info(f"No pending approval found for message ID: {reply_msg_id}")
    update.message.reply_text("⚠️ 没有找到此消息的待审批记录。请检查是否回复了正确的消息。")

def process_custom_amount_approval(update, context, msg_id, approval_data):
    """Process a custom amount approval."""
    global FORWARDING_ENABLED
    img_id = approval_data['img_id']
    custom_amount = approval_data['amount']
    approver_id = update.effective_user.id
    approver_name = update.effective_user.username or update.effective_user.first_name
    
    logger.info(f"Processing approval for image {img_id} with custom amount {custom_amount}")
    logger.info(f"Approval by {approver_name} (ID: {approver_id})")
    logger.info(f"Full approval data: {approval_data}")
    
    # Get the corresponding forwarded message data
    if img_id in forwarded_msgs:
        msg_data = forwarded_msgs[img_id]
        logger.info(f"Found forwarded message data: {msg_data}")
        
        # Process the custom amount like a regular response
        response_text = f"+{custom_amount}"
        
        # Save the response
        group_b_responses[img_id] = response_text
        logger.info(f"Stored custom amount response: {response_text}")
        
        # Save responses
        save_persistent_data()
        
        # Mark the image as open
        db.set_image_status(img_id, "open")
        logger.info(f"Set image {img_id} status to open after custom amount approval")
        
        # Send response to Group A only if forwarding is enabled
        if FORWARDING_ENABLED:
            if 'group_a_chat_id' in msg_data and 'group_a_msg_id' in msg_data:
                try:
                    # Get the original message ID if available
                    original_message_id = msg_data.get('original_message_id')
                    reply_to_message_id = original_message_id if original_message_id else msg_data['group_a_msg_id']
                    
                    logger.info(f"Sending response to Group A - chat_id: {msg_data['group_a_chat_id']}, reply_to: {reply_to_message_id}")
                    
                    # Send response back to Group A
                    sent_msg = safe_send_message(
                        context=context,
                        chat_id=msg_data['group_a_chat_id'],
                        text=response_text,
                        reply_to_message_id=reply_to_message_id
                    )
                    
                    if sent_msg:
                        logger.info(f"Successfully sent custom amount response to Group A: {response_text}")
                    else:
                        logger.warning("safe_send_message completed but did not return a message object")
                except Exception as e:
                    logger.error(f"Error sending custom amount response to Group A: {e}")
                    update.message.reply_text(f"金额已批准，但发送到需方群失败: {e}")
                    return
            else:
                logger.error(f"Missing group_a_chat_id or group_a_msg_id in msg_data: {msg_data}")
                update.message.reply_text("金额已批准，但找不到需方群的消息信息，无法发送回复。")
                return
        else:
            logger.info("Forwarding to Group A is currently disabled by admin - not sending custom amount")
            # Remove the notification message
            # update.message.reply_text("金额已批准，但转发到需方群功能当前已关闭。")
        
        # Send approval confirmation message to Group B
        if update.effective_chat.type == "private":
            # If approved in private chat, send notification to Group B
            if 'group_b_chat_id' in msg_data and msg_data['group_b_chat_id']:
                try:
                    context.bot.send_message(
                        chat_id=msg_data['group_b_chat_id'],
                        text=f"✅ 金额确认修改：+{custom_amount} (由管理员 {approver_name} 批准)",
                        reply_to_message_id=approval_data.get('reply_to_msg_id')
                    )
                    logger.info(f"Sent confirmation message in Group B about approved amount {custom_amount}")
                except Exception as e:
                    logger.error(f"Error sending confirmation to Group B: {e}")
        else:
            # If approved in group chat (Group B), send confirmation in the same chat
            update.message.reply_text(f"✅ 金额确认修改：+{custom_amount}")
            logger.info(f"Sent confirmation message in Group B about approved amount {custom_amount}")
        
        # Remove the admin confirmation message
        # No longer sending "自定义金额 X 已批准，并已发送到群A"
        
        # Delete the pending approval
        if msg_id in pending_custom_amounts:
            del pending_custom_amounts[msg_id]
            logger.info(f"Deleted pending approval with ID {msg_id}")
            save_persistent_data()
        else:
            logger.warning(f"Tried to delete non-existent pending approval with ID {msg_id}")
        
    else:
        logger.error(f"Image {img_id} not found in forwarded_msgs")
        update.message.reply_text("无法找到相关图片信息，批准失败。")

# Add this function to display global admins
def admin_list_command(update: Update, context: CallbackContext) -> None:
    """Display the list of global admins."""
    user_id = update.effective_user.id
    
    # Only allow global admins to see the list
    if not is_global_admin(user_id):
        update.message.reply_text("只有全局管理员可以使用此命令。")
        return
    
    # Format the list of global admins
    admin_list = []
    for admin_id in GLOBAL_ADMINS:
        try:
            # Try to get admin's username
            chat = context.bot.get_chat(admin_id)
            admin_name = chat.username or chat.first_name or "Unknown"
            admin_list.append(f"ID: {admin_id} - @{admin_name}")
        except Exception as e:
            # If can't get username, just show ID
            admin_list.append(f"ID: {admin_id}")
    
    # Send the formatted list
    message = "👑 全局管理员列表:\n" + "\n".join(admin_list)
    update.message.reply_text(message)

# Add this function to handle group image reset
def handle_group_b_reset_images(update: Update, context: CallbackContext) -> None:
    """Handle the command to reset all images in Group B."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # Check if this is Group B
    if chat_id not in GROUP_B_IDS and chat_id != GROUP_B_ID:
        logger.info(f"Reset images command used in non-Group B chat: {chat_id}")
        return
    
    # Check if the message is exactly "重置群码"
    if message_text != "重置群码":
        return
    
    # Check if user is a group admin or global admin
    if not is_group_admin(user_id, chat_id) and not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to reset images but is not an admin")
        update.message.reply_text("只有群操作人或全局管理员可以重置群码。")
        return
    
    logger.info(f"Admin {user_id} is resetting images in Group B: {chat_id}")
    
    # Get current image count for this specific Group B for reporting
    all_images = db.get_all_images()
    logger.info(f"Total images in database before reset: {len(all_images)}")
    
    # Count images associated with this Group B
    group_b_images = []
    if all_images:
        for img in all_images:
            metadata = img.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
                    
            if isinstance(metadata, dict) and 'source_group_b_id' in metadata:
                try:
                    if int(metadata['source_group_b_id']) == int(chat_id):
                        group_b_images.append(img)
                except (ValueError, TypeError) as e:
                    logger.error(f"Error comparing Group B IDs: {e}")
    
    image_count = len(group_b_images)
    logger.info(f"Found {image_count} images associated with Group B {chat_id}")
    
    # Backup the existing images before deleting
    # Backup functionality removed
    
    # Delete only images from this Group B
    try:
        # Use our new function to delete only images from this Group B
        success = db.clear_images_by_group_b(chat_id)
        
        # Also clear related message mappings for this Group B
        global forwarded_msgs, group_b_responses
        
        # Filter out messages related to this Group B
        if forwarded_msgs:
            # Create a new dict to avoid changing size during iteration
            new_forwarded_msgs = {}
            for msg_id, data in forwarded_msgs.items():
                # If the message was sent to this Group B, remove it
                if 'group_b_chat_id' in data and int(data['group_b_chat_id']) != int(chat_id):
                    new_forwarded_msgs[msg_id] = data
                else:
                    logger.info(f"Removing forwarded message mapping for {msg_id}")
            
            forwarded_msgs = new_forwarded_msgs
        
        # Same for group_b_responses
        if group_b_responses:
            new_group_b_responses = {}
            for msg_id, data in group_b_responses.items():
                if 'chat_id' in data and int(data['chat_id']) != int(chat_id):
                    new_group_b_responses[msg_id] = data
            group_b_responses = new_group_b_responses
        
        save_persistent_data()
        
        # Check if all images for this Group B were actually deleted
        remaining_images = db.get_all_images()
        remaining_for_group_b = []
        
        for img in remaining_images:
            metadata = img.get('metadata', {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
                    
            if isinstance(metadata, dict) and 'source_group_b_id' in metadata:
                try:
                    if int(metadata['source_group_b_id']) == int(chat_id):
                        remaining_for_group_b.append(img)
                except (ValueError, TypeError) as e:
                    logger.error(f"Error comparing Group B IDs: {e}")
        
        if success:
            if not remaining_for_group_b:
                logger.info(f"Successfully cleared {image_count} images for Group B: {chat_id}")
                update.message.reply_text(f"🔄 已重置所有群码! 共清除了 {image_count} 个图片。")
            else:
                # Some images still exist for this Group B
                logger.warning(f"Reset didn't clear all images. {len(remaining_for_group_b)} images still remain for Group B {chat_id}")
                update.message.reply_text(f"⚠️ 群码重置部分完成。已清除 {image_count - len(remaining_for_group_b)} 个图片，但还有 {len(remaining_for_group_b)} 个图片未能清除。")
        else:
            logger.error(f"Failed to clear images for Group B: {chat_id}")
            update.message.reply_text("重置群码时出错，请查看日志。")
    except Exception as e:
        logger.error(f"Error clearing images: {e}")
        update.message.reply_text(f"重置群码时出错: {e}")

def set_image_group_b(update: Update, context: CallbackContext) -> None:
    """Set which Group B an image should be associated with."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Only allow global admins
    if not is_global_admin(user_id):
        update.message.reply_text("Only global admins can use this command.")
        return
    
    # Check if we have enough arguments: /setimagegroup <image_id> <group_b_id>
    if not context.args or len(context.args) < 2:
        update.message.reply_text("Usage: /setimagegroup <image_id> <group_b_id>")
        return
    
    image_id = context.args[0]
    group_b_id = int(context.args[1])
    
    # Get the image
    image = db.get_image_by_id(image_id)
    if not image:
        update.message.reply_text(f"Image with ID {image_id} not found.")
        return
    
    # Create metadata
    metadata = {
        'source_group_b_id': group_b_id,
        'target_group_a_id': GROUP_A_ID  # Default to main Group A
    }
    
    # If image already has metadata, update it
    if 'metadata' in image and isinstance(image['metadata'], dict):
        image['metadata'].update(metadata)
        metadata = image['metadata']
    
    # Update the image in database
    success = db.update_image_metadata(image_id, json.dumps(metadata))
    
    if success:
        update.message.reply_text(f"✅ Image {image_id} updated to use Group B: {group_b_id}")
    else:
        update.message.reply_text(f"❌ Failed to update image {image_id}")

# Add a debug_metadata command
def debug_metadata(update: Update, context: CallbackContext) -> None:
    """Debug command to check image metadata."""
    user_id = update.effective_user.id
    
    # Only allow global admins
    if not is_global_admin(user_id):
        update.message.reply_text("Only global admins can use this command.")
        return
    
    # Get all images
    images = db.get_all_images()
    if not images:
        update.message.reply_text("No images available.")
        return
    
    # Format the metadata for each image
    message_parts = ["📋 Image Metadata Debug:"]
    
    for img in images:
        image_id = img['image_id']
        status = img['status']
        number = img['number']
        
        metadata_str = "None"
        if 'metadata' in img:
            if isinstance(img['metadata'], dict):
                metadata_str = str(img['metadata'])
            else:
                try:
                    metadata_str = str(json.loads(img['metadata']) if img['metadata'] else {})
                except:
                    metadata_str = f"Error parsing: {img['metadata']}"
        
        # Check which Group B this image would go to
        target_group_b = get_group_b_for_image(image_id, img.get('metadata', {}))
        
        message_parts.append(f"🔢 Group: {number} | 🆔 ID: {image_id} | ⚡ Status: {status}")
        message_parts.append(f"📊 Metadata: {metadata_str}")
        message_parts.append(f"🔸 Target Group B: {target_group_b}")
        message_parts.append("")  # Empty line for spacing
    
    # Send the debug info
    message = "\n".join(message_parts)
    
    # If message is too long, split it
    if len(message) > 4000:
        # Send in chunks
        chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for chunk in chunks:
            update.message.reply_text(chunk)
    else:
        update.message.reply_text(message)

# Add a global variable to store the dispatcher
dispatcher = None

# Define error handler at global scope
def error_handler(update, context):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")
    # If it's a network error, just log it
    if isinstance(context.error, (NetworkError, TimedOut, RetryAfter)):
        logger.error(f"Network error: {context.error}")

def register_handlers(dispatcher):
    """Register all message handlers."""
    # Clear existing handlers first
    for group in list(dispatcher.handlers.keys()):
        dispatcher.handlers[group].clear()
    
    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("setimage", set_image))
    dispatcher.add_handler(CommandHandler("images", list_images))
    
    # Add button callback handler (highest priority)
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    
    # Add handler for "设置点击模式" command
    dispatcher.add_handler(MessageHandler(
        Filters.text & Filters.regex(r'^设置点击模式$') & (Filters.chat(GROUP_B_ID) | Filters.chat(list(GROUP_B_IDS))),
        handle_set_click_mode,
        run_async=True
    ))
    
    # Handle Group A messages
    dispatcher.add_handler(MessageHandler(
        Filters.text & 
        ~Filters.regex(r'^\+') &  # Exclude messages starting with +
        ((Filters.chat(GROUP_A_ID) | Filters.chat(list(GROUP_A_IDS)))),  # Any message in Group A
        handle_group_a_message,
        run_async=True
    ))
    
    # Handle Group B messages
    dispatcher.add_handler(MessageHandler(
        Filters.text & (Filters.chat(GROUP_B_ID) | Filters.chat(list(GROUP_B_IDS))),
        handle_all_group_b_messages,
        run_async=True
    ))
    
    logger.info(f"Handlers registered with Group A IDs: {GROUP_A_IDS}, Group B IDs: {GROUP_B_IDS}")

def main() -> None:
    """Start the bot."""
    global dispatcher
    
    if not TOKEN:
        logger.error("No token provided. Set TELEGRAM_BOT_TOKEN environment variable.")
        return
    
    # Load persistent data
    load_persistent_data()
    load_config_data()  # Make sure to load configuration data as well
    
    # Create the Updater
    updater = Updater(TOKEN)
    
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    
    # Register all handlers
    register_handlers(dispatcher)
    
    # Start the Bot
    updater.start_polling()
    updater.idle()

def handle_dissolve_group(update: Update, context: CallbackContext) -> None:
    """Handle clearing settings for the current group only."""
    global dispatcher
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if user is a global admin
    if not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to dissolve group {chat_id} but is not a global admin")
        update.message.reply_text("只有全局管理员可以解散群聊设置。")
        return
    
    # Check if this chat is in either Group A or Group B
    in_group_a = int(chat_id) in GROUP_A_IDS
    in_group_b = int(chat_id) in GROUP_B_IDS
    
    if not (in_group_a or in_group_b):
        logger.info(f"Group {chat_id} is not configured as Group A or Group B")
        update.message.reply_text("此群聊未设置为任何群组类型。")
        return
    
    # Remove only this specific chat from the appropriate group
    if in_group_a:
        GROUP_A_IDS.discard(int(chat_id))
        group_type = "供方群 (Group A)"
    elif in_group_b:
        GROUP_B_IDS.discard(int(chat_id))
        group_type = "需方群 (Group B)"
    
    # Save the configuration
    save_config_data()
    
    # Reload handlers to reflect changes
    if dispatcher:
        register_handlers(dispatcher)
    
    logger.info(f"Group {chat_id} removed from {group_type} by user {user_id}")
    update.message.reply_text(f"✅ 此群聊已从{group_type}中移除。其他群聊不受影响。")

def handle_toggle_forwarding(update: Update, context: CallbackContext) -> None:
    """Toggle the forwarding status between Group B and Group A."""
    global FORWARDING_ENABLED
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    
    # Check if user is a global admin
    if not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to toggle forwarding but is not a global admin")
        update.message.reply_text("只有全局管理员可以切换转发状态。")
        return
    
    # Get command text
    text = update.message.text.strip().lower()
    
    # Determine whether to open or close forwarding
    if "开启转发" in text:
        FORWARDING_ENABLED = True
        status_message = "✅ 群转发功能已开启 - 消息将从群B转发到群A"
    elif "关闭转发" in text:
        FORWARDING_ENABLED = False
        status_message = "🚫 群转发功能已关闭 - 消息将不会从群B转发到群A"
    else:
        # Toggle current state if just "转发状态"
        FORWARDING_ENABLED = not FORWARDING_ENABLED
        status_message = "✅ 群转发功能已开启" if FORWARDING_ENABLED else "🚫 群转发功能已关闭"
    
    # Save configuration
    save_config_data()
    
    logger.info(f"Forwarding status set to {FORWARDING_ENABLED} by user {user_id} in {chat_type} chat")
    update.message.reply_text(status_message)

def handle_admin_send_image(update: Update, context: CallbackContext) -> None:
    """Allow global admins to manually send an image."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if user is a global admin
    if not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to use admin send image feature but is not a global admin")
        return
    
    logger.info(f"Global admin {user_id} is using send image feature")
    
    # Get message text (remove the command part)
    full_text = update.message.text.strip()
    
    # Check if there's a target number in the message
    number_match = re.search(r'群(\d+)', full_text)
    number = number_match.group(1) if number_match else None
    
    # Check if we have images in database
    images = db.get_all_images()
    if not images:
        logger.info("No images found in database")
        update.message.reply_text("没有可用的图片。")
        return
    
    # Get an image - if number specified, try to match it
    image = None
    if number:
        # Try to find image with matching number
        for img in images:
            if str(img.get('number')) == number:
                image = img
                logger.info(f"Found image with number {number}: {img['image_id']}")
                break
        
        # If no match found, inform admin
        if not image:
            logger.info(f"No image found with number {number}")
            update.message.reply_text(f"没有找到群号为 {number} 的图片。")
            return
    else:
        # Get a random open image
        image = db.get_random_open_image()
        if not image:
            # If no open images, just get any image
            image = images[0]
            logger.info(f"No open images, using first available: {image['image_id']}")
        else:
            logger.info(f"Using random open image: {image['image_id']}")
    
    # Send the image
    try:
        # If replying to someone, send as reply
        reply_to_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None
        
        sent_msg = context.bot.send_photo(
            chat_id=chat_id,
            photo=image['file_id'],
            caption=f"🌟 群: {image['number']} 🌟",
            reply_to_message_id=reply_to_id
        )
        logger.info(f"Admin manually sent image {image['image_id']} with number {image['number']}")
    except Exception as e:
        logger.error(f"Error sending image: {e}")
        update.message.reply_text(f"发送图片错误: {e}")
        return
    
    # Option to forward to Group B if admin adds "转发" in command
    if "转发" in full_text:
        try:
            # Get a target Group B
            if GROUP_B_IDS:
                target_group_b = list(GROUP_B_IDS)[0]  # Use first Group B
                
                # Extract amount from message if present
                amount_match = re.search(r'金额(\d+)', full_text) 
                amount = amount_match.group(1) if amount_match else "0"
                
                # Forward to Group B
                forwarded = context.bot.send_message(
                    chat_id=target_group_b,
                    text=f"💰 金额：{amount}\n🔢 群：{image['number']}\n\n❌ 如果会员10分钟没进群请回复0"
                )
                
                # Store mapping for responses
                forwarded_msgs[image['image_id']] = {
                    'group_a_msg_id': sent_msg.message_id,
                    'group_a_chat_id': chat_id,
                    'group_b_msg_id': forwarded.message_id,
                    'group_b_chat_id': target_group_b,
                    'image_id': image['image_id'],
                    'amount': amount,
                    'number': str(image['number']),
                    'original_user_id': user_id,
                    'original_message_id': update.message.message_id
                }
                
                save_persistent_data()
                logger.info(f"Admin forwarded image {image['image_id']} to Group B {target_group_b}")
                
                # Only set image to closed if explicitly requested to avoid confusion
                if "关闭" in full_text:
                    db.set_image_status(image['image_id'], "closed")
                    logger.info(f"Admin closed image {image['image_id']}")
            else:
                update.message.reply_text("没有设置群B，无法转发。")
        except Exception as e:
            logger.error(f"Error forwarding to Group B: {e}")
            update.message.reply_text(f"转发至群B失败: {e}")

def handle_reset_specific_image(update: Update, context: CallbackContext) -> None:
    """Handle command to reset a specific image by its number."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    # Check if this is Group B
    if chat_id not in GROUP_B_IDS and chat_id != GROUP_B_ID:
        logger.info(f"Reset specific image command used in non-Group B chat: {chat_id}")
        return
    
    # Extract the image number from the command "重置群{number}"
    match = re.search(r'^重置群(\d+)$', message_text)
    if not match:
        return
    
    image_number = int(match.group(1))
    logger.info(f"Reset command for image number {image_number} detected in Group B {chat_id}")
    
    # Check if user is a group admin or global admin
    if not is_group_admin(user_id, chat_id) and not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to reset image but is not an admin")
        update.message.reply_text("只有群操作人或全局管理员可以重置群码。")
        return
    
    logger.info(f"Admin {user_id} is resetting image number {image_number} in Group B: {chat_id}")
    
    # Get image count before deletion
    all_images = db.get_all_images()
    before_count = len(all_images)
    logger.info(f"Total images in database before reset: {before_count}")
    
    # Delete the specific image by its number
    success = db.delete_image_by_number(image_number, chat_id)
    
    if success:
        # Also clear related message mappings for this image
        global forwarded_msgs, group_b_responses
        
        # Find any message mappings related to this image
        mappings_to_remove = []
        for img_id, data in forwarded_msgs.items():
            if data.get('number') == str(image_number) and data.get('group_b_chat_id') == chat_id:
                mappings_to_remove.append(img_id)
                logger.info(f"Found matching mapping for image {img_id} with number {image_number}")
        
        # Remove the found mappings
        for img_id in mappings_to_remove:
            if img_id in forwarded_msgs:
                logger.info(f"Removing forwarded message mapping for {img_id}")
                del forwarded_msgs[img_id]
            if img_id in group_b_responses:
                logger.info(f"Removing group B response for {img_id}")
                del group_b_responses[img_id]
        
        save_persistent_data()
        
        # Get image count after deletion
        remaining_images = db.get_all_images()
        after_count = len(remaining_images)
        deleted_count = before_count - after_count
        
        # Provide feedback to the user
        if deleted_count > 0:
            update.message.reply_text(f"✅ 已重置群码 {image_number}，删除了 {deleted_count} 张图片。")
            logger.info(f"Successfully reset image number {image_number}")
        else:
            update.message.reply_text(f"⚠️ 未找到群号为 {image_number} 的图片，或者删除操作失败。")
            logger.warning(f"No images with number {image_number} were deleted")
    else:
        update.message.reply_text(f"❌ 重置群码 {image_number} 失败。未找到匹配的图片。")
        logger.error(f"Failed to reset image number {image_number}")

def fix_group_type(update: Update, context: CallbackContext) -> None:
    """Fix group type command for global admins only."""
    user_id = update.message.from_user.id
    
    if not is_global_admin(user_id):
        update.message.reply_text("⚠️ Only global admins can use this command.")
        return
    
    try:
        args = context.args
        if len(args) < 2:
            update.message.reply_text("Usage: /fixgrouptype <group_id> <new_type>")
            return
        
        group_id = int(args[0])
        new_type = args[1].lower()
        
        if new_type == 'a':
            if group_id in GROUP_B_IDS:
                GROUP_B_IDS.remove(group_id)
            GROUP_A_IDS.add(group_id)
            update.message.reply_text(f"✅ Group {group_id} moved to Group A")
        elif new_type == 'b':
            if group_id in GROUP_A_IDS:
                GROUP_A_IDS.remove(group_id)
            GROUP_B_IDS.add(group_id)
            update.message.reply_text(f"✅ Group {group_id} moved to Group B")
        else:
            update.message.reply_text("❌ Type must be 'a' or 'b'")
            return
        
        save_config_data()
        
    except ValueError:
        update.message.reply_text("❌ Invalid group ID format")
    except Exception as e:
        logger.error(f"Error in fix_group_type: {e}")
        update.message.reply_text("❌ Error fixing group type")

def handle_set_group_b_percentage(update: Update, context: CallbackContext) -> None:
    """Set percentage chance for a specific Group B to have its images sent to Group A."""
    user_id = update.message.from_user.id
    
    if not is_global_admin(user_id):
        update.message.reply_text("⚠️ Only global admins can use this command.")
        return
    
    try:
        args = context.args
        if len(args) != 2:
            update.message.reply_text("Usage: /setgroupbpercent <group_b_id> <percentage>\nExample: /setgroupbpercent -1002648811668 75")
            return
        
        group_b_id = int(args[0])
        percentage = int(args[1])
        
        if percentage < 0 or percentage > 100:
            update.message.reply_text("❌ Percentage must be between 0 and 100")
            return
        
        # Check if the group ID is a valid Group B
        if group_b_id not in GROUP_B_IDS and group_b_id != GROUP_B_ID:
            update.message.reply_text(f"⚠️ Group ID {group_b_id} is not a registered Group B")
            return
        
        group_b_percentages[group_b_id] = percentage
        save_config_data()
        
        update.message.reply_text(f"✅ Set Group B {group_b_id} to {percentage}% chance for image distribution")
        logger.info(f"Global admin {user_id} set Group B {group_b_id} to {percentage}%")
        
    except ValueError:
        update.message.reply_text("❌ Invalid format. Use: /setgroupbpercent <group_b_id> <percentage>")
    except Exception as e:
        logger.error(f"Error in handle_set_group_b_percentage: {e}")
        update.message.reply_text("❌ Error setting Group B percentage")

def handle_reset_group_b_percentages(update: Update, context: CallbackContext) -> None:
    """Reset all Group B percentages to normal (no percentage limits)."""
    user_id = update.message.from_user.id
    
    if not is_global_admin(user_id):
        update.message.reply_text("⚠️ Only global admins can use this command.")
        return
    
    try:
        global group_b_percentages
        group_b_percentages.clear()
        save_config_data()
        
        update.message.reply_text("✅ All Group B percentages have been reset. Image distribution is back to normal.")
        logger.info(f"Global admin {user_id} reset all Group B percentages")
        
    except Exception as e:
        logger.error(f"Error in handle_reset_group_b_percentages: {e}")
        update.message.reply_text("❌ Error resetting Group B percentages")

def handle_list_group_b_percentages(update: Update, context: CallbackContext) -> None:
    """List all Group B percentage settings."""
    user_id = update.message.from_user.id
    
    if not is_global_admin(user_id):
        update.message.reply_text("⚠️ Only global admins can use this command.")
        return
    
    try:
        if not group_b_percentages:
            update.message.reply_text("📊 No Group B percentage limits are set. All groups have normal distribution.")
            return
        
        message = "📊 Group B Percentage Settings:\n\n"
        for group_id, percentage in group_b_percentages.items():
            message += f"Group B {group_id}: {percentage}%\n"
        
        message += "\n💡 Groups not listed have normal distribution (100% chance)"
        update.message.reply_text(message)
        
    except Exception as e:
        logger.error(f"Error in handle_list_group_b_percentages: {e}")
        update.message.reply_text("❌ Error listing Group B percentages")

# Click mode management functions
def is_click_mode_enabled(group_b_id):
    """Check if click mode is enabled for a specific Group B."""
    return group_b_click_mode.get(int(group_b_id), False)

def set_click_mode(group_b_id, enabled):
    """Set click mode for a specific Group B."""
    group_b_click_mode[int(group_b_id)] = enabled
    save_config_data()
    logger.info(f"Set click mode for Group B {group_b_id} to {enabled}")

# Message deletion scheduling functions
def schedule_message_deletion(context, chat_id, message_id, delay_seconds=60):
    """Schedule a message to be deleted after a delay."""
    def delete_message():
        try:
            time.sleep(delay_seconds)
            context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"Auto-deleted message {message_id} in chat {chat_id} after {delay_seconds} seconds")
        except Exception as e:
            logger.error(f"Error deleting message {message_id} in chat {chat_id}: {e}")
    
    # Run deletion in a separate thread
    deletion_thread = threading.Thread(target=delete_message)
    deletion_thread.daemon = True
    deletion_thread.start()
    
    deletion_id = f"{chat_id}_{message_id}_{int(time.time())}"
    scheduled_deletions[deletion_id] = {
        'chat_id': chat_id,
        'message_id': message_id,
        'scheduled_time': datetime.now() + timedelta(seconds=delay_seconds),
        'thread': deletion_thread
    }
    logger.info(f"Scheduled deletion for message {message_id} in chat {chat_id} after {delay_seconds} seconds")
    return deletion_id

def cancel_scheduled_deletion(deletion_id):
    """Cancel a scheduled message deletion if possible."""
    if deletion_id in scheduled_deletions:
        # Note: We can't actually stop a thread that's sleeping, but we can remove it from tracking
        del scheduled_deletions[deletion_id]
        logger.info(f"Cancelled scheduled deletion {deletion_id}")
        return True
    return False

def handle_set_click_mode(update: Update, context: CallbackContext) -> None:
    """Handle setting click mode for Group B."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Check if this is Group B
    if chat_id not in GROUP_B_IDS and chat_id != GROUP_B_ID:
        logger.info(f"Click mode command used in non-Group B chat: {chat_id}")
        return
    
    # Check if user is a group admin or global admin
    if not is_group_admin(user_id, chat_id) and not is_global_admin(user_id):
        logger.info(f"User {user_id} tried to set click mode but is not an admin")
        update.message.reply_text("只有群操作人或全局管理员可以设置点击模式。")
        return
    
    # Toggle click mode
    current_mode = is_click_mode_enabled(chat_id)
    new_mode = not current_mode
    set_click_mode(chat_id, new_mode)
    
    if new_mode:
        update.message.reply_text("✅ 已开启点击模式 - 消息将显示单个按钮，点击后图片状态变为开启并在1分钟后自动删除消息")
    else:
        update.message.reply_text("✅ 已关闭点击模式 - 消息将显示默认按钮，图片状态变为开启后在1分钟后自动删除消息")
    
    logger.info(f"Admin {user_id} set click mode for Group B {chat_id} to {new_mode}")

def handle_all_group_b_messages(update: Update, context: CallbackContext) -> None:
    """Handle all messages in Group B."""
    # Add debug logging
    chat_id = update.effective_chat.id
    logger.info(f"Received message in chat ID: {chat_id}")
    logger.info(f"GROUP_A_IDS: {GROUP_A_IDS}, GROUP_B_IDS: {GROUP_B_IDS}")
    logger.info(f"Is chat in Group A: {int(chat_id) in GROUP_A_IDS or int(chat_id) == GROUP_A_ID}")
    logger.info(f"Is chat in Group B: {int(chat_id) in GROUP_B_IDS or int(chat_id) == GROUP_B_ID}")
    
    # Check if this chat is a Group B - ensure we're comparing integers
    if int(chat_id) not in GROUP_B_IDS and int(chat_id) != GROUP_B_ID:
        logger.info(f"Message received in non-Group B chat: {chat_id}")
        return
    
    # Get message text
    text = update.message.text.strip()
    logger.info(f"Received message: {text}")
    
    # Skip messages that start with "+"
    if text.startswith("+"):
        logger.info("Message starts with '+', skipping")
        return
    
    # Match any of the formats:
    # - Just a number
    # - number+群 or number 群
    # - 群+number or 群 number
    # - 微信+number or 微信 number 
    # - number+微信 or number 微信
    # - 微信群+number or 微信群 number
    # - number+微信群 or number 微信群
    patterns = [
        r'^(\d+)$',  # Just a number
        r'^(\d+)\s*群$',  # number+群
        r'^群\s*(\d+)$',  # 群+number
        r'^微信\s*(\d+)$',  # 微信+number
        r'^(\d+)\s*微信$',  # number+微信
        r'^微信群\s*(\d+)$',  # 微信群+number
        r'^(\d+)\s*微信群$',  # number+微信群
        r'^微信\s*群\s*(\d+)$',  # 微信 群 number (with spaces)
        r'^(\d+)\s*微信\s*群$'   # number 微信 群 (with spaces)
    ]
    
    amount = None
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            amount = match.group(1)
            logger.info(f"Matched pattern '{pattern}' with amount: {amount}")
            break
    
    if not amount:
        logger.info("Message doesn't match any accepted format")
        return
    
    # Check if the number is between 20 and 5000 (inclusive)
    try:
        amount_int = int(amount)
        if amount_int < 20 or amount_int > 5000:
            logger.info(f"Number {amount} is outside the allowed range (20-5000).")
            return
    except ValueError:
        logger.info(f"Invalid number format: {amount}")
        return
    
    # Rest of the function remains unchanged
    # Check if we have any images
    images = db.get_all_images()
    if not images:
        logger.info("No images found in database - remaining silent")
        return
    
    # For now, just log that this is a Group B message
    logger.info("Group B message handling completed")

def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks."""
    global FORWARDING_ENABLED
    query = update.callback_query
    query.answer()
    
    # Parse callback data
    data = query.data
    
    if data.startswith('release_'):
        # Single-click mode release button
        image_id = data[8:]  # Remove 'release_' prefix
        
        # Find the message data
        msg_data = None
        for img_id, data in forwarded_msgs.items():
            if img_id == image_id:
                msg_data = data
                break
        
        if msg_data:
            original_amount = msg_data.get('amount', '0')
            
            # Process as if they clicked the amount button
            response_text = f"+{original_amount}"
            
            # Store the response for Group A
            group_b_responses[image_id] = response_text
            logger.info(f"Stored Group B release response for image {image_id}: {response_text}")
            
            # Save updated responses
            save_persistent_data()
            
            try:
                # Set status to open
                if db.set_image_status(image_id, "open"):
                    # Update button to show "已解除状态"
                    keyboard = [
                        [InlineKeyboardButton("已解除状态", callback_data=f"released_{image_id}")]
                    ]
                    query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
                    
                    # Schedule message deletion after 1 minute
                    schedule_message_deletion(context, query.message.chat_id, query.message.message_id, 60)
                
                # Only send response to Group A if forwarding is enabled
                if FORWARDING_ENABLED:
                    if msg_data and 'group_a_chat_id' in msg_data and 'group_a_msg_id' in msg_data:
                        try:
                            # Get the original message ID if available
                            original_message_id = msg_data.get('original_message_id')
                            reply_to_message_id = original_message_id if original_message_id else msg_data['group_a_msg_id']
                            
                            # Send response back to Group A using safe send method
                            safe_send_message(
                                context=context,
                                chat_id=msg_data['group_a_chat_id'],
                                text=response_text,
                                reply_to_message_id=reply_to_message_id
                            )
                            logger.info(f"Sent release response to Group A: {response_text}")
                        except Exception as e:
                            logger.error(f"Error sending release response to Group A: {e}")
                else:
                    logger.info("Forwarding to Group A is currently disabled by admin - not sending release response")
            except (NetworkError, TimedOut) as e:
                logger.error(f"Network error in release callback: {e}")
    
    elif data.startswith('released_'):
        # Button already released, do nothing or show info
        query.answer("状态已解除", show_alert=False)
    
    elif data.startswith('verify_'):
        # Format: verify_image_id_amount
        parts = data.split('_')
        if len(parts) >= 3:
            image_id = parts[1]
            amount = parts[2]
            
            # Find the message data
            msg_data = None
            for img_id, data in forwarded_msgs.items():
                if img_id == image_id:
                    msg_data = data
                    break
            
            # Simplified response format - just +amount or custom message for +0
            response_text = "会员没进群呢哥哥~ 😢" if amount == "0" else f"+{amount}"
            
            # Store the response for Group A
            group_b_responses[image_id] = response_text
            logger.info(f"Stored Group B button response for image {image_id}: {response_text}")
            
            # Save updated responses
            save_persistent_data()
            
            try:
                # Set status to open
                if db.set_image_status(image_id, "open"):
                    query.edit_message_reply_markup(None)
                    
                    # Schedule message deletion after 1 minute
                    schedule_message_deletion(context, query.message.chat_id, query.message.message_id, 60)
                
                # Only send response to Group A if forwarding is enabled
                if FORWARDING_ENABLED:
                    if msg_data and 'group_a_chat_id' in msg_data and 'group_a_msg_id' in msg_data:
                        try:
                            # Get the original message ID if available
                            original_message_id = msg_data.get('original_message_id')
                            reply_to_message_id = original_message_id if original_message_id else msg_data['group_a_msg_id']
                            
                            # Send response back to Group A using safe send method
                            safe_send_message(
                                context=context,
                                chat_id=msg_data['group_a_chat_id'],
                                text=response_text,
                                reply_to_message_id=reply_to_message_id
                            )
                            logger.info(f"Directly sent Group B button response to Group A: {response_text}")
                        except Exception as e:
                            logger.error(f"Error sending button response to Group A: {e}")
                else:
                    logger.info("Forwarding to Group A is currently disabled by admin - not sending button response")
            except (NetworkError, TimedOut) as e:
                logger.error(f"Network error in verify callback: {e}")

if __name__ == '__main__':
    main() 
