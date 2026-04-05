import json
import os
from typing import Dict, List, Optional
from datetime import datetime

class TicketDatabase:
    def __init__(self):
        self.tickets_file = "tickets.json"
        self.config_file = "config.json"
        self.panels_file = "panels.json"
        self._load_data()
    
    def _load_data(self):
        try:
            with open(self.tickets_file, 'r') as f:
                self.tickets = json.load(f)
        except FileNotFoundError:
            self.tickets = {}
        
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "ticket_category_id": None,
                "support_role_id": None,
                "log_channel_id": None,
                "transcript_channel_id": None,
                "max_tickets_per_user": 3,
                "default_embed_color": "#5865F2",
                "default_embed_title": "Support Tickets",
                "default_embed_description": "Click a button below to create a support ticket. Our team will assist you shortly!"
            }
        
        try:
            with open(self.panels_file, 'r') as f:
                self.panels = json.load(f)
        except FileNotFoundError:
            self.panels = {}
    
    def _save_tickets(self):
        with open(self.tickets_file, 'w') as f:
            json.dump(self.tickets, f, indent=4)
    
    def _save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
    
    def _save_panels(self):
        with open(self.panels_file, 'w') as f:
            json.dump(self.panels, f, indent=4)
    
    def create_ticket(self, ticket_id: str, user_id: int, channel_id: int, topic: str, panel_id: str = None):
        self.tickets[ticket_id] = {
            "user_id": user_id,
            "channel_id": channel_id,
            "topic": topic,
            "status": "open",
            "panel_id": panel_id,
            "created_at": datetime.now().isoformat(),
            "messages": []
        }
        self._save_tickets()
    
    def close_ticket(self, ticket_id: str, transcript: List[Dict] = None):
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["status"] = "closed"
            self.tickets[ticket_id]["closed_at"] = datetime.now().isoformat()
            if transcript:
                self.tickets[ticket_id]["transcript"] = transcript
            self._save_tickets()
    
    def add_ticket_message(self, ticket_id: str, author_id: int, content: str):
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["messages"].append({
                "author_id": author_id,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            self._save_tickets()
    
    def get_ticket(self, ticket_id: str) -> Optional[Dict]:
        return self.tickets.get(ticket_id)
    
    def get_user_tickets(self, user_id: int) -> List[Dict]:
        return [t for t in self.tickets.values() if t["user_id"] == user_id and t["status"] == "open"]
    
    def get_all_tickets(self) -> Dict:
        return self.tickets
    
    def update_config(self, key: str, value: any):
        self.config[key] = value
        self._save_config()
    
    def get_config(self, key: str) -> any:
        return self.config.get(key)
    
    def save_panel(self, panel_id: str, panel_data: dict):
        self.panels[panel_id] = panel_data
        self._save_panels()
    
    def get_panel(self, panel_id: str) -> Optional[Dict]:
        return self.panels.get(panel_id)
    
    def get_all_panels(self) -> Dict:
        return self.panels
    
    def delete_panel(self, panel_id: str):
        if panel_id in self.panels:
            del self.panels[panel_id]
            self._save_panels()
    
    def get_ticket_stats(self) -> Dict:
        total = len(self.tickets)
        open_tickets = len([t for t in self.tickets.values() if t["status"] == "open"])
        closed_tickets = len([t for t in self.tickets.values() if t["status"] == "closed"])
        
        # Tickets by panel
        by_panel = {}
        for ticket in self.tickets.values():
            panel_id = ticket.get("panel_id", "unknown")
            by_panel[panel_id] = by_panel.get(panel_id, 0) + 1
        
        return {
            "total": total,
            "open": open_tickets,
            "closed": closed_tickets,
            "by_panel": by_panel
        }

db = TicketDatabase()
