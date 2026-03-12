"""Tests for SiloCommands cog — 8 tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock
import discord

from src.bot.cogs.silo_commands import SiloCommands


@pytest.fixture
def cog():
    bot = MagicMock()
    bot.add_cog = AsyncMock()
    bot.silo_manager = MagicMock()
    bot.silo_manager.active_silos = {111: True, 222: True}
    bot.silo_manager.check_empty_silo = AsyncMock()
    return SiloCommands(bot)


def _leave(cog, ctx):
    """Call the HybridCommand leave_silo via its callback."""
    return cog.leave_silo.callback(cog, ctx)


class TestLeaveSilo:

    @pytest.mark.asyncio
    async def test_not_in_thread(self, cog):
        ctx = MagicMock()
        ctx.channel = MagicMock(spec=discord.TextChannel)
        ctx.send = AsyncMock()
        await _leave(cog, ctx)
        msg = ctx.send.call_args[0][0].lower()
        assert "thread" in msg or "silo" in msg

    @pytest.mark.asyncio
    async def test_not_managed_public(self, cog):
        ctx = MagicMock()
        ctx.channel = MagicMock(spec=discord.Thread)
        ctx.channel.id = 999
        ctx.channel.type = discord.ChannelType.public_thread
        ctx.send = AsyncMock()
        await _leave(cog, ctx)
        assert "not a silo" in ctx.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_managed_success(self, cog):
        ctx = MagicMock()
        ctx.channel = MagicMock(spec=discord.Thread)
        ctx.channel.id = 111
        ctx.channel.remove_user = AsyncMock()
        ctx.author = MagicMock()
        ctx.send = AsyncMock()
        await _leave(cog, ctx)
        ctx.channel.remove_user.assert_called_once_with(ctx.author)

    @pytest.mark.asyncio
    async def test_remove_failure(self, cog):
        ctx = MagicMock()
        ctx.channel = MagicMock(spec=discord.Thread)
        ctx.channel.id = 111
        ctx.channel.remove_user = AsyncMock(side_effect=Exception("err"))
        ctx.author = MagicMock()
        ctx.send = AsyncMock()
        await _leave(cog, ctx)
        msg = ctx.send.call_args[0][0]
        assert "failed" in msg.lower() or "⚠️" in msg

    @pytest.mark.asyncio
    async def test_private_thread_allowed(self, cog):
        ctx = MagicMock()
        ctx.channel = MagicMock(spec=discord.Thread)
        ctx.channel.id = 999
        ctx.channel.type = discord.ChannelType.private_thread
        ctx.channel.remove_user = AsyncMock()
        ctx.author = MagicMock()
        ctx.send = AsyncMock()
        await _leave(cog, ctx)
        ctx.channel.remove_user.assert_called_once()


class TestOnThreadMemberRemove:

    @pytest.mark.asyncio
    async def test_managed(self, cog):
        t = MagicMock(id=111)
        await cog.on_thread_member_remove(t, MagicMock())
        cog.bot.silo_manager.check_empty_silo.assert_called_once_with(t)

    @pytest.mark.asyncio
    async def test_unmanaged(self, cog):
        t = MagicMock(id=999)
        await cog.on_thread_member_remove(t, MagicMock())
        cog.bot.silo_manager.check_empty_silo.assert_not_called()


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup(self):
        from src.bot.cogs.silo_commands import setup
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        await setup(bot)
        bot.add_cog.assert_called_once()
