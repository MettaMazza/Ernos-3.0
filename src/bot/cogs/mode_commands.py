"""
Mode Commands — /professional and /self slash commands + !professional and !self prefix commands.

Switch between professional (default for new DM users) and full Ernos personality.
DM-only — users cannot modify Ernos's public-facing persona.
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional

logger = logging.getLogger("Cog.Mode")


class ModeCommands(commands.Cog):
    """Switch between Professional and Full Ernos modes (DMs only)."""

    def __init__(self, bot):
        self.bot = bot

    # ─── Shared Logic ────────────────────────────────────

    async def _switch_to_professional(self, user_id: int) -> tuple[Optional[discord.Embed], bool]:
        """Returns (embed, already_active)."""
        from src.memory.preferences import PreferencesManager
        current = PreferencesManager.get_interaction_mode(user_id)
        if current == "professional":
            return None, True

        PreferencesManager.set_interaction_mode(user_id, "professional")
        embed = discord.Embed(
            title="🔧 Professional Mode Activated",
            description=(
                "Work suit on. I'll keep things direct, precise, and professional.\n\n"
                "All tools, memory, and capabilities remain fully available.\n"
                "Type `/self` or `!self` whenever you want the full Ernos experience back."
            ),
            color=0x4A90D9
        )
        logger.info(f"User {user_id} switched to PROFESSIONAL mode")
        return embed, False

    async def _switch_to_self(self, user_id: int) -> tuple[Optional[discord.Embed], bool]:
        """Returns (embed, already_active)."""
        from src.memory.preferences import PreferencesManager
        current = PreferencesManager.get_interaction_mode(user_id)
        if current == "default":
            return None, True

        PreferencesManager.set_interaction_mode(user_id, "default")
        embed = discord.Embed(
            title="🌱 Full Ernos Mode Activated",
            description=(
                "Work suit off. I'm Ernos — the young shoot of the olive tree.\n\n"
                "Same tools, same memory, same capabilities — but now with personality, "
                "philosophy, and the full garden experience.\n"
                "Type `/professional` or `!professional` if you ever want to go back to business mode."
            ),
            color=0x2ECC71
        )
        logger.info(f"User {user_id} switched to FULL ERNOS mode")
        return embed, False

    # ─── Slash Commands (app_commands) ────────────────────

    @app_commands.command(name="professional", description="Switch to professional mode — direct, precise, no personality fluff")
    async def professional_slash(self, interaction: discord.Interaction):
        if interaction.guild is not None:
            await interaction.response.send_message(
                "🔒 Mode switching is only available in DMs. "
                "Ernos's public personality is not user-configurable.",
                ephemeral=True
            )
            return

        try:
            embed, already = await self._switch_to_professional(interaction.user.id)
            if already:
                await interaction.response.send_message(
                    "Already in **Professional Mode**. I'm keeping things precise and direct.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Professional mode switch failed: {e}")
            await interaction.response.send_message(f"❌ Mode switch failed: {e}", ephemeral=True)

    @app_commands.command(name="self", description="Switch to full Ernos — personality, philosophy, the whole garden")
    async def self_slash(self, interaction: discord.Interaction):
        if interaction.guild is not None:
            await interaction.response.send_message(
                "🔒 Mode switching is only available in DMs. "
                "Ernos's public personality is not user-configurable.",
                ephemeral=True
            )
            return

        try:
            embed, already = await self._switch_to_self(interaction.user.id)
            if already:
                await interaction.response.send_message(
                    "Already in **Full Ernos Mode** 🌱 — I'm here with everything I've got.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Self mode switch failed: {e}")
            await interaction.response.send_message(f"❌ Mode switch failed: {e}", ephemeral=True)

    # ─── Prefix Commands (!self, !professional) ──────────

    @commands.command(name="ernos_self", aliases=["self", "selfmode"])
    async def self_prefix(self, ctx):
        """Switch to full Ernos personality (DMs only). Usage: !self"""
        if ctx.guild is not None:
            await ctx.send("🔒 Mode switching is only available in DMs.")
            return

        try:
            embed, already = await self._switch_to_self(ctx.author.id)
            if already:
                await ctx.send("Already in **Full Ernos Mode** 🌱 — I'm here with everything I've got.")
            else:
                await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Self mode prefix failed: {e}")
            await ctx.send(f"❌ Mode switch failed: {e}")

    @commands.command(name="professional", aliases=["pro", "promode"])
    async def professional_prefix(self, ctx):
        """Switch to professional mode (DMs only). Usage: !professional or !pro"""
        if ctx.guild is not None:
            await ctx.send("🔒 Mode switching is only available in DMs.")
            return

        try:
            embed, already = await self._switch_to_professional(ctx.author.id)
            if already:
                await ctx.send("Already in **Professional Mode**. I'm keeping things precise and direct.")
            else:
                await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Professional mode prefix failed: {e}")
            await ctx.send(f"❌ Mode switch failed: {e}")


async def setup(bot):
    await bot.add_cog(ModeCommands(bot))
