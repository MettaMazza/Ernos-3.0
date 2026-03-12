"""Tests for DiscordChannelAdapter — 8 tests."""
import pytest
import re
from unittest.mock import MagicMock, AsyncMock, patch
import discord

from src.channels.discord_adapter import DiscordChannelAdapter


@pytest.fixture
def adapter():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 999
    return DiscordChannelAdapter(bot)


class TestPlatformName:
    def test_returns_discord(self, adapter):
        assert adapter.platform_name == "discord"


class TestNormalize:
    @pytest.mark.asyncio
    async def test_dm_message(self, adapter):
        msg = MagicMock(spec=discord.Message)
        msg.channel = MagicMock(spec=discord.DMChannel)
        msg.content = "hello"
        msg.author = MagicMock()
        msg.author.id = 123
        msg.author.display_name = "Maria"
        msg.author.name = "maria"
        msg.author.bot = False
        msg.channel.id = 456
        msg.attachments = []
        msg.reference = None
        msg.guild = None
        unified = await adapter.normalize(msg)
        assert unified.is_dm is True
        assert unified.author_id == "123"
        assert unified.content == "hello"
        assert unified.platform == "discord"

    @pytest.mark.asyncio
    async def test_guild_message(self, adapter):
        msg = MagicMock(spec=discord.Message)
        msg.channel = MagicMock(spec=discord.TextChannel)
        msg.channel.type = discord.ChannelType.text
        msg.content = "hey"
        msg.author = MagicMock()
        msg.author.id = 123
        msg.author.display_name = "Maria"
        msg.author.name = "maria"
        msg.author.bot = False
        msg.channel.id = 789
        msg.attachments = []
        msg.reference = None
        msg.guild = MagicMock()
        unified = await adapter.normalize(msg)
        assert unified.is_dm is False

    @pytest.mark.asyncio
    async def test_attachments(self, adapter):
        msg = MagicMock(spec=discord.Message)
        msg.channel = MagicMock(spec=discord.DMChannel)
        msg.content = "see attachment"
        msg.author = MagicMock()
        msg.author.id = 123
        msg.author.display_name = "Maria"
        msg.author.name = "maria"
        msg.author.bot = False
        msg.channel.id = 456
        msg.guild = None
        msg.reference = None
        att = MagicMock()
        att.filename = "test.png"
        att.content_type = "image/png"
        att.size = 1024
        att.url = "https://cdn.discord.com/test.png"
        msg.attachments = [att]
        unified = await adapter.normalize(msg)
        assert len(unified.attachments) == 1
        assert unified.attachments[0].filename == "test.png"


class TestSendResponse:
    @pytest.mark.asyncio
    async def test_short_message(self, adapter):
        from src.channels.types import OutboundResponse
        resp = OutboundResponse(content="hello", files=[], reactions=[])
        msg = MagicMock()
        msg.reply = AsyncMock()
        msg.add_reaction = AsyncMock()
        await adapter.send_response(resp, msg)
        msg.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_long_message_chunks(self, adapter):
        from src.channels.types import OutboundResponse
        resp = OutboundResponse(content="x" * 3000, files=[], reactions=[])
        msg = MagicMock()
        msg.reply = AsyncMock()
        msg.add_reaction = AsyncMock()
        await adapter.send_response(resp, msg)
        assert msg.reply.call_count == 2  # 2 chunks for 3000 chars

    @pytest.mark.asyncio
    async def test_reactions(self, adapter):
        from src.channels.types import OutboundResponse
        resp = OutboundResponse(content="hi", files=[], reactions=["👍"])
        msg = MagicMock()
        msg.reply = AsyncMock()
        msg.add_reaction = AsyncMock()
        await adapter.send_response(resp, msg)
        msg.add_reaction.assert_called_once_with("👍")


class TestFormatMentions:
    @pytest.mark.asyncio
    async def test_bare_mention(self, adapter):
        result = await adapter.format_mentions("Hello @764896542170939443")
        assert "<@764896542170939443>" in result

    @pytest.mark.asyncio
    async def test_already_formatted(self, adapter):
        result = await adapter.format_mentions("Hello <@764896542170939443>")
        assert result.count("<@764896542170939443>") == 1
