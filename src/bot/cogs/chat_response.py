"""
Chat Response — Response delivery, integrity audit, hippocampus observation,
file attachment handling, and cooldown management.

Extracted from ChatListener.on_message to keep the main cog under 300 lines.
"""
import os
import re
import logging
import datetime
import discord
from src.bot import globals
from src.ui.views import ResponseFeedbackView
from src.channels.types import OutboundResponse

logger = logging.getLogger("ChatCog.Response")

# Internal origin/provenance tag pattern — never user-facing
_ORIGIN_TAG_RE = re.compile(
    r'\[(?:SELF(?:-GENERATED[^\]]*)?|EXTERNAL:[^\]]*|SYSTEM BLOCK)\]:?\s*'
)

# Internal Cognitive Tape Machine tags
_TAPE_TAG_RE = re.compile(
    r'<(?:SEEK|SCAN|WRITE|INSERT|EDIT_CODE|REVERT_CODE|FORK_TAPE):\s*.*?>|<(?:READ|DELETE|HALT)>',
    re.DOTALL | re.IGNORECASE
)
_TAPE_EMIT_RE = re.compile(r'<EMIT:\s*(.*?)\s*>', re.DOTALL | re.IGNORECASE)


async def deliver_response(
    bot, message, final_response_text, files,
    scope_enum, is_dm, is_persona_thread, thread_persona,
    adapter, analysis, images, attachment_origin_tags,
    formatted_context, system_context, complexity, engine,
    dm_cooldowns, dm_cooldown_seconds, dm_queues,
    tool_outputs=None,
):
    """
    Phase 4+ — Send the engine response to Discord.

    Handles: integrity audit, hippocampus observe, activity logging,
    file attachments, mention formatting, chunking, DM cooldowns.
    """
    if not final_response_text:
        return

    # 6.5 Integrity Audit
    try:
        from src.bot.integrity_auditor import audit_response
        audit_result = await audit_response(
            user_message=message.content,
            bot_response=final_response_text,
            bot=bot,
            user_id=str(message.author.id),
            conversation_context=formatted_context or "",
            system_context=system_context or "",
            tool_outputs=tool_outputs or [],
        )
        if audit_result.get("verdict") == "TIER2":
            logger.warning(
                f"Integrity Audit: TIER2 {audit_result.get('failure_type')} "
                f"detected for user {message.author.id}"
            )
    except Exception as e:
        logger.error(f"Integrity Audit failed: {e}")

    # 7. Hippocampus Observe
    try:
        await bot.hippocampus.observe(
            str(message.author.id),
            message.content,
            final_response_text,
            message.channel.id,
            is_dm,
            user_name=message.author.display_name or message.author.name
        )

        # 8. Global Activity Logging
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": ts,
            "scope": scope_enum.name,
            "type": "interaction",
            "summary": f"Chat with {message.author}: {message.content[:30]}..."
        }
        globals.activity_log.append(entry)

        import time
        bot.last_interaction = time.time()
        logger.info("Cycle Complete. Idle Timer Reset.")
    except Exception as e:
        logger.error(f"Hippocampus/Log Failed: {e}")

    # Prepare Discord files
    discord_files = []
    if files:
        for fpath in files:
            if os.path.exists(fpath):
                try:
                    discord_files.append(discord.File(fpath))
                    logger.info(f"Attached file: {fpath}")
                except Exception as e:
                    logger.error(f"Failed to attach {fpath}: {e}")

    # Strip internal origin/provenance tags
    cleaned = _ORIGIN_TAG_RE.sub('', final_response_text)
    
    # Strip Tape system tags, but retain the text Payload of EMIT commands
    cleaned = _TAPE_EMIT_RE.sub(r'\1', cleaned)
    cleaned = _TAPE_TAG_RE.sub('', cleaned).strip()
    
    formatted_text = await adapter.format_mentions(cleaned)

    # Send with chunking + feedback view
    view = ResponseFeedbackView(bot, final_response_text)
    if len(formatted_text) > 2000:
        chunks = [formatted_text[i:i + 2000] for i in range(0, len(formatted_text), 2000)]
        for i, chunk in enumerate(chunks):
            try:
                if i == len(chunks) - 1:
                    await message.reply(chunk, view=view, files=discord_files)
                else:
                    await message.reply(chunk)
            except (discord.HTTPException, discord.NotFound):
                # Original message was deleted — fall back to channel.send
                if i == len(chunks) - 1:
                    await message.channel.send(chunk, view=view, files=discord_files)
                else:
                    await message.channel.send(chunk)
    else:
        try:
            await message.reply(formatted_text, view=view, files=discord_files)
        except (discord.HTTPException, discord.NotFound):
            await message.channel.send(formatted_text, view=view, files=discord_files)

    # 10. DM Cooldown
    if is_dm:
        import time
        user_id = message.author.id
        dm_cooldowns[user_id] = time.time() + dm_cooldown_seconds
        logger.info(f"DM cooldown set for user {user_id}: {dm_cooldown_seconds}s")

        if user_id in dm_queues and dm_queues[user_id]:
            queued = dm_queues.pop(user_id)
            batched = "\n---\n".join(queued)
            await message.channel.send(
                f"📬 **Processing {len(queued)} queued message(s):**\n{batched[:500]}..."
            )


async def handle_engine_error(message, error):
    """Send an error message to the user when the cognitive engine fails."""
    logger.error(f"Cognitive Engine Failure: {error}")
    try:
        await message.reply(f"[ERROR] Cognitive Engine Failure: {error}")
    except (discord.HTTPException, discord.NotFound):
        # Original message deleted — send to channel instead
        try:
            await message.channel.send(f"[ERROR] Cognitive Engine Failure: {error}")
        except Exception:
            logger.warning(f"Could not deliver error to channel: {error}")


def reset_visual_cortex(bot):
    """Reset VisualCortex turn lock after response cycle."""
    try:
        creative = bot.cerebrum.get_lobe("CreativeLobe")
        if creative:
            visual = creative.get_ability("VisualCortexAbility")
            if visual:
                visual.reset_turn_lock()
    except Exception as e:
        logger.error(f"Failed to reset VisualCortex lock: {e}")
