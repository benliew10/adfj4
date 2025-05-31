# Render Deployment Guide

This guide explains how to deploy your Telegram bot to Render using the new bot management scripts.

## 🚀 Quick Deploy

### 1. Push to GitHub
```bash
git add .
git commit -m "Update for Render deployment with bot management"
git push origin main
```

### 2. Deploy on Render
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository: `https://github.com/benliew10/adfj4.git`
4. Configure the service:
   - **Name**: `telegram-bot` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python3 render_start.py`
   - **Plan**: `Free` (or your preferred plan)

### 3. Set Environment Variable
In the Render dashboard, go to your service → Environment tab:
- **Key**: `BOT_TOKEN`
- **Value**: `8087490170:AAGkIL_s_NywMN0z6uyx7Jty6r66Ej9SfS0` (or your bot token)

## 📁 Files Optimized for Render

### `render_start.py` (NEW)
- **Purpose**: Render-optimized startup script
- **Features**:
  - Graceful shutdown handling
  - Process conflict prevention
  - Environment validation
  - Direct bot import (no subprocess)
  - Better error logging

### `render.yaml`
- **Purpose**: Infrastructure as Code configuration
- **Features**:
  - Automatic environment setup
  - Python 3.9.16 specification
  - BOT_TOKEN environment variable

## 🔧 Configuration Details

### Environment Variables Required
```
BOT_TOKEN=your_bot_token_here
```

### Python Dependencies
All dependencies are automatically installed from `requirements.txt`:
- python-telegram-bot==13.15
- APScheduler==3.6.3
- requests==2.31.0
- urllib3==1.26.15
- psutil==5.9.8

## 🎯 Deployment Process

### Automatic Deployment
1. **Push to GitHub** → Render automatically detects changes
2. **Build Phase** → Installs dependencies from requirements.txt
3. **Start Phase** → Runs `render_start.py` which:
   - Validates environment
   - Stops any existing processes
   - Starts the bot cleanly

### Manual Deployment
If you need to manually redeploy:
1. Go to Render Dashboard
2. Select your service
3. Click "Manual Deploy" → "Deploy latest commit"

## 📊 Monitoring & Logs

### View Logs
1. Go to Render Dashboard
2. Select your service
3. Click "Logs" tab to see real-time output

### Log Output Example
```
🚀 Starting Telegram Bot on Render...
🐍 Python version: 3.9.16
📁 Working directory: /opt/render/project/src
✅ BOT_TOKEN found
🔍 Checking for existing bot processes...
✅ No existing bot processes found
📂 Found bot.py
🎯 Starting bot process...
✅ Bot module imported successfully
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. BOT_TOKEN Not Set
**Error**: `❌ BOT_TOKEN environment variable not set!`
**Solution**: Add BOT_TOKEN in Render Dashboard → Environment tab

#### 2. Build Fails
**Error**: `pip install failed`
**Solution**: Check requirements.txt format and dependencies

#### 3. Bot Import Error
**Error**: `❌ Error starting bot: No module named 'bot'`
**Solution**: Ensure bot.py is in repository root

#### 4. Database Issues
**Error**: Database-related errors
**Solution**: 
- Render's filesystem is ephemeral
- Database files will be recreated on each deployment
- Consider using external database for persistence

### Debug Steps
1. **Check Logs** in Render Dashboard
2. **Verify Environment Variables** are set correctly
3. **Test Locally** with same environment:
   ```bash
   export BOT_TOKEN="your_token"
   python3 render_start.py
   ```

## 🔄 Updates & Redeployment

### For Code Changes
```bash
# Make your changes
git add .
git commit -m "Your update message"
git push origin main
# Render will automatically redeploy
```

### For Emergency Restart
1. Go to Render Dashboard
2. Select your service
3. Click "Manual Deploy" → "Deploy latest commit"
4. Or use "Restart Service" for quick restart

## 🔐 Security Considerations

### Environment Variables
- ✅ BOT_TOKEN is properly set as environment variable
- ✅ Not hardcoded in source code
- ✅ Secure transmission via Render's encrypted variables

### Process Management
- ✅ Graceful shutdown handling
- ✅ Process conflict prevention
- ✅ Signal handling for clean restarts

## 📈 Scaling & Performance

### Free Plan Limitations
- **Sleep after 15 minutes** of inactivity
- **750 hours/month** of runtime
- **100GB bandwidth/month**

### Keeping Bot Awake
The bot will automatically wake up when receiving messages, but for 24/7 operation:
1. Upgrade to paid plan ($7/month)
2. Or use external ping service to keep awake

### Performance Optimization
- ✅ Direct bot import (no subprocess overhead)
- ✅ Efficient process management
- ✅ Minimal memory footprint
- ✅ Fast startup time

## 🎉 Success Indicators

Your bot is successfully deployed when you see:
1. ✅ Render deployment status shows "Live"
2. ✅ Logs show "Bot module imported successfully"
3. ✅ Bot responds to Telegram messages
4. ✅ No error messages in logs

## 📞 Support

If you encounter issues:
1. Check this guide first
2. Review Render's logs
3. Test locally with same environment
4. Check Telegram bot settings via @BotFather 