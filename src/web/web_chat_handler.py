"""
Web Chat Handler — Preprocessing pipeline for web users.

Mirrors what chat_preprocessing.py + chat_response.py do for Discord,
adapted for WebSocket delivery instead of Discord message objects.
"""
import logging
import time
import datetime
from typing import Tuple, List, Optional
from pathlib import Path

from src.channels.types import UnifiedMessage, OutboundResponse
from src.prompts.manager import PromptManager

logger = logging.getLogger("Web.ChatHandler")

# Shared PromptManager instance
_prompt_manager = None


def _get_prompt_manager():
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager(prompt_dir="src/prompts")
    return _prompt_manager


async def handle_web_message(
    bot,
    content: str,
    user_id: str,
    username: str,
    websocket=None,
    interaction_mode: str = "professional",
    images: list = None,
    platform: str = "web",
) -> Tuple[str, List[Path]]:
    """
    Process a web chat message through the full Ernos pipeline.

    This mirrors the Discord ChatListener.on_message flow:
      1. Hippocampus recall (memory retrieval)
      2. System prompt generation
      3. Preprocessor analysis
      4. CognitionEngine.process()
      5. Post-processing (hippocampus observe, integrity audit)

    Args:
        bot: The ErnosBot instance
        content: User's message text
        user_id: Unique user identifier
        username: Display name
        websocket: WebSocket connection (for streaming updates)
        interaction_mode: "professional" (default) or "default" (core identity)

    Returns:
        (response_text, file_paths)
    """
    if not bot or not bot.cognition:
        return "Ernos is still starting up. Please try again in a moment.", []

    # Block non-admins during testing mode (mirrors Discord /testing command)
    from config import settings
    if getattr(settings, 'TESTING_MODE', False):
        admin_ids = getattr(settings, 'ADMIN_IDS', {settings.ADMIN_ID})
        # Web user_id may be a string; check both int and str forms
        if int(user_id) not in admin_ids and user_id not in {str(a) for a in admin_ids}:
            return getattr(settings, 'TESTING_MODE_MESSAGE', "Ernos is in testing mode. Please try again later."), []

    logger.info(f"[Web] Processing message from {username} ({user_id}): {content[:80]}...")

    # ─── Phase 0: Full Hippocampus Recall ──────────────────────
    # Uses the same deep recall as Discord DMs: working_memory + related_memories + knowledge_graph
    # This makes glasses/web a seamless extension of the DM conversation
    formatted_context = ""
    try:
        import functools
        # Treat web/glasses as DM (is_dm=True) so hippocampus loads the DM context window
        channel_id = f"web-{user_id}"
        recall_fn = functools.partial(
            bot.hippocampus.recall,
            content, user_id, channel_id, True,  # is_dm=True
            user_name=username
        )
        ctx_obj = await bot.loop.run_in_executor(None, recall_fn)
        parts = []
        if ctx_obj.working_memory:
            parts.append(f"Conversation History:\n{ctx_obj.working_memory}")
        if ctx_obj.related_memories:
            facts = "\n".join([f"- {m}" for m in ctx_obj.related_memories])
            parts.append(f"Related Facts:\n{facts}")
        if ctx_obj.knowledge_graph:
            kg = "\n".join([f"- {m}" for m in ctx_obj.knowledge_graph])
            parts.append(f"Knowledge Graph:\n{kg}")
        formatted_context = "\n\n".join(parts)
    except Exception as e:
        logger.error(f"Hippocampus recall failed: {e}")

    # ─── Phase 0.1: System Prompt ────────────────────────────
    pm = _get_prompt_manager()
    try:
        system_context = pm.get_system_prompt(
            is_core=True,
            persona_name=None,
            interaction_mode=interaction_mode,
            platform=platform,
            scope="PRIVATE",
            user_id=user_id,
            user_name=username,
        )
        # Inject glasses-specific directive — conditionally include vision awareness
        if platform == "glasses":
            has_video = bool(images)
            system_context += (
                "\n\n[GLASSES MODE — VOICE OUTPUT]\n"
                "You are speaking through Meta Ray-Ban smart glasses. "
                "Keep responses SHORT and conversational — they will be spoken aloud via TTS. "
                "No markdown, no bullet points, no formatting. Just natural speech. "
            )
            if has_video:
                system_context += (
                    "The glasses camera is ACTIVE — you CAN see what the user sees. "
                    "Refer to visual context naturally when relevant."
                )
            else:
                system_context += (
                    "The glasses camera is NOT active — this is a VOICE-ONLY call. "
                    "You CANNOT see anything. Do NOT make any visual references, do NOT describe "
                    "what you 'see', and do NOT claim to observe the user's surroundings. "
                    "If asked about something visual, say you can't see right now and suggest "
                    "they enable the camera."
                )
    except Exception as e:
        logger.error(f"System prompt generation failed: {e}")
        system_context = ""

    # ─── Phase 1: Build Context ──────────────────────────────
    # Web users are always PRIVATE scope (like Discord DMs)
    context_parts = [
        f"[PLATFORM: web]",
        f"[USER: {username} ({user_id})]",
        f"[SCOPE: PRIVATE]",
    ]

    if formatted_context:
        context_parts.append(f"\n[MEMORY CONTEXT]\n{formatted_context}")

    # Preprocessor analysis
    try:
        from src.preprocessors.unified import UnifiedPreProcessor
        preprocessor = UnifiedPreProcessor(bot)
        analysis = await preprocessor.analyze(content, user_id=user_id)
        if analysis and hasattr(analysis, "context_injection") and analysis.context_injection:
            context_parts.append(f"\n[PREPROCESSOR]\n{analysis.context_injection}")
    except Exception as e:
        logger.debug(f"Preprocessor skipped: {e}")

    context = "\n".join(context_parts)

    # ─── Phase 2: Cognition Engine ───────────────────────────
    # Add visual context note for glasses platform
    if images and platform == "glasses":
        context += "\n[VISUAL CONTEXT: Live camera frame from Meta Ray-Ban glasses attached.]"

    try:
        result = await bot.cognition.process(
            input_text=content,
            context=context,
            system_context=system_context,
            images=images,
            complexity="HIGH",
            request_scope="PRIVATE",
            user_id=user_id,
            channel_id=f"web-{user_id}",
        )

        # process() returns (response_text, files_to_upload, all_tool_outputs)
        if isinstance(result, tuple):
            if len(result) == 3:
                response_text, files, _tool_outputs = result
            elif len(result) == 2:
                response_text, files = result
            else:
                response_text = result[0] if result else ""
                files = []
        else:
            response_text = result
            files = []

    except Exception as e:
        logger.error(f"Cognition engine error: {e}", exc_info=True)
        return f"I encountered an error processing your message: {str(e)[:200]}", []

    # ─── Phase 3: Post-Processing ────────────────────────────

    # Hippocampus observe (save to memory)
    try:
        await bot.hippocampus.observe(
            user_id,
            content,
            response_text,
            f"web-{user_id}",
            True,  # is_dm equivalent
            user_name=username,
        )

        # Global activity logging
        from src.bot import globals
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": ts,
            "scope": "PRIVATE",
            "type": "interaction",
            "summary": f"Web chat with {username}: {content[:30]}...",
        }
        globals.activity_log.append(entry)
        bot.last_interaction = time.time()
    except Exception as e:
        logger.debug(f"Post-processing partial failure: {e}")

    # Integrity audit
    try:
        from src.bot.integrity_auditor import audit_response
        await audit_response(
            user_message=content,
            bot_response=response_text,
            bot=bot,
            user_id=user_id,
            conversation_context=context,
            system_context=system_context,
            tool_outputs=[],
        )
    except Exception as e:
        logger.debug(f"Integrity audit skipped: {e}")

    # Strip internal provenance tags
    import re
    origin_tag_re = re.compile(
        r'\[(?:SELF(?:-GENERATED[^\]]*)?|EXTERNAL:[^\]]*|SYSTEM BLOCK)\]:?\s*'
    )
    cleaned = origin_tag_re.sub("", response_text or "").strip()

    return cleaned, files or []
