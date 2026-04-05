import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
from database import db
import json

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="create_ticket")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TicketModal()
        await interaction.response.send_modal(modal)

class TicketModal(discord.ui.Modal, title="Create Support Ticket"):
    topic = discord.ui.TextInput(
        label="Issue Topic",
        placeholder="Brief description of your issue...",
        required=True,
        max_length=100
    )
    
    description = discord.ui.TextInput(
        label="Description",
        placeholder="Please provide details about your issue...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category_id = db.get_config("ticket_category_id")
        category = guild.get_channel(category_id) if category_id else None
        
        if not category:
            category = await guild.create_category("Tickets")
            db.update_config("ticket_category_id", category.id)
        
        ticket_number = len([c for c in category.channels if isinstance(c, discord.TextChannel)]) + 1
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
        db.create_ticket(ticket_id, interaction.user.id, channel.id, self.topic.value)
        
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_number}",
            description=f"**Topic:** {self.topic.value}\n**Description:** {self.description.value}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value="Open", inline=True)
        embed.add_field(name="Created by", value=interaction.user.mention, inline=True)
        
        view = TicketControls(ticket_id)
        await channel.send(embed=embed, view=view)
        await channel.send(f"{interaction.user.mention} Support team will assist you shortly!")
        
        await interaction.response.send_message(f"Ticket created! Check {channel.mention}", ephemeral=True)
        
        # Log to log channel
        log_channel_id = db.get_config("log_channel_id")
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="Ticket Created",
                    description=f"Ticket #{ticket_number} created by {interaction.user.mention}",
                    color=discord.Color.green()
                )
                await log_channel.send(embed=log_embed)

class TicketControls(discord.ui.View):
    def __init__(self, ticket_id: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Closing ticket in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        
        ticket_data = db.get_ticket(self.ticket_id)
        if ticket_data:
            channel = interaction.guild.get_channel(ticket_data["channel_id"])
            if channel:
                await channel.send("Ticket is being closed...")
                await asyncio.sleep(2)
                await channel.delete()
            
            db.close_ticket(self.ticket_id)
            
            # Log closure
            log_channel_id = db.get_config("log_channel_id")
            if log_channel_id:
                log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = discord.Embed(
                        title="Ticket Closed",
                        description=f"Ticket closed by {interaction.user.mention}",
                        color=discord.Color.red()
                    )
                    await log_channel.send(embed=embed)
            
            try:
                user = await bot.fetch_user(ticket_data["user_id"])
                if user:
                    await user.send(f"Your ticket has been closed by {interaction.user.name}")
            except:
                pass

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    guild = bot.get_guild(GUILD_ID)
    if guild:
        print(f'Connected to guild: {guild.name}')
    
    # Add persistent view
    bot.add_view(TicketView())
    
    # Setup commands
    await setup_commands()

async def setup_commands():
    @bot.command(name="setup_ticket")
    @commands.has_permissions(administrator=True)
    async def setup_ticket(ctx):
        """Setup ticket system in current channel"""
        embed = discord.Embed(
            title="🎫 Support Ticket System",
            description="Click the button below to create a support ticket. Our team will assist you as soon as possible!",
            color=discord.Color.blue()
        )
        view = TicketView()
        await ctx.send(embed=embed, view=view)
        await ctx.send("Ticket system setup complete!", delete_after=5)
    
    @bot.command(name="set_support_role")
    @commands.has_permissions(administrator=True)
    async def set_support_role(ctx, role: discord.Role):
        """Set the support role for ticket access"""
        db.update_config("support_role_id", role.id)
        await ctx.send(f"Support role set to {role.mention}")
    
    @bot.command(name="set_log_channel")
    @commands.has_permissions(administrator=True)
    async def set_log_channel(ctx, channel: discord.TextChannel):
        """Set the log channel for ticket events"""
        db.update_config("log_channel_id", channel.id)
        await ctx.send(f"Log channel set to {channel.mention}")
    
    @bot.command(name="ticket_stats")
    @commands.has_permissions(administrator=True)
    async def ticket_stats(ctx):
        """View ticket statistics"""
        tickets = db.get_all_tickets()
        open_tickets = [t for t in tickets.values() if t["status"] == "open"]
        closed_tickets = [t for t in tickets.values() if t["status"] == "closed"]
        
        embed = discord.Embed(title="Ticket Statistics", color=discord.Color.green())
        embed.add_field(name="Total Tickets", value=len(tickets), inline=True)
        embed.add_field(name="Open Tickets", value=len(open_tickets), inline=True)
        embed.add_field(name="Closed Tickets", value=len(closed_tickets), inline=True)
        await ctx.send(embed=embed)

async def main():
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
