
import discord
from discord.ext import commands
import logging

logger = logging.getLogger("SiloCommands")

class SiloCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="leave", description="Exit the current Silo (Thread).")
    async def leave_silo(self, ctx):
        """Exit the current Silo (Thread)."""
        # 1. Check if we are in a Thread
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("❌ You can only use `/leave` inside a Silo (Thread).", ephemeral=True)
            return

        # 2. Check if it's a managed Silo
        if ctx.channel.id not in self.bot.silo_manager.active_silos:
            # Maybe it's a private thread but not tracked? 
            # Allow leaving anyway if it's a private thread type
            if ctx.channel.type != discord.ChannelType.private_thread:
                 await ctx.send("❌ This is not a Silo.", ephemeral=True)
                 return
        
        # 3. Remove User
        try:
            await ctx.channel.remove_user(ctx.author)
        except Exception as e:
            logger.error(f"Failed to remove user from Silo: {e}")
            await ctx.send(f"⚠️ Failed to leave: {e}", ephemeral=True)

    @commands.Cog.listener()
    async def on_thread_member_remove(self, thread, member):
        """Monitor Silo departures for auto-deletion."""
        if thread.id in self.bot.silo_manager.active_silos:
             # Trigger check
             # Note: thread.member_count might be cached?
             # Let's force fetch? Thread object passed might be partial?
             # Best to fetch the thread again to be safe.
             
             # Wait a beat for cache update?
             # await asyncio.sleep(1) 
             # Actually, let's just use the manager
             await self.bot.silo_manager.check_empty_silo(thread)

async def setup(bot):
    await bot.add_cog(SiloCommands(bot))
