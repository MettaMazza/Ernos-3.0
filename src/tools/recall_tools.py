"""
Recall Tools — User recall, introspection, and reaction tools.

Extracted from memory_tools.py per <300 line modularity standard.
"""
import os
import json
import logging
from pathlib import Path
from src.tools.registry import ToolRegistry
from src.bot import globals

logger = logging.getLogger("Tools.Memory")


# ─── Reactions ─────────────────────────────────────────────────────

@ToolRegistry.register(name="add_reaction", description="React to the current message with an emoji.")
async def add_reaction(emoji: str, message_id: str = None) -> str:
    """
    Reacts to a message.
    Args:
        emoji: The emoji to react with (unicode or custom).
        message_id: Optional ID. Defaults to the message currently being processed.
    """
    try:
        # 1. Resolve Message
        target_msg = None
        
        # Case A: Explicit ID (Not supported efficiently yet, skipping to B)
        # Case B: Implicit (Current Message)
        if not target_msg and globals.active_message.get():
            target_msg = globals.active_message.get()
            
        if not target_msg:
            return "Error: No active message found to react to."
            
        # 2. Execute Reaction (Async)
        if not globals.bot:
            return "Error: Bot instance not available."
            
        await target_msg.add_reaction(emoji)
        return f"Reacted with {emoji}"
        
    except Exception as e:
        return f"Reaction Error: {e}"


# ─── User Recall ───────────────────────────────────────────────────

@ToolRegistry.register(name="recall_user", description="Recall information about a specific user.")
def recall_user(user_id: str = None, **kwargs) -> str:
    """
    Searches timeline for user interactions.
    """
    try:
        # Infer user_id if missing
        if not user_id and globals.active_message.get():
            user_id = str(globals.active_message.get().author.id)
            
        if not user_id:
            return "Error: No user_id provided and could not infer from context."

        # Use Public User Silo
        from src.privacy.scopes import ScopeManager
        # Strip simple ID from inputs like "<@123>" if needed, but assuming user_id is passed clean
        clean_id = ''.join(filter(str.isdigit, str(user_id)))
        
        silo_path = Path("memory") / "public" / "users" / str(clean_id) / "timeline.jsonl"
        
        if not silo_path.exists():
            return f"No public silo found for user '{user_id}'."
            
        matches = []
        with open(silo_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Read last 20 events
            for line in lines[-20:]:
                try:
                    data = json.loads(line)
                    matches.append(f"[{data['timestamp']}] {data['description']}")
                except Exception:
                    continue
        
        if not matches:
             return f"Silo exists but is empty for user '{user_id}'."
             
        return f"### Public History for {user_id}\n" + "\n".join(matches)
    except Exception as e:
        return f"Recall Error: {e}"


# ─── Introspection ─────────────────────────────────────────────────

@ToolRegistry.register(name="review_my_reasoning", description="Review past thought traces.")
def review_my_reasoning(limit: int = 5, scope: str = None, user_id: str = None, request_scope: str = None, **kwargs) -> str:
    """
    Reads the system's own reasoning logs (Thought Traces).
    Allows introspection of previous logic.
    
    SCOPE FILTERING: Traces are scoped. Each scope sees only its own traces.
    - PUBLIC request → reads reasoning_public.log
    - PRIVATE request → reads reasoning_private.log
    - CORE request → reads reasoning_core.log
    """
    try:
        # Infer user_id from context if not provided
        if not user_id and globals.active_message.get():
            user_id = str(globals.active_message.get().author.id)
        
        # Determine which scope to read from
        scope_suffix = "public"  # Default
        if request_scope == "CORE":
            scope_suffix = "core"
        elif request_scope == "PRIVATE":
            scope_suffix = "private"
        elif request_scope == "PUBLIC":
            scope_suffix = "public"
        
        # Scope-specific trace path
        if user_id and request_scope != "CORE":
            # User-scoped traces (PUBLIC/PRIVATE)
            trace_path = f"memory/users/{user_id}/reasoning_{scope_suffix}.log"
        else:
            # System-level CORE traces
            trace_path = f"memory/core/reasoning_{scope_suffix}.log"
        
        if not os.path.exists(trace_path):
            return f"No {scope_suffix.upper()} reasoning traces found yet. Start a conversation to generate traces."
            
        content = ""
        with open(trace_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            line_limit = limit * 25 
            content = "".join(lines[-line_limit:])
            
        if not content.strip():
            return f"Reasoning trace file exists but is empty for {scope_suffix.upper()} scope."
            
        return f"### REASONING TRACE ({scope_suffix.upper()}, USER: {user_id or 'SYSTEM'})\\n" + content
    except Exception as e:
        return f"Introspection Error: {e}"
