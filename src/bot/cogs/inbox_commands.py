import discord
from discord.ext import commands
from discord import app_commands
import logging

from src.memory.inbox import InboxManager

logger = logging.getLogger("Cog.Inbox")


class InboxCommands(commands.Cog):
    """
    /inbox commands — DM only.
    
    Users can check proactive messages from personas,
    set per-persona notification priority, and clear their inbox.
    """
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="inbox", description="Check your message inbox from AI personas")
    async def inbox_view(self, interaction: discord.Interaction):
        """Show inbox summary with unread counts."""
        if not isinstance(interaction.channel, discord.DMChannel):
            await interaction.response.send_message(
                "🔒 Inbox is only available in DMs.", ephemeral=True
            )
            return
        
        uid = interaction.user.id
        summary = InboxManager.get_inbox_summary(uid)
        
        # Get unread messages (last 10)
        unread = InboxManager.get_unread(uid)
        
        if not unread:
            await interaction.response.send_message(summary)
            return
        
        lines = [summary, ""]
        for msg in unread[-10:]:
            ts = msg["timestamp"][:16].replace("T", " ")
            lines.append(f"**{msg['persona']}** ({ts}):")
            lines.append(f"> {msg['content'][:200]}")
            lines.append("")
        
        if len(unread) > 10:
            lines.append(f"*...and {len(unread) - 10} more. Use `/inbox_read <persona>` to see all.*")
        
        lines.append("\n*Use `/inbox_clear` to mark all as read.*")
        
        # Mark displayed messages as read
        for msg in unread[-10:]:
            InboxManager.mark_read(uid, msg["id"])
        
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="inbox_read", description="Read messages from a specific persona")
    @app_commands.describe(persona="Which persona's messages to read")
    async def inbox_read(self, interaction: discord.Interaction, persona: str):
        """Show messages from a specific persona."""
        if not isinstance(interaction.channel, discord.DMChannel):
            await interaction.response.send_message(
                "🔒 Inbox is only available in DMs.", ephemeral=True
            )
            return
        
        uid = interaction.user.id
        messages = InboxManager.get_unread(uid, persona=persona)
        
        if not messages:
            await interaction.response.send_message(
                f"📭 No unread messages from **{persona}**."
            )
            return
        
        lines = [f"📬 **Messages from {persona}:**\n"]
        for msg in messages[-15:]:
            ts = msg["timestamp"][:16].replace("T", " ")
            lines.append(f"**{ts}:**")
            lines.append(f"> {msg['content'][:300]}")
            lines.append("")
            InboxManager.mark_read(uid, msg["id"])
        
        if len(messages) > 15:
            lines.append(f"*Showing latest 15 of {len(messages)}.*")
        
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="inbox_priority", description="Set notification priority for a persona")
    @app_commands.describe(
        persona="Persona name",
        level="Priority level: notify (DM ping), normal (silent), mute (block)"
    )
    @app_commands.choices(level=[
        app_commands.Choice(name="🔔 Notify (DM me when they message)", value="notify"),
        app_commands.Choice(name="📬 Normal (queue silently)", value="normal"),
        app_commands.Choice(name="🔇 Mute (block messages)", value="mute"),
    ])
    async def inbox_priority(self, interaction: discord.Interaction, persona: str, level: app_commands.Choice[str]):
        """Set notification priority for a persona."""
        if not isinstance(interaction.channel, discord.DMChannel):
            await interaction.response.send_message(
                "🔒 Inbox is only available in DMs.", ephemeral=True
            )
            return
        
        result = InboxManager.set_priority(interaction.user.id, persona, level.value)
        await interaction.response.send_message(result)

    @app_commands.command(name="inbox_clear", description="Mark all inbox messages as read")
    async def inbox_clear(self, interaction: discord.Interaction):
        """Clear all unread messages."""
        if not isinstance(interaction.channel, discord.DMChannel):
            await interaction.response.send_message(
                "🔒 Inbox is only available in DMs.", ephemeral=True
            )
            return
        
        count = InboxManager.mark_all_read(interaction.user.id)
        if count:
            await interaction.response.send_message(f"✅ Marked {count} message{'s' if count != 1 else ''} as read.")
        else:
            await interaction.response.send_message("📭 No unread messages to clear.")


async def setup(bot):
    await bot.add_cog(InboxCommands(bot))
