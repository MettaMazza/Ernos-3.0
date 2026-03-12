"""
Support Tools - For escalating issues to admins.
"""
import logging
from src.tools.registry import ToolRegistry
from config import settings

logger = logging.getLogger("Tools.Support")

@ToolRegistry.register(
    name="escalate_ticket",
    description="Escalate a support thread to a human admin by creating a ticket. Use this when the user explicitly requests human assistance."
)
async def escalate_ticket(
    reason: str,
    priority: str = "normal",
    **kwargs
) -> str:
    """
    Escalates the current specific support situation to admins.
    
    Args:
        reason: Why the user needs human help.
        priority: 'normal' or 'high'
    """
    bot = kwargs.get("bot")
    channel_id = kwargs.get("channel_id")
    user_id = kwargs.get("user_id")
    
    if not bot:
        return "Error: System not ready (no bot context)."

    if not channel_id:
        return "Error: Must be used within a channel/thread to link context."

    try:
        # Get thread info
        thread = bot.get_channel(int(channel_id))
        thread_link = thread.jump_url if thread else f"<#{channel_id}>"
        thread_name = thread.name if thread else "Unknown Thread"
        
        # Get User Info
        user_name = "User"
        if user_id:
            try:
                user = await bot.fetch_user(int(user_id))
                user_name = user.name
            except Exception:
                user_name = f"User {user_id}"

        # Construct Ticket Message
        ticket_msg = (
            f"🎫 **New Support Ticket**\n"
            f"**User**: {user_name}\n"
            f"**Thread**: {thread_link} ({thread_name})\n"
            f"**Reason**: {reason}\n"
            f"**Priority**: {priority.upper()}\n"
            f"Please investigate."
        )

        # Send to Admins
        sent_count = 0
        for admin_id in settings.ADMIN_IDS:
            try:
                admin_user = await bot.fetch_user(admin_id)
                if admin_user:
                    await admin_user.send(ticket_msg)
                    sent_count += 1
            except Exception as e:
                logger.error(f"Failed to DM admin {admin_id}: {e}")

        if sent_count == 0:
            return "Failed to DM any admins. I have logged the request internally."
            
        return f"Ticket created. Notified {sent_count} admins. Human help is on the way!"

    except Exception as e:
        logger.error(f"Escalation failed: {e}")
        return f"System Error during escalation: {e}"
