import os
import threading
from dotenv import load_dotenv

load_dotenv()

def run_web():
    from web_server import app
    port = int(os.getenv('WEB_PORT', 8080))
    print(f"🌐 Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_bot():
    import asyncio
    from bot import bot, TOKEN
    
    async def start():
        await bot.start(TOKEN)
    
    asyncio.run(start())

if __name__ == "__main__":
    print("🚀 Starting Ticket System...")
    
    # Start web server in thread
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Run bot in main thread
    print("🤖 Starting Discord bot...")
    run_bot()
