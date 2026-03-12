"""
Chat Tools — Registered tools for Discord chat operations.

Provides AI-invocable tools for operations that were previously
hardcoded as heuristics in chat.py (v3.3 No Heuristics compliance).
"""
import logging
from src.tools.registry import ToolRegistry

logger = logging.getLogger("Tools.Chat")


@ToolRegistry.register(
    name="create_thread_for_user",
    description="Create a public thread for 1-on-1 conversation with a user. "
                "Use this when a user wants a dedicated space to chat."
)
async def create_thread_for_user(
    reason: str = "Chat",
    **kwargs
) -> str:
    """
    Create a public thread for a user to have a dedicated conversation space.

    The LLM decides when to invoke this based on user intent,
    replacing the old heuristic check for "start a thread" in message content.

    Args:
        reason: Short description for the thread purpose (default: "Chat")
    """
    bot = kwargs.get("bot")
    channel = kwargs.get("channel")

    if not bot or not channel:
        return "❌ Error: No bot or channel context available."

    # Get the original message to create thread from
    from src.bot import globals
    message = globals.active_message

    if not message:
        return "❌ Error: No active message to create thread from."

    try:
        import discord
        # Threads require a guild channel (not DMs)
        if not hasattr(message, "guild") or not message.guild:
            return "❌ Threads can only be created in server channels, not DMs."

        thread = await message.create_thread(
            name=f"{reason} with {message.author.display_name}",
            auto_archive_duration=1440  # 24 hours
        )
        await thread.send(
            f"Hey {message.author.mention}! This is our space to chat. 🌿\n"
            f"It's still public, just a bit more organized."
        )
        await message.add_reaction("✅")
        logger.info(f"Created thread for {message.author}: {thread.name}")

        return f"✅ Created thread: {thread.name}"

    except Exception as e:
        logger.error(f"Failed to create thread: {e}")
        return f"❌ Couldn't create a thread here: {e}"


@ToolRegistry.register(
    name="send_direct_message",
    description="Send a private Direct Message (DM) to the USER YOU ARE TALKING TO. "
                "You cannot DM other users. Use this when the user asks for a private response "
                "or when sharing sensitive info."
)
async def send_direct_message(
    content: str,
    **kwargs
) -> str:
    """
    Send a direct message to the current user.
    
    SECURITY:
    - This tool DOES NOT accept a target user argument.
    - It strictly uses the 'user_id' injected by the system interactions.
    - This prevents the bot from being used to harass others.
    
    Args:
        content: The message text to send.
    """
    bot = kwargs.get("bot")
    user_id = kwargs.get("user_id")

    if not bot or not user_id:
        return "❌ Error: No bot or user context available. I can't DM you right now."

    try:
        # Fetch user object (from cache or API)
        # We try get_user (cache) first, then fetch_user (API)
        user = bot.get_user(user_id)
        if not user:
            user = await bot.fetch_user(user_id)
            
        if not user:
             return f"❌ Error: Could not find user with ID {user_id}."

        # Send DM
        # create_dm() returns the DMChannel, creating it if necessary
        dm_channel = await user.create_dm()
        await dm_channel.send(content)
        
        logger.info(f"Sent DM to {user}: {content[:30]}...")
        return f"✅ Sent DM to {user.name}."

    except Exception as e:
        logger.error(f"Failed to send DM: {e}")
        return f"❌ Failed to send DM: {e}"
