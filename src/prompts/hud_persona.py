"""
HUD Persona — Load HUD data for public persona threads.

Extracted from hud_loaders.py per <300 line modularity standard.
"""
import json
import logging
from typing import Dict

logger = logging.getLogger("PromptManager")


def load_persona_hud(persona_name: str) -> Dict[str, str]:
    """
    Load HUD data for a PUBLIC PERSONA THREAD.
    
    Returns ONLY persona-scoped data — NO Ernos system data (terminal, SoC,
    error logs, goals, tool history, dreams, etc). This prevents context
    leaking between Ernos and personas in public threads.
    """
    hud = {
        "terminal_tail": "System logs unavailable.",
        "error_log": "No recent errors recorded.",
        "activity_tail": "No activity recorded.",
        "room_roster": "Roster unavailable.",
        "reasoning_context": "Context unavailable.",
        "cognition_status": "Online",
        "memory_status": "Active",
        "gaming_status": "Idle",
        "voice_status": "Ready",
        "autonomy_status": "Idle",
        "embodiment_state": "No active embodiment session.",
        "kg_status": "Active",
        "vector_status": "Ready",
        "kg_recent_nodes": "No recent nodes.",
        "kg_beliefs": "No beliefs extracted.",
        "kg_relationships": "No relationships mapped.",
        "lessons_learned": "No lessons recorded.",
        "skills_acquired": "No skills tracked.",
        "pending_research": "No research in progress.",
        "incomplete_goals": "No incomplete goals.",
        "queued_actions": "No actions queued.",
        "tool_call_history": "No recent tool calls.",
        "autonomy_log": "No autonomous thoughts.",
        "wisdom_log": "No wisdom extractions.",
        "proactive_intentions": "No proactive intentions.",
        "provenance_recent": "No recent claims.",
        "channel_adapter_status": "Active (Discord)",
        "skills_loaded": "No skills loaded.",
        "lane_queue_status": "Active",
        "profile_status": "No active profile.",
        "test_health": "No test data available.",
        "dream_status": "No dream cycle data.",
        "compression_status": "No compression data.",
    }
    
    try:
        from src.memory.public_registry import PublicPersonaRegistry
        persona_path = PublicPersonaRegistry.get_persona_path(persona_name)
        if persona_path:
            # Load persona's own lessons
            lessons_path = persona_path / "lessons.json"
            if lessons_path.exists():
                with open(lessons_path, "r", encoding="utf-8") as f:
                    lessons = json.load(f)
                    if lessons:
                        hud["lessons_learned"] = "\n".join([f"• {l}" for l in lessons[:10]])
            
            # Load persona's relationships
            relationships_path = persona_path / "relationships.json"
            if relationships_path.exists():
                with open(relationships_path, "r", encoding="utf-8") as f:
                    rels = json.load(f)
                    if rels:
                        lines = [f"• {k}: {v}" for k, v in rels.items()]
                        hud["kg_relationships"] = "\n".join(lines[:10])
            
            # Load persona's opinions as beliefs
            opinions_path = persona_path / "opinions.json"
            if opinions_path.exists():
                with open(opinions_path, "r", encoding="utf-8") as f:
                    opinions = json.load(f)
                    if opinions:
                        lines = [f"• {k}: {v}" for k, v in opinions.items()]
                        hud["kg_beliefs"] = "\n".join(lines[:10])
            
            # Load persona's recent town hall context
            context_path = persona_path / "context.jsonl"
            if context_path.exists():
                with open(context_path, "r", encoding="utf-8") as f:
                    ctx_lines = f.readlines()[-20:]
                    context_entries = []
                    for line in ctx_lines:
                        try:
                            entry = json.loads(line)
                            speaker = entry.get("speaker", "?")
                            content = entry.get("content", "")[:200]
                            context_entries.append(f"{speaker}: {content}")
                        except Exception as e:
                            logger.warning(f"Suppressed {type(e).__name__}: {e}")
                            continue
                    if context_entries:
                        hud["reasoning_context"] = "\n".join(context_entries)
    except Exception as e:
        logger.error(f"Persona HUD Load Failed for {persona_name}: {e}")
    
    return hud
