"""Tests for AdminFunctions cog — 25 tests.

Updated to target correct sub-cog modules after admin.py split:
  - AdminEngine      → admin_engine.py (cog_check, engine switching, sync)
  - AdminLifecycle   → admin_lifecycle.py (purge_all, cycle_reset)
  - AdminReports     → admin_reports.py (townhall_suggest)
"""
import pytest
from functools import partial
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
import discord

from src.bot.cogs.admin_engine import AdminEngine as AdminFunctions
from src.bot.cogs.admin_lifecycle import AdminLifecycle
from src.bot.cogs.admin_reports import AdminReports


def _bot(**kw):
    bot = MagicMock()
    bot.add_cog = AsyncMock()
    bot.engine_manager = MagicMock()
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock(return_value=[1, 2, 3])
    bot.tree.copy_global_to = MagicMock()
    bot.get_channel = MagicMock(return_value=None)
    bot.fetch_channel = AsyncMock(return_value=None)
    bot.fetch_user = AsyncMock(return_value=None)
    bot.guilds = []
    bot.get_cog = MagicMock(return_value=None)
    bot.cognition = None
    bot.channel_manager = MagicMock()
    bot.town_hall = None
    bot.close = AsyncMock()
    for k, v in kw.items():
        setattr(bot, k, v)
    return bot


def _ctx(*, is_admin=True, in_guild=True):
    ctx = MagicMock()
    ctx.author = MagicMock(id=123)
    ctx.send = AsyncMock()
    ctx.defer = AsyncMock()
    ctx.channel = MagicMock()
    ctx.channel.send = AsyncMock()
    if in_guild:
        ctx.guild = MagicMock(spec=discord.Guild)
        ctx.guild.name = "TestGuild"
    else:
        ctx.guild = None
    return ctx


def _call(cog, name):
    return partial(getattr(cog, name).callback, cog)


@pytest.fixture
def cog():
    return AdminFunctions(_bot())


@pytest.fixture
def lifecycle_cog():
    return AdminLifecycle(_bot())


@pytest.fixture
def reports_cog():
    return AdminReports(_bot())


# ── cog_check ────────────────────────────────────────────────────

class TestCogCheck:

    @pytest.mark.asyncio
    async def test_admin_passes(self, cog):
        ctx = _ctx()
        with patch("src.bot.cogs.admin_engine.settings") as s:
            s.ADMIN_IDS = {123}
            result = await cog.cog_check(ctx)
            assert result is True

    @pytest.mark.asyncio
    async def test_non_admin_fails(self, cog):
        ctx = _ctx()
        with patch("src.bot.cogs.admin_engine.settings") as s:
            s.ADMIN_IDS = {999}
            result = await cog.cog_check(ctx)
            assert result is False


# ── Engine switching ─────────────────────────────────────────────

class TestEngineSwitching:

    @pytest.mark.asyncio
    async def test_cloud_success(self, cog):
        ctx = _ctx()
        cog.bot.engine_manager.set_active_engine.return_value = True
        await _call(cog, "switch_cloud")(ctx)
        assert "Cloud" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cloud_failure(self, cog):
        ctx = _ctx()
        cog.bot.engine_manager.set_active_engine.return_value = False
        await _call(cog, "switch_cloud")(ctx)
        assert "Failed" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_local_success(self, cog):
        ctx = _ctx()
        cog.bot.engine_manager.set_active_engine.return_value = True
        await _call(cog, "switch_local")(ctx)
        assert "Local" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_local_failure(self, cog):
        ctx = _ctx()
        cog.bot.engine_manager.set_active_engine.return_value = False
        await _call(cog, "switch_local")(ctx)
        assert "Failed" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_localsteer_success(self, cog):
        ctx = _ctx()
        cog.bot.engine_manager.set_active_engine.return_value = True
        await _call(cog, "switch_local_steer")(ctx)
        assert "Steering" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_localsteer_failure(self, cog):
        ctx = _ctx()
        cog.bot.engine_manager.set_active_engine.return_value = False
        await _call(cog, "switch_local_steer")(ctx)
        assert "Failed" in ctx.send.call_args[0][0]


# ── Sync ─────────────────────────────────────────────────────────

class TestSync:

    @pytest.mark.asyncio
    async def test_sync(self, cog):
        ctx = _ctx()
        await _call(cog, "sync_commands")(ctx)
        assert "3" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_syncguild_from_guild(self, cog):
        ctx = _ctx(in_guild=True)
        await _call(cog, "sync_guild_commands")(ctx)
        cog.bot.tree.copy_global_to.assert_called_once()
        assert "INSTANT" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_syncguild_from_dm_with_guild_id(self, cog):
        ctx = _ctx(in_guild=False)
        guild = MagicMock(name="TestGuild")
        guild.name = "TestGuild"
        cog.bot.get_guild = MagicMock(return_value=guild)
        with patch("src.bot.cogs.admin_engine.settings") as s:
            s.GUILD_ID = 123
            s.TARGET_CHANNEL_ID = 456
            await _call(cog, "sync_guild_commands")(ctx)
            assert "INSTANT" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_syncguild_from_dm_no_guild(self, cog):
        ctx = _ctx(in_guild=False)
        cog.bot.get_guild = MagicMock(return_value=None)
        cog.bot.get_channel = MagicMock(return_value=None)
        with patch("src.bot.cogs.admin_engine.settings") as s:
            s.GUILD_ID = None
            s.TARGET_CHANNEL_ID = 456
            await _call(cog, "sync_guild_commands")(ctx)
            assert "Could not determine" in ctx.send.call_args[0][0]


# ── purge_all (now in AdminLifecycle) ────────────────────────────

class TestPurge:

    @pytest.mark.asyncio
    async def test_no_channel(self, lifecycle_cog):
        ctx = _ctx()
        lifecycle_cog.bot.get_channel.return_value = None
        lifecycle_cog.bot.fetch_channel = AsyncMock(side_effect=Exception("not found"))
        with patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TARGET_CHANNEL_ID = 999
            await _call(lifecycle_cog, "purge_all")(ctx)
            assert "Could not find" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_success(self, lifecycle_cog):
        ctx = _ctx()
        ch = MagicMock()
        ch.purge = AsyncMock(side_effect=[[1, 2, 3], []])
        lifecycle_cog.bot.get_channel.return_value = ch
        with patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TARGET_CHANNEL_ID = 123
            await _call(lifecycle_cog, "purge_all")(ctx)
            assert "PURGE COMPLETE" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_error(self, lifecycle_cog):
        ctx = _ctx()
        ch = MagicMock()
        ch.purge = AsyncMock(side_effect=Exception("403"))
        lifecycle_cog.bot.get_channel.return_value = ch
        with patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TARGET_CHANNEL_ID = 123
            await _call(lifecycle_cog, "purge_all")(ctx)
            assert "failed" in ctx.send.call_args[0][0].lower()


# ── proxy_send (now lives in ProxyCog) ───────────────────────────

class TestProxy:

    def _proxy_cog(self):
        from src.bot.cogs.proxy_cog import ProxyCog
        bot = _bot()
        return ProxyCog(bot)

    @pytest.mark.asyncio
    async def test_unresolvable_target(self):
        pcog = self._proxy_cog()
        ctx = _ctx()
        pcog.bot.get_channel.return_value = None
        pcog.bot.guilds = []
        with patch("config.settings") as s:
            s.ADMIN_ID = 123  # match ctx.author.id
            await _call(pcog, "proxy_send")(ctx, "nonsense", message="hi")
        last = ctx.send.call_args or ctx.channel.send.call_args
        assert "Could not resolve" in last[0][0]

    @pytest.mark.asyncio
    async def test_channel_mention(self):
        pcog = self._proxy_cog()
        ctx = _ctx()
        ch = MagicMock()
        ch.name = "general"
        ch.send = AsyncMock()
        pcog.bot.get_channel.return_value = ch
        engine = MagicMock()
        pcog.bot.engine_manager.get_active_engine.return_value = engine
        chat_cog = MagicMock()
        chat_cog.prompt_manager.get_system_prompt.return_value = "sys"
        pcog.bot.get_cog.return_value = chat_cog
        cognition = MagicMock()
        cognition.process = AsyncMock(return_value=("Hello world", [], []))
        pcog.bot.cognition = cognition
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value="Hello world")
        pcog.bot.channel_manager.get_adapter.return_value = adapter
        with patch("config.settings") as s:
            s.ADMIN_ID = 123  # match ctx.author.id
            await _call(pcog, "proxy_send")(ctx, "<#12345>", message="say hi")
            ch.send.assert_called_once()
            args, kwargs = ch.send.call_args
            assert args[0] == "Hello world"
            assert "view" in kwargs  # ResponseFeedbackView attached


# ── townhall_suggest (now in AdminReports) ───────────────────────

class TestTownHallSuggest:

    @pytest.mark.asyncio
    async def test_no_town_hall(self, reports_cog):
        ctx = _ctx()
        reports_cog.bot.town_hall = None
        await _call(reports_cog, "townhall_suggest")(ctx, "a", "b", "c")
        assert "not active" in ctx.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_success(self, reports_cog):
        ctx = _ctx()
        th = MagicMock()
        th.add_suggestion.return_value = 3
        th._suggested_topics = ["a", "b", "c"]
        reports_cog.bot.town_hall = th
        await _call(reports_cog, "townhall_suggest")(ctx, "topic1", "topic2", "topic3")
        assert "3 topic" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_valid(self, reports_cog):
        ctx = _ctx()
        th = MagicMock()
        th.add_suggestion.return_value = 0
        reports_cog.bot.town_hall = th
        await _call(reports_cog, "townhall_suggest")(ctx, "", "", "")
        assert "No valid" in ctx.send.call_args[0][0]


# ── setup ────────────────────────────────────────────────────────

class TestSetup:
    @pytest.mark.asyncio
    async def test_setup(self):
        from src.bot.cogs.admin import setup
        bot = _bot()
        bot.load_extension = AsyncMock()
        await setup(bot)
        assert bot.load_extension.call_count == 4
