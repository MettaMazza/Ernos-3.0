"""
Cognition Tools — Tool execution and result handling for CognitionEngine.

Extracted from CognitionEngine.process() to keep cognition.py manageable.
Contains: execute_tool_step (single tool execution with rate limiting,
delivery, anti-laziness tracking, session history management).
"""
import logging
import os
import re
from pathlib import Path
from datetime import datetime

from src.tools.registry import ToolRegistry
from src.tools.error_tracker import error_tracker

logger = logging.getLogger("Engine.Cognition.Tools")


# NOTE: Internal per-turn tool caps have been removed.
# Rate limiting is handled ONLY by the FluxCapacitor (user-facing, tier-based).
# Semantic dedup still prevents identical repeat calls within a single turn.


def _normalize_tool_sig(tool_name: str, args_str: str) -> str:
    """Normalize tool args for dedup — strips whitespace, normalizes quotes."""
    normalized = re.sub(r'\s+', ' ', args_str.strip())
    normalized = normalized.replace("'", '"')
    return f"{tool_name}:{normalized}"


async def execute_tool_step(
    bot, engine, tool_name: str, args_str: str,
    executed_tools_history: list, tool_usage_counts: dict,
    circuit_breaker_count: int, user_id, request_scope: str,
    channel_id, user_tool_history: dict, reading_tracker,
    max_session_history: int, parse_tool_args_fn,
    step: int, skip_defenses: bool = False, turn_id: str = None,
    tracker=None
) -> tuple:
    """
    Execute a single tool call and return the result.

    Returns:
        (result_text: str or None, circuit_breaker_count: int, step_valid: bool)
        result_text is None if the tool was skipped/blocked.
    """
    # Normalize for semantic dedup (whitespace/quote invariant)
    tool_sig = _normalize_tool_sig(tool_name, args_str)

    # ── Tool Auto-Correction: Fix common malformed tool names ──────────
    # When the LLM calls a non-existent tool that's a known alias,
    # auto-correct to the real tool name and remap arguments as needed.
    TOOL_ALIASES = {
        "set_goal":      ("manage_goals", {"_inject": {"action": "add"}}),
        "complete_goal": ("manage_goals", {"_inject": {"action": "complete"}, "_rename": {"goal_id": "description"}}),
        "review_goals":  ("manage_goals", {"_inject": {"action": "list", "description": ""}}),
        "add_goal":      ("manage_goals", {"_inject": {"action": "add"}}),
        "list_goals":    ("manage_goals", {"_inject": {"action": "list", "description": ""}}),
    }
    if tool_name in TOOL_ALIASES:
        real_name, transforms = TOOL_ALIASES[tool_name]
        logger.info(f"Tool auto-correction: '{tool_name}' → '{real_name}'")
        # Parse existing args before remapping
        kwargs = parse_tool_args_fn(args_str) if args_str else {}
        # Rename keys if needed
        for old_key, new_key in transforms.get("_rename", {}).items():
            if old_key in kwargs:
                kwargs[new_key] = kwargs.pop(old_key)
        # Inject required args
        for key, val in transforms.get("_inject", {}).items():
            if key not in kwargs:
                kwargs[key] = val
        # Rebuild args_str
        args_str = ", ".join(f'{k}="{v}"' if isinstance(v, str) else f'{k}={v}' for k, v in kwargs.items())
        tool_name = real_name
        tool_sig = _normalize_tool_sig(tool_name, args_str)

    # Circuit Breaker: semantic dedup (blocks identical calls even with formatting differences)
    _bypass_tools = {"update_persona", "update_identity"}
    if tool_sig in executed_tools_history and tool_name not in _bypass_tools and not skip_defenses:
        logger.warning(f"Circuit Breaker: Semantic dupe blocked: {tool_name}")
        return f"System: Tool {tool_name} with these exact args was already run. Do not repeat.", circuit_breaker_count + 1, False

    # Per-tool-name caps: prevent any single tool from dominating a turn
    _tool_caps = {
        "create_program": 5,
        "start_document": 1,
        "propose_skill": 2,
        "execute_skill": 3,
    }
    _default_tool_cap = 150
    cap = _tool_caps.get(tool_name, _default_tool_cap)
    if tool_usage_counts.get(tool_name, 0) >= cap and tool_name not in _bypass_tools and not skip_defenses:
        logger.warning(f"Per-tool cap: {tool_name} hit limit of {cap}")
        return f"System: Tool {tool_name} has been called {cap} times this turn — limit reached. Use existing results.", circuit_breaker_count, False

    # Once-per-session tools: only one call allowed per cognition cycle, regardless of args.
    # Prevents LLM from creating multiple documents or sending duplicate PDFs.
    # NOTE: entries in executed_tools_history use format "tool_name:normalized_args"
    #       (colon separator from _normalize_tool_sig), NOT parentheses.
    _once_per_session_tools = {"start_document"}
    if tool_name in _once_per_session_tools:
        already_called = any(
            entry.startswith(f"{tool_name}:") for entry in executed_tools_history
        )
        if already_called:
            logger.warning(f"Circuit Breaker: {tool_name} already called once this session — blocking duplicate")
            return (
                f"System: {tool_name} was already called this session. "
                f"The document has already been rendered and sent. Do NOT render again.",
                circuit_breaker_count + 1, False
            )

    # ── FLUX CAPACITOR: Tool Rate Limit Check ──────────
    try:
        from src.core.flux_capacitor import FluxCapacitor
        flux = FluxCapacitor(bot)
        tool_allowed, tool_msg = flux.consume_tool(user_id or 0, tool_name)
        if not tool_allowed:
            logger.info(f"Flux limit for tool {tool_name} (user {user_id}): {tool_msg}")
            return f"System: {tool_msg} Do NOT retry this tool.", circuit_breaker_count, False
        elif tool_msg:
            # Low-usage warning
            pass  # We'll prepend it below if needed
    except Exception as flux_err:
        logger.debug(f"Flux tool check skipped: {flux_err}")
        tool_msg = None

    # Execute
    logger.info(f"Step {step}: Executing {tool_name}")
    # ── Live Status Tracker: update before tool runs ──
    if tracker:
        try:
            await tracker.update(tool_name)
        except Exception as e:
            logger.warning(f"Suppressed {type(e).__name__}: {e}")
    try:
        kwargs = parse_tool_args_fn(args_str)
        
        # Auto-strip trailing commas from string arguments (solves "10," integer crash)
        for k, v in kwargs.items():
            if isinstance(v, str) and v.endswith(','):
                kwargs[k] = v.rstrip(',')

        # Auto-fallback: If create_program is missing `code`, assume the raw parsed string is the code
        if tool_name == "create_program":
            if "code" not in kwargs:
                # check if they used generic text parameter
                if "text" in kwargs:
                    kwargs["code"] = kwargs.pop("text")
                elif len(kwargs) == 1 and list(kwargs.values())[0]:
                    kwargs["code"] = list(kwargs.values())[0]
                else:
                    kwargs["code"] = args_str

        # Prevent collision: Authoritative context overrides AI-generated values
        if 'user_id' in kwargs:
            del kwargs['user_id']
        if 'request_scope' in kwargs:
            del kwargs['request_scope']

        # Auto-detect autonomy mode: system users = autonomous operation
        _is_autonomy = str(user_id) in ("sys", "CORE", "SYSTEM")
        if _is_autonomy:
            kwargs["is_autonomy"] = True

        # Inject channel_id for scope-aware tools
        if channel_id and 'channel_id' not in kwargs:
            kwargs['channel_id'] = str(channel_id)
        elif 'channel_id' not in kwargs:
            try:
                from src.bot import globals as bot_globals
                active_msg = bot_globals.active_message.get()
                if active_msg:
                    kwargs['channel_id'] = str(active_msg.channel.id)
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

        # ── Tape Machine Operations Intercept ──────────
        if tool_name.startswith("tape_"):
            tape_scope = kwargs.pop("request_scope", "PUBLIC") if "request_scope" in kwargs else "PUBLIC"
            tape_machine = bot.hippocampus.get_tape(str(user_id), scope=tape_scope) if user_id else None
            if not tape_machine:
                return f"System: Tape Machine unavailable for user {user_id}", circuit_breaker_count, False
            
            if tool_name == "tape_seek":
                try:
                    if "x" in kwargs and "y" in kwargs and "z" in kwargs:
                        coord = (int(kwargs["x"]), int(kwargs["y"]), int(kwargs["z"]))
                    elif "index" in kwargs:
                        # Fallback for old 1D syntax
                        coord = (int(kwargs["index"]), tape_machine.focus_pointer[1], tape_machine.focus_pointer[2])
                    elif "x" in kwargs:
                        # Fallback for 1D <SEEK: x> syntax parsed as x
                        coord = (int(kwargs["x"]), tape_machine.focus_pointer[1], tape_machine.focus_pointer[2])
                    else:
                        raise ValueError("Missing coordinates in SEEK")
                        
                    tape_machine.op_seek(coord)
                    result = f"Tape: Seek to {coord} executed."
                except Exception as e:
                    return f"TapeFaultError: Invalid coordinates in SEEK: {e}", circuit_breaker_count, False
            elif tool_name == "tape_move":
                direction = kwargs.get("direction", "")
                tape_machine.op_move(direction)
                result = f"Tape: Moved {direction}."
            elif tool_name == "tape_scan":
                tape_machine.op_scan(kwargs.get("query", ""))
                result = "Tape: Scan executed."
            elif tool_name == "tape_read":
                content = tape_machine.op_read()
                result = f"Tape Read:\n{content}"
            elif tool_name == "tape_write":
                tape_machine.op_write(kwargs.get("content", ""))
                result = "Tape: Write executed."
            elif tool_name == "tape_insert":
                tape_machine.op_insert(kwargs.get("cell_type", "MEMORY"), kwargs.get("content", ""))
                result = "Tape: Insert executed."
            elif tool_name == "tape_delete":
                tape_machine.op_delete()
                result = "Tape: Delete executed."
            elif tool_name == "tape_edit_code":
                # SECURITY: Self-modification is ADMIN-ONLY. Verify requesting user.
                try:
                    from config import settings as _cfg
                    _admin_ids = {str(aid) for aid in _cfg.ADMIN_IDS}
                    if str(user_id) not in _admin_ids:
                        logger.critical(f"SECURITY: Non-admin user {user_id} attempted tape_edit_code — BLOCKED.")
                        return f"\U0001f512 Access Denied: Code self-modification is restricted to administrators.", circuit_breaker_count, False
                except Exception as _e:
                    logger.error(f"Admin check failed for tape_edit_code: {_e}")
                    return "System: Admin verification unavailable. tape_edit_code blocked.", circuit_breaker_count, False
                path = kwargs.get("file_path", kwargs.get("path", kwargs.get("file", "")))
                target = kwargs.get("target_string", kwargs.get("target", kwargs.get("old_string", "")))
                replacement = kwargs.get("replacement_string", kwargs.get("replacement", kwargs.get("new_string", "")))
                tape_machine.op_edit_code(path, target, replacement)
                result = "Tape: Code Edit recorded."
            elif tool_name == "tape_revert_code":
                path = kwargs.get("file_path", kwargs.get("path", kwargs.get("file", "")))
                tape_machine.op_revert_code(path)
                result = "Tape: Code Reverted."
            elif tool_name == "tape_fork":
                # SECURITY: Fork/clone is ADMIN-ONLY.
                try:
                    from config import settings as _cfg
                    _admin_ids = {str(aid) for aid in _cfg.ADMIN_IDS}
                    if str(user_id) not in _admin_ids:
                        logger.critical(f"SECURITY: Non-admin user {user_id} attempted tape_fork — BLOCKED.")
                        return f"\U0001f512 Access Denied: Darwinian Fork is restricted to administrators.", circuit_breaker_count, False
                except Exception as _e:
                    logger.error(f"Admin check failed for tape_fork: {_e}")
                    return "System: Admin verification unavailable. tape_fork blocked.", circuit_breaker_count, False
                res = tape_machine.op_fork_tape(kwargs.get("mutation_target", ""))
                from src.engines.evolution_sandbox import SandboxController
                sandbox = SandboxController(bot)
                eval_res = await sandbox.evaluate_mutation(kwargs.get("mutation_target", ""))
                result = f"Tape Fork: {res}\nSandbox Eval: {eval_res}"
            elif tool_name == "tape_emit":
                # Acknowledge the emit without immediately pushing to Discord
                # The LLM's raw text will be used for the final response anyway.
                result = "Tape: Emit acknowledged."
            elif tool_name == "tape_index":
                result = tape_machine.get_index()
            else:
                result = "Unknown tape command."
        else:
            result = await ToolRegistry.execute(tool_name, request_scope=request_scope, user_id=user_id, bot=bot, turn_id=turn_id, **kwargs)

        # Dynamic Limit Calculation
        limit = engine.context_limit

        # Truncate Immediate Output
        truncated_result = str(result)[:limit]
        result_text = f"Tool({tool_name}) Output: {truncated_result}"

        # ─── File Delivery: Send created files to channel ──────
        if tool_name == "create_program" and "Successfully applied" in str(result):
            try:
                import discord
                match = re.search(r'to `(.+?)`', str(result))
                if match:
                    rel_path = match.group(1)
                    abs_path = (Path(os.getcwd()) / rel_path).resolve()
                    if abs_path.exists() and abs_path.stat().st_size < 8_000_000:
                        delivery_channel = None
                        if channel_id:
                            delivery_channel = bot.get_channel(int(channel_id))
                        if not delivery_channel:
                            from src.bot import globals as bot_globals
                            active_msg = bot_globals.active_message.get()
                            if active_msg:
                                delivery_channel = active_msg.channel
                        if delivery_channel:
                            file_obj = discord.File(str(abs_path), filename=abs_path.name)
                            await delivery_channel.send(
                                f"📎 **File created:** `{abs_path.name}`",
                                file=file_obj
                            )
                            logger.info(f"Delivered file {abs_path.name} to channel {delivery_channel.id}")
            except Exception as delivery_err:
                logger.warning(f"File delivery failed (non-fatal): {delivery_err}")

        # ─── Anti-Laziness: Track Document Reads ──────
        result_str = str(result)
        if tool_name in ("read_file", "read_file_page"):
            try:
                m = re.search(r'Lines:\s*(\d+)-(\d+)/(\d+)', result_str)
                if m:
                    r_start, r_end, r_total = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    file_path = kwargs.get('path', tool_name)
                    reading_tracker.record_read(file_path, r_start, r_end, r_total)
            except Exception as track_err:
                logger.debug(f"Reading tracker parse failed: {track_err}")
        elif tool_name == "browse_site":
            try:
                is_truncated = "[DOCUMENT TRUNCATED" in result_str
                url_arg = kwargs.get('url', 'unknown')
                content_len = len(result_str)
                reading_tracker.record_browse(url_arg, content_len, is_truncated)
            except Exception as track_err:
                logger.debug(f"Reading tracker browse failed: {track_err}")

        # Record to session history for cross-turn context (SCOPED BY USER)
        # Increased from 0.2% to 1% for richer cross-turn context
        history_limit = int(limit * 0.01)
        safe_scope = request_scope or "PUBLIC"
        history_key = f"{user_id}_{safe_scope}" if user_id else f"system_{safe_scope}"

        user_tool_history[history_key].append({
            "tool": tool_name,
            "output": str(result)[:history_limit],
            "timestamp": datetime.now().isoformat()
        })
        if len(user_tool_history[history_key]) > max_session_history:
            user_tool_history[history_key] = user_tool_history[history_key][-max_session_history:]

        executed_tools_history.append(tool_sig)
        tool_usage_counts[tool_name] += 1

        # ── Live Status Tracker: mark tool complete ──
        if tracker:
            try:
                await tracker.tool_complete(tool_name)
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

        return result_text, circuit_breaker_count, True

    except Exception as e:
        logger.error(f"Tool Fail: {e}")
        error_tracker.log_tool_failure(
            tool_name=tool_name,
            error=e,
            params={"args": args_str},
            user_id=str(user_id) if user_id else None
        )
        fail_text = (
            f"Tool({tool_name}) FAILED: {e}\n"
            f"[CRITICAL INSTRUCTION]: This tool failed. You MUST NOT fabricate, simulate, or invent "
            f"data that was supposed to come from this tool. Instead: (1) Report the failure honestly, "
            f"(2) State what you cannot verify due to this failure, (3) Do NOT wrap hallucinated data "
            f"in technical-sounding language. If Science Lobe fails on a calculation, say 'I was unable "
            f"to compute this' - NOT 'my simulation shows [invented numbers]'."
        )
        return fail_text, circuit_breaker_count, False
