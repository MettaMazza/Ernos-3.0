import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger("TapeCommands")

class TapeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="restore_tape", description="Restore your Cognitive Tape from a snapshot if Ernos gets stuck")
    async def restore_tape(self, interaction: discord.Interaction):
        # Prevent execution in DMs if missing permissions or context requires it
        if not interaction.guild:
            # We allow restoring in DMs as well since tapes are per-user.
            pass

        user_id = str(interaction.user.id)
        
        # Fast defer since file IO might take a moment
        await interaction.response.defer(ephemeral=True)

        try:
            # Get the hippocampus memory system
            hippocampus = getattr(self.bot, 'hippocampus', None)
            if not hippocampus:
                await interaction.followup.send("⚠️ Hippocampus subsystem is offline. Cannot access Cognitive Tape.")
                return

            # Grab the user's tape machine
            tape_machine = await hippocampus.get_tape(user_id=user_id, user_name=interaction.user.display_name)
            
            # Perform the restore
            success = tape_machine.restore_snapshot()
            
            if success:
                logger.info(f"Tape restored successfully for user {user_id}")
                await interaction.followup.send("✅ **Cognitive Tape Restored**\nYour tape has been successfully rolled back to the last stable snapshot. Ernos's memory and instructions for your session have been reset.")
            else:
                logger.warning(f"Tape restore failed for user {user_id} - no snapshot found")
                await interaction.followup.send("⚠️ **Restore Failed**\nNo valid snapshot was found for your Cognitive Tape. The tape remains unchanged.")

        except Exception as e:
            logger.error(f"Error restoring tape for user {user_id}: {e}", exc_info=True)
            await interaction.followup.send(f"❌ **Critical Error**\nAn error occurred while attempting to restore your tape: `{str(e)}`")

async def setup(bot):
    await bot.add_cog(TapeCommands(bot))
