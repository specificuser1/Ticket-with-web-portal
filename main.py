import os
import threading
from dotenv import load_dotenv
import asyncio
import discord
from discord.ext import commands

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Import bot commands and events
from bot import setup_bot_commands, on_ready_handler

def run_web():
    """Run the web server"""
    from web_server import app, set_bot_instance
    set_bot_instance(bot)
    port = int(os.getenv('WEB_PORT', 8080))
    print(f"🌐 Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def start_bot():
    """Start the Discord bot"""
    # Setup bot commands
    await setup_bot_commands(bot)
    
    # Set on_ready handler
    @bot.event
    async def on_ready():
        await on_ready_handler(bot)
    
    await bot.start(TOKEN)

if __name__ == "__main__":
    print("🚀 Starting Ticket System...")
    
    # Start web server in thread
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Run bot
    print("🤖 Starting Discord bot...")
    asyncio.run(start_bot())
