from flask import Flask, render_template, request, jsonify
from database import db
import discord
import asyncio
import os
from dotenv import load_dotenv
import threading
import json

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Simple auth
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    if password == ADMIN_PASSWORD:
        return jsonify({'success': True})
    return jsonify({'success': False}), 401

@app.route('/api/tickets')
def get_tickets():
    tickets = db.get_all_tickets()
    return jsonify(tickets)

@app.route('/api/stats')
def get_stats():
    tickets = db.get_all_tickets()
    stats = {
        'total': len(tickets),
        'open': len([t for t in tickets.values() if t['status'] == 'open']),
        'closed': len([t for t in tickets.values() if t['status'] == 'closed'])
    }
    return jsonify(stats)

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        data = request.json
        for key, value in data.items():
            db.update_config(key, value)
        return jsonify({'success': True})
    
    config_data = {
        'support_role_id': db.get_config('support_role_id'),
        'log_channel_id': db.get_config('log_channel_id'),
        'ticket_category_id': db.get_config('ticket_category_id')
    }
    return jsonify(config_data)

def run_bot():
    """Run the Discord bot in a separate thread"""
    from bot import bot, TOKEN, GUILD_ID
    import asyncio
    
    async def start_bot():
        await bot.start(TOKEN)
    
    asyncio.run(start_bot())

if __name__ == "__main__":
    # Start Discord bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Run Flask web server
    port = int(os.getenv('WEB_PORT', 8080))
    print(f"Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port)
