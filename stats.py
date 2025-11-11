import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import json
import os
import re

class StatsBot:
    def __init__(self):
        self.intents = discord.Intents.all()
        self.bot = commands.Bot(command_prefix="!", intents=self.intents)
        self.is_running = False
        
        # Configuration
        self.config = {
            "listen_channel_id": 1307161175951147010,  # Channel to listen to
            "relay_channel_id": 1307182459544141896,    # Channel to relay to
            "stats_channel_id": None  # Channel to store/read stats from
        }
        
        # Stats tracking
        self.stats = {
            "total_servers_nuked": 0,
            "total_members_nuked": 0
        }
        self.stats_message_id = None  # ID of the message containing stats
        
        self.setup_events()
    
    async def load_stats_from_channel(self):
        """Load statistics from a channel message"""
        try:
            if not self.config.get("stats_channel_id"):
                print("⚠️ No stats channel configured")
                return
            
            stats_channel = self.bot.get_channel(self.config["stats_channel_id"])
            if not stats_channel:
                stats_channel = await self.bot.fetch_channel(self.config["stats_channel_id"])
            
            if not stats_channel:
                print(f"⚠️ Stats channel not found")
                return
            
            # First, look for the bot's own message
            bot_message = None
            other_message = None
            
            async for message in stats_channel.history(limit=10):
                if "Total servers nuked:" in message.content and "Total members nuked:" in message.content:
                    if message.author == self.bot.user:
                        bot_message = message
                        break  # Found bot's message, use it
                    elif other_message is None:
                        other_message = message  # Store first matching message as backup
            
            # Use bot's own message if found, otherwise use any matching message
            message_to_use = bot_message or other_message
            
            if message_to_use:
                # Parse the stats from the message
                match = re.search(r"Total members nuked: (\d+)", message_to_use.content)
                if match:
                    self.stats["total_members_nuked"] = int(match.group(1))
                
                match = re.search(r"Total servers nuked: (\d+)", message_to_use.content)
                if match:
                    self.stats["total_servers_nuked"] = int(match.group(1))
                
                self.stats_message_id = message_to_use.id
                
                if bot_message:
                    print(f"✅ Loaded stats from bot's own message: {self.stats['total_servers_nuked']} servers, {self.stats['total_members_nuked']} members")
                else:
                    print(f"✅ Loaded stats from existing message by {message_to_use.author.name}: {self.stats['total_servers_nuked']} servers, {self.stats['total_members_nuked']} members")
                    print(f"   Bot will create its own message to edit going forward")
                return
            
            # No stats message found, create initial one
            initial_message = (
                f"📊 **Cumulative Statistics**\n"
                f"Total members nuked: 0\n"
                f"Total servers nuked: 0"
            )
            msg = await stats_channel.send(initial_message)
            self.stats_message_id = msg.id
            print(f"✅ Created initial stats message in channel")
            
        except Exception as e:
            print(f"❌ Error loading stats from channel: {e}")
    
    async def save_stats_to_channel(self):
        """Save statistics to channel message"""
        try:
            if not self.config.get("stats_channel_id"):
                return
            
            stats_channel = self.bot.get_channel(self.config["stats_channel_id"])
            if not stats_channel:
                stats_channel = await self.bot.fetch_channel(self.config["stats_channel_id"])
            
            if not stats_channel:
                print(f"⚠️ Stats channel not found")
                return
            
            stats_message_content = (
                f"📊 **Cumulative Statistics**\n"
                f"Total members nuked: {self.stats['total_members_nuked']}\n"
                f"Total servers nuked: {self.stats['total_servers_nuked']}"
            )
            
            # Try to edit existing message, or create new one
            if self.stats_message_id:
                try:
                    message = await stats_channel.fetch_message(self.stats_message_id)
                    # Check if we can edit it (must be our own message)
                    if message.author == self.bot.user:
                        await message.edit(content=stats_message_content)
                        print(f"✅ Updated stats message (ID: {self.stats_message_id})")
                    else:
                        # Can't edit someone else's message, create our own
                        print(f"⚠️ Previous message was by {message.author.name}, creating bot's own message...")
                        msg = await stats_channel.send(stats_message_content)
                        self.stats_message_id = msg.id
                        print(f"✅ Created new bot message (ID: {self.stats_message_id})")
                except discord.NotFound:
                    # Message was deleted, create new one
                    print(f"⚠️ Previous message not found, creating new one...")
                    msg = await stats_channel.send(stats_message_content)
                    self.stats_message_id = msg.id
                except discord.Forbidden:
                    # No permission to edit, create new one
                    print(f"⚠️ No permission to edit, creating new message...")
                    msg = await stats_channel.send(stats_message_content)
                    self.stats_message_id = msg.id
            else:
                # No message ID, create new one
                msg = await stats_channel.send(stats_message_content)
                self.stats_message_id = msg.id
                print(f"✅ Created stats message (ID: {self.stats_message_id})")
            
        except Exception as e:
            print(f"❌ Error saving stats to channel: {e}")
    
    def update_config(self, config):
        """Update bot configuration"""
        self.config.update(config)
    
    def setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f"Stats Bot logged in as {self.bot.user}")
            print(f"Bot is in {len(self.bot.guilds)} servers")
            
            # Check if bot can access the listen channel
            listen_channel = self.bot.get_channel(self.config['listen_channel_id'])
            if listen_channel:
                print(f"✅ Listening on channel: #{listen_channel.name} in {listen_channel.guild.name}")
            else:
                print(f"⚠️ WARNING: Cannot access listen channel ID {self.config['listen_channel_id']}")
                print(f"   Make sure the bot is invited to the server with this channel!")
            
            # Check if bot can access the relay channel
            relay_channel = self.bot.get_channel(self.config['relay_channel_id'])
            if relay_channel:
                print(f"✅ Relaying to channel: #{relay_channel.name} in {relay_channel.guild.name}")
            else:
                print(f"⚠️ WARNING: Cannot access relay channel ID {self.config['relay_channel_id']}")
                print(f"   Make sure the bot is invited to the server with this channel!")
            
            # Check if bot can access the stats channel and load stats
            if self.config.get('stats_channel_id'):
                stats_channel = self.bot.get_channel(self.config['stats_channel_id'])
                if stats_channel:
                    print(f"✅ Stats channel: #{stats_channel.name} in {stats_channel.guild.name}")
                    await self.load_stats_from_channel()
                else:
                    print(f"⚠️ WARNING: Cannot access stats channel ID {self.config['stats_channel_id']}")
                    print(f"   Make sure the bot is invited to the server with this channel!")
            else:
                print(f"⚠️ No stats channel configured - stats will not persist")
            
            print(f"\nServers the bot is in:")
            for guild in self.bot.guilds:
                print(f"  - {guild.name} (ID: {guild.id})")
        
        @self.bot.event
        async def on_message(message):
            # Don't respond to own messages
            if message.author == self.bot.user:
                return
            
            # Check if message is from the listen channel
            if message.channel.id == self.config["listen_channel_id"]:
                await self.relay_message(message)
    
    async def relay_message(self, message):
        """Relay message to the relay channel"""
        try:
            # Try to get channel from cache first, then fetch if needed
            relay_channel = self.bot.get_channel(self.config["relay_channel_id"])
            if not relay_channel:
                try:
                    relay_channel = await self.bot.fetch_channel(self.config["relay_channel_id"])
                except Exception as e:
                    print(f"Failed to fetch relay channel: {e}")
                    return
            
            if not relay_channel:
                print(f"Relay channel {self.config['relay_channel_id']} not found")
                return
            
            # Only relay messages that match the SMITE_TRIGGERED format
            if message.content and message.content.startswith("SMITE_TRIGGERED"):
                # Parse the message: SMITE_TRIGGERED | Member Count: 50 | Triggered By: 745453478071238808
                match = re.match(r"SMITE_TRIGGERED \| Member Count: (\d+) \| Triggered By: (.+)", message.content)
                
                if match:
                    member_count = int(match.group(1))
                    triggered_by = match.group(2)
                    
                    # Update cumulative stats
                    self.stats["total_servers_nuked"] += 1
                    self.stats["total_members_nuked"] += member_count
                    
                    # Save stats to channel
                    await self.save_stats_to_channel()
                    
                    # Create the relay message with cumulative stats
                    relay_message = (
                        f"SMITE_TRIGGERED | Member Count: {member_count} | Triggered By: {triggered_by}\n"
                        f"Members nuked in this server: {member_count}\n"
                        f"Total members nuked: {self.stats['total_members_nuked']}\n"
                        f"Total servers nuked: {self.stats['total_servers_nuked']}"
                    )
                    
                    await relay_channel.send(relay_message)
                    print(f"✅ Relayed stats - Server #{self.stats['total_servers_nuked']}, {member_count} members")
                else:
                    print(f"Ignored message - incorrect format")
            else:
                print(f"Ignored message - not a SMITE_TRIGGERED message")
            
        except Exception as e:
            print(f"Error relaying message: {e}")
    
    def run(self, token):
        """Start the bot"""
        try:
            self.bot.run(token)
        except Exception as e:
            print(f"Error running stats bot: {e}")
    
    async def start(self, token):
        """Start the bot asynchronously"""
        try:
            await self.bot.start(token)
        except Exception as e:
            print(f"Error starting stats bot: {e}")
    
    async def stop(self):
        """Stop the bot"""
        try:
            await self.bot.close()
            print("Stats bot stopped")
        except Exception as e:
            print(f"Error stopping stats bot: {e}")

if __name__ == "__main__":
    # For testing purposes
    bot = StatsBot()
    token = input("Enter bot token: ")
    bot.run(token)
