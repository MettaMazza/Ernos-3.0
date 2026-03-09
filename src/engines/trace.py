"""
Cognition Trace - Handles reasoning trace persistence and transparency.
Extracted from CognitionEngine for modularity.
"""
import os
import re
import logging
import datetime
from pathlib import Path

logger = logging.getLogger("Engine.Trace")


class CognitionTracer:
    """Handles trace saving and mind channel broadcasting."""
    
    def __init__(self, bot):
        self.bot = bot
    
    def save_trace(self, step, response, results, request_scope=None):
        """Save reasoning trace to appropriate scope-based file."""
        from src.bot import globals as g
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = (
            f"[{timestamp}] [INTERNAL NON-USER-FACING COGNITION AND SELF-CORRECTION] [STEP {step}]\n"
            f"{response}\n"
            f"Tool Results: {results}\n"
            + "-"*40 + "\n"
        )
        
        # Determine scope suffix for file
        scope_suffix = "public"  # Default
        if request_scope == "CORE":
            scope_suffix = "core"
        elif request_scope == "PRIVATE":
            scope_suffix = "private"
        elif request_scope == "PUBLIC":
            scope_suffix = "public"
        
        # User-scoped trace file (scope-specific)
        user_id_val = None
        if g.active_message and g.active_message.get():
            user_id_val = str(g.active_message.get().author.id)
        
        if user_id_val and request_scope != "CORE":
            # User-scoped traces (PUBLIC/PRIVATE)
            trace_path = Path(f"memory/users/{user_id_val}/reasoning_{scope_suffix}.log")
        else:
            # System-level CORE traces
            trace_path = Path(f"memory/core/reasoning_{scope_suffix}.log")
            
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with open(trace_path, "a", encoding="utf-8") as f:
            f.write(log_entry)

    def generate_fallback(self, history):
        """Extracts the last meaningful response if loop fails."""
        # Try to extract actual response text (not tool calls)
        # Look for text between [STEP X ASSISTANT]: and [TOOL: or end
        pattern = r'\[STEP \d+ ASSISTANT\]:\s*(.*?)(?=\[TOOL:|$|\[STEP)'
        matches = re.findall(pattern, history, re.DOTALL)
        
        for match in reversed(matches):  # Start from most recent
            # Clean up the text
            text = match.strip()
            # Remove any remaining [TOOL:...] markers
            text = re.sub(r'\[TOOL:.*?\]', '', text, flags=re.DOTALL).strip()
            
            if text and len(text) > 50:  # Only use substantive text
                return text
        
        # If nothing found, give a graceful error
        return "I'm having trouble organizing my thoughts right now. Could you try rephrasing that?"

    async def send_thought_to_mind(self, step: int, thought: str, request_scope: str = None):
        """Broadcasts reasoning step to Mind Channel for transparency.
        
        PRIVACY: PRIVATE scope reasoning is NEVER broadcast to prevent
        leaking DM content (user names, persona details, personal data)
        to the shared mind channel.
        """
        # PRIVACY FIREWALL: Block PRIVATE reasoning from public mind channel
        if request_scope == "PRIVATE":
            logger.debug(f"Skipping mind broadcast for PRIVATE scope (Step {step})")
            return
            
        try:
            # Format the thought for Discord display
            header = f"**🧠 Step {step}**\n"
            # Truncate if too long for a single message
            content = thought[:1800] if len(thought) > 1800 else thought
            await self.bot.send_to_mind(f"{header}```\n{content}\n```")
        except Exception as e:
            logger.error(f"Failed to send thought to mind: {e}")

