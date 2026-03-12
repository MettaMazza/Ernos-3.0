"""
Self-Stop Tool — Lets Ernos abort its own inference when it realizes
it cannot fulfill a request, triggering the same flow as user /stop.
"""
import logging
from typing import Optional
from src.tools.registry import ToolRegistry
from src.bot import globals as bot_globals

logger = logging.getLogger("Tools.SelfStop")


@ToolRegistry.register(name="self_stop", description=(
    "Abort your current processing and generate a fresh response explaining why. "
    "Use this when you realize you CANNOT fulfill the user's request — for example, "
    "a tool you need doesn't exist, you're stuck in a loop, or you've been "
    "approaching the problem incorrectly. "
    "Args: reason (str — explain WHY you're stopping so the recovery response is accurate)."
))
async def self_stop(
    reason: str,
    user_id: Optional[str] = None,
    bot: Optional[object] = None,
) -> str:
    """
    Self-abort: Ernos calls this on itself when it realizes it can't
    fulfill a request. Triggers the same cancel flow as user /stop,
    but with a self-reported reason that feeds into the recovery response.
    
    Args:
        reason: Why Ernos is stopping (used in the recovery prompt)
        user_id: Injected by system
        bot: Injected by system
    """
    _bot = bot or bot_globals.bot
    if not _bot:
        return "Error: Bot not available."
    
    engine = getattr(_bot, 'cognition', None)
    if not engine:
        return "Error: CognitionEngine not available."
    
    if not user_id:
        return "Error: No user_id for cancel event lookup."
    
    user_id_str = str(user_id)
    
    # Stash the reason so _generate_cancel_response can use it
    if not hasattr(engine, '_self_stop_reasons'):
        engine._self_stop_reasons = {}
    engine._self_stop_reasons[user_id_str] = reason
    
    # Trigger the cancel event (same as /stop)
    cancelled = engine.request_cancel(user_id_str)
    
    if cancelled:
        logger.info(f"SelfStop: Ernos self-stopped for user {user_id_str}. Reason: {reason}")
        return f"Self-stop triggered. Reason logged: {reason}"
    else:
        logger.warning(f"SelfStop: No active cancel event for user {user_id_str}")
        # Even without an event, return the reason as a signal
        return f"No active processing to cancel, but noted: {reason}"
