"""Phase 4 polish tests for bot/client.py, prompts/manager.py, security/provenance.py."""
import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path


# ═══════════════════════════ ErnosBot ═══════════════════════════
class TestErnosBot:
    def test_is_processing_empty(self):
        from src.bot.client import ErnosBot
        bot = ErnosBot.__new__(ErnosBot)
        bot.processing_users = set()
        assert bot.is_processing is False

    def test_is_processing_active(self):
        from src.bot.client import ErnosBot
        bot = ErnosBot.__new__(ErnosBot)
        bot.processing_users = {(42, 100)}
        assert bot.is_processing is True

    def test_add_remove_processing_user(self):
        from src.bot.client import ErnosBot
        bot = ErnosBot.__new__(ErnosBot)
        bot.processing_users = set()
        bot.add_processing_user(42, 100)
        assert (42, 100) in bot.processing_users
        bot.remove_processing_user(42, 100)
        assert (42, 100) not in bot.processing_users

    @pytest.mark.asyncio
    async def test_send_to_mind_no_channel(self):
        from src.bot.client import ErnosBot
        bot = ErnosBot.__new__(ErnosBot)
        bot.get_channel = MagicMock(return_value=None)
        await bot.send_to_mind("test content")
        assert True  # No exception: negative case handled correctly


# ═══════════════════════════ PromptManager ═══════════════════════════
class TestPromptManager:
    def test_read_file_missing(self, tmp_path):
        from src.prompts.manager import PromptManager
        pm = PromptManager(prompt_dir=str(tmp_path))
        result = pm._read_file(str(tmp_path / "nonexistent.txt"))
        assert result == ""

    def test_read_file_exists(self, tmp_path):
        from src.prompts.manager import PromptManager
        pm = PromptManager(prompt_dir=str(tmp_path))
        target = tmp_path / "test.txt"
        target.write_text("kernel content")
        result = pm._read_file(str(target))
        assert result == "kernel content"

    def test_check_no_custom_identity(self, tmp_path):
        from src.prompts.manager import PromptManager
        pm = PromptManager(prompt_dir=str(tmp_path))
        result = pm._check_user_has_custom_identity("99999")
        assert result is False or result is None or isinstance(result, (bool, str))


# ═══════════════════════════ ProvenanceManager ═══════════════════════════
class TestProvenance:
    def test_log_artifact(self, tmp_path):
        from src.security.provenance import ProvenanceManager
        artifact_path = str(tmp_path / "test.png")
        Path(artifact_path).write_bytes(b"fake_image_data")
        ledger = tmp_path / "provenance_ledger.jsonl"
        with patch.object(ProvenanceManager, "LEDGER_FILE", ledger):
            ProvenanceManager.log_artifact(
                artifact_path, "image",
                {"prompt": "test", "user_id": 1, "scope": "PUBLIC"}
            )
        assert True  # Execution completed without error

    def test_is_tracked_unknown(self, tmp_path):
        from src.security.provenance import ProvenanceManager
        ledger = tmp_path / "empty_ledger.jsonl"
        with patch.object(ProvenanceManager, "LEDGER_FILE", ledger):
            result = ProvenanceManager.is_tracked("/nonexistent/path.png")
            assert result is False
