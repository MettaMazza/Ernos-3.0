import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger("Cog.Stop")


class StopCommand(commands.Cog):
    """
    /stop or !stop — Interrupt Ernos while he's processing your message.

    Infrastructure only: signals cancellation to the CognitionEngine
    via an asyncio.Event. The actual user-facing response is generated
    by the cognitive pipeline (_generate_cancel_response), not hardcoded here.
    """
    def __init__(self, bot):
        self.bot = bot

    async def _do_stop(self, user_id: str) -> bool:
        """Signal cancellation. Returns True if there was an active process."""
        engine = getattr(self.bot, 'cognition', None)
        if not engine:
            return False
        return engine.request_cancel(user_id)

    # ─── Slash command (/stop) ───
    @app_commands.command(
        name="stop",
        description="Stop Ernos from processing your current message"
    )
    async def stop_slash(self, interaction: discord.Interaction):
        """Cancel the user's in-flight cognition task (slash command)."""
        cancelled = await self._do_stop(str(interaction.user.id))
        # Minimal infrastructure ack — the cognitive pipeline generates the real response
        if cancelled:
            logger.info(f"Stop: Cancelled processing for user {interaction.user.id}")
            await interaction.response.send_message("⏹️", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing active to stop.", ephemeral=True)

    # ─── Prefix command (!stop or /stop) ───
    @commands.command(name="stop")
    async def stop_prefix(self, ctx: commands.Context):
        """Cancel the user's in-flight cognition task (prefix command)."""
        cancelled = await self._do_stop(str(ctx.author.id))
        if cancelled:
            logger.info(f"Stop: Cancelled processing for user {ctx.author.id}")
            await ctx.message.add_reaction("⏹️")
        # If nothing active, silently ignore — no hardcoded reply


async def setup(bot):
    await bot.add_cog(StopCommand(bot))
