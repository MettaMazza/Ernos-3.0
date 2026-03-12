"""
Learning Tools — Lessons and preferences management.

Extracted from memory_tools.py per <300 line modularity standard.
"""
import logging
from src.tools.registry import ToolRegistry
from src.privacy.scopes import PrivacyScope

logger = logging.getLogger("Tools.Memory")


# ─── Lessons Management ───────────────────────────────────────────

@ToolRegistry.register(
    name="manage_lessons",
    description="Manage structured lessons (facts/truths). Actions: add, search, list, verify, reject, stats"
)
async def manage_lessons(
    action: str,
    content: str = None,
    query: str = None,
    lesson_id: str = None,
    scope: str = "PRIVATE",
    source: str = "interaction",
    confidence: float = 1.0,
    user_id: int = None,
    **kwargs
) -> str:
    """
    Manage Ernos's learning system.
    
    Actions:
    - add: Add a new lesson (requires content, scope)
    - search: Search lessons (requires query)
    - list: List all applicable lessons
    - verify: Mark a lesson as verified (requires lesson_id)
    - reject: Mark a lesson as rejected (requires lesson_id)
    - stats: Get lesson statistics
    
    Scopes: CORE (universal), PRIVATE (DM-only), PUBLIC (visible in guilds)
    """
    from src.memory.lessons import LessonManager
    
    manager = LessonManager()
    
    # Parse scope
    scope_map = {
        "CORE": PrivacyScope.CORE_PRIVATE,
        "PRIVATE": PrivacyScope.PRIVATE,
        "PUBLIC": PrivacyScope.PUBLIC
    }
    privacy_scope = scope_map.get(scope.upper(), PrivacyScope.PRIVATE)
    
    try:
        if action == "add":
            if not content:
                return "❌ Content required for 'add' action."
            return manager.add_lesson(
                content=content,
                scope=privacy_scope,
                user_id=user_id,
                source=source,
                confidence=confidence
            )
        
        elif action == "search":
            if not query:
                return "❌ Query required for 'search' action."
            results = manager.search_lessons(query, privacy_scope, user_id)
            if not results:
                return f"No lessons found for query: '{query}'"
            
            lines = [f"**Found {len(results)} lessons:**"]
            for r in results[:10]:  # Limit output
                lines.append(f"- [{r.get('id')}] {r['content'][:500]}...")
            return "\n".join(lines)
        
        elif action == "list":
            lessons = manager.get_all_lessons(user_id, privacy_scope)
            if not lessons:
                return "No lessons found."
            return "**Active Lessons:**\n" + "\n".join(lessons[:20])
        
        elif action == "verify":
            if not lesson_id:
                return "❌ lesson_id required for 'verify' action."
            return manager.verify_lesson(lesson_id, user_id)
        
        elif action == "reject":
            if not lesson_id:
                return "❌ lesson_id required for 'reject' action."
            return manager.reject_lesson(lesson_id, user_id)
        
        elif action == "stats":
            stats = manager.get_stats(user_id)
            return f"📊 Lessons: {stats['core_lessons']} CORE, {stats['user_lessons']} USER, {stats['total']} total"
        
        else:
            return f"❌ Unknown action: '{action}'. Valid: add, search, list, verify, reject, stats"
    
    except Exception as e:
        logger.error(f"manage_lessons error: {e}")
        return f"❌ Error: {e}"


# ─── Preferences Management ───────────────────────────────────────

@ToolRegistry.register(
    name="manage_preferences",
    description="Manage user preferences. Actions: set, get, list, delete"
)
async def manage_preferences(
    action: str,
    key: str = None,
    value: str = None,
    scope: str = "PRIVATE",
    user_id: int = None,
    **kwargs
) -> str:
    """
    Manage user preferences with scoping.
    
    Actions:
    - set: Set a preference (requires key, value)
    - get: Get a preference value (requires key)
    - list: List all preferences
    - delete: Delete a preference (requires key)
    
    Scopes: PRIVATE (DM-only), PUBLIC (visible everywhere)
    """
    from src.memory.preferences import PreferencesManager
    
    if not user_id:
        return "❌ user_id required for preferences."
    
    # Parse scope
    scope_map = {
        "PRIVATE": PrivacyScope.PRIVATE,
        "PUBLIC": PrivacyScope.PUBLIC
    }
    privacy_scope = scope_map.get(scope.upper(), PrivacyScope.PRIVATE)
    
    try:
        if action == "set":
            if not key or not value:
                return "❌ Both 'key' and 'value' required for 'set' action."
            return PreferencesManager.update_preference(
                user_id=user_id,
                key=key,
                value=value,
                scope=privacy_scope
            )
        
        elif action == "get":
            if not key:
                return "❌ 'key' required for 'get' action."
            result = PreferencesManager.get_preference(user_id, key, privacy_scope)
            if result is None:
                return f"Preference '{key}' not found."
            return f"**{key}**: {result}"
        
        elif action == "list":
            prefs = PreferencesManager.list_preferences(user_id, privacy_scope)
            if not prefs["public"] and not prefs.get("private", {}):
                return "No preferences set."
            
            lines = ["**Your Preferences:**"]
            if prefs["public"]:
                lines.append("\n*Public:*")
                for k, v in prefs["public"].items():
                    lines.append(f"- {k}: {v}")
            if prefs.get("private"):
                lines.append("\n*Private:*")
                for k, v in prefs["private"].items():
                    lines.append(f"- {k}: {v}")
            return "\n".join(lines)
        
        elif action == "delete":
            if not key:
                return "❌ 'key' required for 'delete' action."
            return PreferencesManager.delete_preference(user_id, key, privacy_scope)
        
        else:
            return f"❌ Unknown action: '{action}'. Valid: set, get, list, delete"
    
    except Exception as e:
        logger.error(f"manage_preferences error: {e}")
        return f"❌ Error: {e}"
