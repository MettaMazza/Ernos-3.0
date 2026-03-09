"""
Bridge Tools — Public bridge memory, advice evaluation, and core memory.

Extracted from memory_tools.py per <300 line modularity standard.
"""
import os
import json
import datetime
import logging
from pathlib import Path
from src.tools.registry import ToolRegistry

logger = logging.getLogger("Tools.Memory")


# ─── Bridge Memory ─────────────────────────────────────────────────

@ToolRegistry.register(name="publish_to_bridge", description="Post info to the public Bridge memory.")
def publish_to_bridge(content: str) -> str:
    """Writes to shared public memory."""
    try:
        bridge_path = "memory/public/bridge.log"
        os.makedirs("memory/public", exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(bridge_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {content}\n")
            
        return "Content published to Bridge successfully."
    except Exception as e:
        return f"Bridge Publish Error: {e}"

@ToolRegistry.register(name="read_public_bridge", description="Read the public Bridge memory.")
def read_public_bridge(limit: int = 10) -> str:
    """Reads recent Bridge entries."""
    try:
        bridge_path = "memory/public/bridge.log"
        if not os.path.exists(bridge_path):
            return "Bridge memory is empty."
            
        with open(bridge_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        return "### Bridge Public Memory\n" + "".join(lines[-limit:])
    except Exception as e:
        return f"Bridge Read Error: {e}"


# ─── Advice Evaluation ────────────────────────────────────────────

@ToolRegistry.register(name="evaluate_advice", description="Evaluate a piece of advice.")
def evaluate_advice(advice: str) -> str:
    """Simulated judgment of advice quality."""
    score = min(10, len(advice) // 10)
    verdict = "Useful" if score > 5 else "Generic"
    return f"Advice Evaluation:\nContent: '{advice[:50]}...'\nScore: {score}/10\nVerdict: {verdict}"


# ─── Core Memory ──────────────────────────────────────────────────

@ToolRegistry.register(name="save_core_memory", description="Save a critical fact to long-term Core memory.")
def save_core_memory(content: str, category: str = "general", request_scope: str = None, **kwargs) -> str:
    """
    Saves high-priority information to the Core memory bank.
    Requires CORE scope or Admin privileges.
    """
    try:
        # Enforce Scope
        if request_scope != "CORE":
            return "🔒 Error: Only CORE persona can write to Core Memory. Please switch to Admin/Core context."
            
        core_path = Path("memory/core/facts.jsonl")
        core_path.parent.mkdir(parents=True, exist_ok=True)
        
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "content": content
        }
        
        with open(core_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            
        return f"Core Memory Saved [{category}]: {content}"
    except Exception as e:
        return f"Core Write Error: {e}"
