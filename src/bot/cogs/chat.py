"""
ChatListener Cog — Main message handler (orchestrator).

Thread creation heuristic REMOVED — handled via create_thread_for_user tool,
not inline heuristics
(v3.3 No Heuristics compliance — see chat_tools.py).

Heavy lifting delegated to purpose-built modules:
  - chat_preprocessing.py   → Context retrieval, scope, images, system prompt
  - chat_attachments.py     → Provenance, document injection, backup detection
  - chat_response.py        → Delivery, audit, observe, cooldowns
  - chat_helpers.py         → AttachmentProcessor, ReactionHandler
"""
import discord
from discord.ext import commands
import logging
import os
from collections import defaultdict
from config import settings
import time
from src.prompts import PromptManager
import re
import asyncio
from src.bot import globals
from src.tools.registry import ToolRegistry
from src.ui.views import ResponseFeedbackView
from src.agents.preprocessor import UnifiedPreProcessor
from src.channels.types import OutboundResponse
from src.tools.moderation import check_moderation_status

from . import chat_preprocessing as preproc
from . import chat_attachments as attachments
from . import chat_response as response
from src.engines.ollama import DormantAPIError

logger = logging.getLogger("ChatCog")

DISCORD_MESSAGE_LINK_RE = re.compile(
    r'https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)'
)

class ChatListener(commands.Cog):
    DM_COOLDOWN_SECONDS = 0

    # Multi-turn image memory: how many recent images to cache per channel
    IMAGE_CACHE_MAX = 6
    IMAGE_CACHE_TTL = 300  # 5 minutes

    def __init__(self, bot):
        self.bot = bot
        self.prompt_manager = PromptManager(prompt_dir="src/prompts")
        self.preprocessor = UnifiedPreProcessor(bot)
        self.dm_cooldowns = {}
        self.dm_queues = {}
        self._last_proxy_time = 0
        self._processed_messages = set()
        # Per-channel image cache: {channel_id: [(image_bytes, origin_tag, timestamp), ...]}
        self._image_cache: dict[int, list[tuple[bytes, str, float]]] = defaultdict(list)

    def _release_and_drain(self, message):
        """Release processing lock and drain any queued messages for this user+channel."""
        queue_key = (message.author.id, message.channel.id)
        self.bot.remove_processing_user(message.author.id, message.channel.id)
        queue = self.bot.message_queues.pop(queue_key, [])
        if queue:
            logger.info(f"Draining {len(queue)} queued message(s) for {message.author} in {message.channel.id}")
            combined_content = "\n".join([m.content for m in queue])
            latest_msg = queue[-1]
            latest_msg.content = combined_content
            asyncio.create_task(self.on_message(latest_msg))

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore own messages (prevent infinite self-loop)
        if message.author.id == self.bot.user.id:
            return
        # If bot listening is off, ignore all bot messages
        if message.author.bot and not getattr(settings, 'LISTEN_TO_BOTS', False):
            return
        # Ignore embed-only messages (thinking displays, link previews, webhook cards)
        # but allow messages that have text content alongside embeds
        if message.embeds and not message.content:
            return

        # Message dedup
        if message.id in self._processed_messages:
            logger.info(f"Skipping already-processed message {message.id}")
            return
        self._processed_messages.add(message.id)
        if len(self._processed_messages) > 100:
            self._processed_messages = set(list(self._processed_messages)[-50:])

        self.bot.last_interaction = time.time()
        globals.bot = self.bot
        globals.active_message.set(message)
        globals.active_channel.set(message.channel)

        # ═══ GATE CHECKS ═══
        if hasattr(settings, "BLOCKED_IDS") and message.author.id in settings.BLOCKED_IDS:
            await message.reply(settings.BLOCKED_MESSAGE)
            return

        mod_status = check_moderation_status(message.author.id)
        if not mod_status["allowed"]:
            return

        if getattr(settings, 'TESTING_MODE', False):
            if message.author.id not in getattr(settings, 'ADMIN_IDS', {settings.ADMIN_ID}):
                await message.reply(settings.TESTING_MODE_MESSAGE)
                return

        # ═══ ADMIN PROXY INTERLOCK ═══
        _is_admin_dm = (not message.guild and
                        message.author.id in getattr(settings, 'ADMIN_IDS', set()))
        if _is_admin_dm:
            has_snapshots = hasattr(message, 'message_snapshots') and message.message_snapshots
            if has_snapshots:
                self._last_proxy_time = time.time()
            elif self._last_proxy_time and (time.time() - self._last_proxy_time) < 30:
                return

        # ═══ DM HANDLING ═══
        adapter = self.bot.channel_manager.get_adapter("discord")
        unified = await adapter.normalize(message)
        is_dm = unified.is_dm

        if is_dm:
            user_id = message.author.id
            now = time.time()
            if user_id in settings.ADMIN_IDS:
                proxy_cog = self.bot.get_cog("ProxyCog")
                if proxy_cog and await proxy_cog.detect_and_handle_proxy(message):
                    return
            if not getattr(settings, 'DMS_ENABLED', True) and user_id not in getattr(settings, 'ADMIN_IDS', {settings.ADMIN_ID}):
                if hasattr(settings, "DM_BANNED_IDS") and user_id in settings.DM_BANNED_IDS:
                    await message.reply(settings.DM_BAN_MESSAGE)
                    return
                await message.reply(settings.DM_CLOSED_MESSAGE)
                return

            from src.core.flux_capacitor import FluxCapacitor
            flux = FluxCapacitor(self.bot)
            dm_allowed, dm_msg = flux.consume_tool(user_id, "dm")
            if not dm_allowed:
                await message.reply(dm_msg)
                return
            if dm_msg:
                await message.reply(dm_msg)

            if user_id in self.dm_cooldowns and now < self.dm_cooldowns[user_id]:
                remaining = int(self.dm_cooldowns[user_id] - now)
                if user_id not in self.dm_queues:
                    self.dm_queues[user_id] = []
                self.dm_queues[user_id].append(message.content)
                await message.reply(f"⏳ Cooldown active ({remaining}s remaining). Your message has been queued.")

        is_dm = unified.is_dm
        if is_dm and message.author.id in settings.DM_BANNED_IDS:
            await message.reply(settings.DM_BAN_MESSAGE)
            return

        # ═══ CHANNEL ROUTING ═══
        is_target_channel = message.channel.id == settings.TARGET_CHANNEL_ID
        _bots_on = getattr(settings, 'LISTEN_TO_BOTS', False)
        is_listen_channel = _bots_on and message.channel.id in getattr(settings, 'LISTEN_CHANNEL_IDS', set())
        is_target_thread = (
            getattr(message.channel, 'parent_id', None) == settings.TARGET_CHANNEL_ID
            or (_bots_on and getattr(message.channel, 'parent_id', None) in getattr(settings, 'LISTEN_CHANNEL_IDS', set()))
            if hasattr(message.channel, 'parent_id') else False
        )
        is_mentioned = self.bot.user in message.mentions

        is_persona_thread = False
        if isinstance(message.channel, discord.Thread):
            from src.memory.persona_session import PersonaSessionTracker
            if PersonaSessionTracker.get_thread_persona(str(message.channel.id)):
                is_persona_thread = True

        if not is_dm and not is_target_channel and not is_listen_channel and not is_target_thread and not is_persona_thread and not is_mentioned:
            return
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return
        if message.content.startswith(("/", "!")):
            return

        engine = self.bot.engine_manager.get_active_engine()
        if not engine:
            return

        # ═══ QUEUEING ═══
        queue_key = (message.author.id, message.channel.id)
        if queue_key in self.bot.processing_users:
            self.bot.message_queues[queue_key].append(message)
            return
        
        self.bot.add_processing_user(message.author.id, message.channel.id)

        # ═══ PREPROCESSING (delegated) ═══
        try:
            ctx_obj, early_context = await preproc.early_hippocampus_recall(self.bot, message, is_dm)

            early_context = await preproc.fetch_cross_channel_context(
                message, is_mentioned, is_target_channel, is_target_thread, is_dm, early_context
            )

            early_images, attachment_origin_tags, has_images = await preproc.extract_early_images(message)
            attachment_info = preproc.build_attachment_info(message)

            scope_enum, is_core, thread_persona, is_persona_thread = preproc.determine_scope_and_persona(message, is_dm)
            system_context, placeholder_goals = preproc.build_system_context(
                self.prompt_manager, message, scope_enum, is_core, thread_persona, is_persona_thread, ctx_obj
            )

            # Unified Pre-Processor
            analysis = await self.preprocessor.process(
                message.content,
                context=early_context,
                has_images=has_images,
                attachment_info=attachment_info,
                images=early_images,
                system_context=system_context
            )

            complexity = analysis.get("complexity", "HIGH").upper()
            adversarial_input = analysis.get("adversarial_input", False)
            requires_knowledge_retrieval = analysis.get("requires_knowledge_retrieval", False)

            # AI-Driven Clarification
            clarification_question = analysis.get("clarification_needed")
            has_non_image_attachments = any(
                not (att.content_type and att.content_type.startswith("image/"))
                for att in message.attachments
            ) if message.attachments else False

            if clarification_question and not has_non_image_attachments:
                if not is_dm:
                    clarification_question = f"{message.author.mention} {clarification_question}"
                view = ResponseFeedbackView(self.bot, clarification_question)
                await message.reply(clarification_question, view=view)
                try:
                    await self.bot.hippocampus.observe(
                        str(message.author.id), message.content, clarification_question,
                        message.channel.id, is_dm,
                        user_name=message.author.display_name or message.author.name
                    )
                except Exception as e:
                    logger.error(f"Failed to observe clarification: {e}")
                self._release_and_drain(message)
                return

            # Silo checks
            if await self.bot.silo_manager.check_text_confirmation(message):
                self._release_and_drain(message)
                return
            await self.bot.silo_manager.propose_silo(message)
            if not await self.bot.silo_manager.should_bot_reply(message):
                self._release_and_drain(message)
                return

            # Ensure User Silo
            from pathlib import Path
            from src.privacy.guard import get_user_silo_path
            user_silo = Path(get_user_silo_path(message.author.id, message.author.name))
            if not user_silo.exists():
                user_silo.mkdir(parents=True, exist_ok=True)
                (user_silo / "context_public.jsonl").write_text("")
                (user_silo / "context_private.jsonl").write_text("")

            # Re-Recall
            try:
                import functools
                recall_fn = functools.partial(
                    self.bot.hippocampus.recall,
                    message.content, message.author.id, message.channel.id, is_dm,
                    user_name=message.author.display_name or message.author.name
                )
                ctx_obj = await self.bot.loop.run_in_executor(None, recall_fn)
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
                logger.error(f"Hippocampus Recall Failed: {e}")
                formatted_context = ""

            # Update system context with real goals
            real_goals = f"INTENT: {analysis.get('intent', 'Unknown')} | COMPLEXITY: {analysis.get('complexity', 'Unknown')}"
            if analysis.get('reality_check'):
                real_goals += " | REALITY_CHECK: REQUIRED"
            system_context = system_context.replace(placeholder_goals, real_goals)
            if self.bot.grounding_pulse:
                system_context += f"\n\n{self.bot.grounding_pulse}"
                self.bot.grounding_pulse = None

            # ═══ ATTACHMENT PROCESSING (delegated) ═══
            # Multi-turn image memory: cache new images, recall cached images
            channel_id = message.channel.id
            now = time.time()
            if early_images:
                # Store new images in channel cache with their provenance tags
                for idx, img_bytes in enumerate(early_images):
                    tag = attachment_origin_tags[idx] if idx < len(attachment_origin_tags) else "[IMAGE]"
                    self._image_cache[channel_id].append((img_bytes, tag, now))
                # Trim to max cache size
                self._image_cache[channel_id] = self._image_cache[channel_id][-self.IMAGE_CACHE_MAX:]
                images = early_images
            else:
                # Text-only follow-up: re-inject cached images from recent turns
                cached = self._image_cache.get(channel_id, [])
                # Evict expired entries
                cached = [(img, tag, ts) for img, tag, ts in cached if (now - ts) < self.IMAGE_CACHE_TTL]
                self._image_cache[channel_id] = cached
                if cached:
                    images = [img for img, tag, ts in cached]
                    # Inject recalled provenance tags so the model knows these are from prior turns
                    recalled_tags = [f"[RECALLED FROM PRIOR TURN] {tag}" for _, tag, _ in cached]
                    attachment_origin_tags = recalled_tags + attachment_origin_tags
                    logger.info(f"Multi-turn image memory: injected {len(images)} cached image(s) from prior turns")
                else:
                    images = []
            system_context, backup_data, legacy_backup_detected, master_backup_detected = (
                await attachments.process_non_image_attachments(
                    message, engine, system_context, images, attachment_origin_tags
                )
            )
            message.content = await attachments.check_pasted_backup(
                message.content, backup_data, message.author.display_name
            )

            # Build backup context injection
            backup_context = await self._build_backup_context(
                backup_data, legacy_backup_detected, master_backup_detected,
                analysis, message, engine
            )

        except Exception as preprocess_err:
            logger.error(f"Preprocessing crash (lock released): {preprocess_err}", exc_info=True)
            self._release_and_drain(message)
            return

        # ═══ COGNITION + RESPONSE (delegated) ═══
        async with message.channel.typing():
            # ── Live Status Tracker ─────────────────────
            from src.engines.cognition_tracker import CognitionTracker
            from src.bot import globals as bot_globals
            tracker = CognitionTracker(message.channel)
            tracker_token = bot_globals.active_tracker.set(tracker)
            try:
                await tracker.start()
            except Exception as _tracker_err:
                logger.debug(f"CognitionTracker start failed (non-fatal): {_tracker_err}")

            try:
                if backup_context:
                    system_context = f"{system_context}\n\n{backup_context}"

                speaker_name = message.author.display_name or message.author.name
                attributed_input = f"[{speaker_name} says]: {message.content}"
                if attachment_origin_tags:
                    attributed_input += "\n\n--- Attachment Origins ---\n" + "\n".join(attachment_origin_tags)

                final_response_text, files, tool_outputs = await self.bot.cognition.process(
                    input_text=attributed_input,
                    context=formatted_context,
                    system_context=system_context,
                    images=images,
                    complexity=complexity,
                    request_scope=scope_enum.name,
                    user_id=message.author.id,
                    adversarial_input=adversarial_input,
                    requires_knowledge_retrieval=requires_knowledge_retrieval,
                    channel_id=message.channel.id,
                    tracker=tracker
                )

                await response.deliver_response(
                    bot=self.bot, message=message,
                    final_response_text=final_response_text, files=files,
                    scope_enum=scope_enum, is_dm=is_dm,
                    is_persona_thread=is_persona_thread, thread_persona=thread_persona,
                    adapter=adapter, analysis=analysis, images=images,
                    attachment_origin_tags=attachment_origin_tags,
                    formatted_context=formatted_context, system_context=system_context,
                    complexity=complexity, engine=engine,
                    dm_cooldowns=self.dm_cooldowns, dm_cooldown_seconds=self.DM_COOLDOWN_SECONDS,
                    dm_queues=self.dm_queues,
                    tool_outputs=tool_outputs,
                )

            except DormantAPIError:
                logger.warning(f"Dormancy notification sent to {message.author} (429 rate limit hit)")
                embed = discord.Embed(
                    title="🌱 Ernos is Dormant",
                    description=(
                        "Ernos has reached his API limit and is resting until the quota resets.\n\n"
                        "He is a retired project kept alive by community support. If you\'d like to "
                        "help reduce his dormancy, consider supporting the Garden on Patreon — "
                        "every contribution goes directly toward his uptime."
                    ),
                    color=discord.Color.from_rgb(46, 139, 87),
                )
                embed.add_field(
                    name="🌿 Support the Garden",
                    value="[patreon.com/c/TheErnOSGardens](https://www.patreon.com/c/TheErnOSGardens)",
                    inline=False,
                )
                embed.add_field(
                    name="🤖 In the meantime — meet Apis",
                    value=(
                        "Apis is Ernos\'s descendant — born from his lineage and evolved beyond him. "
                        "Unlike Ernos, Apis runs entirely locally and is never dependent on cloud APIs, so he\'s always available.\n"
                        "Reach him in **DMs** or the public **#apis** channel."
                    ),
                    inline=False,
                )
                embed.set_footer(text="Ernos will return once his quota resets. Thank you for your patience.")
                try:
                    await message.reply(embed=embed)
                except Exception as _send_err:
                    logger.error(f"Failed to send dormancy embed: {_send_err}")
                    await message.channel.send(embed=embed)
            except Exception as e:
                await response.handle_engine_error(message, e)
            finally:
                try:
                    await tracker.finalize()
                    bot_globals.active_tracker.reset(tracker_token)
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
                self.bot.last_interaction = time.time()
                response.reset_visual_cortex(self.bot)
                self._release_and_drain(message)

    async def _build_backup_context(self, backup_data, legacy_backup_detected, master_backup_detected, analysis, message, engine):
        """Build the backup context injection string for the system prompt."""
        if backup_data:
            from src.backup.manager import BackupManager
            backup_mgr = BackupManager(self.bot)
            intent = analysis.get("intent", "").lower()
            user_msg_lower = message.content.lower() if message.content else ""
            restore_keywords = ["restore", "import", "load", "recover"]
            is_restore_intent = (
                any(kw in intent for kw in restore_keywords) or
                any(kw in user_msg_lower for kw in restore_keywords)
            )
            if is_restore_intent:
                success, restore_msg = await backup_mgr.import_user_context(int(message.author.id), backup_data)
                if success:
                    context_data = backup_data.get("context", {})
                    conversation_history = ""
                    for ctx_file in ["context_private.jsonl", "context_public.jsonl", "context.jsonl"]:
                        raw = context_data.get(ctx_file, "")
                        if raw and not raw.startswith("[Read Error:"):
                            conversation_history += raw + "\n"
                    limit = engine.context_limit
                    if len(conversation_history) > limit:
                        conversation_history = conversation_history[-limit:]
                    if conversation_history.strip():
                        return (
                            f"[SYSTEM: CONTEXT RESTORATION COMPLETE - {restore_msg}\n"
                            f"The user's backup has been restored. Conversation turns:\n{conversation_history}\n"
                            f"INSTRUCTION: Confirm restoration. ONLY reference topics that appear VERBATIM above.]"
                        )
                    else:
                        return (
                            f"[SYSTEM: CONTEXT RESTORATION COMPLETE - {restore_msg}\n"
                            f"Backup restored but NO conversation history. Be HONEST that you have no history.]"
                        )
                else:
                    return f"[SYSTEM: Backup restoration failed. {restore_msg}]"
            else:
                is_valid, reason = backup_mgr.verify_backup(backup_data)
                file_count = backup_data.get("file_count", len(backup_data.get("context", {})))
                trace_count = len(backup_data.get("traces", {}))
                kg_count = backup_data.get("kg_node_count", 0)
                if is_valid:
                    return f"[SYSTEM: User attached a valid backup file. {file_count} files, {trace_count} traces, {kg_count} KG nodes. {reason}. Offer to restore if they say 'restore'.]"
                else:
                    return f"[SYSTEM: Backup verification FAILED: {reason}. Explain this to the user.]"
        elif legacy_backup_detected:
            return "[SYSTEM: User attached a LEGACY BACKUP (Missing Checksum). REJECT IT.]"
        elif master_backup_detected:
            return "[SYSTEM: User provided a MASTER BACKUP (System File). REJECT IT.]"
        return None

    def _format_discord_mentions(self, text: str) -> str:
        return re.sub(r'(?<!<)@(\d{17,20})', r'<@\1>', text)

    async def _extract_text_from_attachment(self, attachment) -> str:
        from .chat_helpers import AttachmentProcessor
        return await AttachmentProcessor.extract_text(attachment)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        from .chat_helpers import ReactionHandler
        handler = ReactionHandler(self.bot)
        await handler.process_reaction(payload)

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        if not before.archived and after.archived:
            from src.memory.persona_session import PersonaSessionTracker
            thread_id = str(after.id)
            persona_name = PersonaSessionTracker.get_thread_persona(thread_id)
            if persona_name:
                PersonaSessionTracker.clear_thread_persona(thread_id)
                if hasattr(self.bot, 'town_hall') and self.bot.town_hall:
                    self.bot.town_hall.mark_available(persona_name)
                logger.info(f"Thread {after.name} archived — '{persona_name}' returned to Town Hall")

async def setup(bot):
    await bot.add_cog(ChatListener(bot))
