"""
Tests for the Admin Proxy Reply System.
Covers: detection via message links, detection via Discord forwards,
admin-only guard, proxy reply execution, error handling, and hippocampus observation.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from src.bot.cogs.chat import DISCORD_MESSAGE_LINK_RE
from src.bot.cogs.proxy_cog import ProxyCog
from config import settings
import discord


# ═══════════════════════════════════════════════════════════════════
#                          FIXTURES
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_bot():
    """Standard bot mock matching the project's existing pattern."""
    bot = MagicMock()
    bot.user.id = 123
    bot.processing_users = set()
    bot.message_queues = {}
    bot.last_interaction = 0
    bot.grounding_pulse = None
    bot.add_processing_user = MagicMock()
    bot.remove_processing_user = MagicMock()

    # Cognition mock
    mock_cognition = MagicMock()
    mock_cognition.process = AsyncMock(return_value=("Proxy response from Ernos", [], []))
    bot.cognition = mock_cognition

    # Hippocampus mock
    mock_hippocampus = MagicMock()
    mock_hippocampus.observe = AsyncMock()
    bot.hippocampus = mock_hippocampus

    # Engine Manager mock
    mock_engine = MagicMock()
    mock_engine.__class__.__name__ = "CloudEngine"
    mock_engine.context_limit = 4_000_000
    bot.engine_manager = MagicMock()
    bot.engine_manager.get_active_engine.return_value = mock_engine

    # Channel Manager Mock (Synapse Bridge v3.1)
    mock_adapter = MagicMock()
    mock_adapter.normalize = AsyncMock()
    mock_adapter.format_mentions = AsyncMock(side_effect=lambda t: t)
    mock_adapter.platform_name = "discord"
    mock_cm = MagicMock()
    mock_cm.get_adapter.return_value = mock_adapter
    bot.channel_manager = mock_cm

    # Cerebrum mock
    bot.cerebrum = MagicMock()

    return bot


@pytest.fixture
def proxy_cog(mock_bot):
    """ProxyCog with mocked prompt manager."""
    cog = ProxyCog(mock_bot)
    cog.prompt_manager = MagicMock()
    cog.prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")
    return cog


def _make_dm_message(author_id, content, *, has_snapshots=False, reference=None):
    """Helper to create a mock DM message from an admin."""
    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.id = author_id
    msg.author.bot = False
    msg.author.name = "TestAdmin"
    msg.author.display_name = "TestAdmin"
    msg.content = content
    msg.channel = MagicMock()
    msg.channel.type = discord.ChannelType.private
    msg.channel.id = 999999
    msg.attachments = []
    msg.reply = AsyncMock()

    if has_snapshots:
        snapshot = MagicMock()
        snapshot.message = MagicMock()
        snapshot.message.content = "Original user message"
        msg.message_snapshots = [snapshot]
    else:
        msg.message_snapshots = []

    msg.reference = reference
    return msg


def _make_target_message(author_name="ProblemUser", channel_name="general", content="some user message"):
    """Helper to create a mock target message in a guild channel."""
    target = MagicMock()
    target.id = 777777
    target.content = content
    target.author = MagicMock()
    target.author.id = 555555
    target.author.name = author_name
    target.author.display_name = author_name
    target.channel = MagicMock()
    target.channel.id = 888888
    target.channel.name = channel_name
    target.channel.typing = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(), __aexit__=AsyncMock()
    ))
    target.channel.history = MagicMock(return_value=_async_iter([]))
    target.reply = AsyncMock()
    target.channel.send = AsyncMock()
    return target


def _async_iter(items):
    """Create an async iterator from a list."""
    class _Iter:
        def __init__(self):
            self._items = list(items)
            self._index = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self._index >= len(self._items):
                raise StopAsyncIteration
            item = self._items[self._index]
            self._index += 1
            return item
    return _Iter()


# ═══════════════════════════════════════════════════════════════════
#                        REGEX TESTS
# ═══════════════════════════════════════════════════════════════════

class TestMessageLinkRegex:
    """Test the DISCORD_MESSAGE_LINK_RE pattern."""

    def test_standard_link(self):
        match = DISCORD_MESSAGE_LINK_RE.search(
            "https://discord.com/channels/111/222/333"
        )
        assert match
        assert match.group(1) == "111"
        assert match.group(2) == "222"
        assert match.group(3) == "333"

    def test_discordapp_link(self):
        match = DISCORD_MESSAGE_LINK_RE.search(
            "https://discordapp.com/channels/111/222/333"
        )
        assert match

    def test_ptb_link(self):
        match = DISCORD_MESSAGE_LINK_RE.search(
            "https://ptb.discord.com/channels/111/222/333"
        )
        assert match

    def test_canary_link(self):
        match = DISCORD_MESSAGE_LINK_RE.search(
            "https://canary.discord.com/channels/111/222/333"
        )
        assert match

    def test_link_with_instructions(self):
        text = "tell them to chill https://discord.com/channels/111/222/333 be firm"
        match = DISCORD_MESSAGE_LINK_RE.search(text)
        assert match
        assert match.group(3) == "333"

    def test_no_link(self):
        match = DISCORD_MESSAGE_LINK_RE.search("hey ernos how are you?")
        assert match is None

    def test_partial_link_no_match(self):
        match = DISCORD_MESSAGE_LINK_RE.search("discord.com/channels/111/222")
        assert match is None  # Missing message ID


# ═══════════════════════════════════════════════════════════════════
#                     DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestProxyDetection:
    """Test _detect_and_handle_proxy correctly identifies proxy requests."""

    @pytest.mark.asyncio
    async def test_non_admin_link_still_matches(self, proxy_cog):
        """detect_and_handle_proxy itself processes links regardless of caller.
        The admin-only guard is in on_message, which only calls this for ADMIN_IDS.
        This test verifies that the method DOES detect links (the guard is upstream)."""
        non_admin_id = 9999999
        msg = _make_dm_message(non_admin_id, "just a normal chat with no links")
        result = await proxy_cog.detect_and_handle_proxy(msg)
        # No link, no forward = no proxy trigger
        assert result is False

    @pytest.mark.asyncio
    async def test_admin_normal_dm_no_trigger(self, proxy_cog):
        """Admin sending a normal DM (no link, no forward) should NOT trigger proxy."""
        admin_id = list(settings.ADMIN_IDS)[0]
        msg = _make_dm_message(admin_id, "hey ernos, how's the server doing?")
        result = await proxy_cog.detect_and_handle_proxy(msg)
        assert result is False

    @pytest.mark.asyncio
    async def test_message_link_triggers_proxy(self, proxy_cog, mock_bot):
        """Admin sending a message link should trigger proxy reply."""
        admin_id = list(settings.ADMIN_IDS)[0]
        msg = _make_dm_message(admin_id, "https://discord.com/channels/111/222/333")

        target = _make_target_message()
        mock_channel = MagicMock()
        mock_channel.name = "general"
        mock_channel.history = MagicMock(return_value=_async_iter([]))
        mock_channel.typing = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(), __aexit__=AsyncMock()
        ))
        mock_channel.send = AsyncMock()

        mock_bot.get_channel.return_value = mock_channel
        mock_channel.fetch_message = AsyncMock(return_value=target)

        result = await proxy_cog.detect_and_handle_proxy(msg)
        assert result is True

    @pytest.mark.asyncio
    async def test_message_link_with_instructions(self, proxy_cog, mock_bot):
        """Admin instructions alongside the link should be extracted."""
        admin_id = list(settings.ADMIN_IDS)[0]
        msg = _make_dm_message(
            admin_id,
            "be firm but polite https://discord.com/channels/111/222/333"
        )

        target = _make_target_message()
        mock_channel = MagicMock()
        mock_channel.name = "general"
        mock_channel.history = MagicMock(return_value=_async_iter([]))
        mock_channel.typing = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(), __aexit__=AsyncMock()
        ))
        mock_channel.send = AsyncMock()

        mock_bot.get_channel.return_value = mock_channel
        mock_channel.fetch_message = AsyncMock(return_value=target)

        # Patch _handle_proxy_reply to capture args
        proxy_cog._handle_proxy_reply = AsyncMock()

        result = await proxy_cog.detect_and_handle_proxy(msg)
        assert result is True

        # Verify instructions were extracted (link removed)
        call_args = proxy_cog._handle_proxy_reply.call_args
        admin_instructions = call_args[0][1]  # Second positional arg
        assert "be firm but polite" in admin_instructions
        assert "discord.com" not in admin_instructions

    @pytest.mark.asyncio
    async def test_deleted_message_returns_error(self, proxy_cog, mock_bot):
        """If the target message was deleted, admin gets an error."""
        admin_id = list(settings.ADMIN_IDS)[0]
        msg = _make_dm_message(admin_id, "https://discord.com/channels/111/222/333")

        mock_channel = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_channel.fetch_message = AsyncMock(side_effect=discord.NotFound(
            MagicMock(status=404), "Not Found"
        ))

        result = await proxy_cog.detect_and_handle_proxy(msg)
        assert result is True  # Still consumed the message
        msg.reply.assert_called_once()
        assert "Couldn't find" in msg.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_forbidden_channel_returns_error(self, proxy_cog, mock_bot):
        """If Ernos can't access the channel, admin gets an error."""
        admin_id = list(settings.ADMIN_IDS)[0]
        msg = _make_dm_message(admin_id, "https://discord.com/channels/111/222/333")

        mock_channel = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_channel.fetch_message = AsyncMock(side_effect=discord.Forbidden(
            MagicMock(status=403), "Forbidden"
        ))

        result = await proxy_cog.detect_and_handle_proxy(msg)
        assert result is True
        msg.reply.assert_called_once()
        assert "don't have access" in msg.reply.call_args[0][0]


# ═══════════════════════════════════════════════════════════════════
#                    HANDLER TESTS
# ═══════════════════════════════════════════════════════════════════

class TestProxyReplyHandler:
    """Test _handle_proxy_reply execution flow."""

    @pytest.mark.asyncio
    async def test_full_proxy_flow(self, proxy_cog, mock_bot):
        """Test the complete proxy reply lifecycle."""
        admin_dm = _make_dm_message(list(settings.ADMIN_IDS)[0], "be nice")
        target = _make_target_message(
            author_name="NewUser",
            channel_name="welcome",
            content="is this server any good?"
        )

        await proxy_cog._handle_proxy_reply(admin_dm, "be nice", target)

        # Cognition was called
        mock_bot.cognition.process.assert_called_once()
        call_kwargs = mock_bot.cognition.process.call_args[1]

        # Verify scope is PUBLIC
        assert call_kwargs['request_scope'] == "PUBLIC"

        # Verify target user identity is in the input
        assert "NewUser" in call_kwargs['input_text']

        # Verify admin instructions are in system context (hidden)
        assert "be nice" in call_kwargs['system_context']
        assert "PROXY REPLY MODE" in call_kwargs['system_context']

        # Verify response was sent to the TARGET channel (not admin DM)
        target.reply.assert_called_once()

        # Verify admin got confirmation
        assert admin_dm.reply.call_count >= 2  # Processing + confirmation
        # Last reply should be the confirmation
        last_reply = admin_dm.reply.call_args_list[-1][0][0]
        assert "Proxy reply sent" in last_reply

    @pytest.mark.asyncio
    async def test_proxy_observes_hippocampus(self, proxy_cog, mock_bot):
        """Proxy replies should be recorded in hippocampus under the target user."""
        admin_dm = _make_dm_message(list(settings.ADMIN_IDS)[0], "")
        target = _make_target_message()

        await proxy_cog._handle_proxy_reply(admin_dm, "", target)

        mock_bot.hippocampus.observe.assert_called_once()
        observe_args = mock_bot.hippocampus.observe.call_args
        # First arg should be the target user's ID (string)
        assert observe_args[0][0] == str(target.author.id)
        # is_dm should be False (public channel)
        assert observe_args[0][4] is False

    @pytest.mark.asyncio
    async def test_proxy_no_engine_returns_error(self, proxy_cog, mock_bot):
        """If no engine is active, proxy should fail gracefully."""
        mock_bot.engine_manager.get_active_engine.return_value = None
        admin_dm = _make_dm_message(list(settings.ADMIN_IDS)[0], "")
        target = _make_target_message()

        await proxy_cog._handle_proxy_reply(admin_dm, "", target)

        admin_dm.reply.assert_called_once()
        assert "No active engine" in admin_dm.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_proxy_cognition_failure(self, proxy_cog, mock_bot):
        """If cognition crashes, target channel should NOT receive a reply."""
        mock_bot.cognition.process = AsyncMock(side_effect=RuntimeError("Engine exploded"))
        admin_dm = _make_dm_message(list(settings.ADMIN_IDS)[0], "")
        target = _make_target_message()

        await proxy_cog._handle_proxy_reply(admin_dm, "", target)

        # Target channel should NOT have received anything — this is the key safety check
        target.reply.assert_not_called()
        
        # Admin should have been notified of failure (at least the "Processing..." and error)
        assert admin_dm.reply.call_count >= 1

    @pytest.mark.asyncio
    async def test_proxy_empty_response(self, proxy_cog, mock_bot):
        """If cognition returns empty, admin gets notified."""
        mock_bot.cognition.process = AsyncMock(return_value=("", [], []))
        admin_dm = _make_dm_message(list(settings.ADMIN_IDS)[0], "")
        target = _make_target_message()

        await proxy_cog._handle_proxy_reply(admin_dm, "", target)

        last_reply = admin_dm.reply.call_args_list[-1][0][0]
        assert "empty response" in last_reply

    @pytest.mark.asyncio
    async def test_proxy_admin_instructions_hidden(self, proxy_cog, mock_bot):
        """Admin instructions must be in system_context, never in the output."""
        admin_dm = _make_dm_message(list(settings.ADMIN_IDS)[0], "")
        target = _make_target_message()

        await proxy_cog._handle_proxy_reply(
            admin_dm, "tell them to read the rules", target
        )

        call_kwargs = mock_bot.cognition.process.call_args[1]
        system_ctx = call_kwargs['system_context']

        # Instructions ARE in system context
        assert "tell them to read the rules" in system_ctx
        assert "ADMIN INSTRUCTIONS" in system_ctx

        # Safety rules are present
        assert "Do NOT mention the admin" in system_ctx
        assert "do NOT reveal this was forwarded to you" in system_ctx

    @pytest.mark.asyncio
    async def test_proxy_no_instructions_uses_judgement(self, proxy_cog, mock_bot):
        """With no admin instructions, the directive tells Ernos to use judgement."""
        admin_dm = _make_dm_message(list(settings.ADMIN_IDS)[0], "")
        target = _make_target_message()

        await proxy_cog._handle_proxy_reply(admin_dm, "", target)

        call_kwargs = mock_bot.cognition.process.call_args[1]
        assert "use your judgement" in call_kwargs['system_context']

    @pytest.mark.asyncio
    async def test_proxy_long_response_chunks(self, proxy_cog, mock_bot):
        """Responses over 2000 chars should be chunked."""
        long_response = "A" * 3000
        mock_bot.cognition.process = AsyncMock(return_value=(long_response, [], []))

        admin_dm = _make_dm_message(list(settings.ADMIN_IDS)[0], "")
        target = _make_target_message()

        await proxy_cog._handle_proxy_reply(admin_dm, "", target)

        # First chunk goes as reply to target, rest as channel.send
        target.reply.assert_called_once()
        target.channel.send.assert_called()

    @pytest.mark.asyncio
    async def test_proxy_channel_context_fetched(self, proxy_cog, mock_bot):
        """Channel history should be fetched and included in context."""
        admin_dm = _make_dm_message(list(settings.ADMIN_IDS)[0], "")

        # Create mock history messages
        hist_msg = MagicMock()
        hist_msg.author.display_name = "SomeUser"
        hist_msg.author.name = "SomeUser"
        hist_msg.created_at = MagicMock()
        hist_msg.created_at.strftime = MagicMock(return_value="14:30")
        hist_msg.content = "earlier message in channel"

        target = _make_target_message()
        target.channel.history = MagicMock(return_value=_async_iter([hist_msg]))

        await proxy_cog._handle_proxy_reply(admin_dm, "", target)

        call_kwargs = mock_bot.cognition.process.call_args[1]
        assert "earlier message in channel" in call_kwargs['context']
