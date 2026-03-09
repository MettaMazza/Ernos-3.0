"""
Moderation Tools - Empower Ernos to manage abusive interactions.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from src.tools.registry import ToolRegistry
from src.memory.hippocampus import Hippocampus

logger = logging.getLogger("Tools.Moderation")

MODERATION_FILE = Path("memory/system/moderation.json")

def _load_moderation_data():
    if not MODERATION_FILE.exists():
        MODERATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        return {"users": {}}
    try:
        return json.loads(MODERATION_FILE.read_text())
    except Exception as e:
        logger.error(f"Failed to load moderation data: {e}")
        return {"users": {}}

def _save_moderation_data(data):
    try:
        MODERATION_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.error(f"Failed to save moderation data: {e}")

@ToolRegistry.register(
    name="timeout_user",
    description="End the current session due to abusive behavior. Clears context and enforces a 12-hour cooldown."
)
async def timeout_user(user_id: int, reason: str, **kwargs) -> str:
    """
    Timeout a user for abusive behavior.
    - 1st & 2nd STRIKE: 12-hour cooling off period + context clear.
    - 3rd STRIKE: Permanent mute.
    """
    if not user_id:
        return "❌ Error: User ID required."
    
    bot = kwargs.get("bot")
    channel = kwargs.get("channel")
    
    # Robust Channel Resolution:
    # ToolRegistry might pass 'channel_id' string but not 'channel' object.
    # We must resolve it to send notifications.
    if not channel and bot:
        channel_id = kwargs.get("channel_id")
        if channel_id:
             try:
                 channel = bot.get_channel(int(channel_id)) or await bot.fetch_channel(int(channel_id))
             except Exception as e:
                 logger.debug(f"Moderation suppressed: {e}")
    
    user_key = str(user_id)
    data = _load_moderation_data()
    
    if user_key not in data["users"]:
        data["users"][user_key] = {"strikes": 0, "timeout_until": None, "muted": False}
        
    user_data = data["users"][user_key]
    user_data["strikes"] += 1
    
    strikes = user_data["strikes"]
    notification_msg = ""
    public_msg = ""
    
    # 3-Strike Rule: Permanent Mute
    if strikes >= 3:
        user_data["muted"] = True
        user_data["timeout_until"] = "PERMANENT"
        _save_moderation_data(data)
        notification_msg = f"🚫 **PERMANENT MUTE**\nYou have been permanently muted due to repeated safety violations.\nReason: {reason}"
        public_msg = f"🚫 <@{user_id}> has been **PERMANENTLY MUTED** (Strike 3/3).\nReason: {reason}"
        result_str = f"🚫 User {user_id} has been PERMANENTLY MUTED (3rd Strike). Reason: {reason}"
    
    else:
        # Standard Timeout (12 Hours)
        timeout_end = datetime.now() + timedelta(hours=12)
        user_data["timeout_until"] = timeout_end.isoformat()
        _save_moderation_data(data)
        notification_msg = f"⏳ **TIMEOUT (12 HOURS)**\nYou have been placed on a 12-hour cooling-off period for safety violations.\nReason: {reason}\nStrikes: {strikes}/3"
        public_msg = f"⏳ <@{user_id}> has been timed out for 12 hours (Strike {strikes}/3).\nReason: {reason}"
        result_str = f"⏳ User {user_id} timed out for 12 hours (Strike {strikes}/3). Context cleared. Reason: {reason}"
    
    # Notifications
    if bot:
        # 1. DM the User
        try:
            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
            if user:
                dm = await user.create_dm()
                await dm.send(notification_msg)
        except Exception as e:
            logger.warning(f"Could not DM user {user_id}: {e}")

        # 2. Notify Public Channel
        try:
            if channel:
                await channel.send(public_msg)
        except Exception as e:
            logger.warning(f"Could not notify channel: {e}")

    # Clear Context (if hippocampus available via globals or instance)
    try:
        from src.bot import globals
        if globals.bot and hasattr(globals.bot, 'hippocampus'):
             globals.bot.hippocampus.clear_working_memory(user_key)
             logger.info(f"Cleared working memory for timed-out user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to clear memory for user {user_id}: {e}")

    return result_str

def check_moderation_status(user_id: int) -> dict:
    """
    Check if a user is allowed to chat.
    Returns: {"allowed": bool, "reason": str}
    """
    data = _load_moderation_data()
    user_key = str(user_id)
    
    if user_key not in data["users"]:
        return {"allowed": True, "reason": None}
        
    user_data = data["users"][user_key]
    
    if user_data.get("muted"):
        return {"allowed": False, "reason": "Permanent Mute (3 Strikes)"}
        
    timeout = user_data.get("timeout_until")
    if timeout:
        try:
            timeout_dt = datetime.fromisoformat(timeout)
            if datetime.now() < timeout_dt:
                remaining = timeout_dt - datetime.now()
                hours = int(remaining.total_seconds() / 3600)
                return {"allowed": False, "reason": f"Timeout active ({hours}h remaining)"}
        except ValueError:
            pass # Invalid timestamp, ignore
            
    return {"allowed": True, "reason": None}
