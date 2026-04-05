from flask import Flask, render_template, request, jsonify, send_from_directory
from database import db
import os
import json
from dotenv import load_dotenv
import traceback
import asyncio
import discord
from threading import Thread

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# Global variable to store bot instance
bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

@app.route('/')
def index():
    try:
        return render_template('dashboard.html')
    except Exception as e:
        print(f"Error rendering dashboard: {e}")
        return f"Error: {str(e)}", 500

@app.route('/panel-builder')
def panel_builder():
    try:
        return render_template('panel_builder.html')
    except Exception as e:
        print(f"Error rendering panel_builder: {e}")
        traceback.print_exc()
        return f"Error loading panel builder: {str(e)}", 500

@app.route('/settings')
def settings():
    try:
        return render_template('settings.html')
    except Exception as e:
        print(f"Error rendering settings: {e}")
        traceback.print_exc()
        return f"Error loading settings: {str(e)}", 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        password = request.json.get('password')
        if password == ADMIN_PASSWORD:
            return jsonify({'success': True, 'token': 'dummy_token'})
        return jsonify({'success': False}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        return jsonify(db.get_ticket_stats())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tickets')
def get_tickets():
    try:
        tickets = db.get_all_tickets()
        return jsonify(tickets)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tickets/<ticket_id>')
def get_ticket(ticket_id):
    try:
        ticket = db.get_ticket(ticket_id)
        return jsonify(ticket or {})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    try:
        if request.method == 'POST':
            data = request.json
            for key, value in data.items():
                db.update_config(key, value)
            return jsonify({'success': True})
        return jsonify(db.config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/panels', methods=['GET', 'POST', 'DELETE'])
def panels():
    try:
        if request.method == 'POST':
            panel_data = request.json
            panel_id = panel_data.get('id', f"panel_{len(db.get_all_panels()) + 1}")
            db.save_panel(panel_id, panel_data)
            return jsonify({'success': True, 'id': panel_id})
        elif request.method == 'DELETE':
            panel_id = request.json.get('id')
            db.delete_panel(panel_id)
            return jsonify({'success': True})
        else:
            return jsonify(db.get_all_panels())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/send-panel', methods=['POST'])
def send_panel():
    try:
        data = request.json
        panel_id = data['panel_id']
        channel_id = int(data['channel_id'])
        
        panel_data = db.get_panel(panel_id)
        if not panel_data:
            return jsonify({'error': 'Panel not found'}), 404
        
        # Send panel through bot
        if bot_instance:
            # Create an async task to send the panel
            asyncio.run_coroutine_threadsafe(
                send_panel_to_discord(bot_instance, channel_id, panel_id, panel_data),
                bot_instance.loop
            )
            return jsonify({'success': True, 'message': 'Panel sent to Discord!'})
        else:
            return jsonify({'error': 'Bot not connected'}), 500
            
    except Exception as e:
        print(f"Error sending panel: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

async def send_panel_to_discord(bot, channel_id, panel_id, panel_data):
    """Send the ticket panel to Discord channel"""
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"Channel {channel_id} not found")
            return
        
        # Create embed
        embed_color = int(panel_data.get('embed_color', '#5865F2').lstrip('#'), 16)
        
        embed = discord.Embed(
            title=panel_data.get('embed_title', 'Support Tickets'),
            description=panel_data.get('embed_description', 'Click a button below to create a support ticket. Our team will assist you shortly!'),
            color=embed_color
        )
        
        if panel_data.get('footer_text'):
            embed.set_footer(text=panel_data['footer_text'])
        
        if panel_data.get('thumbnail_url'):
            embed.set_thumbnail(url=panel_data['thumbnail_url'])
        
        # Import here to avoid circular import
        from bot import DynamicTicketView
        
        # Create view with buttons and dropdown
        view = DynamicTicketView(panel_id, panel_data)
        
        # Send to channel
        await channel.send(embed=embed, view=view)
        print(f"Panel {panel_id} sent to channel {channel_id}")
        
    except Exception as e:
        print(f"Error sending panel to Discord: {e}")
        traceback.print_exc()

@app.route('/api/embed-colors')
def get_embed_colors():
    colors = {
        'default': '#5865F2',
        'success': '#57F287',
        'danger': '#ED4245',
        'warning': '#FEE75C',
        'info': '#EB459E'
    }
    return jsonify(colors)

@app.route('/debug-templates')
def debug_templates():
    import os
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    files = os.listdir(template_dir) if os.path.exists(template_dir) else []
    return jsonify({
        'template_dir': template_dir,
        'exists': os.path.exists(template_dir),
        'files': files
    })

if __name__ == "__main__":
    port = int(os.getenv('WEB_PORT', 8080))
    print(f"Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
