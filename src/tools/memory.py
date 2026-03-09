"""
Memory Tools — Re-export shim.

All tool implementations now live in focused modules:
  - persona_tools.py, recall_tools.py, bridge_tools.py,
  - learning_tools.py, scheduling_tools.py

This module re-exports symbols for backward compatibility with existing imports.
"""
from src.tools.memory_tools import (
    update_persona,
    add_reaction,
    recall_user,
    review_my_reasoning,
    publish_to_bridge,
    read_public_bridge,
    evaluate_advice,
    save_core_memory,
    manage_lessons,
    manage_preferences,
    manage_calendar,
    manage_goals,
    read_channel,
)

# Backward-compatible synchronous wrapper for manage_goals.
# The canonical async version lives in scheduling_tools.py, but many callers
# (production code like goal.py + tests) call manage_goals synchronously.
# Since the function body contains zero awaits, this sync version is equivalent.
# We rename the async import to avoid shadowing:
from src.tools.scheduling_tools import manage_goals as _manage_goals_async  # noqa: F811

def manage_goals(  # noqa: F811
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
    """Synchronous manage_goals wrapper — delegates to goal manager."""
    import logging
    from src.memory.goals import get_goal_manager

    logger = logging.getLogger("Tools.Memory")
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
