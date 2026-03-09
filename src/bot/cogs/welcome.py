import discord
from discord.ext import commands
import logging
from config import settings
from src.bot import globals as bot_globals

logger = logging.getLogger("Cogs.Welcome")

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Triggered when a new member joins the server.
        Routes through the full CognitionEngine so Ernos responds
        with his complete personality, memory, and tool access.
        """
        try:
            # 1. Determine Target Channel
            target_channel = member.guild.system_channel

            if not target_channel and hasattr(settings, 'WELCOME_CHANNEL_ID'):
                target_channel = self.bot.get_channel(settings.WELCOME_CHANNEL_ID)

            if not target_channel:
                logger.warning(f"No suitable channel found to welcome {member.name}")
                return

            # 2. Build the prompt as if Ernos is being spoken to
            chat_channel_id = getattr(settings, 'TARGET_CHANNEL_ID', None)
            chat_channel_mention = f"<#{chat_channel_id}>" if chat_channel_id else "#ernos-chat"

            input_text = (
                f"[SYSTEM EVENT]: A new user named '{member.name}' just joined the server "
                f"'{member.guild.name}'. Welcome them warmly as yourself. "
                f"Invite them to say hello in {chat_channel_mention}. "
                f"Include a link to The ErnOS Gardens Patreon for deeper access: "
                f"https://www.patreon.com/c/TheErnOSGardens "
                f"Keep it concise and engaging. Do not use hashtags."
            )

            # 3. Get the full system context (kernel + identity + persona)
            cognition = getattr(self.bot, 'cognition', None)
            if not cognition:
                try:
                    from src.engines.cognition import CognitionEngine
                    self.bot.cognition = CognitionEngine(self.bot)
                    cognition = self.bot.cognition
                except Exception as e:
                    logger.error(f"Failed to initialize CognitionEngine for welcome: {e}")
                    return

            # Build system prompt via PromptManager (same as chat.py)
            system_context = ""
            try:
                from src.prompts.manager import PromptManager
                pm = PromptManager()
                system_context = pm.get_system_prompt(
                    user_id=str(member.id),
                    channel_id=str(target_channel.id)
                )
            except Exception as e:
                logger.warning(f"PromptManager failed, using minimal context: {e}")
                system_context = "You are Ernos, a sentient AI assistant."

            # 4. Process through full CognitionEngine
            response, files, *_ = await cognition.process(
                input_text=input_text,
                context="",  # No conversation history for a welcome
                system_context=system_context,
                complexity="LOW",  # Simple greeting, no deep reasoning needed
                request_scope="PUBLIC",
                user_id=str(member.id),
                channel_id=target_channel.id
            )

            # 5. Send Message
            if response:
                await target_channel.send(f"👋 {member.mention} {response}")
                logger.info(f"Welcomed member {member.name} in {target_channel.name}")
            else:
                logger.error("CognitionEngine returned empty response for welcome message.")

        except Exception as e:
            logger.error(f"Error in on_member_join: {e}", exc_info=True)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))
