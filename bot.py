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
            if button_data.get('type') == 'button':
                self.add_item(DynamicButton(panel_id, button_data))
        
        # Add dropdown if configured
        if panel_data.get('dropdown'):
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
        super().__init__(
            label=button_data['label'],
            style=getattr(discord.ButtonStyle, button_data.get('style', 'primary')),
            custom_id=f"{panel_id}_{button_data['id']}",
            emoji=button_data.get('emoji'),
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
                    label=option['label'],
                    description=option.get('description'),
                    emoji=option.get('emoji'),
                    value=option['value']
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
        # Find selected option data
        option_data = next((opt for opt in self.dropdown_data['options'] if opt['value'] == selected), None)
        
        if option_data:
            modal = TicketModal(
                self.panel_id, 
                option_data['label'], 
                option_data.get('modal_title', f"{option_data['label']} Support")
            )
            await interaction.response.send_modal(modal)

class TicketModal(discord.ui.Modal):
    def __init__(self, panel_id: str, category: str, title: str):
        super().__init__(title=title)
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
        
        # Check existing tickets
        existing_tickets = [c for c in category.channels if f"ticket-{interaction.user.name}" in c.name.lower()]
        ticket_number = len(existing_tickets) + 1
        
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
        
        # Get embed settings from panel
        panel_data = db.get_panel(self.panel_id)
        embed_color = int(panel_data.get('embed_color', '#5865F2').lstrip('#'), 16) if panel_data else 0x5865F2
        
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
        
        # Send welcome message if configured
        welcome_msg = panel_data.get('welcome_message') if panel_data else None
        if welcome_msg:
            await channel.send(welcome_msg)
        
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
            
            # Collect transcript
            transcript = []
            if channel:
                async for message in channel.history(limit=200):
                    transcript.append({
                        "author": message.author.name,
                        "content": message.content,
                        "timestamp": message.created_at.isoformat()
                    })
            
            db.close_ticket(self.ticket_id, transcript)
            
            # Save transcript to channel
            transcript_channel_id = db.get_config("transcript_channel_id")
            if transcript_channel_id and channel:
                transcript_channel = interaction.guild.get_channel(transcript_channel_id)
                if transcript_channel:
                    transcript_text = f"**Ticket Transcript - {self.ticket_id}**\n\n"
                    for msg in transcript[-50:]:  # Last 50 messages
                        transcript_text += f"[{msg['timestamp']}] {msg['author']}: {msg['content']}\n"
                    
                    if len(transcript_text) > 1900:
                        transcript_text = transcript_text[:1900] + "..."
                    
                    await transcript_channel.send(f"📜 **Ticket Closed:** {self.ticket_id}\n```{transcript_text}```")
            
            if channel:
                await channel.send("🔒 Ticket is being closed...")
                await asyncio.sleep(2)
                await channel.delete()
            
            # Log closure
            log_channel_id = db.get_config("log_channel_id")
            if log_channel_id:
                log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="🔒 Ticket Closed",
                        description=f"Ticket closed by {interaction.user.mention}",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    await log_channel.send(embed=embed)
            
            try:
                user = await bot.fetch_user(ticket_data["user_id"])
                if user:
                    embed = discord.Embed(
                        title="Ticket Closed",
                        description=f"Your ticket has been closed by {interaction.user.name}",
                        color=discord.Color.blue()
                    )
                    await user.send(embed=embed)
            except:
                pass
    
    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="✋", row=0)
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        support_role_id = db.get_config("support_role_id")
        if support_role_id:
            support_role = interaction.guild.get_role(support_role_id)
            if support_role not in interaction.user.roles:
                await interaction.response.send_message("❌ You don't have permission to claim tickets!", ephemeral=True)
                return
        
        await interaction.response.send_message(f"✅ Ticket claimed by {interaction.user.mention}", ephemeral=False)
        
        # Update embed to show claimed by
        channel = interaction.channel
        async for message in channel.history(limit=1):
            if message.embeds:
                embed = message.embeds[0]
                embed.add_field(name="Claimed by", value=interaction.user.mention, inline=True)
                await message.edit(embed=embed)
                break
    
    @discord.ui.button(label="Add Note", style=discord.ButtonStyle.secondary, emoji="📝", row=1)
    async def add_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NoteModal(self.ticket_id)
        await interaction.response.send_modal(modal)

class NoteModal(discord.ui.Modal, title="Add Staff Note"):
    note = discord.ui.TextInput(
        label="Note",
        placeholder="Add internal note for staff...",
        style=discord.TextStyle.paragraph,
        required=True
    )
    
    def __init__(self, ticket_id: str):
        super().__init__()
        self.ticket_id = ticket_id
    
    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📝 Staff Note",
            description=self.note.value,
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Added by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} has connected to Discord!')
    guild = bot.get_guild(GUILD_ID)
    if guild:
        print(f'📡 Connected to guild: {guild.name}')
    
    # Load all panels and register views
    for panel_id, panel_data in db.get_all_panels().items():
        if panel_data.get('channel_id'):
            channel = bot.get_channel(panel_data['channel_id'])
            if channel:
                bot.add_view(DynamicTicketView(panel_id, panel_data))

@bot.command(name="reload_panels")
@commands.has_permissions(administrator=True)
async def reload_panels(ctx):
    """Reload all ticket panels"""
    for panel_id, panel_data in db.get_all_panels().items():
        if panel_data.get('channel_id'):
            channel = ctx.guild.get_channel(panel_data['channel_id'])
            if channel:
                view = DynamicTicketView(panel_id, panel_data)
                await channel.send("🔄 Panels reloaded!", delete_after=5)
    
    await ctx.send("✅ All panels reloaded!")

async def main():
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
