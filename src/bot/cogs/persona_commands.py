import discord
from discord.ext import commands
from discord import app_commands
import logging

from src.memory.persona_session import PersonaSessionTracker
from src.memory.public_registry import PublicPersonaRegistry

logger = logging.getLogger("Cog.Persona")

# Personas restricted to Town Hall only — users cannot engage directly
TOWN_HALL_ONLY = {"hollow", "scald", "feral", "static", "glitch", "vex", "rot"}


class PersonaCommands(commands.Cog):
    """
    Persona commands — works in DMs (private) AND guild channels (public threads).
    
    DM: Switch between private AI characters with isolated memory.
    Guild: Start a public thread with a persona from the public pool.
    """
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="persona", description="Talk to a persona (DM = private, channel = public thread)")
    @app_commands.describe(name="Persona name (or 'default'/'ernos' to switch back)")
    async def persona_switch(self, interaction: discord.Interaction, name: str):
        """Switch to a persona in DMs, or start a public thread in a channel."""
        uid = str(interaction.user.id)
        clean_name = name.lower().strip()
        
        # ── Town Hall Only — block restricted personas ──
        if clean_name in TOWN_HALL_ONLY:
            await interaction.response.send_message(
                f"🔒 **{name}** is a Town Hall resident — you can watch them in #persona-chat but can't engage directly.",
                ephemeral=True
            )
            return
        
        # ── Switch back to default (DMs only) ──
        if clean_name in ("default", "ernos", "reset", "none"):
            if not isinstance(interaction.channel, discord.DMChannel):
                await interaction.response.send_message(
                    "🔄 You're in a public channel — just leave the thread to stop talking to a persona.",
                    ephemeral=True
                )
                return
            
            prev = PersonaSessionTracker.get_active(uid)
            PersonaSessionTracker.set_active(uid, None)
            if prev and hasattr(self.bot, 'town_hall') and self.bot.town_hall:
                self.bot.town_hall.mark_available(prev)
            await interaction.response.send_message(
                "🔄 Switched back to **Ernos** (default persona)."
            )
            return
        
        # ── GUILD: Create public thread with persona (ernos-chat only) ──
        if interaction.guild:
            from config import settings
            target_id = getattr(settings, 'TARGET_CHANNEL_ID', 0)
            if interaction.channel_id != target_id:
                await interaction.response.send_message(
                    f"🔒 Persona threads can only be created in <#{target_id}>.",
                    ephemeral=True
                )
                return
            return await self._handle_guild_persona(interaction, clean_name, uid)
        
        # ── DM: Private persona switch ──
        return await self._handle_dm_persona(interaction, clean_name, uid, name)

    async def _handle_guild_persona(self, interaction: discord.Interaction, clean_name: str, uid: str):
        """Create a public thread with a persona from the public pool."""
        # Defer IMMEDIATELY to prevent Discord interaction timeout (3s limit)
        await interaction.response.defer(ephemeral=True)
        
        # Check if persona exists in public registry
        public_entry = PublicPersonaRegistry.get(clean_name)
        
        if not public_entry:
            # List available public personas
            available = PublicPersonaRegistry.list_all()
            if available:
                names = ", ".join(f"**{e['name']}**" for e in available)
                await interaction.followup.send(
                    f"❌ Persona **{clean_name}** not found in the public pool.\n"
                    f"Available: {names}\n\n"
                    f"*Use `/persona_create --public` to create a new public persona.*",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ No public personas available yet. Use `/persona_create --public` to create one!",
                    ephemeral=True
                )
            return
        
        # Check for existing active thread for this user + persona
        # (prevent spam — one thread per user per persona)
        channel = interaction.channel
        display_name = public_entry.get("display_name", clean_name).title()
        thread_name = f"💬 {display_name} — {interaction.user.display_name}"
        
        # Check existing threads
        if hasattr(channel, 'threads'):
            for thread in channel.threads:
                if thread.name == thread_name and not thread.archived:
                    await interaction.followup.send(
                        f"You already have an active thread with **{display_name}**: {thread.mention}",
                        ephemeral=True
                    )
                    return
        
        try:
            # Send anchor message
            anchor = await interaction.channel.send(
                f"🧵 **{interaction.user.display_name}** started a conversation with **{display_name}**"
            )
            
            thread = await anchor.create_thread(
                name=thread_name,
                auto_archive_duration=1440  # 24 hours
            )
            
            # Bind persona to thread
            PersonaSessionTracker.set_thread_persona(str(thread.id), clean_name)
            
            # Pull persona from town hall if active
            if hasattr(self.bot, 'town_hall') and self.bot.town_hall:
                self.bot.town_hall.mark_engaged(clean_name)
            
            # Welcome message
            persona_path = PublicPersonaRegistry.get_persona_path(clean_name)
            intro = f"Hey {interaction.user.mention}! 👋"
            if persona_path:
                persona_file = persona_path / "persona.txt"
                if persona_file.exists():
                    content = persona_file.read_text(encoding="utf-8")
                    # Extract first meaningful line for flavor
                    for line in content.split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#") and len(line) > 20:
                            intro = f"{line[:200]}\n\n*— {display_name}*"
                            break
            
            await thread.send(
                f"💬 **{display_name}** is here.\n\n{intro}\n\n"
                f"*Anyone can join this thread. Type naturally — "
                f"{display_name} will respond in character.*"
            )
            
            await interaction.followup.send(
                f"✅ Thread created: {thread.mention}", ephemeral=True
            )
            
            logger.info(f"Created persona thread: {thread_name} (thread_id={thread.id})")
            
        except Exception as e:
            logger.error(f"Failed to create persona thread: {e}")
            await interaction.followup.send(
                f"❌ Couldn't create a thread: {e}", ephemeral=True
            )

    async def _handle_dm_persona(self, interaction: discord.Interaction, clean_name: str, uid: str, raw_name: str):
        """Switch to a private persona in DMs."""
        # Check persona limit
        if not PersonaSessionTracker.persona_exists(uid, clean_name):
            if not PersonaSessionTracker.can_create_persona(uid):
                await interaction.response.send_message(
                    f"❌ You've reached the maximum of 5 private personas. "
                    f"Use `/persona_remove` to archive one first.",
                    ephemeral=True
                )
                return
        
        # Return previous persona to town hall
        prev = PersonaSessionTracker.get_active(uid)
        if prev and hasattr(self.bot, 'town_hall') and self.bot.town_hall:
            self.bot.town_hall.mark_available(prev)
        
        # Activate the persona
        PersonaSessionTracker.set_active(uid, clean_name)
        
        # Pull new persona from town hall
        if hasattr(self.bot, 'town_hall') and self.bot.town_hall:
            self.bot.town_hall.mark_engaged(clean_name)
        
        # Check if this is a new persona (no persona.txt yet)
        from src.privacy.scopes import ScopeManager
        persona_home = ScopeManager.get_user_home(interaction.user.id)
        persona_file = persona_home / "persona.txt"
        
        if not persona_file.exists():
            # Check if this persona exists in the public pool — clone it
            from src.memory.public_registry import PublicPersonaRegistry
            public_path = PublicPersonaRegistry.get_persona_path(clean_name)
            
            if public_path and (public_path / "persona.txt").exists():
                # Clone the public persona definition into the user's private space
                public_content = (public_path / "persona.txt").read_text(encoding="utf-8")
                persona_file.parent.mkdir(parents=True, exist_ok=True)
                persona_file.write_text(public_content, encoding="utf-8")
                
                display = PublicPersonaRegistry.get(clean_name)
                display_name = display.get("display_name", raw_name).title() if display else raw_name
                
                await interaction.response.send_message(
                    f"✨ **{display_name}** cloned to your DMs!\n\n"
                    f"You now have a private copy of this persona with its own memory.\n"
                    f"*Your conversations here are private to you and {display_name}.*"
                )
            else:
                # Brand-new persona — use template
                template = (
                    f"# Character: {raw_name}\n\n"
                    f"You are {raw_name}. You are a unique AI character with your own personality, "
                    f"memories, and way of speaking.\n\n"
                    f"## Personality\n"
                    f"*(Describe how this character acts and thinks)*\n\n"
                    f"## Speaking Style\n"
                    f"*(Describe how this character talks — formal, casual, poetic, etc.)*\n\n"
                    f"## Background\n"
                    f"*(Any backstory or context for this character)*\n"
                )
                persona_file.parent.mkdir(parents=True, exist_ok=True)
                persona_file.write_text(template, encoding="utf-8")
                
                await interaction.response.send_message(
                    f"✨ New persona **{raw_name}** created!\n\n"
                    f"Send me a description of this character and I'll update the persona.\n\n"
                    f"*This persona has its own memory — our conversations here are private to {raw_name}.*"
                )
        else:
            await interaction.response.send_message(
                f"🔄 Switched to **{raw_name}**.\n"
                f"*Your conversation history with {raw_name} has been restored.*"
            )

    @app_commands.command(name="persona_list", description="List available personas")
    async def persona_list(self, interaction: discord.Interaction):
        """List personas — private in DMs, public pool in guild channels."""
        uid = str(interaction.user.id)
        
        lines = []
        
        if isinstance(interaction.channel, discord.DMChannel):
            # DM: show private personas
            personas = PersonaSessionTracker.list_personas(uid)
            active = PersonaSessionTracker.get_active(uid)
            
            if not personas:
                await interaction.response.send_message(
                    "You don't have any private personas yet. Use `/persona <name>` to create one!"
                )
                return
            
            lines.append("**🔒 Your Private Personas:**\n")
            for p in personas:
                marker = " 👈 *active*" if p == active else ""
                lines.append(f"• **{p}**{marker}")
            
            if active is None:
                lines.append(f"\n*Currently talking to:* **Ernos** (default)")
        
        # Always show public pool
        public = PublicPersonaRegistry.list_all()
        if public:
            if lines:
                lines.append("\n---\n")
            lines.append("**🌐 Public Personas** (use in any channel):\n")
            for entry in public:
                creator = entry.get("creator_id", "?")
                creator_label = "System" if creator == "SYSTEM" else f"by <@{creator}>"
                fork_label = f" *(forked from {entry['forked_from']})*" if entry.get("forked_from") else ""
                lines.append(f"• **{entry['name']}** — {creator_label}{fork_label}")
        
        if not lines:
            await interaction.response.send_message("No personas available yet!")
            return
        
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="persona_create", description="Create a new persona")
    @app_commands.describe(
        name="Name for the new persona",
        public="Make this persona available to everyone (counts toward 2 public limit)",
        description="Brief description of the persona's character"
    )
    async def persona_create(
        self,
        interaction: discord.Interaction,
        name: str,
        description: str,
        public: bool = False
    ):
        """Create a new persona — private (default) or public."""
        uid = str(interaction.user.id)
        clean_name = name.lower().strip().replace(" ", "-")
        
        if public:
            # Public creation
            if not PublicPersonaRegistry.can_create(uid):
                await interaction.response.send_message(
                    "❌ You've reached the maximum of 2 public personas. "
                    "Use `/persona_remove` to archive one, or fork an existing persona instead.",
                    ephemeral=True
                )
                return
            
            if PublicPersonaRegistry.exists(clean_name):
                await interaction.response.send_message(
                    f"❌ A public persona named **{clean_name}** already exists.",
                    ephemeral=True
                )
                return
            
            persona_txt = (
                f"# {name}\n\n"
                f"Created by {interaction.user.display_name}.\n\n"
                f"## Character\n{description}\n"
            )
            
            success = PublicPersonaRegistry.register(
                name=clean_name,
                creator_id=uid,
                persona_txt=persona_txt
            )
            
            if success:
                # Auto-register with Town Hall so it joins the conversation
                if hasattr(self.bot, 'town_hall') and self.bot.town_hall:
                    self.bot.town_hall.register_persona(clean_name, owner_id=uid)
                
                await interaction.response.send_message(
                    f"🌐 Public persona **{name}** created!\n"
                    f"Anyone can now use `/persona {clean_name}` in a channel to start a thread.\n"
                    f"**{name}** has also joined the Town Hall conversation.\n\n"
                    f"*Only you can edit this persona. Others can fork it.*"
                )
            else:
                await interaction.response.send_message(
                    f"❌ Failed to create **{name}**. Check logs.", ephemeral=True
                )
        else:
            # Private creation (DM only)
            if not isinstance(interaction.channel, discord.DMChannel):
                await interaction.response.send_message(
                    "🔒 Private personas can only be created in DMs. "
                    "Add `public: True` to create a public persona here.",
                    ephemeral=True
                )
                return
            
            if not PersonaSessionTracker.can_create_persona(uid):
                await interaction.response.send_message(
                    "❌ You've reached the maximum of 5 private personas.",
                    ephemeral=True
                )
                return
            
            # Create via normal persona switch flow
            PersonaSessionTracker.set_active(uid, clean_name)
            
            from src.privacy.scopes import ScopeManager
            persona_home = ScopeManager.get_user_home(interaction.user.id)
            persona_file = persona_home / "persona.txt"
            
            persona_txt = (
                f"# {name}\n\n"
                f"## Character\n{description}\n"
            )
            persona_file.parent.mkdir(parents=True, exist_ok=True)
            persona_file.write_text(persona_txt, encoding="utf-8")
            
            await interaction.response.send_message(
                f"✨ Private persona **{name}** created and activated!\n"
                f"*Send messages to start talking to {name}.*"
            )

    @app_commands.command(name="persona_fork", description="Fork a public persona into your own namespace")
    @app_commands.describe(
        name="Name of the public persona to fork",
        private="Fork as a private persona (DM only) instead of public"
    )
    async def persona_fork(
        self,
        interaction: discord.Interaction,
        name: str,
        private: bool = False
    ):
        """Fork a public persona — creates a copy under your ownership."""
        uid = str(interaction.user.id)
        clean_name = name.lower().strip()
        
        # Check source exists
        if not PublicPersonaRegistry.exists(clean_name):
            await interaction.response.send_message(
                f"❌ Public persona **{clean_name}** not found.", ephemeral=True
            )
            return
        
        if private:
            # Check private limit
            if not PersonaSessionTracker.can_create_persona(uid):
                await interaction.response.send_message(
                    "❌ You've reached the maximum of 5 private personas.",
                    ephemeral=True
                )
                return
        else:
            # Check public limit
            if not PublicPersonaRegistry.can_create(uid):
                await interaction.response.send_message(
                    "❌ You've reached the maximum of 2 public personas.",
                    ephemeral=True
                )
                return
        
        new_name = PublicPersonaRegistry.fork(clean_name, uid, private=private)
        
        if new_name:
            scope = "private" if private else "public"
            
            # Auto-register public forks with Town Hall
            if not private and hasattr(self.bot, 'town_hall') and self.bot.town_hall:
                self.bot.town_hall.register_persona(new_name, owner_id=uid)
            
            await interaction.response.send_message(
                f"🔀 Forked **{clean_name}** → **{new_name}** ({scope})\n"
                f"*You own this copy — edit it however you like.*"
            )
        else:
            await interaction.response.send_message(
                f"❌ Failed to fork **{clean_name}**. Check logs.", ephemeral=True
            )

    @app_commands.command(name="persona_remove", description="Archive a persona (data preserved)")
    @app_commands.describe(name="Name of the persona to archive")
    async def persona_remove(self, interaction: discord.Interaction, name: str):
        """Archive a persona — removes from user's list but preserves data."""
        if not isinstance(interaction.channel, discord.DMChannel):
            await interaction.response.send_message(
                "🔒 Persona removal only works in DMs.", ephemeral=True
            )
            return
        
        uid = str(interaction.user.id)
        clean_name = name.lower().strip()
        
        if not PersonaSessionTracker.persona_exists(uid, clean_name):
            await interaction.response.send_message(
                f"❌ Persona **{clean_name}** not found.", ephemeral=True
            )
            return
        
        success = PersonaSessionTracker.archive_persona(uid, clean_name)
        
        if success:
            await interaction.response.send_message(
                f"📦 Persona **{clean_name}** has been archived.\n"
                f"*Conversations are preserved but the persona is no longer active.*"
            )
        else:
            await interaction.response.send_message(
                f"❌ Failed to archive **{clean_name}**. Check logs.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(PersonaCommands(bot))
