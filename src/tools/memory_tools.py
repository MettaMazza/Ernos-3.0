"""
Memory Tools — Re-export shim for backward compatibility.

Implementations split into focused modules per <300 line standard:
  - persona_tools.py    → update_persona
  - recall_tools.py     → add_reaction, recall_user, review_my_reasoning
  - bridge_tools.py     → publish_to_bridge, read_public_bridge, evaluate_advice, save_core_memory
  - learning_tools.py   → manage_lessons, manage_preferences
  - scheduling_tools.py → manage_calendar, manage_goals, read_channel
"""
from pathlib import Path  # noqa: F401 — tests patch src.tools.memory_tools.Path
from src.tools.persona_tools import update_persona        # noqa: F401
from src.tools.recall_tools import (                      # noqa: F401
    add_reaction,
    recall_user,
    review_my_reasoning,
)
from src.tools.bridge_tools import (                      # noqa: F401
    publish_to_bridge,
    read_public_bridge,
    evaluate_advice,
    save_core_memory,
)
from src.tools.learning_tools import (                    # noqa: F401
    manage_lessons,
    manage_preferences,
)
from src.tools.scheduling_tools import (                  # noqa: F401
    manage_calendar,
    manage_goals,
    read_channel,
)
