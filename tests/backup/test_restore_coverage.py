"""Tests for BackupRestorer — 10 tests."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.backup.restore import BackupRestorer


@pytest.fixture
def restorer():
    bot = MagicMock()
    bot.hippocampus = MagicMock()
    bot.hippocampus.working = MagicMock()
    bot.hippocampus.embedder = MagicMock()
    bot.hippocampus.vector_store = MagicMock()
    bot.hippocampus.graph = MagicMock()
    return BackupRestorer(bot=bot)


def _valid_data(user_id=123, context=None, public_timeline=None, traces=None, kg=None):
    return {
        "user_id": user_id,
        "format_version": "1.0",
        "exported_at": "2025-01-01T00:00:00",
        "context": context or {},
        "traces": traces or {},
        "public_timeline": public_timeline or {},
        "knowledge_graph": kg or [],
        "checksum": "valid",
        "file_count": 0,
        "kg_node_count": 0
    }


class TestImportUserContext:

    @pytest.mark.asyncio
    async def test_invalid_backup(self, restorer):
        restorer._verifier.verify_backup = MagicMock(return_value=(False, "bad checksum"))
        ok, msg = await restorer.import_user_context(123, {"bad": True})
        assert ok is False
        assert "failed" in msg.lower()

    @pytest.mark.asyncio
    async def test_user_id_mismatch(self, restorer):
        restorer._verifier.verify_backup = MagicMock(return_value=(True, "OK"))
        data = _valid_data(user_id=999)
        ok, msg = await restorer.import_user_context(123, data)
        assert ok is False
        assert "different user" in msg

    @pytest.mark.asyncio
    async def test_restores_context_files(self, restorer, tmp_path):
        restorer._verifier.verify_backup = MagicMock(return_value=(True, "OK"))
        data = _valid_data(context={"notes.txt": "hello world"})
        user_home = tmp_path / "user_123"
        user_home.mkdir()
        with patch("src.backup.restore.ScopeManager") as sm:
            sm.get_user_home.return_value = user_home
            ok, msg = await restorer.import_user_context(123, data)
            assert ok is True
            assert (user_home / "notes.txt").read_text() == "hello world"

    @pytest.mark.asyncio
    async def test_skips_read_errors(self, restorer, tmp_path):
        restorer._verifier.verify_backup = MagicMock(return_value=(True, "OK"))
        data = _valid_data(context={"bad.txt": "[Read Error: fail]", "good.txt": "ok"})
        user_home = tmp_path / "user_123"
        user_home.mkdir()
        with patch("src.backup.restore.ScopeManager") as sm:
            sm.get_user_home.return_value = user_home
            ok, msg = await restorer.import_user_context(123, data)
            assert ok is True
            assert not (user_home / "bad.txt").exists()
            assert (user_home / "good.txt").exists()

    @pytest.mark.asyncio
    async def test_restores_public_timeline(self, restorer, tmp_path):
        restorer._verifier.verify_backup = MagicMock(return_value=(True, "OK"))
        data = _valid_data(public_timeline={"timeline.txt": "events"})
        user_home = tmp_path / "user_123"
        user_home.mkdir()
        public_silo = tmp_path / "public" / "users" / "123"
        with patch("src.backup.restore.ScopeManager") as sm:
            sm.get_user_home.return_value = user_home
            with patch("src.backup.restore.Path") as mock_path:
                # Let user_silo return our tmp_path
                mock_path.return_value = public_silo
                ok, msg = await restorer.import_user_context(123, data)
                assert ok is True

    @pytest.mark.asyncio
    async def test_consolidates_traces(self, restorer, tmp_path):
        restorer._verifier.verify_backup = MagicMock(return_value=(True, "OK"))
        data = _valid_data(
            context={"reasoning_log.txt": "trace data"},
            traces={"trace_123.txt": "extra trace"}
        )
        user_home = tmp_path / "user_123"
        user_home.mkdir()
        with patch("src.backup.restore.ScopeManager") as sm:
            sm.get_user_home.return_value = user_home
            ok, msg = await restorer.import_user_context(123, data)
            assert ok is True
            assert "restored" in msg.lower()

    @pytest.mark.asyncio
    async def test_restores_turns(self, restorer, tmp_path):
        restorer._verifier.verify_backup = MagicMock(return_value=(True, "OK"))
        turn_line = json.dumps({"user": "hi", "bot": "hello", "scope": "PRIVATE"})
        data = _valid_data(context={"context_private.jsonl": turn_line})
        user_home = tmp_path / "user_123"
        user_home.mkdir()
        with patch("src.backup.restore.ScopeManager") as sm:
            sm.get_user_home.return_value = user_home
            ok, msg = await restorer.import_user_context(123, data)
            assert ok is True
            restorer.bot.hippocampus.working.add_turn.assert_called()

    @pytest.mark.asyncio
    async def test_no_bot_partial(self, tmp_path):
        restorer = BackupRestorer(bot=None)
        restorer._verifier.verify_backup = MagicMock(return_value=(True, "OK"))
        data = _valid_data(context={"test.txt": "hello"})
        user_home = tmp_path / "user_123"
        user_home.mkdir()
        with patch("src.backup.restore.ScopeManager") as sm:
            sm.get_user_home.return_value = user_home
            ok, msg = await restorer.import_user_context(123, data)
            assert ok is True

    @pytest.mark.asyncio
    async def test_reembed_vectors(self, restorer, tmp_path):
        restorer._verifier.verify_backup = MagicMock(return_value=(True, "OK"))
        data = _valid_data(context={"notes.txt": "This is a long enough document to embed into vector store for testing."})
        user_home = tmp_path / "user_123"
        user_home.mkdir()
        restorer.bot.hippocampus.embedder.get_embedding.return_value = [0.1, 0.2]
        with patch("src.backup.restore.ScopeManager") as sm:
            sm.get_user_home.return_value = user_home
            ok, msg = await restorer.import_user_context(123, data)
            assert ok is True
            restorer.bot.hippocampus.vector_store.add_element.assert_called()

    @pytest.mark.asyncio
    async def test_kg_restore(self, restorer, tmp_path):
        restorer._verifier.verify_backup = MagicMock(return_value=(True, "OK"))
        kg_nodes = [{"name": "Maria", "labels": ["Person"], "properties": {"layer": "narrative"}}]
        data = _valid_data(kg=kg_nodes)
        user_home = tmp_path / "user_123"
        user_home.mkdir()
        with patch("src.backup.restore.ScopeManager") as sm:
            sm.get_user_home.return_value = user_home
            with patch("src.backup.restore.KnowledgeGraph", create=True) as mock_kg_cls:
                mock_kg = MagicMock()
                mock_kg_cls.return_value = mock_kg
                with patch("src.backup.restore.GraphLayer", create=True) as mock_gl:
                    mock_gl.NARRATIVE = "narrative"
                    mock_gl.return_value = "narrative"
                    ok, msg = await restorer.import_user_context(123, data)
                    assert ok is True
