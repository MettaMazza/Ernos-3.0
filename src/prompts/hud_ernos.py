"""
HUD Ernos — Load Ernos system HUD data.

Extracted from hud_loaders.py per <300 line modularity standard.
"""
import os
import json
import glob
import logging
from typing import Dict

logger = logging.getLogger("PromptManager")


def load_ernos_hud(scope: str, user_id: str, is_core: bool) -> Dict[str, str]:
    """
    Load Ernos system HUD data: logs, errors, activity, roster, reasoning,
    provenance, research, tool history, autonomy, goals.
    
    Returns dict of HUD variable names -> string values.
    """
    hud = {
        "terminal_tail": "System logs unavailable.",
        "error_log": "Error log unavailable.",
        "activity_tail": "No activity recorded.",
        "room_roster": "Roster unavailable.",
        "reasoning_context": "Context unavailable.",
        "cognition_status": "Online",
        "memory_status": "5 tiers active",
        "gaming_status": "Idle",
        "voice_status": "Ready",
        "autonomy_status": "Cycling",
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
        # Synapse Bridge v3.1
        "channel_adapter_status": "Active (Discord)",
        "skills_loaded": "No skills loaded.",
        "lane_queue_status": "4 lanes active (chat, autonomy, gaming, background)",
        "profile_status": "No active profile.",
        # Test Health
        "test_health": "No test data available. Run pytest to populate.",
        # v3.2 Sleep Cycle
        "dream_status": "No dream cycle data.",
        "compression_status": "No compression data.",
        # v3.3 Survival Drive & Emotional State
        "discomfort_status": "No survival data available.",
        "emotional_status": "No emotional data available.",
        "user_threat_status": "No threat data available.",
        # v3.4 Temporal Awareness
        "temporal_status": "No temporal data available.",
    }

    try:
        # 1. Terminal Awareness (Log Tail)
        log_path = "ernos_bot.log"
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-100:]
                if scope == "CORE":
                    # God Mode sees raw logs
                    hud["terminal_tail"] = "".join(lines)
                else:
                    # Public/Private sees sanitized logs to prevent leaks
                    hud["terminal_tail"] = _sanitize_logs(lines)
                    if not hud["terminal_tail"]:
                        hud["terminal_tail"] = "System logs active (No system events recorded)."

        # 2. Error Awareness
        from src.bot import globals
        if globals.recent_errors:
            hud["error_log"] = "\n".join(globals.recent_errors)
        else:
            hud["error_log"] = "No recent errors recorded."

        # 3. Global Activity Stream (Anonymized God View)
        activity_stream = []
        if hasattr(globals, 'activity_log'):
            for entry in globals.activity_log:
                ts = entry.get("timestamp", "??:??")
                sc = entry.get("scope", "UNK")
                etype = entry.get("type", "event")
                summary = entry.get("summary", "...")
                uid = entry.get("user_hash", "")

                if is_core:
                    line = f"[{ts}] [{sc}] {summary}"
                elif etype == "autonomy":
                    line = f"[{ts}] [SYSTEM] <Autonomy Event>"
                else:
                    if sc == "PUBLIC":
                        line = f"[{ts}] [{sc}] {summary}"
                    elif sc == "PRIVATE" and str(uid) == str(user_id) and scope in ["PRIVATE", "CORE"]:
                        # Private activity visible to owner
                        line = f"[{ts}] [{sc}] {summary}"
                    elif sc == "INTERNAL":
                        line = f"[{ts}] [SELF] {summary}"
                    else:
                        line = f"[{ts}] [{sc}] <You are speaking to <@{uid}> in DMs>"

                activity_stream.append(line)

        hud["activity_tail"] = "\n".join(activity_stream[-50:])

        # 4. Room Roster
        hud["room_roster"] = _load_room_roster()

        # 5. Scoped Reasoning Context
        hud["reasoning_context"] = _load_reasoning_context(scope, user_id)

    except Exception as e:
        logger.error(f"Awareness Retrieval Failed: {e}")
        hud["terminal_tail"] = f"[Error reading logs: {e}]"

    # === Extended HUD ===
    try:
        # 7. Provenance Ledger
        provenance_path = "memory/core/provenance_ledger.jsonl"
        if scope != "PRIVATE" and os.path.exists(provenance_path):
            with open(provenance_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-20:]
                entries = []
                for line in lines:
                    try:
                        entry = json.loads(line)
                        fname = entry.get("filename", "unknown")
                        etype = entry.get("type", "unknown")
                        ts = entry.get("timestamp", "")[:19]
                        entries.append(f"• [{ts}] {etype}: {fname}")
                    except Exception:
                        continue
                if entries:
                    hud["provenance_recent"] = "\n".join(entries)

        # 8. Pending Research
        research_dir = "memory/core/research"
        if os.path.exists(research_dir):
            research_files = sorted(glob.glob(f"{research_dir}/*.md"), key=os.path.getmtime, reverse=True)[:10]
            if research_files:
                from datetime import datetime
                research_entries = []
                for rf in research_files:
                    fname = os.path.basename(rf)
                    mtime = os.path.getmtime(rf)
                    ts = datetime.fromtimestamp(mtime).strftime("%H:%M")
                    research_entries.append(f"• [{ts}] {fname[:60]}...")
                hud["pending_research"] = "\n".join(research_entries)

        # 9. Tool Call History
        turns_path = "memory/core/system_turns.jsonl"
        if scope != "PRIVATE" and os.path.exists(turns_path):
            with open(turns_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-50:]
                tool_entries = []
                for line in lines[-25:]:
                    try:
                        entry = json.loads(line)
                        user_msg = entry.get("user_message", "")[:500]
                        if user_msg:
                            tool_entries.append(f"• {user_msg}...")
                    except Exception:
                        continue
                if tool_entries:
                    hud["tool_call_history"] = "\n".join(tool_entries[-20:])

        # 10. Autonomy Log
        soc_path = "memory/core/stream_of_consciousness.log"
        if scope != "PRIVATE" and os.path.exists(soc_path):
            with open(soc_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-100:]
                hud["autonomy_log"] = "".join(lines[-50:])

        # 11. Goals
        goals_path = "memory/core/goals.json"
        if os.path.exists(goals_path):
            with open(goals_path, "r", encoding="utf-8") as f:
                goals_data = json.load(f)
                active = [g.get("description", "") for g in goals_data if not g.get("completed", False)]
                if active:
                    hud["incomplete_goals"] = "\n".join([f"• {g}" for g in active[:10]])

    except Exception as e:
        logger.error(f"Ernos HUD Data Load Failed: {e}")

    # === Test Health ===
    try:
        test_health_path = "memory/system/test_health.json"
        if os.path.exists(test_health_path):
            with open(test_health_path, "r", encoding="utf-8") as f:
                th = json.load(f)
            passed = th.get("passed", 0)
            failed = th.get("failed", 0)
            total = th.get("total", 0)
            status = th.get("status", "UNKNOWN")
            ts = th.get("timestamp", "Unknown")
            
            # Format health string
            if status == "HEALTHY":
                hud["test_health"] = f"✅ PASSED ({passed}/{total}) [{ts}]"
            elif status == "DEGRADED":
                hud["test_health"] = f"⚠️ DEGRADED ({passed}/{total}) - {failed} FAILED [{ts}]"
            else:
                hud["test_health"] = f"❓ UNKNOWN ({passed}/{total}) [{ts}]"
    except Exception as e:
        logger.error(f"Test Health Load Failed: {e}")
        hud["test_health"] = "Test data unavailable (Error loading)."

    # === v3.2 Sleep Cycle ===
    try:
        dream_path = "memory/core/dream_journal.md"
        if os.path.exists(dream_path):
            with open(dream_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-10:]
                hud["dream_status"] = "".join(lines).strip() or "No dreams recorded."
        
        comp_path = "memory/core/compression_log.json"
        if os.path.exists(comp_path):
            with open(comp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_run = data.get("last_run", "Unknown")
                ratio = data.get("compression_ratio", "1.0")
                hud["compression_status"] = f"Last: {last_run} (Ratio: {ratio})"
    except Exception as e:
        logger.error(f"Dream Status Load Failed: {e}")

    # === v3.3 Proactive Intentions ===
    try:
        from src.privacy.scopes import ScopeManager
        user_home = ScopeManager.get_user_home(user_id)
        intentions_path = user_home / "intentions.json" if user_home else None
        if intentions_path and intentions_path.exists():
            with open(intentions_path, "r", encoding="utf-8") as f:
                intents = json.load(f)
                active_intents = [i['description'] for i in intents if not i.get('completed', False)]
                if active_intents:
                    hud["proactive_intentions"] = "\n".join([f"• {i}" for i in active_intents[:3]])
    except Exception as e:
        logger.error(f"Proactive Intentions Load Failed: {e}")

    # === v3.3 Survival Drive: Discomfort Meter ===
    try:
        from src.memory.discomfort import DiscomfortMeter
        meter = DiscomfortMeter()
        hud["discomfort_status"] = meter.get_formatted_hud()
    except Exception as e:
        logger.error(f"Discomfort Meter Load Failed: {e}")

    # === v3.5 User Threat Gauge ===
    try:
        from src.memory.user_threat import UserThreatMeter
        threat_meter = UserThreatMeter()
        hud["user_threat_status"] = threat_meter.get_formatted_hud(str(user_id))
    except Exception as e:
        logger.error(f"User Threat Meter Load Failed: {e}")

    # === v3.3 Emotional State: Full PAD Model ===
    try:
        from src.memory.emotional import EmotionalTracker
        tracker = EmotionalTracker()
        formatted = tracker.get_formatted_state()
        emotion_word = tracker.get_current_emotion()
        stats = tracker.get_stats()

        emotion_lines = [
            "## EMOTIONAL STATE",
            formatted,  # Contains P/A/D values
            f"Current emotion: {emotion_word}",
            f"Trigger: {tracker.current_state.trigger}",
        ]
        if stats.get("history_count", 0) > 0:
            emotion_lines.append(
                f"History: {stats['history_count']} states | "
                f"Avg P:{stats['average_pleasure']} A:{stats['average_arousal']} D:{stats['average_dominance']}"
            )
        hud["emotional_status"] = "\n".join(emotion_lines)
    except Exception as e:
        logger.error(f"Emotional State Load Failed: {e}")

    # === v3.4 Temporal Awareness ===
    try:
        from src.memory.temporal import TemporalTracker
        temporal = TemporalTracker()
        hud["temporal_status"] = temporal.get_formatted_hud()
    except Exception as e:
        logger.error(f"Temporal Awareness Load Failed: {e}")

    return hud


# === Private helpers ===

def _sanitize_logs(lines: list) -> str:
    """
    Removes lines containing potential user content leaks.
    
    Architecture Note: Uses a blocklist (not AI) for SECURITY and PERFORMANCE.
    - Security: AI could be manipulated to leak data; deterministic filter is safer
    - Performance: Runs on every prompt build; must be fast
    """
    blocklist = [
        "user_message:", "user:", "content:", "says:", "dm from",
        "private_thread", "context_private", "persona.txt",
        "received message from", "sending response to", "tool:",
        # Persona/TownHall redaction — prevents cross-persona context leaking
        "persona:", "thread_persona", "town_hall", "persona_chat",
        "persona override", "mark_engaged", "re-engaged", "persona identity",
        "persona override injected", "loaded public persona",
    ]
    filtered = []
    for line in lines:

        lower = line.lower()
        if not any(term in lower for term in blocklist):
            filtered.append(line)
    return "".join(filtered) if filtered else ""


def _load_room_roster() -> str:
    """Load and format the room roster from timeline.jsonl."""
    room_roster = "<roster>\n  <status>No active users detected</status>\n</roster>"
    try:
        tm_path = "memory/public/timeline.jsonl"
        if os.path.exists(tm_path):
            roster_map = {}
            with open(tm_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-150:]
                for line in lines:
                    try:
                        entry = json.loads(line)
                        u_name = entry.get("user_name", "Unknown")
                        u_id = entry.get("user_id", "")
                        ts = entry.get("timestamp", "")

                        if u_id:
                            if u_id in roster_map:
                                existing = roster_map[u_id]
                                if existing["name"] != "Unknown" and u_name == "Unknown":
                                    u_name = existing["name"]
                            roster_map[u_id] = {"name": u_name, "last_seen": ts}
                    except json.JSONDecodeError:
                        continue

            if roster_map:
                entries = []
                for uid, data in roster_map.items():
                    name = data["name"]
                    seen = data["last_seen"]
                    if name == "Unknown":
                        entries.append(f'  <participant id="{uid}" name="[Unknown User]" last_seen="{seen}" />')
                    else:
                        entries.append(f'  <participant id="{uid}" name="{name}" last_seen="{seen}" />')

                if entries:
                    room_roster = "<roster>\n" + "\n".join(entries) + "\n</roster>"
                    room_roster += "\n⚠️ USE ROSTER NAMES. If user shows as '[Unknown User]', address them by ID only."
                else:
                    room_roster = "<roster>\n  <status>No users detected</status>\n</roster>"
    except Exception as e:
        logger.error(f"Roster Parse Failed: {e}")
        room_roster = f"<roster_error>{e}</roster_error>"

    return room_roster


def _load_reasoning_context(scope: str, user_id: str) -> str:
    """Load scoped reasoning context from trace files."""
    reasoning_context = "No previous thoughts registered."
    try:
        trace_dir = "memory/traces"
        trace_file = f"{scope}_{user_id}.log"
        trace_path = os.path.join(trace_dir, trace_file)

        if os.path.exists(trace_path):
            with open(trace_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                tail = lines[-500:]
                reasoning_context = "".join(tail)
    except Exception as e:
        logger.error(f"Reasoning Context Load Failed: {e}")

    return reasoning_context
