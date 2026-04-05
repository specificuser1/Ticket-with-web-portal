import os
import threading
from dotenv import load_dotenv
import asyncio

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))

def run_web():
    """Run the web server"""
    from web_server import app, set_bot_instance
    # Import bot after web_server to avoid circular import
    from bot import bot
    set_bot_instance(bot)
    port = int(os.getenv('WEB_PORT', 8080))
    print(f"🌐 Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def start_bot():
    """Start the Discord bot"""
    from bot import bot
    
    # Start the bot
    await bot.start(TOKEN)

if __name__ == "__main__":
    print("🚀 Starting Ticket System...")
    
    # Start web server in thread
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Run bot
    print("🤖 Starting Discord bot...")
    asyncio.run(start_bot())
