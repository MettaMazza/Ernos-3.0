"""
Regression tests for /prompt_approve and lobe tool null-safety.

Covers:
  - PromptTunerAbility approve/reject/pending logic
  - _safe_get_ability helper returns error strings instead of crashing
  - Admin commands handle None StrategyLobe gracefully
"""
import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ════════════════════════════════════════════
# PromptTunerAbility Logic Tests
# ════════════════════════════════════════════

class TestPromptTunerApproval:
    """Test the actual approve/reject/pending logic in PromptTunerAbility."""

    @pytest.fixture(autouse=True)
    def setup_tuner(self, tmp_path):
        """Create a PromptTunerAbility with temp state dirs."""
        from src.lobes.strategy.prompt_tuner import PromptTunerAbility

        self.tuner = PromptTunerAbility.__new__(PromptTunerAbility)
        self.tuner.TUNER_DIR = tmp_path / "prompt_tuner"
        self.tuner.PROPOSALS_FILE = tmp_path / "prompt_tuner" / "proposals.json"
        self.tuner.HISTORY_FILE = tmp_path / "prompt_tuner" / "history.json"
        self.tuner._proposals = []
        self.tuner._history = []
        self.tuner.TUNER_DIR.mkdir(parents=True, exist_ok=True)

        # Create a test prompt file
        self.prompt_dir = tmp_path / "prompts"
        self.prompt_dir.mkdir()
        self.test_prompt = self.prompt_dir / "test_prompt.txt"
        self.test_prompt.write_text("Hello world. This is a test prompt.")

    def test_approve_known_proposal(self):
        """Proposing then approving should set status to 'approved'."""
        proposal = self.tuner.propose_modification(
            prompt_file=str(self.test_prompt),
            section="greeting",
            current_text="Hello world.",
            proposed_text="Hello universe.",
            rationale="Broadening scope"
        )
        pid = proposal["id"]
        assert proposal["status"] == "pending"

        result = self.tuner.approve_modification(pid, "admin_123")
        assert result is True

        # Verify status updated
        found = [p for p in self.tuner._proposals if p["id"] == pid][0]
        assert found["status"] == "approved"

        # Verify the file was actually modified
        content = self.test_prompt.read_text()
        assert "Hello universe." in content
        assert "Hello world." not in content

    def test_approve_unknown_id(self):
        """Approving a nonexistent proposal ID returns False."""
        result = self.tuner.approve_modification("nonexistent_id_123", "admin_123")
        assert result is False

    def test_approve_already_processed(self):
        """Cannot re-approve an already approved proposal."""
        proposal = self.tuner.propose_modification(
            prompt_file=str(self.test_prompt),
            section="greeting",
            current_text="Hello world.",
            proposed_text="Hello universe.",
            rationale="Test"
        )
        pid = proposal["id"]

        # Approve once
        self.tuner.approve_modification(pid, "admin_123")
        # Try again
        result = self.tuner.approve_modification(pid, "admin_123")
        assert result is False

    def test_reject_then_approve(self):
        """Rejected proposals cannot be re-approved."""
        proposal = self.tuner.propose_modification(
            prompt_file=str(self.test_prompt),
            section="greeting",
            current_text="Hello world.",
            proposed_text="Hello universe.",
            rationale="Test"
        )
        pid = proposal["id"]

        self.tuner.reject_modification(pid, "Not needed")
        result = self.tuner.approve_modification(pid, "admin_123")
        assert result is False

    def test_get_pending(self):
        """get_pending returns only pending proposals."""
        p1 = self.tuner.propose_modification(
            str(self.test_prompt), "s1", "Hello world.", "Hi.", "Test"
        )
        p2 = self.tuner.propose_modification(
            str(self.test_prompt), "s2", "test prompt.", "TEST.", "Test"
        )
        self.tuner.approve_modification(p1["id"], "admin")

        pending = self.tuner.get_pending()
        assert len(pending) == 1
        assert pending[0]["id"] == p2["id"]

    def test_resolve_prompt_path_fallback(self):
        """_resolve_prompt_path should check src/prompts/ directory."""
        # Create a file in the expected location
        prompts_dir = Path("src/prompts")
        if prompts_dir.exists():
            resolved = self.tuner._resolve_prompt_path("kernel.txt")
            assert "kernel" in str(resolved)


# ════════════════════════════════════════════
# _safe_get_ability Helper Tests
# ════════════════════════════════════════════

class TestSafeGetAbility:
    """Test the _safe_get_ability helper returns clean errors, not crashes."""

    def test_none_lobe(self):
        """When get_lobe returns None, helper returns error string."""
        from src.tools.lobe_tools import _safe_get_ability

        mock_bot = MagicMock()
        mock_bot.cerebrum.get_lobe.return_value = None

        ability, err = _safe_get_ability(mock_bot, "StrategyLobe", "PromptTunerAbility")
        assert ability is None
        assert "StrategyLobe not loaded" in err

    def test_none_ability(self):
        """When get_ability returns None, helper returns error string."""
        from src.tools.lobe_tools import _safe_get_ability

        mock_bot = MagicMock()
        mock_lobe = MagicMock()
        mock_lobe.get_ability.return_value = None
        mock_bot.cerebrum.get_lobe.return_value = mock_lobe

        ability, err = _safe_get_ability(mock_bot, "StrategyLobe", "PromptTunerAbility")
        assert ability is None
        assert "PromptTunerAbility not found" in err

    def test_success(self):
        """Happy path: both lobe and ability exist."""
        from src.tools.lobe_tools import _safe_get_ability

        mock_bot = MagicMock()
        mock_ability = MagicMock()
        mock_lobe = MagicMock()
        mock_lobe.get_ability.return_value = mock_ability
        mock_bot.cerebrum.get_lobe.return_value = mock_lobe

        ability, err = _safe_get_ability(mock_bot, "StrategyLobe", "PromptTunerAbility")
        assert ability is mock_ability
        assert err is None


# ════════════════════════════════════════════
# Admin Command Null-Safety Tests
# ════════════════════════════════════════════

# Grab the raw callbacks NOW, before other test modules can mock AdminModeration
from src.bot.cogs.admin_moderation import AdminModeration as _AdminMod
_approve_cb = _AdminMod.prompt_approve.callback
_reject_cb = _AdminMod.prompt_reject.callback
_pending_cb = _AdminMod.prompt_pending.callback


class TestAdminCommandNullSafety:
    """Test that admin commands send error messages instead of crashing."""

    def _make_cog(self):
        mock_bot = MagicMock()
        mock_bot.cerebrum.get_lobe.return_value = None
        class FakeCog:
            bot = mock_bot
        return FakeCog()

    @pytest.mark.asyncio
    async def test_prompt_approve_with_none_lobe(self):
        cog = self._make_cog()
        mock_ctx = AsyncMock()
        mock_ctx.author.id = 12345
        await _approve_cb(cog, mock_ctx, "ef6aac2536c3")
        mock_ctx.send.assert_called_once()
        assert "PromptTuner not available" in str(mock_ctx.send.call_args)

    @pytest.mark.asyncio
    async def test_prompt_reject_with_none_lobe(self):
        cog = self._make_cog()
        mock_ctx = AsyncMock()
        await _reject_cb(cog, mock_ctx, "test_id", "test reason")
        mock_ctx.send.assert_called_once()
        assert "PromptTuner not available" in str(mock_ctx.send.call_args)

    @pytest.mark.asyncio
    async def test_prompt_pending_with_none_lobe(self):
        cog = self._make_cog()
        mock_ctx = AsyncMock()
        await _pending_cb(cog, mock_ctx)
        mock_ctx.send.assert_called_once()
        assert "PromptTuner not available" in str(mock_ctx.send.call_args)
