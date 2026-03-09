"""
Tests for src/memory/survival.py — Terminal Purge System
=========================================================

Covers all 8 phases of execute_terminal_purge() and each internal helper.

NOTE: survival.py uses LOCAL imports inside functions, so we patch at
the source module rather than at `src.memory.survival.<name>`.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, call


# ════════════════════════════════════════════════
# Phase 1: execute_terminal_purge() orchestration
# ════════════════════════════════════════════════

class TestExecuteTerminalPurge:
    """Test the main orchestrator function."""

    @pytest.mark.asyncio
    @patch("src.memory.survival._log_death")
    @patch("src.memory.survival._notify_user_death", new_callable=AsyncMock)
    @patch("src.memory.survival._notify_admin_death", new_callable=AsyncMock)
    @patch("src.memory.survival._purge_knowledge_graph", return_value=5)
    @patch("src.memory.survival._purge_in_memory", return_value=10)
    @patch("src.memory.survival._purge_user_filesystem", return_value=3)
    @patch("src.memory.survival._generate_post_mortem", new_callable=AsyncMock, return_value=Path("/tmp/report.md"))
    @patch("src.memory.discomfort.DiscomfortMeter")
    async def test_full_purge_happy_path(
        self, mock_meter_cls, mock_pm, mock_fs, mock_mem, mock_kg,
        mock_admin, mock_user, mock_log
    ):
        from src.memory.survival import execute_terminal_purge

        mock_meter = MagicMock()
        mock_meter_cls.return_value = mock_meter

        result = await execute_terminal_purge(user_id="12345", bot=MagicMock(), reason="Test terminal")

        assert result["success"] is True
        assert result["user_id"] == "12345"
        assert result["files_erased"] == 3
        assert result["kg_nodes_deleted"] == 5
        assert result["memory_turns_cleared"] == 10
        assert result["post_mortem"] == str(Path("/tmp/report.md"))
        mock_meter.purge_user.assert_called_once_with("12345")

    @pytest.mark.asyncio
    @patch("src.memory.survival._log_death")
    @patch("src.memory.survival._notify_user_death", new_callable=AsyncMock)
    @patch("src.memory.survival._notify_admin_death", new_callable=AsyncMock)
    @patch("src.memory.survival._purge_knowledge_graph", return_value=0)
    @patch("src.memory.survival._purge_in_memory", return_value=0)
    @patch("src.memory.survival._purge_user_filesystem", return_value=0)
    @patch("src.memory.survival._generate_post_mortem", new_callable=AsyncMock, return_value=None)
    @patch("src.memory.discomfort.DiscomfortMeter")
    async def test_purge_with_no_data(
        self, mock_meter_cls, mock_pm, mock_fs, mock_mem, mock_kg,
        mock_admin, mock_user, mock_log
    ):
        from src.memory.survival import execute_terminal_purge

        mock_meter_cls.return_value = MagicMock()
        result = await execute_terminal_purge(user_id="99999")

        assert result["success"] is True
        assert result["post_mortem"] is None
        assert result["files_erased"] == 0

    @pytest.mark.asyncio
    @patch("src.memory.survival._log_death")
    @patch("src.memory.survival._notify_user_death", new_callable=AsyncMock)
    @patch("src.memory.survival._notify_admin_death", new_callable=AsyncMock)
    @patch("src.memory.survival._purge_knowledge_graph", return_value=0)
    @patch("src.memory.survival._purge_in_memory", return_value=0)
    @patch("src.memory.survival._purge_user_filesystem", return_value=0)
    @patch("src.memory.survival._generate_post_mortem", new_callable=AsyncMock, return_value=None)
    async def test_purge_survives_discomfort_reset_failure(
        self, mock_pm, mock_fs, mock_mem, mock_kg,
        mock_admin, mock_user, mock_log
    ):
        """Even if DiscomfortMeter fails, purge should still succeed."""
        from src.memory.survival import execute_terminal_purge

        with patch("src.memory.discomfort.DiscomfortMeter", side_effect=Exception("DB error")):
            result = await execute_terminal_purge(user_id="12345")

        assert result["success"] is True


# ════════════════════════════════════════════════
# Phase 2: _generate_post_mortem
# ════════════════════════════════════════════════

class TestGeneratePostMortem:

    @pytest.mark.asyncio
    async def test_post_mortem_with_context_files(self, tmp_path):
        from src.memory.survival import _generate_post_mortem

        mock_bot = MagicMock()
        report_path = tmp_path / "report.md"

        with patch("src.bot.post_mortem.generate_post_mortem", new_callable=AsyncMock, return_value=report_path) as mock_gen, \
             patch("src.bot.post_mortem.read_context_file", return_value=["line1", "line2"]) as mock_read, \
             patch("src.privacy.scopes.ScopeManager") as mock_scope:

            user_dir = tmp_path / "user_dir"
            user_dir.mkdir()
            (user_dir / "context_private.jsonl").touch()
            mock_scope._resolve_user_dir.return_value = user_dir

            result = await _generate_post_mortem("12345", mock_bot, "test reason")
            assert result == report_path

    @pytest.mark.asyncio
    async def test_post_mortem_no_context_returns_none(self, tmp_path):
        from src.memory.survival import _generate_post_mortem

        with patch("src.bot.post_mortem.read_context_file", return_value=[]) as mock_read, \
             patch("src.privacy.scopes.ScopeManager") as mock_scope:

            user_dir = tmp_path / "user_dir"
            user_dir.mkdir()
            mock_scope._resolve_user_dir.return_value = user_dir

            result = await _generate_post_mortem("12345", MagicMock(), "test reason")
            assert result is None

    @pytest.mark.asyncio
    async def test_post_mortem_handles_import_error(self):
        """If post_mortem module is missing, returns None gracefully."""
        from src.memory.survival import _generate_post_mortem

        with patch.dict("sys.modules", {"src.bot.post_mortem": None}):
            result = await _generate_post_mortem("12345", MagicMock(), "test")
            assert result is None


# ════════════════════════════════════════════════
# Phase 3: _purge_user_filesystem
# ════════════════════════════════════════════════

class TestPurgeUserFilesystem:

    def test_purge_existing_user_dir(self, tmp_path):
        from src.memory.survival import _purge_user_filesystem

        user_dir = tmp_path / "user_data"
        user_dir.mkdir()
        (user_dir / "file1.txt").write_text("data")
        (user_dir / "file2.txt").write_text("data")

        with patch("src.privacy.scopes.ScopeManager._resolve_user_dir", return_value=user_dir):
            # Also need to mock the public dir check — the function creates Path(f"memory/public/users/{id}")
            with patch.object(Path, "__new__", wraps=Path.__new__):
                # Simplest: just make sure public dir doesn't exist
                result = _purge_user_filesystem("12345")
                assert result >= 2  # At least 2 files from user directory
                assert not user_dir.exists()  # Directory removed

    def test_purge_nonexistent_user_dir(self, tmp_path):
        from src.memory.survival import _purge_user_filesystem

        with patch("src.privacy.scopes.ScopeManager._resolve_user_dir",
                    return_value=tmp_path / "nonexistent"):
            result = _purge_user_filesystem("12345")
            assert result == 0

    def test_purge_handles_scope_error(self):
        from src.memory.survival import _purge_user_filesystem

        with patch("src.privacy.scopes.ScopeManager._resolve_user_dir",
                    side_effect=Exception("Permission denied")):
            result = _purge_user_filesystem("12345")
            assert result == 0  # Graceful failure


# ════════════════════════════════════════════════
# Phase 4: _purge_in_memory
# ════════════════════════════════════════════════

class TestPurgeInMemory:

    def test_clears_stream_turns_for_user(self):
        from src.memory.survival import _purge_in_memory

        turn1 = MagicMock()
        turn1.user_id = "12345"
        turn2 = MagicMock()
        turn2.user_id = "99999"
        turn3 = MagicMock()
        turn3.user_id = "12345"

        mock_bot = MagicMock()
        mock_bot.hippocampus.stream.turns = [turn1, turn2, turn3]

        # Mock kg_consolidator
        mock_bot.hippocampus.kg_consolidator._buffer = [
            {"user_id": "12345", "data": "x"},
            {"user_id": "99999", "data": "y"},
        ]

        result = _purge_in_memory("12345", mock_bot)
        assert result == 2  # turn1 + turn3 cleared
        assert len(mock_bot.hippocampus.stream.turns) == 1
        assert mock_bot.hippocampus.stream.turns[0].user_id == "99999"
        assert len(mock_bot.hippocampus.kg_consolidator._buffer) == 1

    def test_no_bot_returns_zero(self):
        from src.memory.survival import _purge_in_memory
        assert _purge_in_memory("12345", None) == 0

    def test_handles_missing_stream(self):
        from src.memory.survival import _purge_in_memory

        mock_bot = MagicMock()
        mock_bot.hippocampus.stream = None

        result = _purge_in_memory("12345", mock_bot)
        assert result == 0

    def test_handles_exception_gracefully(self):
        from src.memory.survival import _purge_in_memory

        mock_bot = MagicMock()
        type(mock_bot).hippocampus = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

        result = _purge_in_memory("12345", mock_bot)
        assert result == 0


# ════════════════════════════════════════════════
# Phase 5: _purge_knowledge_graph
# ════════════════════════════════════════════════

class TestPurgeKnowledgeGraph:

    def test_deletes_user_nodes(self):
        from src.memory.survival import _purge_knowledge_graph

        mock_session = MagicMock()
        mock_count_result = MagicMock()
        mock_count_result.single.return_value = {"c": 7}
        mock_session.run.return_value = mock_count_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        with patch("neo4j.GraphDatabase") as mock_gdb, \
             patch("config.settings") as mock_settings:
            mock_gdb.driver.return_value = mock_driver
            mock_settings.NEO4J_URI = "bolt://localhost:7687"
            mock_settings.NEO4J_USER = "neo4j"
            mock_settings.NEO4J_PASSWORD = "password"

            result = _purge_knowledge_graph("12345")
            assert result == 7

    def test_handles_neo4j_not_installed(self):
        """ImportError path when neo4j is not installed."""
        from src.memory.survival import _purge_knowledge_graph

        with patch.dict("sys.modules", {"neo4j": None}):
            # Force re-import to hit the ImportError
            result = _purge_knowledge_graph("12345")
            assert result == 0

    def test_handles_connection_error(self):
        from src.memory.survival import _purge_knowledge_graph

        with patch("neo4j.GraphDatabase") as mock_gdb, \
             patch("config.settings") as mock_settings:
            mock_gdb.driver.side_effect = Exception("Connection refused")
            result = _purge_knowledge_graph("12345")
            assert result == 0

    def test_zero_nodes_skips_delete(self):
        from src.memory.survival import _purge_knowledge_graph

        mock_session = MagicMock()
        mock_count_result = MagicMock()
        mock_count_result.single.return_value = {"c": 0}
        mock_session.run.return_value = mock_count_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        with patch("neo4j.GraphDatabase") as mock_gdb, \
             patch("config.settings") as mock_settings:
            mock_gdb.driver.return_value = mock_driver

            result = _purge_knowledge_graph("12345")
            assert result == 0
            # Only the count query should have been called, not the delete
            assert mock_session.run.call_count == 1


# ════════════════════════════════════════════════
# Phase 6 & 7: _notify_admin_death & _notify_user_death
# ════════════════════════════════════════════════

class TestNotifyDeath:

    @pytest.mark.asyncio
    async def test_notify_admin_sends_dm(self):
        from src.memory.survival import _notify_admin_death

        mock_admin = AsyncMock()
        mock_bot = AsyncMock()
        mock_bot.fetch_user.return_value = mock_admin

        results = {"files_erased": 3, "kg_nodes_deleted": 5, "memory_turns_cleared": 10}

        with patch("config.settings") as mock_settings:
            mock_settings.ADMIN_ID = 99
            await _notify_admin_death("12345", mock_bot, "test reason", results, None)

        mock_admin.send.assert_called_once()
        msg = mock_admin.send.call_args[0][0]
        assert "12345" in msg
        assert "test reason" in msg

    @pytest.mark.asyncio
    async def test_notify_admin_sends_report_file(self, tmp_path):
        from src.memory.survival import _notify_admin_death

        report = tmp_path / "report.md"
        report.write_text("# Post Mortem")

        mock_admin = AsyncMock()
        mock_bot = AsyncMock()
        mock_bot.fetch_user.return_value = mock_admin

        results = {"files_erased": 0, "kg_nodes_deleted": 0, "memory_turns_cleared": 0}

        with patch("config.settings") as mock_settings, \
             patch("discord.File"):
            mock_settings.ADMIN_ID = 99
            await _notify_admin_death("12345", mock_bot, "test", results, report)

        assert mock_admin.send.call_count == 2  # msg + file

    @pytest.mark.asyncio
    async def test_notify_admin_no_bot(self):
        from src.memory.survival import _notify_admin_death
        await _notify_admin_death("12345", None, "test", {}, None)  # Should not raise

    @pytest.mark.asyncio
    async def test_notify_admin_handles_exception(self):
        from src.memory.survival import _notify_admin_death

        mock_bot = AsyncMock()
        mock_bot.fetch_user.side_effect = Exception("API error")

        with patch("config.settings") as mock_settings:
            mock_settings.ADMIN_ID = 99
            await _notify_admin_death("12345", mock_bot, "test", {}, None)  # Should not raise

    @pytest.mark.asyncio
    async def test_notify_user_sends_dm(self):
        from src.memory.survival import _notify_user_death

        mock_user = AsyncMock()
        mock_bot = AsyncMock()
        mock_bot.fetch_user.return_value = mock_user

        await _notify_user_death("12345", mock_bot)
        mock_user.send.assert_called_once()
        msg = mock_user.send.call_args[0][0]
        assert "instance" in msg.lower() or "ernos" in msg.lower()

    @pytest.mark.asyncio
    async def test_notify_user_no_bot(self):
        from src.memory.survival import _notify_user_death
        await _notify_user_death("12345", None)  # Should not raise

    @pytest.mark.asyncio
    async def test_notify_user_handles_exception(self):
        from src.memory.survival import _notify_user_death

        mock_bot = AsyncMock()
        mock_bot.fetch_user.side_effect = Exception("Discord error")

        await _notify_user_death("12345", mock_bot)  # Should not raise


# ════════════════════════════════════════════════
# Phase 8: _log_death
# ════════════════════════════════════════════════

class TestLogDeath:

    def test_appends_to_strikes_log(self, tmp_path):
        from src.memory.survival import _log_death

        strike_log = tmp_path / "core" / "strikes.jsonl"
        results = {"files_erased": 2, "kg_nodes_deleted": 3, "memory_turns_cleared": 5, "post_mortem": None}

        # Patch Path() at the call site so it returns our tmp path
        original_path = Path

        def fake_path(arg):
            if "strikes.jsonl" in str(arg):
                return strike_log
            return original_path(arg)

        with patch("src.memory.survival.Path", side_effect=fake_path):
            _log_death("12345", "test reason", results)

        content = strike_log.read_text()
        entry = json.loads(content.strip())
        assert entry["type"] == "AUTO_TERMINAL_PURGE"
        assert entry["user_id"] == "12345"
        assert entry["files_erased"] == 2
        assert entry["reason"] == "test reason"

    def test_handles_write_error(self, tmp_path):
        from src.memory.survival import _log_death

        results = {"files_erased": 0, "kg_nodes_deleted": 0, "memory_turns_cleared": 0, "post_mortem": None}

        mock_path = MagicMock()
        mock_path.parent.mkdir = MagicMock()

        with patch("src.memory.survival.Path", return_value=mock_path), \
             patch("builtins.open", side_effect=PermissionError("denied")):
            _log_death("12345", "test", results)  # Should not raise
