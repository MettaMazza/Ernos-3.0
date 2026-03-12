
import discord
from discord import app_commands
from discord.ext import commands
import logging
from src.tools import skill_admin_tools
from src.tools.skill_forge_tool import propose_skill

logger = logging.getLogger("Cogs.SkillCommands")

class SkillCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("SkillCommands Cog Initialized")

    @app_commands.command(name="approve_skill", description="Approve a pending skill proposal")
    @app_commands.describe(proposal="The name of the pending skill file", scope="CORE or User ID (defaults to CORE)")
    async def approve_skill_cmd(self, interaction: discord.Interaction, proposal: str, scope: str = "CORE"):
        """Approve a pending skill."""
        # Simple auth check (Owner or Admin)
        if not await self.bot.is_owner(interaction.user):
            # Also check if user has admin permissions in guild
            if not interaction.permissions.administrator:
                await interaction.response.send_message("❌ You do not have permission to approve Core skills.", ephemeral=True)
                return

        await interaction.response.defer()
        try:
            result = await skill_admin_tools.approve_skill(proposal, scope)
            await interaction.followup.send(result)
        except Exception as e:
            logger.error(f"Error in approve_skill_cmd: {e}")
            await interaction.followup.send(f"❌ Error: {e}")

    # Fallback Prefix Command (Instant)
    @commands.command(name="approve_skill")
    async def approve_skill_prefix(self, ctx, proposal: str, scope: str = "CORE"):
        """Approve a skill (Prefix command for immediate use)."""
        if not await self.bot.is_owner(ctx.author) and not ctx.author.guild_permissions.administrator:
            return await ctx.send("❌ Permission denied.")
            
        async with ctx.typing():
            try:
                result = await skill_admin_tools.approve_skill(proposal, scope)
                await ctx.send(result)
            except Exception as e:
                await ctx.send(f"❌ Error: {e}")

    @commands.command(name="list_proposals")
    async def list_proposals_prefix(self, ctx):
        """List proposals (Prefix command)."""
        async with ctx.typing():
            try:
                result = await skill_admin_tools.list_proposals()
                await ctx.send(result)
            except Exception as e:
                await ctx.send(f"❌ Error: {e}")

    @commands.command(name="list_proposals")
    async def list_proposals_prefix(self, ctx):
        """List proposals (Prefix command)."""
        async with ctx.typing():
            try:
                result = await skill_admin_tools.list_proposals()
                await ctx.send(result)
            except Exception as e:
                await ctx.send(f"❌ Error: {e}")

    @commands.command(name="schedule_skill")
    async def schedule_skill_prefix(self, ctx, skill: str, hour: int, minute: int):
        """Schedule a skill (Prefix command)."""
        # 1. Admin/Owner Bypass
        is_admin = (await self.bot.is_owner(ctx.author)) or (ctx.author.guild_permissions.administrator)
        
        # 2. DM Check for Non-Admins
        if not is_admin:
            if ctx.guild is not None:
                return await ctx.send("❌ You can only schedule skills in DMs to prevent public spam.")

        async with ctx.typing():
            try:
                # Pass user_id for per-user scoping and channel_id for routing
                result = await skill_admin_tools.schedule_skill(
                    skill, hour, minute, user_id=str(ctx.author.id), channel_id=str(ctx.channel.id)
                )
                await ctx.send(result)
            except Exception as e:
                await ctx.send(f"❌ Error: {e}")
    @app_commands.describe(skill="Name of the skill", hour="Hour (0-23)", minute="Minute (0-59)")
    async def schedule_skill_cmd(self, interaction: discord.Interaction, skill: str, hour: int, minute: int):
        """Schedule a daily skill task."""
        # 1. Admin/Owner Bypass
        is_admin = (await self.bot.is_owner(interaction.user)) or (interaction.permissions.administrator)
        
        # 2. DM Check for Non-Admins
        if not is_admin:
            # If not admin, MUST be in DM
            if interaction.guild is not None:
                await interaction.response.send_message("❌ You can only schedule skills in DMs to prevent public spam.", ephemeral=True)
                return

        await interaction.response.defer()
        try:
            # Pass user_id for per-user scoping and channel_id for routing
            result = await skill_admin_tools.schedule_skill(
                skill, hour, minute, user_id=str(interaction.user.id), channel_id=str(interaction.channel_id)
            )
            await interaction.followup.send(result)
        except Exception as e:
            logger.error(f"Error in schedule_skill_cmd: {e}")
            await interaction.followup.send(f"❌ Error: {e}")

    @app_commands.command(name="list_proposals", description="List pending skill proposals")
    async def list_proposals_cmd(self, interaction: discord.Interaction):
        """List current pending proposals."""
        await interaction.response.defer()
        try:
            result = await skill_admin_tools.list_proposals()
            await interaction.followup.send(result)
        except Exception as e:
             await interaction.followup.send(f"❌ Error: {e}")

    @app_commands.command(name="reload_skills", description="Force reload of skill registry")
    async def reload_skills_cmd(self, interaction: discord.Interaction):
        """Reload user and core skills."""
        if not await self.bot.is_owner(interaction.user) and not interaction.permissions.administrator:
             await interaction.response.send_message("❌ Permission denied.", ephemeral=True)
             return

        await interaction.response.defer()
        result = await skill_admin_tools.reload_skills()
        await interaction.followup.send(result)

async def setup(bot):
    await bot.add_cog(SkillCommands(bot))
    logger.info("SkillCommands Cog Loaded")
