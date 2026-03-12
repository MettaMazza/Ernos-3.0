"""Tests for SiloManager — 10 tests."""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
import discord

from src.silo_manager import SiloManager


@pytest.fixture
def silo():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 999
    return SiloManager(bot)


class TestInit:
    def test_creates_manager(self, silo):
        assert silo.bot is not None
        assert silo.pending_silos == {}


class TestProposeSilo:
    @pytest.mark.asyncio
    async def test_no_mentions(self, silo):
        msg = MagicMock(spec=discord.Message)
        msg.mentions = []
        msg.author = MagicMock()
        msg.author.id = 123
        msg.author.bot = False
        result = await silo.propose_silo(msg)
        assert result is None or result is False

    @pytest.mark.asyncio
    async def test_only_bot_mentioned(self, silo):
        msg = MagicMock(spec=discord.Message)
        bot_user = MagicMock()
        bot_user.id = 999
        msg.mentions = [bot_user]
        msg.author = MagicMock()
        msg.author.id = 123
        msg.author.bot = False
        result = await silo.propose_silo(msg)
        assert result is None or result is False

    @pytest.mark.asyncio
    async def test_valid_silo_request(self, silo):
        msg = MagicMock(spec=discord.Message)
        bot_user = MagicMock()
        bot_user.id = 999
        friend = MagicMock()
        friend.id = 456
        friend.bot = False
        msg.mentions = [bot_user, friend]
        msg.author = MagicMock()
        msg.author.id = 123
        msg.author.bot = False
        msg.id = 111
        msg.reply = AsyncMock()
        msg.add_reaction = AsyncMock()
        msg.channel = MagicMock()
        silo.bot.user = bot_user
        silo.bot.loop = MagicMock()
        silo.bot.loop.create_task = MagicMock()
        reply_msg = MagicMock()
        reply_msg.id = 222
        reply_msg.add_reaction = AsyncMock()
        msg.reply = AsyncMock(return_value=reply_msg)
        await silo.propose_silo(msg)
        assert 222 in silo.pending_silos


class TestCheckQuorum:
    @pytest.mark.asyncio
    async def test_unknown_message(self, silo):
        payload = MagicMock()
        payload.message_id = 999999
        result = await silo.check_quorum(payload)
        assert result is None


class TestActivateSilo:
    @pytest.mark.asyncio
    async def test_creates_thread(self, silo):
        msg = MagicMock(spec=discord.Message)
        msg.channel = MagicMock()
        msg.author = MagicMock()
        msg.author.id = 123
        thread = MagicMock(spec=discord.Thread)
        thread.add_user = AsyncMock()
        thread.send = AsyncMock()
        thread.id = 555
        msg.channel.create_thread = AsyncMock(return_value=thread)
        msg.reply = AsyncMock()
        await silo.activate_silo(msg, {123, 456})
        msg.channel.create_thread.assert_called_once()
        assert 555 in silo.active_silos


class TestCheckEmptySilo:
    @pytest.mark.asyncio
    async def test_empty_thread(self, silo):
        thread = MagicMock(spec=discord.Thread)
        thread.member_count = 1  # Only bot
        thread.id = 100
        thread.delete = AsyncMock()
        silo.active_silos.add(100)
        await silo.check_empty_silo(thread)
        thread.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_active_thread(self, silo):
        thread = MagicMock(spec=discord.Thread)
        thread.member_count = 3
        thread.delete = AsyncMock()
        await silo.check_empty_silo(thread)
        thread.delete.assert_not_called()


class TestShouldBotReply:
    @pytest.mark.asyncio
    async def test_round_robin_not_silo(self, silo):
        msg = MagicMock(spec=discord.Message)
        msg.channel = MagicMock(spec=discord.Thread)
        msg.channel.id = 100  # Not in active_silos
        msg.author = MagicMock()
        msg.author.id = 123
        msg.author.bot = False
        result = await silo.should_bot_reply(msg)
        assert result is True  # Not a silo, normal rules apply


class TestExpireProposal:
    @pytest.mark.asyncio
    async def test_removes_proposal(self, silo):
        silo.pending_silos[111] = {123, 456}
        with patch("src.silo_manager.asyncio.sleep", new_callable=AsyncMock):
            await silo._expire_proposal(111)
            assert 111 not in silo.pending_silos
