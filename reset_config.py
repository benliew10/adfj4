import json
import os

# Files to clear
config_files = [
    "forwarded_msgs.json",
    "group_b_responses.json",
    "group_a_ids.json",
    "group_b_ids.json",
    "group_admins.json",
    "pending_custom_amounts.json",
    "bot_settings.json"
]

# Process each file independently to ensure all are handled
for file in config_files:
    try:
        if os.path.exists(file):
            if file == "group_a_ids.json" or file == "group_b_ids.json":
                # For group ID files, write empty array
                with open(file, 'w') as f:
                    json.dump([], f)
                print(f"Reset {file} to empty array")
            elif file == "bot_settings.json":
                # Keep the bot settings file but with default settings
                with open(file, 'w') as f:
                    json.dump({"forwarding_enabled": True}, f)
                print(f"Reset {file} to default settings")
            else:
                # For all other files, write empty dict
                with open(file, 'w') as f:
                    json.dump({}, f)
                print(f"Reset {file} to empty dict")
        else:
            print(f"File {file} does not exist, skipping")
    except Exception as e:
        print(f"Error processing {file}: {e}")

print("\nAll configurations have been reset. You can now set up groups yourself.") 