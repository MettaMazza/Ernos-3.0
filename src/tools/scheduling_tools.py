"""
Scheduling Tools — Calendar, goals, and channel reading.

Extracted from memory_tools.py per <300 line modularity standard.
"""
import logging
from src.tools.registry import ToolRegistry
from src.privacy.scopes import PrivacyScope

logger = logging.getLogger("Tools.Memory")


# ─── Calendar Management ──────────────────────────────────────────

@ToolRegistry.register(
    name="manage_calendar",
    description="Manage calendar events. Actions: add, remove, list, update"
)
async def manage_calendar(
    action: str,
    title: str = None,
    start_time: str = None,
    end_time: str = None,
    event_id: str = None,
    description: str = "",
    recurring: str = None,
    scope: str = "PRIVATE",
    user_id: int = None,
    **kwargs
) -> str:
    """
    Manage calendar events with scoping.
    
    Actions:
    - add: Add event (requires title, start_time, end_time)
    - remove: Remove event (requires event_id)
    - list: List upcoming events
    - update: Update event (requires event_id)
    
    Scopes: CORE (system), PRIVATE (user), PUBLIC (read-only)
    """
    from src.memory.calendar import CalendarManager
    
    scope_map = {
        "CORE": PrivacyScope.CORE,
        "PRIVATE": PrivacyScope.PRIVATE,
        "PUBLIC": PrivacyScope.PUBLIC
    }
    privacy_scope = scope_map.get(scope.upper(), PrivacyScope.PRIVATE)
    
    try:
        if action == "add":
            if not title or not start_time:
                return "❌ 'title' and 'start_time' required for 'add' action."
            return CalendarManager.add_event(
                title=title,
                start_time=start_time,
                end_time=end_time or start_time,
                scope=privacy_scope,
                user_id=user_id,
                description=description,
                recurring=recurring
            )
        
        elif action == "remove":
            if not event_id:
                return "❌ 'event_id' required for 'remove' action."
            return CalendarManager.remove_event(event_id, privacy_scope, user_id)
        
        elif action == "list":
            return CalendarManager.list_events(privacy_scope, user_id)
        
        elif action == "update":
            if not event_id:
                return "❌ 'event_id' required for 'update' action."
            return CalendarManager.update_event(
                event_id=event_id,
                scope=privacy_scope,
                user_id=user_id,
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description
            )
        
        else:
            return f"❌ Unknown action: '{action}'. Valid: add, remove, list, update"
    
    except Exception as e:
        logger.error(f"manage_calendar error: {e}")
        return f"❌ Error: {e}"


# ─── Goals Management ─────────────────────────────────────────────

@ToolRegistry.register(
    name="manage_goals",
    description="Manage goals. Actions: add, complete, abandon, list, progress"
)
async def manage_goals(
    action: str,
    description: str = None,
    goal_id: str = None,
    priority: int = 3,
    progress: int = None,
    deadline: str = None,
    reason: str = "",
    user_id: int = None,
    **kwargs
) -> str:
    """
    Manage hierarchical goals.
    
    Actions:
    - add: Add goal (requires description)
    - complete: Mark goal complete (requires goal_id)
    - abandon: Abandon goal (requires goal_id)
    - list: List active goals
    - progress: Update progress (requires goal_id, progress 0-100)
    
    user_id: User ID for per-user goals. Omit for CORE goals.
    """
    from src.memory.goals import get_goal_manager
    
    try:
        gm = get_goal_manager(user_id)
        
        if action == "add":
            if not description:
                return "❌ 'description' required for 'add' action."
            return gm.add_goal(
                description=description,
                priority=priority,
                deadline=deadline
            )
        
        elif action == "complete":
            if not goal_id:
                return "❌ 'goal_id' required for 'complete' action."
            return gm.complete_goal(goal_id)
        
        elif action == "abandon":
            if not goal_id:
                return "❌ 'goal_id' required for 'abandon' action."
            return gm.abandon_goal(goal_id, reason)
        
        elif action == "list":
            return gm.list_goals()
        
        elif action == "progress":
            if not goal_id or progress is None:
                return "❌ 'goal_id' and 'progress' required for 'progress' action."
            return gm.update_progress(goal_id, progress)
        
        else:
            return f"❌ Unknown action: '{action}'. Valid: add, complete, abandon, list, progress"
    
    except Exception as e:
        logger.error(f"manage_goals error: {e}")
        return f"❌ Error: {e}"


# ─── Channel Reading ──────────────────────────────────────────────

@ToolRegistry.register(
    name="read_channel",
    description="Read recent messages from a Discord channel. Use this when asked to read or check another channel."
)
async def read_channel(
    channel_name: str,
    limit: int = 20,
    **kwargs
) -> str:
    """
    Read recent messages from a specified channel.
    
    Args:
        channel_name: Name of the channel to read (without #)
        limit: Number of messages to fetch (default 20, max 50)
    """
    bot = kwargs.get("bot")
    
    if not bot:
        return "❌ Error: No bot context"
    
    # Clamp limit
    limit = min(max(1, limit), 50)
    
    try:
        # Find channel by name across all guilds (exact match first, then fuzzy)
        target_channel = None
        channel_name_clean = channel_name.lower().replace("#", "").replace(" ", "-").strip()
        # Strip trailing 's' for fuzzy match (e.g. "persona-chats" -> "persona-chat")
        channel_name_variants = [channel_name_clean]
        if channel_name_clean.endswith("s"):
            channel_name_variants.append(channel_name_clean[:-1])
        if not channel_name_clean.endswith("s"):
            channel_name_variants.append(channel_name_clean + "s")
        
        for guild in bot.guilds:
            # Exact match
            for channel in guild.text_channels:
                if channel.name.lower() in channel_name_variants:
                    target_channel = channel
                    break
            if target_channel:
                break
            # Fuzzy match (substring)
            for channel in guild.text_channels:
                if channel_name_clean in channel.name.lower() or channel.name.lower() in channel_name_clean:
                    target_channel = channel
                    break
            if target_channel:
                break
        
        if not target_channel:
            return f"❌ Channel '{channel_name}' not found. Make sure I have access to it."
        
        # Check permissions
        if not target_channel.permissions_for(guild.me).read_message_history:
            return f"❌ I don't have permission to read messages in #{target_channel.name}"
        
        # Fetch messages (handles both regular text AND embeds from Town Hall/bots)
        messages = []
        async for msg in target_channel.history(limit=limit):
            timestamp = msg.created_at.strftime("%H:%M")
            author = msg.author.display_name
            
            # Regular text content
            content = msg.content[:1000] + "..." if len(msg.content) > 1000 else msg.content
            
            # Embed content (Town Hall posts as embeds with author + description)
            if msg.embeds:
                for embed in msg.embeds:
                    embed_author = embed.author.name if embed.author else author
                    embed_desc = embed.description or ""
                    if embed_desc:
                        embed_text = embed_desc[:1000] + "..." if len(embed_desc) > 1000 else embed_desc
                        if content:
                            content += f" | [{embed_author}]: {embed_text}"
                        else:
                            content = f"[{embed_author}]: {embed_text}"
            
            if content:
                messages.append(f"[{timestamp}] {author}: {content}")
        
        messages.reverse()  # Chronological order
        
        if not messages:
            return f"📭 #{target_channel.name} has no recent messages."
        
        header = f"📖 Recent messages from #{target_channel.name} ({len(messages)} messages):\n"
        return header + "\n".join(messages)
        
    except Exception as e:
        logger.error(f"read_channel error: {e}")
        return f"❌ Error reading channel: {e}"
