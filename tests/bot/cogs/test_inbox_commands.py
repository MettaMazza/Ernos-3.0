"""Tests for InboxCommands cog — 13 tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord

from src.bot.cogs.inbox_commands import InboxCommands


def _ix(*, is_dm=True):
    ix = MagicMock(spec=discord.Interaction)
    user = MagicMock(spec=discord.User)
    user.id = 12345
    ix.user = user
    if is_dm:
        ix.channel = MagicMock(spec=discord.DMChannel)
    else:
        ix.channel = MagicMock(spec=discord.TextChannel)
    ix.response = MagicMock()
    ix.response.send_message = AsyncMock()
    return ix


from functools import partial

def _call(cog, name):
    return partial(getattr(cog, name).callback, cog)


@pytest.fixture
def cog():
    return InboxCommands(MagicMock())


class TestInboxView:

    @pytest.mark.asyncio
    async def test_not_dm(self, cog):
        ix = _ix(is_dm=False)
        await _call(cog, "inbox_view")(ix)
        assert "dm" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_empty(self, cog):
        ix = _ix()
        with patch("src.bot.cogs.inbox_commands.InboxManager") as m:
            m.get_inbox_summary.return_value = "📭 Inbox empty."
            m.get_unread.return_value = []
            await _call(cog, "inbox_view")(ix)
            assert "empty" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_with_messages(self, cog):
        ix = _ix()
        with patch("src.bot.cogs.inbox_commands.InboxManager") as m:
            m.get_inbox_summary.return_value = "📬 1 unread"
            m.get_unread.return_value = [
                {"id": "m1", "persona": "echo", "timestamp": "2026-02-08T12:00:00Z", "content": "Hello"}
            ]
            await _call(cog, "inbox_view")(ix)
            m.mark_read.assert_called()

    @pytest.mark.asyncio
    async def test_overflow(self, cog):
        ix = _ix()
        with patch("src.bot.cogs.inbox_commands.InboxManager") as m:
            m.get_inbox_summary.return_value = "📬 15 unread"
            m.get_unread.return_value = [
                {"id": f"m{i}", "persona": "echo", "timestamp": "2026-02-08T12:00:00Z", "content": f"Msg {i}"}
                for i in range(15)
            ]
            await _call(cog, "inbox_view")(ix)
            assert "more" in ix.response.send_message.call_args[0][0].lower()


class TestInboxRead:

    @pytest.mark.asyncio
    async def test_not_dm(self, cog):
        ix = _ix(is_dm=False)
        await _call(cog, "inbox_read")(ix, "echo")
        assert "dm" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_no_messages(self, cog):
        ix = _ix()
        with patch("src.bot.cogs.inbox_commands.InboxManager") as m:
            m.get_unread.return_value = []
            await _call(cog, "inbox_read")(ix, "echo")
            assert "no unread" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_with_messages(self, cog):
        ix = _ix()
        with patch("src.bot.cogs.inbox_commands.InboxManager") as m:
            m.get_unread.return_value = [{"id": "m1", "timestamp": "2026-02-08T12:00:00Z", "content": "Hi"}]
            await _call(cog, "inbox_read")(ix, "echo")
            m.mark_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_overflow(self, cog):
        ix = _ix()
        with patch("src.bot.cogs.inbox_commands.InboxManager") as m:
            m.get_unread.return_value = [
                {"id": f"m{i}", "timestamp": "2026-02-08T12:00:00Z", "content": f"Msg {i}"}
                for i in range(20)
            ]
            await _call(cog, "inbox_read")(ix, "echo")
            assert "15" in ix.response.send_message.call_args[0][0]


class TestInboxPriority:

    @pytest.mark.asyncio
    async def test_not_dm(self, cog):
        ix = _ix(is_dm=False)
        level = MagicMock(value="mute")
        await _call(cog, "inbox_priority")(ix, "echo", level)
        assert "dm" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_set(self, cog):
        ix = _ix()
        level = MagicMock(value="notify")
        with patch("src.bot.cogs.inbox_commands.InboxManager") as m:
            m.set_priority.return_value = "✅ Set."
            await _call(cog, "inbox_priority")(ix, "echo", level)
            m.set_priority.assert_called_once_with(12345, "echo", "notify")


class TestInboxClear:

    @pytest.mark.asyncio
    async def test_not_dm(self, cog):
        ix = _ix(is_dm=False)
        await _call(cog, "inbox_clear")(ix)
        assert "dm" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_clear_some(self, cog):
        ix = _ix()
        with patch("src.bot.cogs.inbox_commands.InboxManager") as m:
            m.mark_all_read.return_value = 5
            await _call(cog, "inbox_clear")(ix)
            assert "5" in ix.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_clear_empty(self, cog):
        ix = _ix()
        with patch("src.bot.cogs.inbox_commands.InboxManager") as m:
            m.mark_all_read.return_value = 0
            await _call(cog, "inbox_clear")(ix)
            assert "no unread" in ix.response.send_message.call_args[0][0].lower()
