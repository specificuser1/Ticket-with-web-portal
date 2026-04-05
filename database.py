import json
import asyncio
from typing import Dict, List, Optional

class TicketDatabase:
    def __init__(self):
        self.tickets_file = "tickets.json"
        self.config_file = "config.json"
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
            # Convert category_id to int if it exists
            if 'category_id' in self.config and self.config['category_id']:
                self.config['category_id'] = int(self.config['category_id'])
        except FileNotFoundError:
            self.config = {
                "ticket_category_id": None,
                "support_role_id": None,
                "log_channel_id": None
            }
    
    def _save_tickets(self):
        with open(self.tickets_file, 'w') as f:
            json.dump(self.tickets, f, indent=4)
    
    def _save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
    
    def create_ticket(self, ticket_id: str, user_id: int, channel_id: int, topic: str):
        self.tickets[ticket_id] = {
            "user_id": user_id,
            "channel_id": channel_id,
            "topic": topic,
            "status": "open",
            "created_at": str(asyncio.get_event_loop().time())
        }
        self._save_tickets()
    
    def close_ticket(self, ticket_id: str):
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["status"] = "closed"
            self._save_tickets()
    
    def get_ticket(self, ticket_id: str) -> Optional[Dict]:
        return self.tickets.get(ticket_id)
    
    def get_user_tickets(self, user_id: int) -> List[Dict]:
        return [t for t in self.tickets.values() if t["user_id"] == user_id]
    
    def get_all_tickets(self) -> Dict:
        return self.tickets
    
    def update_config(self, key: str, value: any):
        self.config[key] = value
        self._save_config()
    
    def get_config(self, key: str) -> any:
        return self.config.get(key)

db = TicketDatabase()
