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
    step: int,
) -> tuple:
    """
    Execute a single tool call and return the result.

    Returns:
        (result_text: str or None, circuit_breaker_count: int, step_valid: bool)
        result_text is None if the tool was skipped/blocked.
    """
    # Normalize for semantic dedup (whitespace/quote invariant)
    tool_sig = _normalize_tool_sig(tool_name, args_str)

    # Circuit Breaker: semantic dedup (blocks identical calls even with formatting differences)
    _bypass_tools = {"update_persona", "update_identity"}
    if tool_sig in executed_tools_history and tool_name not in _bypass_tools:
        logger.warning(f"Circuit Breaker: Semantic dupe blocked: {tool_name}")
        return f"System: Tool {tool_name} with these exact args was already run. Do not repeat.", circuit_breaker_count + 1, False

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
    try:
        kwargs = parse_tool_args_fn(args_str)

        # Prevent collision: Authoritative context overrides AI-generated values
        if 'user_id' in kwargs:
            del kwargs['user_id']
        if 'request_scope' in kwargs:
            del kwargs['request_scope']

        # Inject channel_id for scope-aware tools
        if channel_id and 'channel_id' not in kwargs:
            kwargs['channel_id'] = str(channel_id)
        elif 'channel_id' not in kwargs:
            try:
                from src.bot import globals as bot_globals
                active_msg = bot_globals.active_message.get()
                if active_msg:
                    kwargs['channel_id'] = str(active_msg.channel.id)
            except Exception:
                pass

        result = await ToolRegistry.execute(tool_name, request_scope=request_scope, user_id=user_id, bot=bot, **kwargs)

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
        history_limit = int(limit * 0.002)
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
