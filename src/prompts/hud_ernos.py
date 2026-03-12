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
        "self_review_history": "No reviews available.",
        # v3.3 Survival Drive & Emotional State
        "discomfort_status": "No survival data available.",
        "emotional_status": "No emotional data available.",
        "user_threat_status": "No threat data available.",
        # v3.4 Temporal Awareness
        "temporal_status": "No temporal data available.",
        # Gaming Session (structured fields)
        "game_name": "No active session",
        "game_username": "—",
        "game_health": "—",
        "game_food": "—",
        "game_time_of_day": "—",
        "game_biome": "—",
        "game_threats": "None",
        "game_nearby": "—",
        "game_inventory": "—",
        "game_goal": "—",
        "game_action": "—",
        "game_precognition": "—",
        "game_narrative": "No active gaming session.",
        # v4.0 Cognitive Integrity (GWT)
        "tape_focus": "Unknown",
        "tape_cell_count": "0",
        "flux_status": "No rate limit data.",
        "superego_pipeline_status": "No audit data available.",
    }

    # LIVE GAMING STATE — read from gaming_state.json written by GamingAgent
    try:
        gaming_state_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "gaming_state.json")
        if os.path.exists(gaming_state_path):
            with open(gaming_state_path, "r", encoding="utf-8") as f:
                gaming_data = json.load(f)
            if gaming_data.get("active"):
                game = gaming_data.get("game", "Minecraft")
                action = gaming_data.get("current_action", "playing")
                goal = gaming_data.get("current_goal", "exploring")
                health = gaming_data.get("health", 20)
                food = gaming_data.get("food", 20)
                is_day = gaming_data.get("is_day", True)
                biome = gaming_data.get("biome", "unknown")
                hostiles = gaming_data.get("hostiles_nearby", False)
                nearby = gaming_data.get("nearby", "nobody")
                inventory = gaming_data.get("inventory_summary", "empty")
                precog = gaming_data.get("precognition_queue", "safety reflexes")
                mc_user = gaming_data.get("mc_username", "Ernos")
                narrative = gaming_data.get("narrative", f"Currently playing {game}.")

                hud["gaming_status"] = f"🎮 ACTIVE — {game} (HP:{health}/20 Food:{food}/20) — {action}"
                hud["embodiment_state"] = narrative

                # Structured gaming fields for Section 15
                hud["game_name"] = f"🎮 {game}"
                hud["game_username"] = mc_user
                hud["game_health"] = f"❤️ {health}/20"
                hud["game_food"] = f"🍖 {food}/20"
                hud["game_time_of_day"] = "☀️ Daytime" if is_day else "🌙 Nighttime"
                hud["game_biome"] = biome
                hud["game_threats"] = f"⚠️ HOSTILES NEARBY — {nearby}" if hostiles else "✅ Area is safe"
                hud["game_nearby"] = nearby
                hud["game_inventory"] = inventory if inventory else "empty"
                hud["game_goal"] = goal
                hud["game_action"] = action
                hud["game_precognition"] = precog
                hud["game_narrative"] = narrative
            else:
                hud["gaming_status"] = "Idle (no active session)"
                hud["embodiment_state"] = gaming_data.get("narrative", "No active gaming session.")
    except Exception as e:
        logger.debug(f"Gaming state read failed (non-critical): {e}")

    # ─── Glasses Embodiment State ────────────────────────────────
    try:
        from src.web.glasses_handler import GlassesSession
        # Check for active glasses sessions via the web server's active connections
        from src.web import web_server
        # If the glasses websocket endpoint has been hit recently, note it
        if hasattr(web_server, '_glasses_active') and web_server._glasses_active:
            glasses_info = "🕶️ Meta Ray-Ban glasses connected (live voice + camera)"
            current = hud.get("embodiment_state", "")
            if current and "No active" not in current:
                hud["embodiment_state"] = f"{current}\n{glasses_info}"
            else:
                hud["embodiment_state"] = glasses_info
    except Exception:
        pass  # Glasses module may not be loaded yet


    # Inject Real-Time Model Name
    try:
        from src.bot import globals
        from config import settings
        if hasattr(globals, 'bot') and globals.bot and hasattr(globals.bot, 'engine_manager'):
            eng = globals.bot.engine_manager.get_active_engine()
            if eng:
                # Mode Heuristics
                mode = "Custom"
                if settings.OLLAMA_CLOUD_MODEL in eng.name: mode = "Cloud"
                elif settings.OLLAMA_LOCAL_MODEL in eng.name: mode = "Local"
                elif "steering" in str(eng).lower(): mode = "Steering"
                
                hud["cognition_status"] = f"Online ({eng.name} [{mode}])"
    except Exception as e:
        logger.warning(f"Suppressed {type(e).__name__}: {e}")

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
                    except Exception as e:
                        logger.warning(f"Suppressed {type(e).__name__}: {e}")
                        continue
                if entries:
                    hud["provenance_recent"] = "\n".join(entries)

        # 8. Pending Research — scan ALL research directories (core + user-scoped)
        research_dirs = ["memory/core/research"]
        # Also scan user-scoped research directories
        for user_research_root in glob.glob("memory/users/*/research"):
            research_dirs.append(user_research_root)
        for public_research_root in glob.glob("memory/public/*/research"):
            research_dirs.append(public_research_root)

        all_research_files = []
        for rdir in research_dirs:
            if os.path.exists(rdir):
                for md_file in glob.glob(f"{rdir}/**/*.md", recursive=True):
                    all_research_files.append(md_file)

        if all_research_files:
            # Sort by modification time, newest first
            all_research_files.sort(key=os.path.getmtime, reverse=True)
            from datetime import datetime
            research_entries = []
            for rf in all_research_files[:15]:
                fname = os.path.basename(rf)
                mtime = os.path.getmtime(rf)
                ts = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                # Show source directory for context
                rel = rf.replace("memory/", "")
                research_entries.append(f"• [{ts}] {fname[:60]} ({rel[:40]})")
            hud["pending_research"] = "\n".join(research_entries)

        # 8b. Self-Review History — recent self-correction verdicts
        review_log = "memory/core/self_reviews.jsonl"
        if os.path.exists(review_log):
            try:
                with open(review_log, "r", encoding="utf-8") as f:
                    review_lines = f.readlines()[-3:]
                review_entries = []
                for line in review_lines:
                    try:
                        entry = json.loads(line)
                        verdict = entry.get("verdict", "?")
                        conf = entry.get("confidence", 0)
                        reason = entry.get("reasoning", "")[:80]
                        ts = entry.get("timestamp", "")[:16]
                        emoji = {"CONCEDE": "🔄", "HOLD": "🛡️", "CLARIFY": "💡"}.get(verdict, "❓")
                        review_entries.append(f"• [{ts}] {emoji} {verdict} ({conf:.0%}) — {reason}")
                    except (json.JSONDecodeError, ValueError):
                        continue
                if review_entries:
                    hud["self_review_history"] = "\n".join(review_entries)
            except Exception as e:
                logger.warning(f"Failed to load self-review history: {e}")

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
                    except Exception as e:
                        logger.warning(f"Suppressed {type(e).__name__}: {e}")
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
            if status == "HEALTHY" or "OPERATIONAL" in status:
                hud["test_health"] = f"✅ {status} ({passed}/{total}) [{ts}]"
                if failed > 0:
                    hud["test_health"] += f" ({failed} minor)"
            elif status == "DEGRADED":
                hud["test_health"] = f"⚠️ DEGRADED ({passed}/{total}) - {failed} FAILED [{ts}]"
            elif status == "CRITICAL":
                hud["test_health"] = f"🔴 CRITICAL ({passed}/{total}) - {failed} FAILED [{ts}]"
            else:
                hud["test_health"] = f"❓ {status} ({passed}/{total}) [{ts}]"
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
    # === v4.0 Cognitive Integrity: GWT Data Sources ===

    # 3D Tape Machine State
    try:
        from src.bot import globals as bot_globals
        if bot_globals.bot and hasattr(bot_globals.bot, 'hippocampus'):
            tape = bot_globals.bot.hippocampus.get_tape(str(user_id)) if user_id else None
            if tape:
                x, y, z = tape.focus_pointer
                hud["tape_focus"] = f"[{x},{y},{z}]"
                hud["tape_cell_count"] = str(len(tape.tape.cells))
    except Exception as e:
        logger.debug(f"Tape state load failed (non-critical): {e}")

    # Knowledge Graph Snapshot
    try:
        from src.bot import globals as bot_globals
        if bot_globals.bot and hasattr(bot_globals.bot, 'hippocampus') and hasattr(bot_globals.bot.hippocampus, 'graph'):
            kg = bot_globals.bot.hippocampus.graph
            if kg:
                # Recent nodes (last 10)
                try:
                    recent = kg.get_recent_nodes(limit=10) if hasattr(kg, 'get_recent_nodes') else []
                    if recent:
                        hud["kg_recent_nodes"] = "\n".join(
                            f"• {n.get('name', '?')} [{n.get('label', '?')}]" for n in recent
                        )
                except Exception:
                    pass
                # Beliefs
                try:
                    beliefs = kg.get_beliefs(limit=5) if hasattr(kg, 'get_beliefs') else []
                    if beliefs:
                        hud["kg_beliefs"] = "\n".join(f"• {b}" for b in beliefs)
                except Exception:
                    pass
                # Relationships
                try:
                    rels = kg.get_recent_relationships(limit=5) if hasattr(kg, 'get_recent_relationships') else []
                    if rels:
                        hud["kg_relationships"] = "\n".join(
                            f"• {r.get('source', '?')} —[{r.get('type', '?')}]→ {r.get('target', '?')}" for r in rels
                        )
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"KG snapshot load failed (non-critical): {e}")

    # Active Skills Registry
    try:
        import glob as _glob
        skill_dirs = _glob.glob("memory/users/*/skills/*/SKILL.md")
        if skill_dirs:
            skill_names = [os.path.basename(os.path.dirname(s)) for s in skill_dirs[:10]]
            hud["skills_loaded"] = ", ".join(skill_names)
    except Exception as e:
        logger.debug(f"Skills load failed (non-critical): {e}")

    # Flux Capacitor Usage (high-value tools only)
    try:
        from src.core.flux_capacitor import FluxCapacitor
        from src.bot import globals as bot_globals
        if bot_globals.bot:
            flux = FluxCapacitor(bot_globals.bot)
            uid = int(user_id) if user_id and str(user_id).isdigit() else 0
            flux_lines = []
            for tool_name in ["generate_image", "generate_video", "start_deep_research"]:
                remaining = flux.get_remaining(uid, tool_name) if hasattr(flux, 'get_remaining') else None
                if remaining is not None:
                    flux_lines.append(f"• {tool_name}: {remaining} remaining")
            if flux_lines:
                hud["flux_status"] = "\n".join(flux_lines)
    except Exception as e:
        logger.debug(f"Flux capacitor load failed (non-critical): {e}")

    # Superego Pipeline Status
    try:
        from src.bot import globals as bot_globals
        if bot_globals.bot and hasattr(bot_globals.bot, 'cerebrum'):
            superego = bot_globals.bot.cerebrum.get_lobe("SuperegoLobe")
            if superego:
                abilities = []
                for name in ["IdentityAbility", "AuditAbility", "RealityAbility", "SentinelAbility", "MediatorAbility"]:
                    ab = superego.get_ability(name)
                    abilities.append(f"• {name}: {'Active' if ab else 'Missing'}")
                hud["superego_pipeline_status"] = "\n".join(abilities)
    except Exception as e:
        logger.debug(f"Superego pipeline load failed (non-critical): {e}")

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
                    except json.JSONDecodeError as e:
                        logger.debug(f"Suppressed {type(e).__name__}: {e}")
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
