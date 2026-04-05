import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from database import db
from datetime import datetime

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

class DynamicTicketView(discord.ui.View):
    def __init__(self, panel_id: str, panel_data: dict):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        self.panel_data = panel_data
        
        # Add buttons based on panel configuration
        for button_data in panel_data.get('buttons', []):
            if button_data.get('type') == 'button' or 'label' in button_data:
                self.add_item(DynamicButton(panel_id, button_data))
        
        # Add dropdown if configured
        if panel_data.get('dropdown') and panel_data['dropdown'].get('options'):
            self.add_item(DynamicDropdown(panel_id, panel_data['dropdown']))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Check if user has reached max tickets
        user_tickets = db.get_user_tickets(interaction.user.id)
        max_tickets = db.get_config('max_tickets_per_user')
        
        if len(user_tickets) >= max_tickets:
            await interaction.response.send_message(
                f"You have reached the maximum limit of {max_tickets} open tickets. Please close existing tickets first.",
                ephemeral=True
            )
            return False
        return True

class DynamicButton(discord.ui.Button):
    def __init__(self, panel_id: str, button_data: dict):
        style_map = {
            'primary': discord.ButtonStyle.primary,
            'secondary': discord.ButtonStyle.secondary,
            'success': discord.ButtonStyle.success,
            'danger': discord.ButtonStyle.danger
        }
        style = style_map.get(button_data.get('style', 'primary'), discord.ButtonStyle.primary)
        
        super().__init__(
            label=button_data.get('label', 'Support'),
            style=style,
            custom_id=f"{panel_id}_{button_data.get('id', 'btn')}",
            emoji=button_data.get('emoji', '🎫'),
            row=button_data.get('row', 0)
        )
        self.panel_id = panel_id
        self.category = button_data.get('category', 'General')
        self.modal_title = button_data.get('modal_title', 'Create Support Ticket')
    
    async def callback(self, interaction: discord.Interaction):
        modal = TicketModal(self.panel_id, self.category, self.modal_title)
        await interaction.response.send_modal(modal)

class DynamicDropdown(discord.ui.Select):
    def __init__(self, panel_id: str, dropdown_data: dict):
        options = []
        for option in dropdown_data.get('options', []):
            options.append(
                discord.SelectOption(
                    label=option.get('label', 'Option'),
                    description=option.get('description', ''),
                    emoji=option.get('emoji', '📁'),
                    value=option.get('value', 'category')
                )
            )
        
        super().__init__(
            placeholder=dropdown_data.get('placeholder', 'Select ticket category'),
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"{panel_id}_dropdown"
        )
        self.panel_id = panel_id
        self.dropdown_data = dropdown_data
    
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        option_data = next((opt for opt in self.dropdown_data['options'] if opt['value'] == selected), None)
        
        if option_data:
            modal = TicketModal(
                self.panel_id, 
                option_data.get('label', 'Support'), 
                option_data.get('modal_title', f"{option_data.get('label', 'Support')} Support")
            )
            await interaction.response.send_modal(modal)

class TicketModal(discord.ui.Modal):
    def __init__(self, panel_id: str, category: str, title: str):
        super().__init__(title=title[:45])  # Discord modal title limit
        self.panel_id = panel_id
        self.category = category
        
        self.topic = discord.ui.TextInput(
            label="Issue Topic",
            placeholder="Brief description of your issue...",
            required=True,
            max_length=100
        )
        
        self.description = discord.ui.TextInput(
            label="Description",
            placeholder="Please provide details about your issue...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        
        self.add_item(self.topic)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category_id = db.get_config("ticket_category_id")
        category = guild.get_channel(category_id) if category_id else None
        
        if not category:
            category = await guild.create_category("Tickets")
            db.update_config("ticket_category_id", category.id)
        
        ticket_number = len([c for c in category.channels if isinstance(c, discord.TextChannel) and f"ticket-{interaction.user.name}" in c.name.lower()]) + 1
        
        channel_name = f"ticket-{interaction.user.name}-{ticket_number}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        support_role_id = db.get_config("support_role_id")
        if support_role_id:
            support_role = guild.get_role(support_role_id)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await category.create_text_channel(channel_name, overwrites=overwrites)
        
        ticket_id = f"{interaction.user.id}_{ticket_number}"
        db.create_ticket(ticket_id, interaction.user.id, channel.id, self.topic.value, self.panel_id)
        
        embed_color = int(db.get_config('default_embed_color', '#5865F2').lstrip('#'), 16)
        
        embed = discord.Embed(
            title=f"🎫 Ticket: {self.category}",
            description=f"**Topic:** {self.topic.value}\n\n**Description:** {self.description.value}",
            color=embed_color,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Status", value="🟢 Open", inline=True)
        embed.add_field(name="Category", value=self.category, inline=True)
        embed.add_field(name="Created by", value=interaction.user.mention, inline=True)
        embed.set_footer(text=f"Ticket ID: {ticket_id}")
        
        view = TicketControls(ticket_id)
        await channel.send(embed=embed, view=view)
        await channel.send(f"{interaction.user.mention} Support team will assist you shortly!")
        
        await interaction.response.send_message(f"✅ Ticket created! Check {channel.mention}", ephemeral=True)
        
        # Log to log channel
        log_channel_id = db.get_config("log_channel_id")
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="📫 Ticket Created",
                    description=f"**User:** {interaction.user.mention}\n**Category:** {self.category}\n**Channel:** {channel.mention}",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                await log_channel.send(embed=log_embed)

class TicketControls(discord.ui.View):
    def __init__(self, ticket_id: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", row=0)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏳ Closing ticket in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        
        ticket_data = db.get_ticket(self.ticket_id)
        if ticket_data:
            channel = interaction.guild.get_channel(ticket_data["channel_id"])
            
            transcript = []
            if channel:
                async for message in channel.history(limit=200):
                    transcript.append({
                        "author": message.author.name,
                        "content": message.content,
                        "timestamp": message.created_at.isoformat()
                    })
            
            db.close_ticket(self.ticket_id, transcript)
            
            if channel:
                await channel.send("🔒 Ticket is being closed...")
                await asyncio.sleep(2)
                await channel.delete()
            
            try:
                user = await interaction.client.fetch_user(ticket_data["user_id"])
                if user:
                    embed = discord.Embed(
                        title="Ticket Closed",
                        description=f"Your ticket has been closed by {interaction.user.name}",
                        color=discord.Color.blue()
                    )
                    await user.send(embed=embed)
            except:
                pass
            
            await interaction.followup.send("Ticket closed successfully!", ephemeral=True)

async def setup_bot_commands(bot_instance):
    """Setup bot commands"""
    
    @bot_instance.command(name="setup_ticket")
    @commands.has_permissions(administrator=True)
    async def setup_ticket(ctx):
        """Setup ticket system in current channel"""
        embed = discord.Embed(
            title="🎫 Support Ticket System",
            description="Click the button below to create a support ticket. Our team will assist you as soon as possible!",
            color=discord.Color.blue()
        )
        # Create a default view if no panel exists
        from bot import DynamicTicketView
        panels = db.get_all_panels()
        if panels:
            first_panel_id = list(panels.keys())[0]
            view = DynamicTicketView(first_panel_id, panels[first_panel_id])
        else:
            # Create default view
            default_panel = {
                'embed_title': 'Support Tickets',
                'embed_description': 'Click the button below to create a ticket',
                'buttons': [{'label': 'Support', 'style': 'primary', 'emoji': '🎫', 'category': 'General'}]
            }
            view = DynamicTicketView('default', default_panel)
        
        await ctx.send(embed=embed, view=view)
        await ctx.send("Ticket system setup complete!", delete_after=5)

async def on_ready_handler(bot_instance):
    """Handle bot ready event"""
    print(f'✅ {bot_instance.user} has connected to Discord!')
    guild = bot_instance.get_guild(GUILD_ID)
    if guild:
        print(f'📡 Connected to guild: {guild.name}')
    
    # Load all panels and register views
    for panel_id, panel_data in db.get_all_panels().items():
        bot_instance.add_view(DynamicTicketView(panel_id, panel_data))
        print(f"Loaded panel: {panel_id}")
