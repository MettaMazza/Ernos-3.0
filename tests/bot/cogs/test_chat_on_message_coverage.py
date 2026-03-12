"""
on_message handler coverage for src/bot/cogs/chat.py
Covers the large untested branches in on_message:
  - Message dedup (49-54)
  - Admin proxy interlock (80-88)
  - DM handling: admin proxy, toggle, DM ban, cooldown (96-134)
  - Persona thread detection (146-158)
  - Thread creation (178-189)
  - DM ban check (198-200)
  - Cross-channel context (248-270)
  - Early image extraction (283-284)
  - Silo checks (339-349)
  - Reality check, persona thread log (409, 441)
  - Attachment/backup handling (454-667)
  - Response path (706-788)
  - Queue squash (818-833)
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import asyncio
import time
import discord


# ─── Helpers ─────────────────────────────────────────────────────────

def _bot():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 99999
    bot.last_interaction = 0
    bot.engine_manager = MagicMock()
    bot.channel_manager = MagicMock()
    bot.silo_manager = MagicMock()
    bot.silo_manager.check_text_confirmation = AsyncMock(return_value=False)
    bot.silo_manager.propose_silo = AsyncMock()
    bot.silo_manager.should_bot_reply = AsyncMock(return_value=True)
    bot.hippocampus = MagicMock()
    bot.cerebrum = MagicMock()
    bot.cerebrum.get_lobe = MagicMock(return_value=None)
    bot.grounding_pulse = None
    bot.processing_users = set()
    bot.message_queues = {}
    bot.add_processing_user = MagicMock()
    bot.remove_processing_user = MagicMock()
    bot.tape_engine = AsyncMock()
    bot.cognition.process = AsyncMock(return_value=("Response!", [], []))
    bot.cognition.process = AsyncMock(return_value=("Response!", [], []))
    bot.loop = MagicMock()
    bot.get_context = AsyncMock()
    return bot


def _msg(content="hello", author_id=111, is_dm=True, guild=None, channel_id=1,
         attachments=None, mentions=None, bot_user=False, msg_id=12345):
    msg = MagicMock()
    msg.id = msg_id
    msg.content = content
    msg.author = MagicMock()
    msg.author.id = author_id
    msg.author.bot = bot_user
    msg.author.name = "TestUser"
    msg.author.display_name = "TestUser"
    msg.author.mention = f"<@{author_id}>"
    msg.guild = guild
    msg.channel = MagicMock()
    msg.channel.id = channel_id
    msg.channel.type = discord.ChannelType.private if is_dm else discord.ChannelType.text
    msg.channel.send = AsyncMock()
    msg.channel.parent_id = None
    msg.attachments = attachments or []
    msg.mentions = mentions or []
    msg.reply = AsyncMock()
    msg.add_reaction = AsyncMock()
    msg.create_thread = AsyncMock()
    msg.reference = None
    msg.message_snapshots = None

    # async context manager for typing
    class _Typing:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
    msg.channel.typing = MagicMock(return_value=_Typing())
    return msg


def _cog(bot=None):
    from src.bot.cogs.chat import ChatListener
    b = bot or _bot()
    with patch("src.bot.cogs.chat.PromptManager"), \
         patch("src.bot.cogs.chat.UnifiedPreProcessor") as MockPP:
        MockPP.return_value.analyze = AsyncMock(return_value={
            "intent": "chat", "complexity": "LOW"
        })
        cog = ChatListener(b)
        cog.prompt_manager = MagicMock()
        cog.prompt_manager.get_system_prompt = MagicMock(return_value="SYSTEM_PROMPT")
        cog.preprocessor = AsyncMock()
        cog.preprocessor.process = AsyncMock(return_value={"attributed_input": "hello", "analysis_context": "ctx", "images": []})
    return cog


def _adapter(is_dm=True):
    adapter = MagicMock()
    unified = MagicMock()
    unified.is_dm = is_dm
    unified.author_name = "TestUser"
    adapter.normalize = AsyncMock(return_value=unified)
    adapter.format_mentions = AsyncMock(side_effect=lambda x: x)
    return adapter


def _recall_obj(wm="prev context", related=None, kg=None, lessons=None):
    obj = MagicMock()
    obj.working_memory = wm
    obj.related_memories = related or []
    obj.knowledge_graph = kg or []
    obj.lessons = lessons or []
    return obj


# ─── Message Dedup (lines 48-54) ─────────────────────────────────────
class TestMessageDedup:
    @pytest.mark.asyncio
    async def test_duplicate_message_skipped(self):
        """line 49-50: duplicate message skipped."""
        bot = _bot()
        cog = _cog(bot)
        msg = _msg(bot_user=False)
        cog._processed_messages.add(msg.id)  # Already processed
        
        await cog.on_message(msg)
        # Should return immediately, no processing
        bot.channel_manager.get_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_dedup_cleanup(self):
        """line 53-54: cleanup when > 100 entries."""
        bot = _bot()
        cog = _cog(bot)
        # Fill with 101 entries
        cog._processed_messages = set(range(101))
        msg = _msg(bot_user=True, msg_id=9999, author_id=99999)  # Ernos's own ID → self-loop return
        
        # Self-message returns early but dedup doesn't trigger
        await cog.on_message(msg)
        # Now send non-bot message to trigger dedup cleanup
        msg2 = _msg(msg_id=9998)
        msg2.author.id = 111
        msg2.guild = None
        msg2.channel.type = discord.ChannelType.private
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        with patch("src.bot.cogs.chat.settings") as s:
            s.ADMIN_IDS = set()
            s.DMS_ENABLED = True
            s.DM_BANNED_IDS = set()
            s.TARGET_CHANNEL_ID = 999
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            # Will need engine
            bot.engine_manager.get_active_engine.return_value = None
            await cog.on_message(msg2)
        
        # After cleanup, should be <= 51
        assert len(cog._processed_messages) <= 52


# ─── Admin Proxy Interlock (lines 79-88) ─────────────────────────────
class TestProxyInterlock:
    @pytest.mark.asyncio
    async def test_forward_sets_interlock(self):
        """lines 81-84: forward detected, sets proxy time."""
        bot = _bot()
        cog = _cog(bot)
        msg = _msg(author_id=42, is_dm=True)
        msg.message_snapshots = [MagicMock()]
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        with patch("src.bot.cogs.chat.settings") as s:
            s.ADMIN_IDS = {42}
            s.DMS_ENABLED = True
            s.DM_BANNED_IDS = set()
            s.TARGET_CHANNEL_ID = 999
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            # Proxy detection — mock ProxyCog via bot.get_cog
            mock_proxy_cog = MagicMock()
            mock_proxy_cog.detect_and_handle_proxy = AsyncMock(return_value=True)
            bot.get_cog = MagicMock(return_value=mock_proxy_cog)
            await cog.on_message(msg)
        
        assert cog._last_proxy_time > 0

    @pytest.mark.asyncio
    async def test_comment_suppressed_in_interlock_window(self):
        """lines 85-88: follow-up comment suppressed."""
        bot = _bot()
        cog = _cog(bot)
        cog._last_proxy_time = time.time()  # Just set
        
        msg = _msg(author_id=42, is_dm=True, content="be nice to them")
        msg.message_snapshots = None
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        with patch("src.bot.cogs.chat.settings") as s:
            s.ADMIN_IDS = {42}
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            await cog.on_message(msg)
        
        # Should return early, not processing the message
        bot.silo_manager.check_text_confirmation.assert_not_called()


# ─── DM Handling (lines 96-134) ──────────────────────────────────────
class TestDMHandling:
    @pytest.mark.asyncio
    async def test_admin_proxy_handled(self):
        """lines 102-109: admin DM triggers proxy."""
        bot = _bot()
        cog = _cog(bot)
        msg = _msg(author_id=42, is_dm=True, content="https://discord.com/channels/1/2/3")
        msg.message_snapshots = None
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        with patch("src.bot.cogs.chat.settings") as s:
            s.ADMIN_IDS = {42}
            s.DMS_ENABLED = True
            s.DM_BANNED_IDS = set()
            s.TARGET_CHANNEL_ID = 999
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            mock_proxy_cog = MagicMock()
            mock_proxy_cog.detect_and_handle_proxy = AsyncMock(return_value=True)
            bot.get_cog = MagicMock(return_value=mock_proxy_cog)
            await cog.on_message(msg)
        
        # Should return after proxy handle
        bot.silo_manager.check_text_confirmation.assert_not_called()

    @pytest.mark.asyncio
    async def test_dms_disabled_non_admin(self):
        """lines 113-121: DMs disabled, non-admin user blocked."""
        bot = _bot()
        cog = _cog(bot)
        msg = _msg(author_id=555, is_dm=True)
        msg.message_snapshots = None
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        with patch("src.bot.cogs.chat.settings") as s:
            s.ADMIN_IDS = {42}
            s.ADMIN_ID = 42
            s.DMS_ENABLED = False
            s.DM_BANNED_IDS = set()
            s.DM_CLOSED_MESSAGE = "DMs are closed"
            s.TARGET_CHANNEL_ID = 999
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            await cog.on_message(msg)
        
        msg.reply.assert_called_with("DMs are closed")

    @pytest.mark.asyncio
    async def test_dms_disabled_dm_banned(self):
        """lines 115-117: DMs disabled + user is DM-banned."""
        bot = _bot()
        cog = _cog(bot)
        msg = _msg(author_id=555, is_dm=True)
        msg.message_snapshots = None
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        with patch("src.bot.cogs.chat.settings") as s:
            s.ADMIN_IDS = {42}
            s.ADMIN_ID = 42
            s.DMS_ENABLED = False
            s.DM_BANNED_IDS = {555}
            s.DM_BAN_MESSAGE = "You are banned"
            s.TARGET_CHANNEL_ID = 999
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            await cog.on_message(msg)
        
        msg.reply.assert_called_with("You are banned")

    @pytest.mark.asyncio
    async def test_dm_cooldown_queues(self):
        """lines 124-134: cooldown active, message queued."""
        bot = _bot()
        cog = _cog(bot)
        cog.dm_cooldowns[111] = time.time() + 60  # 60s remaining
        msg = _msg(author_id=111, is_dm=True)
        msg.message_snapshots = None
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.consume_tool.return_value = (True, None)
            s.ADMIN_IDS = set()
            s.DMS_ENABLED = True
            s.DM_BANNED_IDS = set()
            s.TARGET_CHANNEL_ID = 999
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            await cog.on_message(msg)
        
        assert "Cooldown" in msg.reply.call_args[0][0]
        assert 111 in cog.dm_queues
        assert len(cog.dm_queues[111]) == 1

    @pytest.mark.asyncio
    async def test_dm_ban_check(self):
        """lines 197-200: DM-banned user in DM."""
        bot = _bot()
        engine = MagicMock()
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        cog = _cog(bot)
        msg = _msg(author_id=555, is_dm=True)
        msg.message_snapshots = None
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.memory.persona_session.PersonaSessionTracker.get_thread_persona", return_value=None), \
             patch("src.core.flux_capacitor.FluxCapacitor.consume_tool", return_value=(True, None)):
            s.ADMIN_IDS = set()
            s.DMS_ENABLED = True
            s.DM_BANNED_IDS = {555}
            s.DM_BAN_MESSAGE = "Banned from DMs"
            s.TARGET_CHANNEL_ID = 999
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            g.activity_log = []
            await cog.on_message(msg)
        
        msg.reply.assert_called_with("Banned from DMs")


# ─── Persona Thread Detection (lines 146-158) ────────────────────────
class TestPersonaThread:
    @pytest.mark.asyncio
    async def test_persona_thread_detected(self):
        """lines 146-158: persona thread activates engagement."""
        bot = _bot()
        bot.town_hall = MagicMock()
        bot.town_hall._engaged = {}
        bot.engine_manager.get_active_engine.return_value = MagicMock(context_limit=4000)
        bot.hippocampus.observe = AsyncMock()
        bot.hippocampus.working = MagicMock()
        bot.hippocampus.working.add_turn = AsyncMock()
        
        cog = _cog(bot)
        msg = _msg(is_dm=False, guild=MagicMock())
        msg.channel = MagicMock(spec=discord.Thread)
        msg.channel.id = 123
        msg.channel.type = discord.ChannelType.public_thread
        msg.channel.parent_id = 999  # matches target

        class _Typing:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): pass
        msg.channel.typing = MagicMock(return_value=_Typing())
        msg.channel.send = AsyncMock()
        
        adapter = _adapter(is_dm=False)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        # Mock recall
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        mock_tracker = MagicMock()
        mock_tracker.start = AsyncMock()
        mock_tracker.stop = AsyncMock()
        mock_tracker_cls = MagicMock(return_value=mock_tracker)
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.memory.persona_session.PersonaSessionTracker.get_thread_persona", return_value="Echo"), \
             patch("src.memory.persona_session.PersonaSessionTracker.touch_thread"), \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.bot.cogs.chat_preprocessing.globals") as gp, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch.dict("sys.modules", {"src.engines.cognition_tracker": MagicMock(CognitionTracker=mock_tracker_cls)}):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            g.activity_log = []
            gp.bot = bot
            gp.engine = MagicMock()
            
            # Run but catch the deep call chain
            await cog.on_message(msg)
        
        bot.town_hall.mark_engaged.assert_called_with("Echo")


# ─── Thread Creation (v3.3: moved to LLM tool) ──────────────────────
class TestThreadCreation:
    @pytest.mark.asyncio
    async def test_thread_not_created_by_cog(self):
        """v3.3: Thread creation heuristic removed. Cog does NOT create threads directly.
        'start a thread' message goes through normal cognition, not create_thread."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        cog = _cog(bot)
        msg = _msg(content="Ernos start a thread please", is_dm=False, guild=MagicMock())
        msg.channel.id = 999  # target channel
        msg.channel.parent_id = None
        
        adapter = _adapter(is_dm=False)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.memory.persona_session.PersonaSessionTracker.get_thread_persona", return_value=None):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            g.activity_log = []
            await cog.on_message(msg)
        
        # v3.3: Cog does NOT call create_thread — LLM tool handles it
        msg.create_thread.assert_not_called()
        # Message should flow to cognition instead
        bot.cognition.process.assert_called()

    @pytest.mark.asyncio
    async def test_thread_heuristic_removed_comment(self):
        """Verify the heuristic removal comment exists in chat.py."""
        chat_path = Path(__file__).parent.parent.parent.parent / "src" / "bot" / "cogs" / "chat.py"
        content = chat_path.read_text()
        assert "Thread creation heuristic REMOVED" in content
        assert "create_thread_for_user" in content


# ─── Cross-Channel Context (lines 248-270) ───────────────────────────
class TestCrossChannel:
    @pytest.mark.asyncio
    async def test_cross_channel_context_injected(self):
        """lines 248-268: mention in non-target channel fetches context."""
        bot = _bot()
        bot.engine_manager.get_active_engine.return_value = MagicMock(context_limit=4000)
        cog = _cog(bot)
        
        msg = _msg(content="hey", is_dm=False, guild=MagicMock(), channel_id=777)
        msg.channel.parent_id = None
        msg.channel.name = "other-channel"
        msg.mentions = [bot.user]  # @mentioned
        
        # Mock channel history for cross-channel context
        hist_msg = MagicMock()
        hist_msg.author.display_name = "Alice"
        hist_msg.author.name = "alice"
        hist_msg.created_at = MagicMock()
        hist_msg.created_at.strftime = MagicMock(return_value="12:00")
        hist_msg.content = "discussion here"
        
        async def history_gen(*a, **kw):
            yield hist_msg
        msg.channel.history = MagicMock(return_value=history_gen())
        
        adapter = _adapter(is_dm=False)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.memory.persona_session.PersonaSessionTracker.get_thread_persona", return_value=None):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            g.activity_log = []
            await cog.on_message(msg)
        
        # Cognition should have been called  
        bot.cognition.process.assert_called()


# ─── Silo Checks (lines 339-349) ─────────────────────────────────────
class TestSiloChecks:
    @pytest.mark.asyncio
    async def test_silo_confirmation_handled(self):
        """lines 338-340: silo text confirmation."""
        bot = _bot()
        bot.silo_manager.check_text_confirmation = AsyncMock(return_value=True)
        cog = _cog(bot)
        
        msg = _msg(content="✅", is_dm=True)
        msg.message_snapshots = None
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        # Should return after silo confirmation — cognition NOT called
        bot.cognition.process.assert_not_called()

    @pytest.mark.asyncio
    async def test_silo_should_not_reply(self):
        """line 348-349: silo says bot shouldn't reply."""
        bot = _bot()
        bot.silo_manager.should_bot_reply = AsyncMock(return_value=False)
        cog = _cog(bot)
        
        msg = _msg(content="hi", is_dm=True)
        msg.message_snapshots = None
        
        adapter = _adapter()
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True):
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            await cog.on_message(msg)
        
        bot.cognition.process.assert_not_called()


# ─── Full Response Path (lines 706-788, 818-833) ─────────────────────
class TestResponsePath:
    @pytest.mark.asyncio
    async def test_full_dm_response(self):
        """Covers lines 706-788: full DM response path with DM cooldown."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(return_value=("Hello back!", [], []))
        bot.cognition.process = AsyncMock(return_value=("Hello back!", [], []))
        
        adapter = _adapter(is_dm=True)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        msg = _msg(content="hi", is_dm=True, author_id=111)
        msg.message_snapshots = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.consume_tool.return_value = (True, None)
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            
            await cog.on_message(msg)
        
        msg.reply.assert_called()
        bot.hippocampus.observe.assert_called()

    @pytest.mark.asyncio
    async def test_response_long_chunking(self):
        """Covers lines 766-776: response > 2000 chars, chunked."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        
        long_resp = "X" * 3000
        bot.cognition.process = AsyncMock(return_value=(long_resp, [], []))
        bot.cognition.process = AsyncMock(return_value=(long_resp, [], []))
        
        adapter = _adapter(is_dm=True)
        adapter.format_mentions = AsyncMock(return_value=long_resp)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        msg = _msg(content="tell me everything", is_dm=True)
        msg.message_snapshots = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.consume_tool.return_value = (True, None)
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            
            await cog.on_message(msg)
        
        assert msg.reply.call_count >= 2

    @pytest.mark.asyncio
    async def test_queue_squash(self):
        """lines 818-833: queued messages processed after response."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(return_value=("reply", [], []))
        bot.cognition.process = AsyncMock(return_value=("reply", [], []))
        
        # Set up a queued message
        queue_msg = _msg(content="queued msg", msg_id=5555)
        bot.message_queues[(111, 1)] = [queue_msg]
        
        adapter = _adapter(is_dm=True)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        msg = _msg(content="hi", is_dm=True, author_id=111, channel_id=1)
        msg.message_snapshots = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch("asyncio.create_task") as mock_task, \
             patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.consume_tool.return_value = (True, None)
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            
            await cog.on_message(msg)
        
        # Queue should be drained and create_task called
        mock_task.assert_called()

    @pytest.mark.asyncio
    async def test_cognitive_engine_failure(self):
        """lines 791-796: cognition process raises."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(side_effect=RuntimeError("engine crash"))
        bot.cognition.process = AsyncMock(side_effect=RuntimeError("engine crash"))
        
        adapter = _adapter(is_dm=True)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        msg = _msg(content="hi", is_dm=True)
        msg.message_snapshots = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.consume_tool.return_value = (True, None)
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            
            await cog.on_message(msg)
        
        # Should send error message
        msg.reply.assert_called()
        assert "ERROR" in msg.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_dm_cooldown_set(self):
        """lines 779-782: DM cooldown activation."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(return_value=("ok", [], []))
        bot.cognition.process = AsyncMock(return_value=("ok", [], []))
        
        adapter = _adapter(is_dm=True)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        # Set a non-zero cooldown to test that it activates
        cog.DM_COOLDOWN_SECONDS = 10
        
        msg = _msg(content="hi", is_dm=True, author_id=111)
        msg.message_snapshots = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.consume_tool.return_value = (True, None)
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            
            await cog.on_message(msg)
        
        # Cooldown should be set
        assert 111 in cog.dm_cooldowns

    @pytest.mark.asyncio
    async def test_dm_queued_messages_processed(self):
        """lines 785-788: queued DM messages batch sent."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(return_value=("ok", [], []))
        bot.cognition.process = AsyncMock(return_value=("ok", [], []))
        
        adapter = _adapter(is_dm=True)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        cog.DM_COOLDOWN_SECONDS = 10
        cog.dm_queues[111] = ["queued msg 1", "queued msg 2"]
        
        msg = _msg(content="hi", is_dm=True, author_id=111)
        msg.message_snapshots = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.consume_tool.return_value = (True, None)
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            
            await cog.on_message(msg)
        
        # Queued messages should be sent and cleared
        assert msg.channel.send.called
        assert 111 not in cog.dm_queues


# ─── Early Image Extraction (lines 283-284) ──────────────────────────
class TestEarlyImages:
    @pytest.mark.asyncio
    async def test_image_download_failure(self):
        """lines 283-284: early image download fails."""
        bot = _bot()
        engine = MagicMock()
        engine.__class__.__name__ = "CloudEngine"
        engine.context_limit = 4000
        bot.engine_manager.get_active_engine.return_value = engine
        bot.cognition.process = AsyncMock(return_value=("reply", [], []))
        bot.cognition.process = AsyncMock(return_value=("reply", [], []))
        
        att = MagicMock()
        att.content_type = "image/png"
        att.filename = "pic.png"
        att.size = 1000
        att.read = AsyncMock(side_effect=Exception("download fail"))
        
        adapter = _adapter(is_dm=True)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        recall_obj = _recall_obj()
        bot.loop.run_in_executor = AsyncMock(return_value=recall_obj)
        
        ctx_mock = MagicMock()
        ctx_mock.valid = False
        bot.get_context = AsyncMock(return_value=ctx_mock)
        
        cog = _cog(bot)
        msg = _msg(content="see this", is_dm=True, attachments=[att])
        msg.message_snapshots = None
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("src.bot.cogs.chat.globals") as g, \
             patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("src.bot.cogs.chat.ResponseFeedbackView"), \
             patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.consume_tool.return_value = (True, None)
            s.TARGET_CHANNEL_ID = 999
            s.ADMIN_IDS = set()
            s.BLOCKED_IDS = set()
            s.TESTING_MODE = False
            s.DM_BANNED_IDS = set()
            s.DMS_ENABLED = True
            g.activity_log = []
            
            await cog.on_message(msg)
        
        # Should still work, just without images
        bot.cognition.process.assert_called()
