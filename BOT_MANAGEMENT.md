# Bot Management Scripts

This directory contains scripts to safely manage the Telegram bot process and prevent conflicts when starting new instances.

## Scripts Available

### 1. Bash Scripts (Linux/macOS)

#### `start_bot.sh`
- **Purpose**: Terminates any existing bot processes and starts a new one
- **Usage**: `./start_bot.sh`
- **Features**:
  - Gracefully terminates existing bot processes (SIGTERM)
  - Force kills if graceful termination fails (SIGKILL)
  - Starts new bot instance in background
  - Logs output to `bot.log`
  - Provides status feedback

#### `stop_bot.sh`
- **Purpose**: Stops all running bot processes
- **Usage**: `./stop_bot.sh`
- **Features**:
  - Graceful termination first
  - Force termination if needed
  - Clean process cleanup

### 2. Python Scripts (Cross-platform)

#### `simple_restart.py` (Recommended - No dependencies)
- **Purpose**: Bot process management using only standard Python libraries
- **Usage**: 
  ```bash
  python3 simple_restart.py start    # Start the bot
  python3 simple_restart.py stop     # Stop the bot
  python3 simple_restart.py restart  # Restart the bot
  python3 simple_restart.py status   # Check bot status
  ```
- **Features**:
  - Cross-platform (Windows, Linux, macOS)
  - No external dependencies required
  - Process finding and termination
  - Detailed logging and error handling

#### `restart_bot.py` (Advanced - Requires psutil)
- **Purpose**: Advanced bot process management with detailed monitoring
- **Usage**: 
  ```bash
  python3 restart_bot.py start    # Start the bot
  python3 restart_bot.py stop     # Stop the bot
  python3 restart_bot.py restart  # Restart the bot
  python3 restart_bot.py status   # Check bot status
  ```
- **Features**:
  - Cross-platform (Windows, Linux, macOS)
  - Process monitoring with CPU/Memory usage
  - Detailed logging and error handling
  - Dependency: `psutil` (included in requirements.txt)

## Quick Start

### For Development (Local)
```bash
# Method 1: Using bash script (Linux/macOS)
./start_bot.sh

# Method 2: Using simple Python script (Any OS, no dependencies)
python3 simple_restart.py start

# Method 3: Using advanced Python script (Any OS, requires psutil)
python3 restart_bot.py start
```

### For Production/Deployment
```bash
# Stop any existing instances
./stop_bot.sh
# or
python3 simple_restart.py stop

# Start new instance
./start_bot.sh
# or
python3 simple_restart.py start
```

## Monitoring

### Check if bot is running
```bash
# Using simple Python script (recommended)
python3 simple_restart.py status

# Using advanced Python script
python3 restart_bot.py status

# Using command line
ps aux | grep bot.py
```

### View logs
```bash
# Real-time log monitoring
tail -f bot.log

# View last 50 lines
tail -50 bot.log
```

### Kill bot manually
```bash
# Find bot process
ps aux | grep bot.py

# Kill by PID
kill <PID>

# Or force kill
kill -9 <PID>
```

## Why These Scripts?

### Problem
When developing or deploying the bot, running multiple instances can cause:
- Webhook conflicts
- Database locking issues
- Port conflicts
- Message duplication
- Unpredictable behavior

### Solution
These scripts ensure:
- Only one bot instance runs at a time
- Clean process termination
- Proper resource cleanup
- Safe restart procedures
- Process monitoring capabilities

## Error Handling

If the bot fails to start:
1. Check `bot.log` for error messages
2. Verify `BOT_TOKEN` environment variable is set
3. Ensure all dependencies are installed: `pip install -r requirements.txt`
4. Check database permissions
5. Verify network connectivity

## Best Practices

1. **Always use these scripts** instead of running `python bot.py` directly
2. **Monitor logs** regularly: `tail -f bot.log`
3. **Check status** before manual interventions: `python3 simple_restart.py status`
4. **Use restart** instead of stop+start: `python3 simple_restart.py restart`
5. **Set up monitoring** in production environments

## Integration with CI/CD

For automated deployments, use:
```bash
# In your deployment script
./stop_bot.sh
# Deploy new code
./start_bot.sh
```

Or with Python:
```bash
python3 simple_restart.py stop
# Deploy new code  
python3 simple_restart.py start
```

## Choosing the Right Script

- **`simple_restart.py`** - Recommended for most use cases, no external dependencies
- **`restart_bot.py`** - Use if you need detailed process monitoring (CPU/Memory usage)
- **Bash scripts** - Good for Linux/macOS environments and shell scripting integration 