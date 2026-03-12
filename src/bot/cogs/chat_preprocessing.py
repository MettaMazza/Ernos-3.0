"""
Chat Preprocessing — Early context retrieval, image extraction, provenance,
system prompt generation, and pre-processor coordination.

Extracted from ChatListener.on_message to keep the main cog under 300 lines.
"""
import logging
import functools
import datetime
import discord
from config import settings
from src.bot import globals

logger = logging.getLogger("ChatCog.Preprocessing")


async def early_hippocampus_recall(bot, message, is_dm):
    """Phase 0 — Run hippocampus recall and build unified context string.
    
    Returns (ctx_obj, early_context_str).
    """
    ctx_obj = None
    early_context = ""
    try:
        recall_fn = functools.partial(
            bot.hippocampus.recall,
            message.content, message.author.id, message.channel.id, is_dm,
            user_name=message.author.display_name or message.author.name
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
        if ctx_obj.lessons:
            lessons = "\n".join([f"- {l}" for l in ctx_obj.lessons])
            parts.append(f"Lessons:\n{lessons}")
        early_context = "\n\n".join(parts)
    except Exception as e:
        logger.warning(f"Early context retrieval failed (continuing): {e}")
    return ctx_obj, early_context


async def fetch_cross_channel_context(message, is_mentioned, is_target_channel, is_target_thread, is_dm, early_context):
    """Phase 0.01 — Fetch recent messages when @mentioned in a non-target channel."""
    is_cross_channel = is_mentioned and not is_target_channel and not is_target_thread and not is_dm
    if not is_cross_channel:
        return early_context
    try:
        channel_history_lines = []
        async for hist_msg in message.channel.history(limit=25, before=message):
            author_name = hist_msg.author.display_name or hist_msg.author.name
            ts = hist_msg.created_at.strftime("%H:%M")
            content = hist_msg.content[:1000] if hist_msg.content else "[no text]"
            channel_history_lines.append(f"[{ts}] {author_name}: {content}")
        channel_history_lines.reverse()
        if channel_history_lines:
            channel_name = getattr(message.channel, 'name', 'unknown-channel')
            channel_context = (
                f"\n\n[CHANNEL CONTEXT: #{channel_name}]\n"
                f"You were @mentioned in #{channel_name}. Here are the recent messages "
                f"from this channel so you understand the conversation:\n"
                + "\n".join(channel_history_lines)
                + "\n[END CHANNEL CONTEXT]"
            )
            early_context = channel_context + ("\n\n" + early_context if early_context else "")
            logger.info(f"Injected {len(channel_history_lines)} messages of channel context from #{channel_name}")
    except Exception as e:
        logger.warning(f"Cross-channel context fetch failed (continuing): {e}")
    return early_context


async def extract_early_images(message):
    """Phase 0.05 — Download images and run provenance checks.
    
    Returns (images: list[bytes], attachment_origin_tags: list[str], has_images: bool).
    """
    images = []
    attachment_origin_tags = []
    has_images = False
    if not message.attachments:
        return images, attachment_origin_tags, has_images

    for att in message.attachments:
        if not (att.content_type and att.content_type.startswith("image/")):
            continue
        try:
            image_bytes = await att.read()
            images.append(image_bytes)
            has_images = True
            
            # Provenance check
            try:
                prov_manager = getattr(globals.bot, 'provenance', None) if hasattr(globals, 'bot') else None
                if not prov_manager:
                    from src.security.provenance import ProvenanceManager
                    prov_manager = ProvenanceManager

                checksum = prov_manager.compute_checksum(image_bytes)
                record = prov_manager.lookup_by_checksum(checksum)

                if record:
                    meta = record.get("metadata", {})
                    prompt = meta.get("prompt", "Unknown Prompt")
                    intention = meta.get("intention", "Unknown Intention")
                    origin_tag = f"[SELF-GENERATED IMAGE: {att.filename}]"
                    if prompt != "Unknown Prompt":
                        origin_tag += f' (Prompt: "{prompt}"'
                        if intention != "Unknown Intention":
                            origin_tag += f' | Intention: "{intention}"'
                        origin_tag += ')'
                    attachment_origin_tags.append(origin_tag)
                    logger.info(f"Provenance HIT (Early): {att.filename} -> {origin_tag}")
                else:
                    attachment_origin_tags.append(
                        f"[EXTERNAL:USER IMAGE: {att.filename}] "
                        f"(Uploaded by {message.author.display_name})"
                    )
                    logger.info(f"Provenance MISS (Early): {att.filename} is external")
            except Exception as prov_err:
                logger.warning(f"Provenance check failed for {att.filename}: {prov_err}")
                attachment_origin_tags.append(f"[UNVERIFIED IMAGE: {att.filename}]")
        except Exception as e:
            logger.warning(f"Early image download failed: {e}")

    return images, attachment_origin_tags, has_images


def build_attachment_info(message):
    """Phase 0.06 — Build attachment summary string for preprocessor context."""
    if not message.attachments:
        return ""
    att_parts = []
    for att in message.attachments:
        type_desc = "image" if att.content_type and att.content_type.startswith("image/") else "file"
        att_parts.append(f"- {att.filename} ({type_desc}, {att.size} bytes)")
    return "ATTACHMENTS:\n" + "\n".join(att_parts)


def build_system_context(prompt_manager, message, scope_enum, is_core, thread_persona, is_persona_thread, ctx_obj):
    """Phase 0.1 — Generate the system prompt with placeholder goals."""
    from src.privacy.scopes import ScopeManager

    # Determine Active Engine & Mode
    from config import settings
    active_engine = "Unknown"
    active_mode = "Manual/Unknown"
    
    if hasattr(globals, 'bot') and getattr(globals.bot, 'engine_manager', None):
        eng = globals.bot.engine_manager.get_active_engine()
        if eng:
            active_engine = str(eng.name)
            # Mode Heuristics
            cloud_model = str(getattr(settings, 'OLLAMA_CLOUD_MODEL', ''))
            local_model = str(getattr(settings, 'OLLAMA_LOCAL_MODEL', ''))
            if cloud_model and cloud_model in active_engine:
                 active_mode = "Cloud (RAG)"
            elif local_model and local_model in active_engine:
                 active_mode = "Local (RAG)"
            elif "steering" in str(eng).lower():
                 active_mode = "Local Steering"
            else:
                 # Fallback if names don't match exactly
                 if "cloud" in active_engine.lower(): active_mode = "Cloud"
                 elif "local" in active_engine.lower(): active_mode = "Local"

    # Construct Model Config String
    model_config = (
        f"Cloud Mode: {settings.OLLAMA_CLOUD_MODEL} | "
        f"Local Mode: {settings.OLLAMA_LOCAL_MODEL} | "
        f"Steering: {settings.STEERING_MODEL_PATH}"
    )

    placeholder_goals = "[SYSTEM STATUS: PRE-COGNITIVE TRIAGE - ANALYZING USER INPUT]"

    # Determine interaction mode (DM-only — public always uses default Ernos)
    interaction_mode = "default"
    if scope_enum.name == "PRIVATE":
        try:
            from src.memory.preferences import PreferencesManager
            interaction_mode = PreferencesManager.get_interaction_mode(int(message.author.id))
        except Exception as e:
            logger.debug(f"Interaction mode check skipped: {e}")

    system_context = prompt_manager.get_system_prompt(
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        scope=scope_enum.name,
        user_id=str(message.author.id),
        user_name=str(message.author.display_name or message.author.name),
        active_engine=active_engine,
        active_mode=active_mode,
        model_config=model_config,
        active_goals=placeholder_goals,
        working_memory_summary=f"{len(ctx_obj.working_memory) if ctx_obj and ctx_obj.working_memory else 0} chars",
        is_core=is_core,
        persona_name=thread_persona if is_persona_thread else None,
        interaction_mode=interaction_mode
    )
    return system_context, placeholder_goals


def determine_scope_and_persona(message, is_dm):
    """Determine privacy scope and detect persona threads.
    
    Returns (scope_enum, is_core, thread_persona, is_persona_thread).
    """
    from src.privacy.scopes import ScopeManager

    scope_enum = ScopeManager.get_scope(message.author.id, message.channel.id, is_dm=is_dm)
    is_core = (scope_enum.name == 'CORE')

    thread_persona = None
    is_persona_thread = False
    if isinstance(message.channel, discord.Thread):
        from src.memory.persona_session import PersonaSessionTracker
        thread_persona = PersonaSessionTracker.get_thread_persona(str(message.channel.id))
        if thread_persona:
            is_persona_thread = True
            PersonaSessionTracker.touch_thread(str(message.channel.id))
            bot = globals.bot
            if bot and hasattr(bot, 'town_hall') and bot.town_hall:
                if thread_persona.lower() not in bot.town_hall._engaged:
                    bot.town_hall.mark_engaged(thread_persona)
                    logger.info(f"Re-engaged '{thread_persona}' from Town Hall for thread {message.channel.id}")

    # DM PERSONA DETECTION: Check if user has an active persona in DMs
    # This ensures DM personas get persona-mode prompts (fork HUD, persona identity)
    # instead of the full Ernos kernel + Ernos HUD
    if not is_persona_thread and is_dm:
        from src.memory.persona_session import PersonaSessionTracker
        dm_persona = PersonaSessionTracker.get_active(str(message.author.id))
        if dm_persona:
            thread_persona = dm_persona
            is_persona_thread = True

    return scope_enum, is_core, thread_persona, is_persona_thread
