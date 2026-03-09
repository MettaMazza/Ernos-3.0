"""
Relationship Commands — User-facing Discord slash commands for outreach controls.

Users can set per-persona outreach policy, frequency, and view their relationship summary.
Supports: public, private, both, or none — independently for each persona.
"""
import discord
from discord import app_commands
from discord.ext import commands
from src.memory.relationships import RelationshipManager


# Active personas for autocomplete
PERSONA_NAMES = [
    "ernos", "echo", "iris-keeper", "lucid", "solance",
    "threshold", "gemini3", "axiom",
    "forge", "prism", "cipher", "meridian", "vertex", "drift", "tessera",
    "crucible", "keel"
]


class RelationshipCommands(commands.Cog):
    """
    /outreach_policy, /outreach_frequency, /relationship_status

    Gives users direct control over how each persona reaches out to them.
    Settings are independent per persona and securely scoped.
    """

    def __init__(self, bot):
        self.bot = bot

    async def persona_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for persona names."""
        choices = [
            app_commands.Choice(name=f"🎭 {p.title()}", value=p)
            for p in PERSONA_NAMES
            if current.lower() in p.lower()
        ]
        # Add "all" option
        if "all" in f"all".lower() or not current:
            choices.insert(0, app_commands.Choice(name="🌐 All Personas (default)", value="_default"))
        return choices[:25]

    @app_commands.command(name="outreach_policy", description="Control how a persona reaches out to you")
    @app_commands.describe(
        setting="Where outreach messages go",
        persona="Which persona to configure (default = all)"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="🔒 Private — Messages go to your DM inbox", value="private"),
        app_commands.Choice(name="📢 Public — Persona can check in via public channel", value="public"),
        app_commands.Choice(name="🔄 Both — Deliver to public AND private", value="both"),
        app_commands.Choice(name="🚫 None — Persona never reaches out to you", value="none"),
    ])
    @app_commands.autocomplete(persona=persona_autocomplete)
    async def outreach_policy(self, interaction: discord.Interaction,
                              setting: app_commands.Choice[str],
                              persona: str = "_default"):
        """Set your outreach policy per persona."""
        uid = interaction.user.id
        result = RelationshipManager.set_outreach_policy(uid, setting.value, persona)
        await interaction.response.send_message(result, ephemeral=True)

    @app_commands.command(name="outreach_frequency", description="Control how often a persona can reach out")
    @app_commands.describe(
        setting="Maximum frequency for proactive messages",
        persona="Which persona to configure (default = all)"
    )
    @app_commands.choices(setting=[
        app_commands.Choice(name="🐢 Low — At most once per 24 hours", value="low"),
        app_commands.Choice(name="⚖️ Medium — At most once per 12 hours", value="medium"),
        app_commands.Choice(name="⚡ High — At most once per 3 hours", value="high"),
        app_commands.Choice(name="♾️ Unlimited — No cooldown", value="unlimited"),
    ])
    @app_commands.autocomplete(persona=persona_autocomplete)
    async def outreach_frequency(self, interaction: discord.Interaction,
                                 setting: app_commands.Choice[str],
                                 persona: str = "_default"):
        """Set your outreach frequency per persona."""
        uid = interaction.user.id
        result = RelationshipManager.set_outreach_frequency(uid, setting.value, persona)
        await interaction.response.send_message(result, ephemeral=True)

    @app_commands.command(name="relationship_status", description="View your relationship summary and outreach settings")
    async def relationship_status(self, interaction: discord.Interaction):
        """Show the user's relationship summary and per-persona outreach settings."""
        uid = interaction.user.id

        # Get relationship summary
        summary = RelationshipManager.get_relationship_summary(uid)

        # Get all persona outreach settings
        all_settings = RelationshipManager.get_outreach_settings(uid)

        embed = discord.Embed(
            title=f"🤝 Relationship with {interaction.user.display_name}",
            color=0x5865F2
        )

        embed.add_field(
            name="📊 Relationship Summary",
            value=summary,
            inline=False
        )

        # Build per-persona settings display
        if all_settings:
            policy_emoji = {"public": "📢", "private": "🔒", "both": "🔄", "none": "🚫"}
            freq_emoji = {"low": "🐢", "medium": "⚖️", "high": "⚡", "unlimited": "♾️"}

            lines = []
            for persona, s in sorted(all_settings.items()):
                p = s.get("policy", "private")
                f = s.get("frequency", "medium")
                display_name = "All (default)" if persona == "_default" else persona.title()
                lines.append(
                    f"{policy_emoji.get(p, '❓')} **{display_name}**: "
                    f"{p} / {freq_emoji.get(f, '❓')} {f}"
                )

            embed.add_field(
                name="📤 Per-Persona Outreach",
                value="\n".join(lines) if lines else "No settings configured",
                inline=False
            )
        else:
            embed.add_field(
                name="📤 Outreach Settings",
                value="🔒 **Default**: private / ⚖️ medium",
                inline=False
            )

        embed.set_footer(text="Use /outreach_policy and /outreach_frequency with a persona name to configure individually")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(RelationshipCommands(bot))
