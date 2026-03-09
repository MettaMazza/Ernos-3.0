"""
Final precision tests for chat.py remaining uncovered lines.
Covers:
  - Forward proxy history capture (864-871)
  - Forward reference/snapshot handling (876-882, 891-892)
  - Forward proxy exception (899-901)
  - Message link channel fetch fallback (913)
  - _handle_proxy_reply context fetch (948-954)
  - Proxy reply file attachments (1062-1064)
  - Proxy reply chunking middle (1075)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import discord
import asyncio


def _bot():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 99999
    bot.engine_manager = MagicMock()
    bot.channel_manager = MagicMock()
    bot.silo_manager = MagicMock()
    bot.hippocampus = MagicMock()
    bot.cerebrum = MagicMock()
    bot.cerebrum.get_lobe = MagicMock(return_value=None)
    bot.cognition = AsyncMock()
    bot.cognition.process = AsyncMock(return_value=("Reply!", [], []))
    bot.get_channel = MagicMock(return_value=None)
    bot.fetch_channel = AsyncMock(return_value=None)
    bot.get_cog = MagicMock(return_value=None)
    return bot


def _cog(bot=None):
    from src.bot.cogs.chat import ChatListener
    b = bot or _bot()
    with patch("src.bot.cogs.chat.PromptManager"), \
         patch("src.bot.cogs.chat.UnifiedPreProcessor"):
        cog = ChatListener(b)
        cog.preprocessor.process = AsyncMock(return_value={"intent": "chat", "complexity": "LOW"})
        cog.prompt_manager = MagicMock()
        cog.prompt_manager.get_system_prompt = MagicMock(return_value="SYSTEM_PROMPT")
    return cog


def _proxy_cog(bot=None):
    from src.bot.cogs.proxy_cog import ProxyCog
    b = bot or _bot()
    return ProxyCog(b)


def _msg(admin_id=42, has_snapshots=True, content=""):
    msg = MagicMock()
    msg.id = 5555
    msg.content = content
    msg.author = MagicMock()
    msg.author.id = admin_id
    msg.author.bot = False
    msg.author.name = "Admin"
    msg.author.display_name = "Admin"
    msg.channel = MagicMock()
    msg.channel.id = 1
    msg.channel.type = discord.ChannelType.private
    msg.channel.send = AsyncMock()
    msg.reply = AsyncMock()
    msg.add_reaction = AsyncMock()
    msg.reference = None
    
    if has_snapshots:
        snap = MagicMock()
        snap.message = MagicMock()
        snap.message.channel = MagicMock()
        snap.message.channel.fetch_message = AsyncMock()
        snap.message.id = 9999
        msg.message_snapshots = [snap]
    else:
        msg.message_snapshots = None
    
    return msg


def _target_msg():
    target = MagicMock()
    target.id = 7777
    target.content = "Hello from user"
    target.author = MagicMock()
    target.author.id = 111
    target.author.name = "TestUser"
    target.author.display_name = "TestUser"
    target.author.bot = False
    target.channel = MagicMock()
    target.channel.name = "general"
    target.channel.id = 222
    target.channel.send = AsyncMock()
    target.reply = AsyncMock()
    target.attachments = []
    target.created_at = MagicMock()
    target.created_at.strftime = MagicMock(return_value="14:30")
    return target


# ─── Forward Proxy History Capture (lines 864-871) ───────────────────

class TestForwardHistoryCapture:
    """Tests for admin forward DM detection and instruction capture."""

    @pytest.mark.asyncio
    async def test_forward_captures_follow_up_instructions(self):
        """lines 864-869: history scan captures admin follow-up comment."""
        bot = _bot()
        cog = _proxy_cog(bot)
        msg = _msg(admin_id=42)
        
        # Set up reference to a channel we can fetch
        target = _target_msg()
        ref_channel = MagicMock()
        ref_channel.fetch_message = AsyncMock(return_value=target)
        bot.get_channel = MagicMock(return_value=ref_channel)
        
        msg.reference = MagicMock()
        msg.reference.channel_id = 222
        msg.reference.message_id = 7777
        
        # History returns a follow-up admin message
        follow_up = MagicMock()
        follow_up.author.id = 42
        follow_up.author.bot = False
        follow_up.content = "Be gentle in your reply"
        
        async def mock_history(**kwargs):
            yield follow_up
        msg.channel.history = mock_history
        
        # Set up cognition and adapter
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value="Reply!")
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        chat_cog = MagicMock()
        chat_cog.prompt_manager = MagicMock()
        chat_cog.prompt_manager.get_system_prompt = MagicMock(return_value="SP")
        bot.get_cog = MagicMock(return_value=chat_cog)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            s.ADMIN_IDS = {42}
            result = await cog.detect_and_handle_proxy(msg)
        
        assert result is True
        target.reply.assert_called()

    @pytest.mark.asyncio
    async def test_forward_history_scan_exception(self):
        """lines 870-871: history scan fails."""
        bot = _bot()
        cog = _proxy_cog(bot)
        msg = _msg(admin_id=42)
        
        target = _target_msg()
        ref_channel = MagicMock()
        ref_channel.fetch_message = AsyncMock(return_value=target)
        bot.get_channel = MagicMock(return_value=ref_channel)
        
        msg.reference = MagicMock()
        msg.reference.channel_id = 222
        msg.reference.message_id = 7777
        
        # History raises
        async def bad_history(**kwargs):
            raise RuntimeError("history fail")
            yield  # make it a generator
        msg.channel.history = bad_history
        
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value="Reply!")
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        chat_cog = MagicMock()
        chat_cog.prompt_manager = MagicMock()
        chat_cog.prompt_manager.get_system_prompt = MagicMock(return_value="SP")
        bot.get_cog = MagicMock(return_value=chat_cog)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            s.ADMIN_IDS = {42}
            result = await cog.detect_and_handle_proxy(msg)
        
        assert result is True


# ─── Forward Reference/Snapshot Handling (lines 876-892) ─────────────

class TestForwardReferenceHandling:
    @pytest.mark.asyncio
    async def test_forward_reference_fetch_fails(self):
        """lines 876-882: reference fetch fails, falls through to snapshot."""
        bot = _bot()
        cog = _proxy_cog(bot)
        msg = _msg(admin_id=42)
        
        msg.reference = MagicMock()
        msg.reference.channel_id = 222
        msg.reference.message_id = 7777
        
        # Reference fetch fails
        ref_channel = MagicMock()
        ref_channel.fetch_message = AsyncMock(side_effect=Exception("not found"))
        bot.get_channel = MagicMock(return_value=ref_channel)
        
        # Snapshot fallback succeeds
        target = _target_msg()
        msg.message_snapshots[0].message.channel.fetch_message = AsyncMock(return_value=target)
        
        async def empty_history(**kwargs):
            return
            yield
        msg.channel.history = empty_history
        
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value="Reply!")
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        chat_cog = MagicMock()
        chat_cog.prompt_manager = MagicMock()
        chat_cog.prompt_manager.get_system_prompt = MagicMock(return_value="SP")
        bot.get_cog = MagicMock(return_value=chat_cog)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            s.ADMIN_IDS = {42}
            result = await cog.detect_and_handle_proxy(msg)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_forward_no_target_found(self):
        """lines 897-898: neither reference nor snapshot resolves."""
        bot = _bot()
        cog = _proxy_cog(bot)
        msg = _msg(admin_id=42)
        
        # No reference
        msg.reference = None
        
        # Snapshot also fails
        msg.message_snapshots[0].message.channel = None
        
        async def empty_history(**kwargs):
            return
            yield
        msg.channel.history = empty_history
        
        with patch("src.bot.cogs.chat.settings") as s, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            s.ADMIN_IDS = {42}
            result = await cog.detect_and_handle_proxy(msg)
        
        assert result is True
        msg.reply.assert_called()
        call_text = msg.reply.call_args[0][0]
        assert "Couldn't" in call_text

    @pytest.mark.asyncio
    async def test_forward_proxy_exception(self):
        """lines 899-901: forward proxy exception wrapper."""
        bot = _bot()
        cog = _proxy_cog(bot)
        msg = _msg(admin_id=42)

        # Force snapshot indexing to raise
        msg.message_snapshots = MagicMock()
        msg.message_snapshots.__len__ = MagicMock(return_value=1)
        msg.message_snapshots.__bool__ = MagicMock(return_value=True)
        msg.message_snapshots.__getitem__ = MagicMock(side_effect=IndexError("boom"))

        async def empty_history(**kwargs):
            return
            yield
        msg.channel.history = empty_history

        with patch("src.bot.cogs.chat.settings") as s, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            s.ADMIN_IDS = {42}
            result = await cog.detect_and_handle_proxy(msg)

        assert result is True
        msg.reply.assert_called()


# ─── Message Link Proxy (line 913) ───────────────────────────────────

class TestMessageLinkProxy:
    @pytest.mark.asyncio
    async def test_link_channel_fetch_fallback(self):
        """line 913: bot.get_channel returns None, falls back to fetch_channel."""
        bot = _bot()
        cog = _proxy_cog(bot)
        msg = _msg(admin_id=42, has_snapshots=False)
        msg.content = "https://discord.com/channels/111/222/333 be nice"
        
        target = _target_msg()
        ch = MagicMock()
        ch.fetch_message = AsyncMock(return_value=target)
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(return_value=ch)
        
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value="Reply!")
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        chat_cog = MagicMock()
        chat_cog.prompt_manager = MagicMock()
        chat_cog.prompt_manager.get_system_prompt = MagicMock(return_value="SP")
        bot.get_cog = MagicMock(return_value=chat_cog)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        with patch("src.bot.cogs.chat.settings") as s:
            s.ADMIN_IDS = {42}
            result = await cog.detect_and_handle_proxy(msg)
        
        assert result is True
        bot.fetch_channel.assert_called()


# ─── _handle_proxy_reply Tests (lines 948-954, 1062-1064, 1075) ──────

class TestHandleProxyReply:
    @pytest.mark.asyncio
    async def test_context_fetch_success(self):
        """lines 948-952: channel history fetch for context."""
        bot = _bot()
        cog = _proxy_cog(bot)
        
        admin_dm = MagicMock()
        admin_dm.add_reaction = AsyncMock()
        admin_dm.reply = AsyncMock()
        
        target = _target_msg()
        
        # Channel history
        hist = MagicMock()
        hist.author.display_name = "User2"
        hist.author.name = "User2"
        hist.content = "Previous message"
        hist.created_at = MagicMock()
        hist.created_at.strftime = MagicMock(return_value="14:00")
        
        async def mock_history(**kwargs):
            yield hist
        target.channel.history = mock_history
        
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value="Reply!")
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        chat_cog = MagicMock()
        chat_cog.prompt_manager = MagicMock()
        chat_cog.prompt_manager.get_system_prompt = MagicMock(return_value="SP")
        bot.get_cog = MagicMock(return_value=chat_cog)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        await cog._handle_proxy_reply(admin_dm, "be kind", target)
        
        target.reply.assert_called()

    @pytest.mark.asyncio
    async def test_context_fetch_fails(self):
        """lines 953-954: channel history fetch fails."""
        bot = _bot()
        cog = _proxy_cog(bot)
        
        admin_dm = MagicMock()
        admin_dm.add_reaction = AsyncMock()
        admin_dm.reply = AsyncMock()
        
        target = _target_msg()
        
        # History raises
        async def bad_history(**kwargs):
            raise RuntimeError("perms")
            yield
        target.channel.history = bad_history
        
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value="Reply!")
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        chat_cog = MagicMock()
        chat_cog.prompt_manager = MagicMock()
        chat_cog.prompt_manager.get_system_prompt = MagicMock(return_value="SP")
        bot.get_cog = MagicMock(return_value=chat_cog)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        await cog._handle_proxy_reply(admin_dm, "reply", target)
        
        target.reply.assert_called()

    @pytest.mark.asyncio
    async def test_reply_with_files(self):
        """lines 1062-1064: response includes file attachments."""
        bot = _bot()
        bot.cognition.process = AsyncMock(return_value=("Reply!", ["/tmp/image.png"], []))
        cog = _proxy_cog(bot)
        
        admin_dm = MagicMock()
        admin_dm.add_reaction = AsyncMock()
        admin_dm.reply = AsyncMock()
        
        target = _target_msg()
        
        async def empty_history(**kwargs):
            return
            yield
        target.channel.history = empty_history
        
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value="Short reply")
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        chat_cog = MagicMock()
        chat_cog.prompt_manager = MagicMock()
        chat_cog.prompt_manager.get_system_prompt = MagicMock(return_value="SP")
        bot.get_cog = MagicMock(return_value=chat_cog)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        with patch("os.path.exists", return_value=True), \
             patch("discord.File"):
            await cog._handle_proxy_reply(admin_dm, "reply", target)
        
        target.reply.assert_called()

    @pytest.mark.asyncio
    async def test_reply_long_chunking(self):
        """lines 1067-1075: long response gets chunked (3+ chunks)."""
        bot = _bot()
        long_reply = "A" * 5000  # Will become 3 chunks
        bot.cognition.process = AsyncMock(return_value=(long_reply, [], []))
        cog = _proxy_cog(bot)
        
        admin_dm = MagicMock()
        admin_dm.add_reaction = AsyncMock()
        admin_dm.reply = AsyncMock()
        
        target = _target_msg()
        
        async def empty_history(**kwargs):
            return
            yield
        target.channel.history = empty_history
        
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value=long_reply)
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        chat_cog = MagicMock()
        chat_cog.prompt_manager = MagicMock()
        chat_cog.prompt_manager.get_system_prompt = MagicMock(return_value="SP")
        bot.get_cog = MagicMock(return_value=chat_cog)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        await cog._handle_proxy_reply(admin_dm, "reply", target)
        
        # First chunk goes to target.reply, rest to channel.send
        target.reply.assert_called_once()
        assert target.channel.send.call_count >= 2  # middle + last chunks
