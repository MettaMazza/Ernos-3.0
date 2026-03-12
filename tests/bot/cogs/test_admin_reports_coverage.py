"""
Coverage tests for src/bot/cogs/admin_reports.py
Uses monkeypatch.chdir so Path("memory/users") resolves in a temp directory.
"""
import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import discord


def _make_bot():
    bot = MagicMock()
    bot.guilds = []
    bot.fetch_user = AsyncMock(return_value=None)
    bot.get_cog = MagicMock(return_value=None)
    bot.tape_engine = None
    bot.engine_manager = MagicMock()
    bot.close = AsyncMock()
    return bot


def _make_ctx(is_dm=True):
    ctx = AsyncMock()
    ctx.send = AsyncMock()
    ctx.defer = AsyncMock()
    ctx.author = MagicMock()
    ctx.author.id = 42
    if is_dm:
        ctx.channel = MagicMock(spec=discord.DMChannel)
    else:
        ctx.channel = MagicMock(spec=discord.TextChannel)
    return ctx


def _reports_cog(bot=None):
    from src.bot.cogs.admin_reports import AdminReports
    return AdminReports(bot or _make_bot())


def _setup_cognition(bot, response="Report text"):
    bot.engine_manager.get_active_engine.return_value = MagicMock()
    chat_cog = MagicMock()
    chat_cog.prompt_manager.get_system_prompt.return_value = "SP"
    bot.get_cog.return_value = chat_cog
    tape_engine = MagicMock()
    bot.tape_engine = tape_engine
    cognition_engine = MagicMock()
    cognition_engine.process = AsyncMock(return_value=(response, []))
    bot.cognition = cognition_engine


class TestCogCheck:
    @pytest.mark.asyncio
    async def test_admin_passes(self):
        cog = _reports_cog()
        ctx = _make_ctx()
        ctx.author.id = 42
        with patch("src.bot.cogs.admin_reports.settings") as s:
            s.ADMIN_IDS = {42}
            assert await cog.cog_check(ctx) is True


class TestTownhallSuggest:
    @pytest.mark.asyncio
    async def test_no_town_hall(self):
        bot = _make_bot()
        if hasattr(bot, 'town_hall'):
            del bot.town_hall
        cog = _reports_cog(bot)
        ctx = _make_ctx()
        await cog.townhall_suggest.callback(cog, ctx, "t1", "t2", "t3")
        assert "not active" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_topics_added(self):
        bot = _make_bot()
        town_hall = MagicMock()
        town_hall.add_suggestion.return_value = 3
        town_hall._suggested_topics = ["a", "b", "c"]
        bot.town_hall = town_hall
        cog = _reports_cog(bot)
        ctx = _make_ctx()
        await cog.townhall_suggest.callback(cog, ctx, "t1", "t2", "t3")
        assert "submitted" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_valid_topics(self):
        bot = _make_bot()
        town_hall = MagicMock()
        town_hall.add_suggestion.return_value = 0
        bot.town_hall = town_hall
        cog = _reports_cog(bot)
        ctx = _make_ctx()
        await cog.townhall_suggest.callback(cog, ctx, "ab", "cd", "ef")
        assert "No valid" in ctx.send.call_args[0][0]


class TestUserReport:
    @pytest.mark.asyncio
    async def test_not_dm(self):
        cog = _reports_cog()
        ctx = _make_ctx(is_dm=False)
        await cog.user_report.callback(cog, ctx)
        assert "DMs with me" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_users_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cog = _reports_cog()
        ctx = _make_ctx()
        await cog.user_report.callback(cog, ctx)
        assert "No user data" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_numeric_user_id(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        ud = users / "12345"
        ud.mkdir(parents=True)

        bot = _make_bot()
        user_obj = MagicMock(display_name="Alice", name="alice")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 2

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_username_guild_member(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "12345").mkdir(parents=True)

        bot = _make_bot()
        member = MagicMock(name="alice", display_name="Alice", id=12345)
        member.name = "alice"
        member.global_name = "Alice"
        guild = MagicMock()
        guild.members = [member]
        bot.guilds = [guild]
        user_obj = MagicMock(display_name="Alice", name="alice")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 1

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="alice")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_username_query_members(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "99999").mkdir(parents=True)

        bot = _make_bot()
        member = MagicMock()
        member.name = "bob"
        member.display_name = "Bob"
        member.id = 99999
        guild = MagicMock()
        guild.members = []
        guild.query_members = AsyncMock(return_value=[member])
        bot.guilds = [guild]
        user_obj = MagicMock(display_name="Bob", name="bob")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="bob")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_username_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "memory" / "users").mkdir(parents=True)

        bot = _make_bot()
        guild = MagicMock()
        guild.members = []
        guild.query_members = AsyncMock(return_value=[])
        bot.guilds = [guild]

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        await cog.user_report.callback(cog, ctx, username="nonexistent")
        assert "Could not find" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_reports(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "memory" / "users").mkdir(parents=True)

        bot = _make_bot()
        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="99999")
        assert "No user data found" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_engine_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "11111").mkdir(parents=True)

        bot = _make_bot()
        bot.engine_manager.get_active_engine.return_value = None
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 1

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="11111")
        all_calls = [str(c) for c in ctx.send.call_args_list]
        assert any("Engine unavailable" in c for c in all_calls)

    @pytest.mark.asyncio
    async def test_report_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "11111").mkdir(parents=True)

        bot = _make_bot()
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        chat_cog = MagicMock()
        chat_cog.prompt_manager.get_system_prompt.return_value = "SP"
        bot.get_cog.return_value = chat_cog
        tape_engine = MagicMock()
        bot.tape_engine = tape_engine
        cognition_engine = MagicMock()
        cognition_engine.process = AsyncMock(side_effect=RuntimeError("bad"))
        bot.cognition = cognition_engine
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="11111")
        all_calls = [str(c) for c in ctx.send.call_args_list]
        assert any("Report failed" in c or "failed" in c.lower() for c in all_calls)

    @pytest.mark.asyncio
    async def test_all_users(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "11111").mkdir(parents=True)
        (users / "22222").mkdir(parents=True)

        bot = _make_bot()
        user_obj = MagicMock(display_name="U", name="u")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot, "All users overview")

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username=None)
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_empty_response(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "11111").mkdir(parents=True)

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot, "")

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="11111")
        all_calls = [str(c) for c in ctx.send.call_args_list]
        assert any("empty response" in c for c in all_calls)

    @pytest.mark.asyncio
    async def test_long_report(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "11111").mkdir(parents=True)

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot, "A" * 3000)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="11111")
        assert ctx.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_with_context_and_media(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        ud = users / "12345"
        ud.mkdir(parents=True)
        (ud / "context_private.jsonl").write_text('{"role":"user","content":"hi"}\n')
        (ud / "context_public.jsonl").write_text('{"role":"user","content":"pub"}\n')
        (ud / "usage.json").write_text('{"tokens":100}')
        media = ud / "media"
        media.mkdir()
        (media / "img1.png").write_text("fake")

        bot = _make_bot()
        user_obj = MagicMock(display_name="Alice", name="alice")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 3

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_query_members_exception(self, tmp_path, monkeypatch):
        """Covers lines 104-105: query_members raises exception."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "memory" / "users").mkdir(parents=True)

        bot = _make_bot()
        guild = MagicMock()
        guild.members = []
        guild.query_members = AsyncMock(side_effect=RuntimeError("gateway error"))
        bot.guilds = [guild]

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        await cog.user_report.callback(cog, ctx, username="bob")
        assert "Could not find" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_fetch_user_exception(self, tmp_path, monkeypatch):
        """Covers lines 130-131: fetch_user raises during report generation."""
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "12345").mkdir(parents=True)

        bot = _make_bot()
        bot.fetch_user = AsyncMock(side_effect=RuntimeError("user not found"))
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_get_tier_exception(self, tmp_path, monkeypatch):
        """Covers lines 135-136: flux.get_tier raises."""
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "12345").mkdir(parents=True)

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.side_effect = RuntimeError("tier err")

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_json_decode_error_private_context(self, tmp_path, monkeypatch):
        """Covers lines 150-151: JSONDecodeError in private context."""
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        ud = users / "12345"
        ud.mkdir(parents=True)
        # Write invalid JSON to trigger JSONDecodeError
        (ud / "context_private.jsonl").write_text("not-json\n{\"valid\":true}\n")

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_json_decode_error_public_context(self, tmp_path, monkeypatch):
        """Covers lines 161-162: JSONDecodeError in public context."""
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        ud = users / "12345"
        ud.mkdir(parents=True)
        (ud / "context_public.jsonl").write_text("bad-json-line\n")

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_private_context_read_text_fails(self, tmp_path, monkeypatch):
        """Covers lines 152-153: read_text raises on private context."""
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        ud = users / "12345"
        ud.mkdir(parents=True)
        pf = ud / "context_private.jsonl"
        pf.write_text("placeholder")

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()

        original_read = Path.read_text
        def read_side(self_p, *a, **kw):
            if "context_private" in str(self_p):
                raise PermissionError("no access")
            return original_read(self_p, *a, **kw)

        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}), \
             patch.object(Path, "read_text", read_side):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_public_context_read_text_fails(self, tmp_path, monkeypatch):
        """Covers lines 163-164: read_text raises on public context."""
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        ud = users / "12345"
        ud.mkdir(parents=True)
        pf = ud / "context_public.jsonl"
        pf.write_text("placeholder")

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()

        original_read = Path.read_text
        def read_side(self_p, *a, **kw):
            if "context_public" in str(self_p):
                raise PermissionError("no access")
            return original_read(self_p, *a, **kw)

        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}), \
             patch.object(Path, "read_text", read_side):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_usage_json_parse_error(self, tmp_path, monkeypatch):
        """Covers lines 171-172: usage.json is invalid JSON."""
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        ud = users / "12345"
        ud.mkdir(parents=True)
        (ud / "usage.json").write_text("not-valid-json!!!")

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_report_data_truncation(self, tmp_path, monkeypatch):
        """Covers line 199: report data > 80000 chars gets truncated."""
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        ud = users / "12345"
        ud.mkdir(parents=True)
        # Create lots of context to produce >80000 chars of JSON
        # Code reads last 50 lines, so each line must be ~2000 chars to reach 80K
        big_context = "\n".join(json.dumps({"r": "user", "content": f"x" * 2000}) for i in range(60))
        (ud / "context_private.jsonl").write_text(big_context)

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        _setup_cognition(bot)

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {"src.core.flux_capacitor": flux_mod}):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_cognition_fallback_creation(self, tmp_path, monkeypatch):
        """Covers lines 264-266: cognition is None, creates CognitionEngine inline."""
        monkeypatch.chdir(tmp_path)
        users = tmp_path / "memory" / "users"
        (users / "12345").mkdir(parents=True)

        bot = _make_bot()
        user_obj = MagicMock(display_name="T", name="t")
        bot.fetch_user = AsyncMock(return_value=user_obj)
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        chat_cog = MagicMock()
        chat_cog.prompt_manager.get_system_prompt.return_value = "SP"
        bot.get_cog.return_value = chat_cog
        bot.tape_engine = None  # Force fallback

        mock_cog_engine = AsyncMock()
        cog_mod = MagicMock()
        cog_mod.CognitionEngine.return_value = mock_cog_engine

        flux_mod = MagicMock()
        flux_mod.FluxCapacitor.return_value.get_tier.return_value = 0

        cog = _reports_cog(bot)
        ctx = _make_ctx()
        with patch.dict("sys.modules", {
                "src.core.flux_capacitor": flux_mod,
                "src.engines.cognition": cog_mod,
             }):
            await cog.user_report.callback(cog, ctx, username="12345")
        assert ctx.send.call_count >= 1


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup(self):
        from src.bot.cogs.admin_reports import setup
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        await setup(bot)
        bot.add_cog.assert_called_once()
