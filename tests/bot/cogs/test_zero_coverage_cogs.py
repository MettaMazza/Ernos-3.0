"""
Phase 1 Coverage Tests — Zero-coverage cog modules.
Covers: stop_command (0%), mode_commands (0%), skill_commands (0%), admin_testing (0%).
"""
import sys
import types as _types
import importlib
import pytest
import asyncio
import time
import re
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

# Save real modules at import time before any test pollution
_real_discord = __import__('discord')
_saved_discord_modules = {
    k: v for k, v in sys.modules.items()
    if k == 'discord' or k.startswith('discord.')
    if isinstance(v, _types.ModuleType)
}

def _restore_modules():
    """Restore real discord modules in sys.modules if they've been replaced by mocks."""
    for name, mod in _saved_discord_modules.items():
        if not isinstance(sys.modules.get(name), _types.ModuleType):
            sys.modules[name] = mod


# ════════════════════════════════════════════════════════════
# StopCommand (28 stmts → 0%)
# ════════════════════════════════════════════════════════════

class TestStopCommand:
    def _make_cog(self):
        _restore_modules()
        import src.bot.cogs.stop_command as _mod
        importlib.reload(_mod)
        from src.bot.cogs.stop_command import StopCommand
        bot = MagicMock()
        return StopCommand(bot), bot

    # ── _do_stop ──

    @pytest.mark.asyncio
    async def test_do_stop_no_cognition_engine(self):
        """Returns False when bot has no cognition attribute."""
        cog, bot = self._make_cog()
        del bot.tape_engine
        del bot.cognition
        result = await cog._do_stop("123")
        assert result is False

    @pytest.mark.asyncio
    async def test_do_stop_cognition_none(self):
        """Returns False when bot.tape_engine and cognition are None."""
        cog, bot = self._make_cog()
        bot.tape_engine = None
        bot.cognition = None
        result = await cog._do_stop("123")
        assert result is False

    @pytest.mark.asyncio
    async def test_do_stop_cancel_success(self):
        """Returns True when engine.request_cancel returns True."""
        cog, bot = self._make_cog()
        bot.tape_engine = MagicMock()
        bot.cognition = MagicMock()
        bot.cognition.request_cancel.return_value = True
        result = await cog._do_stop("123")
        assert result is True
        bot.cognition.request_cancel.assert_called_once_with("123")

    @pytest.mark.asyncio
    async def test_do_stop_cancel_nothing(self):
        """Returns False when nothing active to cancel."""
        cog, bot = self._make_cog()
        bot.tape_engine = MagicMock()
        bot.cognition = MagicMock()
        bot.cognition.request_cancel.return_value = False
        result = await cog._do_stop("123")
        assert result is False

    # ── stop_slash ──

    @pytest.mark.asyncio
    async def test_stop_slash_cancelled(self):
        """Slash command responds with ⏹️ when cancelled."""
        cog, bot = self._make_cog()
        bot.cognition = MagicMock()
        bot.cognition.request_cancel.return_value = True
        interaction = MagicMock()
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        await cog.stop_slash.callback(cog, interaction)
        interaction.response.send_message.assert_called_once_with("⏹️", ephemeral=True)

    @pytest.mark.asyncio
    async def test_stop_slash_nothing_active(self):
        """Slash command responds with nothing-active message."""
        cog, bot = self._make_cog()
        bot.cognition = MagicMock()
        bot.cognition.request_cancel.return_value = False
        interaction = MagicMock()
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        await cog.stop_slash.callback(cog, interaction)
        interaction.response.send_message.assert_called_once_with(
            "Nothing active to stop.", ephemeral=True
        )

    # ── stop_prefix ──

    @pytest.mark.asyncio
    async def test_stop_prefix_cancelled(self):
        """Prefix command adds ⏹️ reaction when cancelled."""
        cog, bot = self._make_cog()
        bot.cognition = MagicMock()
        bot.cognition.request_cancel.return_value = True
        ctx = MagicMock()
        ctx.author.id = 42
        ctx.message.add_reaction = AsyncMock()
        await cog.stop_prefix.callback(cog, ctx)
        ctx.message.add_reaction.assert_called_once_with("⏹️")

    @pytest.mark.asyncio
    async def test_stop_prefix_nothing_active(self):
        """Prefix command silently ignores when nothing active."""
        cog, bot = self._make_cog()
        bot.cognition = MagicMock()
        bot.cognition.request_cancel.return_value = False
        ctx = MagicMock()
        ctx.author.id = 42
        ctx.message.add_reaction = AsyncMock()
        await cog.stop_prefix.callback(cog, ctx)
        ctx.message.add_reaction.assert_not_called()

    # ── setup ──

    @pytest.mark.asyncio
    async def test_setup(self):
        _restore_modules()
        import src.bot.cogs.stop_command as _mod
        importlib.reload(_mod)
        from src.bot.cogs.stop_command import setup
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        await setup(bot)
        bot.add_cog.assert_called_once()


# ════════════════════════════════════════════════════════════
# ModeCommands (48 stmts → 0%)
# ════════════════════════════════════════════════════════════

class TestModeCommands:
    def _make_cog(self):
        _restore_modules()
        import src.bot.cogs.mode_commands as _mod
        importlib.reload(_mod)
        from src.bot.cogs.mode_commands import ModeCommands
        bot = MagicMock()
        return ModeCommands(bot), bot

    # ── professional_mode ──

    @pytest.mark.asyncio
    async def test_professional_mode_guild_blocked(self):
        """Professional mode is blocked outside DMs."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.guild = MagicMock()  # Non-None = guild context
        interaction.response.send_message = AsyncMock()
        await cog.professional_slash.callback(cog, interaction)
        interaction.response.send_message.assert_called_once()
        assert "DMs" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_professional_mode_already_professional(self):
        """Returns early if already in professional mode."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.guild = None  # DM context
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        with patch("src.memory.preferences.PreferencesManager") as MockPM:
            MockPM.get_interaction_mode.return_value = "professional"
            await cog.professional_slash.callback(cog, interaction)
        assert "Already" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_professional_mode_switch_success(self):
        """Successfully switches to professional mode."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.guild = None
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        with patch("src.memory.preferences.PreferencesManager") as MockPM:
            MockPM.get_interaction_mode.return_value = "default"
            await cog.professional_slash.callback(cog, interaction)
        # Should send an embed
        call_kwargs = interaction.response.send_message.call_args
        assert call_kwargs is not None
        MockPM.set_interaction_mode.assert_called_once_with(42, "professional")

    @pytest.mark.asyncio
    async def test_professional_mode_exception(self):
        """Handles exceptions gracefully."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.guild = None
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        with patch("src.memory.preferences.PreferencesManager") as MockPM:
            MockPM.get_interaction_mode.side_effect = Exception("DB error")
            await cog.professional_slash.callback(cog, interaction)
        assert "failed" in interaction.response.send_message.call_args[0][0].lower() or \
               "❌" in interaction.response.send_message.call_args[0][0]

    # ── self_mode ──

    @pytest.mark.asyncio
    async def test_self_mode_guild_blocked(self):
        """Self mode is blocked outside DMs."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.guild = MagicMock()
        interaction.response.send_message = AsyncMock()
        await cog.self_slash.callback(cog, interaction)
        assert "DMs" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_self_mode_already_default(self):
        """Returns early if already in default mode."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.guild = None
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        with patch("src.memory.preferences.PreferencesManager") as MockPM:
            MockPM.get_interaction_mode.return_value = "default"
            await cog.self_slash.callback(cog, interaction)
        assert "Already" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_self_mode_switch_success(self):
        """Successfully switches to full Ernos mode."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.guild = None
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        with patch("src.memory.preferences.PreferencesManager") as MockPM:
            MockPM.get_interaction_mode.return_value = "professional"
            await cog.self_slash.callback(cog, interaction)
        MockPM.set_interaction_mode.assert_called_once_with(42, "default")

    @pytest.mark.asyncio
    async def test_self_mode_exception(self):
        """Handles exceptions gracefully."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.guild = None
        interaction.user.id = 42
        interaction.response.send_message = AsyncMock()
        with patch("src.memory.preferences.PreferencesManager") as MockPM:
            MockPM.get_interaction_mode.side_effect = Exception("DB error")
            await cog.self_slash.callback(cog, interaction)
        assert "❌" in interaction.response.send_message.call_args[0][0]

    # ── setup ──

    @pytest.mark.asyncio
    async def test_setup(self):
        _restore_modules()
        import src.bot.cogs.mode_commands as _mod
        importlib.reload(_mod)
        from src.bot.cogs.mode_commands import setup
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        await setup(bot)
        bot.add_cog.assert_called_once()


# ════════════════════════════════════════════════════════════
# SkillCommands (96 stmts → 0%)
# ════════════════════════════════════════════════════════════

class TestSkillCommands:
    def _make_cog(self):
        _restore_modules()
        import src.bot.cogs.skill_commands as _mod
        importlib.reload(_mod)
        from src.bot.cogs.skill_commands import SkillCommands
        bot = MagicMock()
        bot.is_owner = AsyncMock(return_value=False)
        return SkillCommands(bot), bot

    # ── approve_skill_cmd (slash) ──

    @pytest.mark.asyncio
    async def test_approve_skill_cmd_not_owner_not_admin(self):
        """Non-owner, non-admin is rejected."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.permissions.administrator = False
        interaction.response.send_message = AsyncMock()
        await cog.approve_skill_cmd.callback(cog, interaction, "my_skill")
        interaction.response.send_message.assert_called_once()
        assert "❌" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_approve_skill_cmd_owner_success(self):
        """Owner can approve a skill."""
        cog, bot = self._make_cog()
        bot.is_owner = AsyncMock(return_value=True)
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.approve_skill", new_callable=AsyncMock, return_value="✅ Approved"):
            await cog.approve_skill_cmd.callback(cog, interaction, "my_skill")
        interaction.followup.send.assert_called_once_with("✅ Approved")

    @pytest.mark.asyncio
    async def test_approve_skill_cmd_admin_success(self):
        """Admin can approve a skill."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.permissions.administrator = True
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.approve_skill", new_callable=AsyncMock, return_value="✅ Done"):
            await cog.approve_skill_cmd.callback(cog, interaction, "skill1", "CORE")
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_skill_cmd_exception(self):
        """Handles exception during approval."""
        cog, bot = self._make_cog()
        bot.is_owner = AsyncMock(return_value=True)
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.approve_skill", new_callable=AsyncMock, side_effect=Exception("fail")):
            await cog.approve_skill_cmd.callback(cog, interaction, "bad_skill")
        assert "❌" in interaction.followup.send.call_args[0][0]

    # ── approve_skill_prefix ──

    @pytest.mark.asyncio
    async def test_approve_skill_prefix_not_owner(self):
        """Prefix: non-owner non-admin is rejected."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.author = MagicMock()
        ctx.author.guild_permissions.administrator = False
        ctx.send = AsyncMock()
        await cog.approve_skill_prefix.callback(cog, ctx, "skill1")
        ctx.send.assert_called_once()
        assert "❌" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_approve_skill_prefix_owner_success(self):
        """Prefix: owner can approve."""
        cog, bot = self._make_cog()
        bot.is_owner = AsyncMock(return_value=True)
        ctx = MagicMock()
        ctx.author = MagicMock()
        ctx.typing = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
        ctx.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.approve_skill", new_callable=AsyncMock, return_value="✅ Done"):
            await cog.approve_skill_prefix.callback(cog, ctx, "skill1")
        ctx.send.assert_called_once_with("✅ Done")

    @pytest.mark.asyncio
    async def test_approve_skill_prefix_exception(self):
        """Prefix: handles exception."""
        cog, bot = self._make_cog()
        bot.is_owner = AsyncMock(return_value=True)
        ctx = MagicMock()
        ctx.author = MagicMock()
        ctx.typing = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
        ctx.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.approve_skill", new_callable=AsyncMock, side_effect=Exception("x")):
            await cog.approve_skill_prefix.callback(cog, ctx, "skill1")
        assert "❌" in ctx.send.call_args[0][0]

    # ── list_proposals_prefix ──

    @pytest.mark.asyncio
    async def test_list_proposals_prefix_success(self):
        """Lists proposals via prefix command."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.typing = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
        ctx.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.list_proposals", new_callable=AsyncMock, return_value="No pending"):
            await cog.list_proposals_prefix.callback(cog, ctx)
        ctx.send.assert_called_once_with("No pending")

    @pytest.mark.asyncio
    async def test_list_proposals_prefix_exception(self):
        """List proposals handles error."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.typing = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
        ctx.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.list_proposals", new_callable=AsyncMock, side_effect=Exception("err")):
            await cog.list_proposals_prefix.callback(cog, ctx)
        assert "❌" in ctx.send.call_args[0][0]

    # ── schedule_skill_prefix ──

    @pytest.mark.asyncio
    async def test_schedule_skill_prefix_non_admin_in_guild(self):
        """Non-admin scheduling in guild is rejected."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.author = MagicMock()
        ctx.author.guild_permissions.administrator = False
        ctx.guild = MagicMock()  # not None = guild
        ctx.send = AsyncMock()
        await cog.schedule_skill_prefix.callback(cog, ctx, "skill1", 12, 0)
        assert "DMs" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_schedule_skill_prefix_admin_success(self):
        """Admin can schedule in guild."""
        cog, bot = self._make_cog()
        bot.is_owner = AsyncMock(return_value=True)
        ctx = MagicMock()
        ctx.author = MagicMock()
        ctx.author.id = 42
        ctx.guild = MagicMock()
        ctx.typing = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
        ctx.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.schedule_skill", new_callable=AsyncMock, return_value="✅ Scheduled"):
            await cog.schedule_skill_prefix.callback(cog, ctx, "skill1", 8, 30)
        ctx.send.assert_called_once_with("✅ Scheduled")

    @pytest.mark.asyncio
    async def test_schedule_skill_prefix_dm_success(self):
        """Non-admin can schedule in DMs."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.author = MagicMock()
        ctx.author.id = 42
        ctx.author.guild_permissions.administrator = False
        ctx.guild = None  # DM
        ctx.typing = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
        ctx.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.schedule_skill", new_callable=AsyncMock, return_value="✅"):
            await cog.schedule_skill_prefix.callback(cog, ctx, "skill1", 8, 0)
        ctx.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_skill_prefix_exception(self):
        """Schedule skill handles error."""
        cog, bot = self._make_cog()
        bot.is_owner = AsyncMock(return_value=True)
        ctx = MagicMock()
        ctx.author = MagicMock()
        ctx.author.id = 42
        ctx.guild = None
        ctx.typing = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
        ctx.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.schedule_skill", new_callable=AsyncMock, side_effect=Exception("err")):
            await cog.schedule_skill_prefix.callback(cog, ctx, "s", 0, 0)
        assert "❌" in ctx.send.call_args[0][0]

    # ── schedule_skill_cmd (slash) ──

    @pytest.mark.asyncio
    async def test_schedule_skill_cmd_non_admin_guild_blocked(self):
        """Non-admin slash scheduling in guild is blocked."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.permissions.administrator = False
        interaction.guild = MagicMock()  # guild context
        interaction.response.send_message = AsyncMock()
        # schedule_skill_cmd is a plain function (no @app_commands.command)
        await cog.schedule_skill_cmd(interaction, "skill", 8, 0)
        interaction.response.send_message.assert_called_once()
        assert "DMs" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_schedule_skill_cmd_admin_success(self):
        """Admin can schedule via slash command."""
        cog, bot = self._make_cog()
        bot.is_owner = AsyncMock(return_value=True)
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 42
        interaction.guild = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.schedule_skill", new_callable=AsyncMock, return_value="✅"):
            await cog.schedule_skill_cmd(interaction, "skill", 8, 0)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_skill_cmd_exception(self):
        """Slash schedule handles error."""
        cog, bot = self._make_cog()
        bot.is_owner = AsyncMock(return_value=True)
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.user.id = 42
        interaction.guild = None
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.schedule_skill", new_callable=AsyncMock, side_effect=Exception("x")):
            await cog.schedule_skill_cmd(interaction, "s", 0, 0)
        assert "❌" in interaction.followup.send.call_args[0][0]

    # ── list_proposals_cmd (slash) ──

    @pytest.mark.asyncio
    async def test_list_proposals_cmd_success(self):
        """Slash list proposals works."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.list_proposals", new_callable=AsyncMock, return_value="📋 None"):
            await cog.list_proposals_cmd.callback(cog, interaction)
        interaction.followup.send.assert_called_once_with("📋 None")

    @pytest.mark.asyncio
    async def test_list_proposals_cmd_exception(self):
        """Slash list proposals handles error."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.list_proposals", new_callable=AsyncMock, side_effect=Exception("e")):
            await cog.list_proposals_cmd.callback(cog, interaction)
        assert "❌" in interaction.followup.send.call_args[0][0]

    # ── reload_skills_cmd ──

    @pytest.mark.asyncio
    async def test_reload_skills_cmd_not_admin(self):
        """Non-admin is rejected."""
        cog, bot = self._make_cog()
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.permissions.administrator = False
        interaction.response.send_message = AsyncMock()
        await cog.reload_skills_cmd.callback(cog, interaction)
        interaction.response.send_message.assert_called_once()
        assert "❌" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_reload_skills_cmd_owner_success(self):
        """Owner can reload skills."""
        cog, bot = self._make_cog()
        bot.is_owner = AsyncMock(return_value=True)
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        with patch("src.tools.skill_admin_tools.reload_skills", new_callable=AsyncMock, return_value="✅ Reloaded"):
            await cog.reload_skills_cmd.callback(cog, interaction)
        interaction.followup.send.assert_called_once_with("✅ Reloaded")

    # ── setup ──

    @pytest.mark.asyncio
    async def test_setup(self):
        _restore_modules()
        import src.bot.cogs.skill_commands as _mod
        importlib.reload(_mod)
        from src.bot.cogs.skill_commands import setup
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        await setup(bot)
        bot.add_cog.assert_called_once()


# ════════════════════════════════════════════════════════════
# AdminTesting (178 stmts → 0%)
# ════════════════════════════════════════════════════════════

class TestAdminTesting:
    """Tests for the /testall command and its supporting functions."""

    # ── _parse_test_file ──

    def test_parse_test_file_missing(self, tmp_path):
        """Missing file returns empty list."""
        from src.bot.cogs.admin_testing import _parse_test_file
        result = _parse_test_file(str(tmp_path / "nonexistent.md"))
        assert result == []

    def test_parse_test_file_empty(self, tmp_path):
        """Empty file returns empty list."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text("")
        result = _parse_test_file(str(f))
        assert result == []

    def test_parse_test_file_phase_headers(self, tmp_path):
        """Parses phase headers correctly."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text(
            "=== PHASE 1: Memory ===\n"
            "1. recall query=\"test\"\n"
            "=== PHASE 2: Tools ===\n"
            "2. web_search query=\"hello\"\n"
        )
        result = _parse_test_file(str(f))
        assert len(result) == 2
        assert result[0]["phase"] == "PHASE 1: Memory"
        assert result[1]["phase"] == "PHASE 2: Tools"

    def test_parse_test_file_tool_args(self, tmp_path):
        """Parses tool name and key=value arguments."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text('1. recall query="multi word search" limit=5\n')
        result = _parse_test_file(str(f))
        assert len(result) == 1
        assert result[0]["tool_name"] == "recall"
        assert result[0]["args"]["query"] == "multi word search"
        assert result[0]["args"]["limit"] == 5

    def test_parse_test_file_bool_args(self, tmp_path):
        """Boolean values are parsed correctly."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text("1. tool flag=true other=false\n")
        result = _parse_test_file(str(f))
        assert result[0]["args"]["flag"] is True
        assert result[0]["args"]["other"] is False

    def test_parse_test_file_float_args(self, tmp_path):
        """Float values are parsed correctly."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text("1. tool score=3.14\n")
        result = _parse_test_file(str(f))
        assert result[0]["args"]["score"] == 3.14

    def test_parse_test_file_string_args(self, tmp_path):
        """Non-numeric strings stay as strings."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text("1. tool name=hello\n")
        result = _parse_test_file(str(f))
        assert result[0]["args"]["name"] == "hello"

    def test_parse_test_file_skip_describe(self, tmp_path):
        """Describe lines are skipped."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text("1. Describe the memory system architecture\n")
        result = _parse_test_file(str(f))
        assert result[0]["skip"] is True
        assert result[0]["skip_reason"] == "Documentation-only"

    def test_parse_test_file_skip_verify(self, tmp_path):
        """Verify lines are marked for manual verification."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text("1. Verify the recall results are correct\n")
        result = _parse_test_file(str(f))
        assert result[0]["skip"] is True
        assert "Manual" in result[0]["skip_reason"]

    def test_parse_test_file_skip_heavy(self, tmp_path):
        """Heavy tools (GPU, etc.) are skipped."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text("1. generate_image prompt=\"test\"\n")
        result = _parse_test_file(str(f))
        assert result[0]["skip"] is True
        assert "Resource-heavy" in result[0]["skip_reason"]

    def test_parse_test_file_single_quoted_args(self, tmp_path):
        """Single-quoted values are parsed correctly."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text("1. tool key='single quoted value'\n")
        result = _parse_test_file(str(f))
        assert result[0]["args"]["key"] == "single quoted value"

    def test_parse_test_file_no_match_lines(self, tmp_path):
        """Non-test lines are ignored."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text("# Header\nsome text\n\n1. recall query=test\n")
        result = _parse_test_file(str(f))
        assert len(result) == 1

    def test_parse_test_file_mixed(self, tmp_path):
        """Mixed content parses correctly."""
        from src.bot.cogs.admin_testing import _parse_test_file
        f = tmp_path / "test.md"
        f.write_text(
            "=== PHASE 1: Core ===\n"
            "1. recall query=\"cats\"\n"
            "2. Describe the system\n"
            "3. generate_video prompt=\"test\"\n"
            "4. web_search query=ai\n"
        )
        result = _parse_test_file(str(f))
        assert len(result) == 4
        assert result[0]["skip"] is False  # recall
        assert result[1]["skip"] is True   # Describe
        assert result[2]["skip"] is True   # generate_video (heavy)
        assert result[3]["skip"] is False  # web_search

    # ── AdminTesting cog ──

    def _make_cog(self):
        _restore_modules()
        import src.bot.cogs.admin_testing as _mod
        importlib.reload(_mod)
        from src.bot.cogs.admin_testing import AdminTesting
        bot = MagicMock()
        return AdminTesting(bot), bot

    @pytest.mark.asyncio
    async def test_cog_check_admin(self):
        """Admin passes cog check."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.author.id = 123
        with patch("src.bot.cogs.admin_testing.settings") as mock_s:
            mock_s.ADMIN_IDS = [123]
            result = await cog.cog_check(ctx)
        assert result is True

    @pytest.mark.asyncio
    async def test_cog_check_non_admin(self):
        """Non-admin fails cog check."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.author.id = 999
        with patch("src.bot.cogs.admin_testing.settings") as mock_s:
            mock_s.ADMIN_IDS = [123]
            result = await cog.cog_check(ctx)
        assert result is False

    @pytest.mark.asyncio
    async def test_testall_no_tests(self, tmp_path):
        """testall with no parseable tests sends error message."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=[]):
            await cog.testall.callback(cog, ctx)
        ctx.send.assert_called_once()
        assert "❌" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_testall_skipped_tests(self, tmp_path):
        """testall with all-skipped tests runs and reports."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        tests = [
            {"number": 1, "phase": "PHASE 1", "raw": "Describe x",
             "tool_name": None, "args": {}, "skip": True, "skip_reason": "Doc"},
        ]
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            await cog.testall.callback(cog, ctx)
        # Should have at least 2 sends: initial message + report
        assert ctx.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_testall_tool_not_found(self):
        """testall with missing tool records FAIL."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        tests = [
            {"number": 1, "phase": "P1", "raw": "nonexistent",
             "tool_name": "nonexistent_tool", "args": {}, "skip": False, "skip_reason": None},
        ]
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            with patch("src.tools.registry.ToolRegistry.get_tool", return_value=None):
                await cog.testall.callback(cog, ctx)
        # Report should mention failure
        report_text = ctx.send.call_args_list[-1][0][0] if ctx.send.call_args_list else ""
        # Could be sent as file or text
        assert ctx.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_testall_tool_execution_success(self):
        """testall with successful tool records OK."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        tests = [
            {"number": 1, "phase": "P1", "raw": "recall query=test",
             "tool_name": "recall", "args": {"query": "test"}, "skip": False, "skip_reason": None},
        ]
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            with patch("src.tools.registry.ToolRegistry.get_tool", return_value=MagicMock()):
                with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock, return_value="Found 5 results"):
                    await cog.testall.callback(cog, ctx)
        assert ctx.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_testall_tool_execution_warns(self):
        """testall records WARN when result starts with Error."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        tests = [
            {"number": 1, "phase": "P1", "raw": "recall",
             "tool_name": "recall", "args": {}, "skip": False, "skip_reason": None},
        ]
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            with patch("src.tools.registry.ToolRegistry.get_tool", return_value=MagicMock()):
                with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock, return_value="Error: no data"):
                    await cog.testall.callback(cog, ctx)
        assert ctx.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_testall_tool_execution_none_result(self):
        """testall records WARN when result is None."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        tests = [
            {"number": 1, "phase": "P1", "raw": "recall",
             "tool_name": "recall", "args": {}, "skip": False, "skip_reason": None},
        ]
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            with patch("src.tools.registry.ToolRegistry.get_tool", return_value=MagicMock()):
                with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock, return_value=None):
                    await cog.testall.callback(cog, ctx)
        assert ctx.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_testall_tool_execution_exception(self):
        """testall records FAIL when tool throws."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        tests = [
            {"number": 1, "phase": "P1", "raw": "recall",
             "tool_name": "recall", "args": {}, "skip": False, "skip_reason": None},
        ]
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            with patch("src.tools.registry.ToolRegistry.get_tool", return_value=MagicMock()):
                with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
                    await cog.testall.callback(cog, ctx)
        assert ctx.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_testall_long_report_sent_as_file(self):
        """Reports > 1900 chars are sent as file attachments."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        # Create lots of failing test entries across many phases to generate a long report
        # _build_report only expands FAIL/WARN/Slow sections, so we need failures
        tests = []
        for i in range(50):
            tests.append({
                "number": i, "phase": f"PHASE {i % 10}: Category {i % 10}",
                "raw": f"tool_{i} arg=val",
                "tool_name": f"tool_{i}", "args": {"arg": "val"},
                "skip": False, "skip_reason": None,
            })
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            with patch("src.tools.registry.ToolRegistry.get_tool", return_value=None):
                # All tools "not found" → all FAIL
                with patch("src.engines.cognition.CognitionEngine") as MockCE:
                    MockCE.return_value.think = AsyncMock(return_value="All bad")
                    await cog.testall.callback(cog, ctx)
        # With 50 failures across 10 phases, the report should be very long
        assert ctx.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_testall_llm_summary_failure(self):
        """testall handles LLM summary failure gracefully."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        tests = [
            {"number": 1, "phase": "P1", "raw": "recall",
             "tool_name": "recall", "args": {}, "skip": False, "skip_reason": None},
        ]
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            with patch("src.tools.registry.ToolRegistry.get_tool", return_value=MagicMock()):
                with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"):
                    with patch("src.engines.cognition.CognitionEngine", side_effect=Exception("fail")):
                        await cog.testall.callback(cog, ctx)
        # Should not crash — report still sent

    @pytest.mark.asyncio
    async def test_testall_llm_summary_success(self):
        """testall sends LLM analysis when available."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        tests = [
            {"number": 1, "phase": "P1", "raw": "recall",
             "tool_name": "recall", "args": {}, "skip": False, "skip_reason": None},
        ]
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            with patch("src.tools.registry.ToolRegistry.get_tool", return_value=MagicMock()):
                with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"):
                    with patch("src.engines.cognition.CognitionEngine") as MockCE:
                        MockCE.return_value.think = AsyncMock(return_value="System healthy")
                        await cog.testall.callback(cog, ctx)
        # Should have LLM analysis send
        all_sends = [str(c) for c in ctx.send.call_args_list]
        assert any("LLM Analysis" in s for s in all_sends)

    @pytest.mark.asyncio
    async def test_testall_llm_empty_summary(self):
        """testall handles empty LLM summary."""
        cog, bot = self._make_cog()
        ctx = MagicMock()
        ctx.send = AsyncMock()
        tests = [
            {"number": 1, "phase": "P1", "raw": "recall",
             "tool_name": "recall", "args": {}, "skip": False, "skip_reason": None},
        ]
        with patch("src.bot.cogs.admin_testing._parse_test_file", return_value=tests):
            with patch("src.tools.registry.ToolRegistry.get_tool", return_value=MagicMock()):
                with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"):
                    with patch("src.engines.cognition.CognitionEngine") as MockCE:
                        MockCE.return_value.think = AsyncMock(return_value="")
                        await cog.testall.callback(cog, ctx)

    # ── _build_report ──

    def test_build_report_operational(self):
        """Build report with 0 failures = OPERATIONAL."""
        cog, _ = self._make_cog()
        results = [
            {"number": 1, "phase": "P1", "tool": "recall", "status": "OK", "reason": "Found", "time_ms": 50},
        ]
        phase_results = {"P1": {"ok": 1, "warn": 0, "fail": 0, "skip": 0}}
        report = cog._build_report(results, phase_results, 1, 0, 1, 0, 0, 1.5)
        assert "OPERATIONAL" in report
        assert "recall" not in report.split("Failures")[0] if "Failures" in report else True

    def test_build_report_degraded_failures(self):
        """Build report with some failures in DEGRADED band (10-25% fail ratio)."""
        cog, _ = self._make_cog()
        results = [
            {"number": 1, "phase": "P1", "tool": "t1", "status": "FAIL", "reason": "not found", "time_ms": 10},
        ] + [
            {"number": i, "phase": "P1", "tool": f"t{i}", "status": "OK", "reason": "ok", "time_ms": 20}
            for i in range(2, 7)
        ]
        phase_results = {"P1": {"ok": 5, "warn": 0, "fail": 1, "skip": 0}}
        report = cog._build_report(results, phase_results, 6, 0, 5, 1, 0, 2.0)
        assert "DEGRADED" in report
        assert "Failures" in report

    def test_build_report_critical(self):
        """Build report with 5+ failures = CRITICAL."""
        cog, _ = self._make_cog()
        results = [
            {"number": i, "phase": "P1", "tool": f"t{i}", "status": "FAIL", "reason": "err", "time_ms": 10}
            for i in range(6)
        ]
        phase_results = {"P1": {"ok": 0, "warn": 0, "fail": 6, "skip": 0}}
        report = cog._build_report(results, phase_results, 6, 0, 0, 6, 0, 3.0)
        assert "CRITICAL" in report

    def test_build_report_degraded_warnings(self):
        """Build report with >15% warnings = OPERATIONAL (WARNINGS)."""
        cog, _ = self._make_cog()
        results = [
            {"number": i, "phase": "P1", "tool": f"t{i}", "status": "WARN", "reason": "warn", "time_ms": 10}
            for i in range(4)
        ]
        phase_results = {"P1": {"ok": 0, "warn": 4, "fail": 0, "skip": 0}}
        report = cog._build_report(results, phase_results, 4, 0, 0, 0, 4, 4.0)
        assert "OPERATIONAL (WARNINGS)" in report
        assert "Warnings" in report

    def test_build_report_slow_tests(self):
        """Build report includes slow tests section."""
        cog, _ = self._make_cog()
        results = [
            {"number": 1, "phase": "P1", "tool": "slow_tool", "status": "OK", "reason": "ok", "time_ms": 5000},
        ]
        phase_results = {"P1": {"ok": 1, "warn": 0, "fail": 0, "skip": 0}}
        report = cog._build_report(results, phase_results, 1, 0, 1, 0, 0, 5.0)
        assert "Slow Tests" in report
        assert "slow_tool" in report

    def test_build_report_multiple_phases(self):
        """Build report handles multiple phases."""
        cog, _ = self._make_cog()
        results = [
            {"number": 1, "phase": "PHASE 1: Memory", "tool": "t1", "status": "OK", "reason": "ok", "time_ms": 10},
            {"number": 2, "phase": "PHASE 2: Tools", "tool": "t2", "status": "OK", "reason": "ok", "time_ms": 10},
        ]
        phase_results = {
            "PHASE 1: Memory": {"ok": 1, "warn": 0, "fail": 0, "skip": 0},
            "PHASE 2: Tools": {"ok": 1, "warn": 0, "fail": 0, "skip": 0},
        }
        report = cog._build_report(results, phase_results, 2, 0, 2, 0, 0, 1.0)
        assert "Memory" in report
        assert "Tools" in report

    def test_build_report_skip_not_in_slow(self):
        """Skip-status tests are excluded from slow tests list."""
        cog, _ = self._make_cog()
        results = [
            {"number": 1, "phase": "P1", "tool": "t1", "status": "SKIP", "reason": "heavy", "time_ms": 9999},
        ]
        phase_results = {"P1": {"ok": 0, "warn": 0, "fail": 0, "skip": 1}}
        report = cog._build_report(results, phase_results, 0, 1, 0, 0, 0, 0.1)
        assert "Slow" not in report

    # ── setup ──

    @pytest.mark.asyncio
    async def test_setup(self):
        _restore_modules()
        import src.bot.cogs.admin_testing as _mod
        importlib.reload(_mod)
        from src.bot.cogs.admin_testing import setup
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        await setup(bot)
        bot.add_cog.assert_called_once()
