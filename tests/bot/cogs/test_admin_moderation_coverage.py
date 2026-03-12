"""
Coverage tests for src/bot/cogs/admin_moderation.py
Covers: cog_check, prompt_approve, prompt_reject, prompt_pending, strike, core_talk, setup
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


# ─── Helpers ─────────────────────────────────────────────────────────

def _make_bot():
    bot = MagicMock()
    bot.engine_manager = MagicMock()
    bot.get_cog = MagicMock(return_value=None)
    bot.tape_engine = None
    bot.cerebrum = MagicMock()
    bot.hippocampus = MagicMock()
    bot.fetch_user = AsyncMock(return_value=None)
    bot.close = AsyncMock()
    return bot


def _make_ctx():
    ctx = AsyncMock()
    ctx.send = AsyncMock()
    ctx.defer = AsyncMock()
    ctx.author = MagicMock()
    ctx.author.id = 42
    ctx.channel = AsyncMock()
    return ctx


def _moderation_cog(bot=None):
    from src.bot.cogs.admin_moderation import AdminModeration
    return AdminModeration(bot or _make_bot())


# ─── cog_check ────────────────────────────────────────────────────

class TestCogCheck:
    @pytest.mark.asyncio
    async def test_admin_passes(self):
        cog = _moderation_cog()
        ctx = _make_ctx()
        ctx.author.id = 42
        with patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_IDS = {42}
            assert await cog.cog_check(ctx) is True

    @pytest.mark.asyncio
    async def test_non_admin_fails(self):
        cog = _moderation_cog()
        ctx = _make_ctx()
        ctx.author.id = 999
        with patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_IDS = {42}
            assert await cog.cog_check(ctx) is False


# ─── prompt_approve ──────────────────────────────────────────────────

class TestPromptApprove:
    @pytest.mark.asyncio
    async def test_no_tuner(self):
        bot = _make_bot()
        bot.cerebrum.get_lobe.return_value = None
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.prompt_approve.callback(cog, ctx, "p1")
        assert "not available" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_approve_success(self):
        bot = _make_bot()
        tuner = MagicMock()
        tuner.approve_modification.return_value = True
        lobe = MagicMock()
        lobe.get_ability.return_value = tuner
        bot.cerebrum.get_lobe.return_value = lobe
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.prompt_approve.callback(cog, ctx, "p1")
        assert "APPROVED" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_approve_fail(self):
        bot = _make_bot()
        tuner = MagicMock()
        tuner.approve_modification.return_value = False
        lobe = MagicMock()
        lobe.get_ability.return_value = tuner
        bot.cerebrum.get_lobe.return_value = lobe
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.prompt_approve.callback(cog, ctx, "p1")
        assert "Failed" in ctx.send.call_args[0][0]


# ─── prompt_reject ──────────────────────────────────────────────────

class TestPromptReject:
    @pytest.mark.asyncio
    async def test_no_tuner(self):
        bot = _make_bot()
        bot.cerebrum.get_lobe.return_value = None
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.prompt_reject.callback(cog, ctx, "p1")
        assert "not available" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_reject_success(self):
        bot = _make_bot()
        tuner = MagicMock()
        tuner.reject_modification.return_value = True
        lobe = MagicMock()
        lobe.get_ability.return_value = tuner
        bot.cerebrum.get_lobe.return_value = lobe
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.prompt_reject.callback(cog, ctx, "p1", "bad idea")
        assert "REJECTED" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_reject_fail(self):
        bot = _make_bot()
        tuner = MagicMock()
        tuner.reject_modification.return_value = False
        lobe = MagicMock()
        lobe.get_ability.return_value = tuner
        bot.cerebrum.get_lobe.return_value = lobe
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.prompt_reject.callback(cog, ctx, "p1")
        assert "Failed" in ctx.send.call_args[0][0]


# ─── prompt_pending ──────────────────────────────────────────────────

class TestPromptPending:
    @pytest.mark.asyncio
    async def test_no_tuner(self):
        bot = _make_bot()
        bot.cerebrum.get_lobe.return_value = None
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.prompt_pending.callback(cog, ctx)
        assert "not available" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_pending(self):
        bot = _make_bot()
        tuner = MagicMock()
        tuner.get_pending.return_value = []
        lobe = MagicMock()
        lobe.get_ability.return_value = tuner
        bot.cerebrum.get_lobe.return_value = lobe
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.prompt_pending.callback(cog, ctx)
        assert "No pending" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_with_pending(self):
        bot = _make_bot()
        tuner = MagicMock()
        tuner.get_pending.return_value = [
            {"id": "p1", "operation": "replace", "prompt_file": "main.txt",
             "section": "greeting", "rationale": "Better tone " * 20}
        ]
        lobe = MagicMock()
        lobe.get_ability.return_value = tuner
        bot.cerebrum.get_lobe.return_value = lobe
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.prompt_pending.callback(cog, ctx)
        assert "Pending Proposals" in ctx.send.call_args[0][0]
        assert "p1" in ctx.send.call_args[0][0]


# ─── strike ──────────────────────────────────────────────────────────

class TestStrike:
    @pytest.mark.asyncio
    async def test_invalid_user_id(self):
        cog = _moderation_cog()
        ctx = _make_ctx()
        await cog.strike.callback(cog, ctx, "not_a_number", reason="test")
        assert "Invalid user ID" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_full_strike_happy_path(self):
        bot = _make_bot()
        # Setup hippocampus with stream
        stream = MagicMock()
        turn = MagicMock()
        turn.user_id = "12345"
        stream.turns = [turn]
        bot.hippocampus.stream = stream

        target_user = AsyncMock()
        target_user.send = AsyncMock()
        admin_user = AsyncMock()
        admin_user.send = AsyncMock()

        async def fetch_side(uid):
            if uid == 42:
                return admin_user
            return target_user
        bot.fetch_user = AsyncMock(side_effect=fetch_side)

        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        mock_report_path = MagicMock(spec=Path)
        mock_report_path.exists.return_value = True
        mock_report_path.name = "report.md"

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.return_value = ["line1", "line2"]
        post_mortem_mod.generate_post_mortem = AsyncMock(return_value=mock_report_path)

        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("builtins.open", MagicMock()), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            # Mock Path operations for context files and strike log
            with patch("pathlib.Path.exists", return_value=False), \
                 patch("pathlib.Path.mkdir"), \
                 patch("pathlib.Path.parent", new_callable=lambda: MagicMock()):
                await cog.strike.callback(cog, ctx, "12345", reason="test strike")

        assert ctx.send.call_count >= 5

    @pytest.mark.asyncio
    async def test_strike_dm_forbidden(self):
        import discord
        bot = _make_bot()
        bot.hippocampus.stream = None
        target_user = AsyncMock()
        target_user.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "blocked"))
        bot.fetch_user = AsyncMock(return_value=target_user)

        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.return_value = []
        post_mortem_mod.generate_post_mortem = AsyncMock(return_value=None)

        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("builtins.open", MagicMock()), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            await cog.strike.callback(cog, ctx, "12345", reason="test")

        # Should mention DMs disabled
        all_send_args = [str(c) for c in ctx.send.call_args_list]
        joined = " ".join(all_send_args)
        assert "DMs disabled" in joined or "STRIKE COMPLETE" in joined

    @pytest.mark.asyncio
    async def test_strike_context_read_exception(self):
        """Covers lines 114-118: read_context_file raises."""
        bot = _make_bot()
        bot.hippocampus.stream = None
        bot.fetch_user = AsyncMock(return_value=None)
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.side_effect = IOError("read fail")
        post_mortem_mod.generate_post_mortem = AsyncMock(return_value=None)

        # Make context files "exist" so the try block is entered
        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.unlink"), \
             patch("pathlib.Path.mkdir"), \
             patch("builtins.open", MagicMock()), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            await cog.strike.callback(cog, ctx, "12345", reason="test")

        assert ctx.send.call_count >= 5

    @pytest.mark.asyncio
    async def test_strike_post_mortem_exception(self):
        """Covers lines 138-140: generate_post_mortem raises."""
        bot = _make_bot()
        bot.hippocampus.stream = None
        bot.fetch_user = AsyncMock(return_value=None)
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.return_value = ["line1"]
        post_mortem_mod.generate_post_mortem = AsyncMock(side_effect=RuntimeError("gen fail"))

        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("builtins.open", MagicMock()), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            await cog.strike.callback(cog, ctx, "12345", reason="test")

        all_send = " ".join(str(c) for c in ctx.send.call_args_list)
        assert "Post-mortem failed" in all_send or "gen fail" in all_send

    @pytest.mark.asyncio
    async def test_strike_admin_dm_fail(self):
        """Covers lines 152-153: DM to admin fails."""
        bot = _make_bot()
        bot.hippocampus.stream = None

        target_user = AsyncMock()
        target_user.send = AsyncMock()
        admin_user = AsyncMock()
        admin_user.send = AsyncMock(side_effect=RuntimeError("DM fail"))

        async def fetch_side(uid):
            if uid == 42:
                return admin_user
            return target_user
        bot.fetch_user = AsyncMock(side_effect=fetch_side)

        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        mock_report_path = MagicMock(spec=Path)
        mock_report_path.exists.return_value = True
        mock_report_path.name = "report.md"

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.return_value = []
        post_mortem_mod.generate_post_mortem = AsyncMock(return_value=mock_report_path)

        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("builtins.open", MagicMock()), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            await cog.strike.callback(cog, ctx, "12345", reason="test")

        assert ctx.send.call_count >= 5

    @pytest.mark.asyncio
    async def test_strike_context_erasure_and_unlink_fail(self):
        """Covers lines 160-165: context files exist, unlink succeeds then fails."""
        bot = _make_bot()
        bot.hippocampus.stream = None
        bot.fetch_user = AsyncMock(return_value=None)
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.return_value = []
        post_mortem_mod.generate_post_mortem = AsyncMock(return_value=None)

        unlink_calls = [0]
        original_exists = Path.exists
        def exists_side(self_p):
            p_str = str(self_p)
            if "context_private" in p_str or "context_public" in p_str:
                return True
            if "strikes.jsonl" in p_str:
                return False
            return False

        def unlink_side(self_p, *a, **kw):
            unlink_calls[0] += 1
            if unlink_calls[0] == 2:
                raise OSError("unlink fail")

        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("pathlib.Path.exists", side_effect=exists_side, autospec=True), \
             patch("pathlib.Path.unlink", side_effect=unlink_side, autospec=True), \
             patch("pathlib.Path.mkdir"), \
             patch("builtins.open", MagicMock()), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            await cog.strike.callback(cog, ctx, "12345", reason="test")

        assert ctx.send.call_count >= 5

    @pytest.mark.asyncio
    async def test_strike_hippocampus_clear_fail(self):
        """Covers lines 179-180: clearing in-memory state raises."""
        bot = _make_bot()
        hippo = MagicMock()
        hippo.stream = MagicMock()
        type(hippo.stream).turns = property(lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
        bot.hippocampus = hippo
        bot.fetch_user = AsyncMock(return_value=None)
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.return_value = []
        post_mortem_mod.generate_post_mortem = AsyncMock(return_value=None)

        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("builtins.open", MagicMock()), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            await cog.strike.callback(cog, ctx, "12345", reason="test")

        assert ctx.send.call_count >= 5

    @pytest.mark.asyncio
    async def test_strike_user_not_found(self):
        """Covers line 196: fetch_user returns None."""
        bot = _make_bot()
        bot.hippocampus.stream = None
        bot.fetch_user = AsyncMock(return_value=None)
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.return_value = []
        post_mortem_mod.generate_post_mortem = AsyncMock(return_value=None)

        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("builtins.open", MagicMock()), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            await cog.strike.callback(cog, ctx, "12345", reason="test")

        all_send = " ".join(str(c) for c in ctx.send.call_args_list)
        assert "Could not find user" in all_send

    @pytest.mark.asyncio
    async def test_strike_dm_generic_exception(self):
        """Covers lines 199-201: DM to user raises non-Forbidden exception."""
        bot = _make_bot()
        bot.hippocampus.stream = None
        target_user = AsyncMock()
        target_user.send = AsyncMock(side_effect=RuntimeError("network error"))
        bot.fetch_user = AsyncMock(return_value=target_user)
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.return_value = []
        post_mortem_mod.generate_post_mortem = AsyncMock(return_value=None)

        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("builtins.open", MagicMock()), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            await cog.strike.callback(cog, ctx, "12345", reason="test")

        all_send = " ".join(str(c) for c in ctx.send.call_args_list)
        assert "Failed to notify user" in all_send

    @pytest.mark.asyncio
    async def test_strike_log_write_fails(self):
        """Covers lines 217-218: strike log write raises."""
        bot = _make_bot()
        bot.hippocampus.stream = None
        bot.fetch_user = AsyncMock(return_value=None)
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        scope_mod = MagicMock()
        scope_mod.ScopeManager._resolve_user_dir.return_value = Path("/tmp/test_user")

        post_mortem_mod = MagicMock()
        post_mortem_mod.read_context_file.return_value = []
        post_mortem_mod.generate_post_mortem = AsyncMock(return_value=None)

        def open_side(path, *a, **kw):
            if "strikes" in str(path):
                raise IOError("write fail")
            return MagicMock()

        with patch.dict("sys.modules", {
                "src.privacy.scopes": scope_mod,
                "src.bot.post_mortem": post_mortem_mod,
             }), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.mkdir"), \
             patch("builtins.open", side_effect=open_side), \
             patch("src.bot.cogs.admin_moderation.settings") as s:
            s.ADMIN_ID = 42
            await cog.strike.callback(cog, ctx, "12345", reason="test")

        assert ctx.send.call_count >= 5


# ─── core_talk ───────────────────────────────────────────────────────

class TestCoreTalk:
    @pytest.mark.asyncio
    async def test_no_engine(self):
        bot = _make_bot()
        bot.engine_manager.get_active_engine.return_value = None
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.core_talk.callback(cog, ctx, message="hello")
        assert "No active engine" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_chat_cog(self):
        bot = _make_bot()
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        bot.get_cog.return_value = None
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.core_talk.callback(cog, ctx, message="hello")
        assert "Chat system not loaded" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_success_short_response(self):
        bot = _make_bot()
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        chat_cog = MagicMock()
        chat_cog.prompt_manager.get_system_prompt.return_value = "SP"
        bot.get_cog.return_value = chat_cog
        tape_engine = MagicMock()
        bot.tape_engine = tape_engine
        cognition_engine = MagicMock()
        cognition_engine.process = AsyncMock(return_value=("Hello admin!", []))
        bot.cognition = cognition_engine
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        view_mod = MagicMock()
        view_mod.ResponseFeedbackView.return_value = MagicMock()

        with patch.dict("sys.modules", {"src.ui.views": view_mod}):
            await cog.core_talk.callback(cog, ctx, message="hello core")

        assert ctx.send.call_count >= 1

    @pytest.mark.asyncio
    async def test_success_long_response(self):
        bot = _make_bot()
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        chat_cog = MagicMock()
        chat_cog.prompt_manager.get_system_prompt.return_value = "SP"
        bot.get_cog.return_value = chat_cog
        tape_engine = MagicMock()
        bot.tape_engine = tape_engine
        cognition_engine = MagicMock()
        cognition_engine.process = AsyncMock(return_value=("A" * 3000, []))
        bot.cognition = cognition_engine
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        view_mod = MagicMock()
        view_mod.ResponseFeedbackView.return_value = MagicMock()

        with patch.dict("sys.modules", {"src.ui.views": view_mod}):
            await cog.core_talk.callback(cog, ctx, message="hello")

        assert ctx.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_empty_response(self):
        bot = _make_bot()
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        chat_cog = MagicMock()
        chat_cog.prompt_manager.get_system_prompt.return_value = "SP"
        bot.get_cog.return_value = chat_cog
        tape_engine = MagicMock()
        bot.tape_engine = tape_engine
        cognition_engine = MagicMock()
        cognition_engine.process = AsyncMock(return_value=("", []))
        bot.cognition = cognition_engine
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.core_talk.callback(cog, ctx, message="hello")
        assert "empty response" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cognition_exception(self):
        bot = _make_bot()
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        chat_cog = MagicMock()
        chat_cog.prompt_manager.get_system_prompt.return_value = "SP"
        bot.get_cog.return_value = chat_cog
        tape_engine = MagicMock()
        bot.tape_engine = tape_engine
        cognition_engine = MagicMock()
        cognition_engine.process = AsyncMock(side_effect=RuntimeError("boom"))
        bot.cognition = cognition_engine
        cog = _moderation_cog(bot)
        ctx = _make_ctx()
        await cog.core_talk.callback(cog, ctx, message="hello")
        assert "Cognition failed" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cognition_fallback_creation(self):
        """When bot.tape_engine is None, creates CognitionEngine inline."""
        bot = _make_bot()
        bot.engine_manager.get_active_engine.return_value = MagicMock()
        chat_cog = MagicMock()
        chat_cog.prompt_manager.get_system_prompt.return_value = "SP"
        bot.get_cog.return_value = chat_cog
        bot.tape_engine = None
        cog = _moderation_cog(bot)
        ctx = _make_ctx()

        mock_cog_engine = AsyncMock()
        cog_mod = MagicMock()
        cog_mod.CognitionEngine.return_value = mock_cog_engine

        view_mod = MagicMock()
        view_mod.ResponseFeedbackView.return_value = MagicMock()

        with patch.dict("sys.modules", {
                "src.engines.cognition": cog_mod,
                "src.ui.views": view_mod,
             }):
            await cog.core_talk.callback(cog, ctx, message="hello")

        assert ctx.send.call_count >= 1


# ─── setup ───────────────────────────────────────────────────────────

class TestSetup:
    @pytest.mark.asyncio
    async def test_setup(self):
        from src.bot.cogs.admin_moderation import setup
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        await setup(bot)
        bot.add_cog.assert_called_once()
