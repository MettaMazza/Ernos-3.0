"""
Admin Engine Cog — Engine switching, sync, and testing mode.

Split from admin.py per <300 line modularity standard.
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from config import settings

logger = logging.getLogger("AdminCogs")


class AdminEngine(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return ctx.author.id in settings.ADMIN_IDS

    @commands.hybrid_command(name="cloud", description="Switch to Cloud engine")
    async def switch_cloud(self, ctx):
        """Switch to Cloud engine."""
        success = self.bot.engine_manager.set_active_engine("cloud")
        if success:
            await ctx.send(f"Active Engine: **Cloud ({settings.OLLAMA_CLOUD_MODEL} + RAG)**")
        else:
            await ctx.send("Failed to switch to Cloud.")

    @commands.hybrid_command(name="local", description="Switch to Local engine")
    async def switch_local(self, ctx):
        """Switch to Local engine."""
        success = self.bot.engine_manager.set_active_engine("local")
        if success:
            await ctx.send(f"Active Engine: **Local ({settings.OLLAMA_LOCAL_MODEL} + RAG)**")
        else:
            await ctx.send("Failed to switch to Local.")

    @commands.hybrid_command(name="localsteer", description="Switch to Local Steering (Llama.cpp + Control Vectors)")
    async def switch_local_steer(self, ctx):
        """Switch to Local Steering (Llama.cpp + Control Vectors)."""
        success = self.bot.engine_manager.set_active_engine("LocalSteer")
        if success:
            await ctx.send("Active Engine: **Local Steering (Llama.cpp + Control Vectors)**")
        else:
            await ctx.send("Failed to switch to Local Steering.")

    @commands.command(name="sync")
    async def sync_commands(self, ctx):
        """Sync slash commands globally (may take up to 1 hour)."""
        synced = await self.bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} commands globally. May take up to 1 hour to appear.")

    @commands.command(name="syncguild")
    async def sync_guild_commands(self, ctx):
        """Sync slash commands to THIS guild only (instant)."""
        guild = ctx.guild
        if not guild:
            guild_id = getattr(settings, 'GUILD_ID', None)
            if guild_id:
                guild = self.bot.get_guild(guild_id)
            if not guild:
                target_ch = self.bot.get_channel(settings.TARGET_CHANNEL_ID)
                if target_ch and target_ch.guild:
                    guild = target_ch.guild
            if not guild:
                await ctx.send("❌ Could not determine guild. Run from a server channel.")
                return
        self.bot.tree.copy_global_to(guild=guild)
        synced = await self.bot.tree.sync(guild=guild)
        await ctx.send(f"✅ Synced {len(synced)} commands to **{guild.name}** (INSTANT).")

    @commands.hybrid_command(name="testing", description="Toggle testing mode — only admins can interact when enabled")
    async def toggle_testing(self, ctx):
        """Toggle testing mode on/off. When on, Ernos ignores all non-admin messages."""
        settings.TESTING_MODE = not settings.TESTING_MODE
        state = "🔧 **ON** — Only admins can interact" if settings.TESTING_MODE else "🌿 **OFF** — Everyone can interact"
        logger.info(f"Testing mode toggled to {settings.TESTING_MODE} by {ctx.author.id}")
        await ctx.send(f"Testing Mode: {state}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminEngine(bot))
