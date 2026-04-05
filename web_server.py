from flask import Flask, render_template, request, jsonify, send_from_directory
from database import db
import os
import json
from dotenv import load_dotenv
import discord
import asyncio

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
bot_instance = None

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/panel-builder')
def panel_builder():
    return render_template('panel_builder.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/login', methods=['POST'])
def login():
    password = request.json.get('password')
    if password == ADMIN_PASSWORD:
        return jsonify({'success': True, 'token': 'dummy_token'})
    return jsonify({'success': False}), 401

@app.route('/api/stats')
def get_stats():
    return jsonify(db.get_ticket_stats())

@app.route('/api/tickets')
def get_tickets():
    tickets = db.get_all_tickets()
    return jsonify(tickets)

@app.route('/api/tickets/<ticket_id>')
def get_ticket(ticket_id):
    ticket = db.get_ticket(ticket_id)
    return jsonify(ticket or {})

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        data = request.json
        for key, value in data.items():
            db.update_config(key, value)
        return jsonify({'success': True})
    
    return jsonify(db.config)

@app.route('/api/panels', methods=['GET', 'POST', 'DELETE'])
def panels():
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

@app.route('/api/send-panel', methods=['POST'])
def send_panel():
    data = request.json
    panel_id = data['panel_id']
    channel_id = int(data['channel_id'])
    
    panel_data = db.get_panel(panel_id)
    if not panel_data:
        return jsonify({'error': 'Panel not found'}), 404
    
    # This would need to be handled by the bot
    # For now, we'll simulate
    return jsonify({'success': True, 'message': 'Panel sent to channel'})

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

if __name__ == "__main__":
    port = int(os.getenv('WEB_PORT', 8080))
    app.run(host='0.0.0.0', port=port)
