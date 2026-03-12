"""Tests for BackupExporter — 12 tests."""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from src.backup.export import BackupExporter


@pytest.fixture
def exporter(tmp_path):
    with patch.object(BackupExporter, "BACKUP_DIR", tmp_path / "backups"), \
         patch.object(BackupExporter, "EXPORT_DIR", tmp_path / "exports"), \
         patch.object(BackupExporter, "RATE_LIMIT_FILE", tmp_path / "rate.json"):
        ex = BackupExporter(bot=MagicMock())
        return ex


class TestRateLimits:

    def test_load_empty(self, exporter):
        assert exporter._last_export == {}

    def test_load_existing(self, tmp_path):
        rf = tmp_path / "rate.json"
        now = datetime.now()
        rf.write_text(json.dumps({"123": now.isoformat()}))
        with patch.object(BackupExporter, "BACKUP_DIR", tmp_path), \
             patch.object(BackupExporter, "EXPORT_DIR", tmp_path / "ex"), \
             patch.object(BackupExporter, "RATE_LIMIT_FILE", rf):
            ex = BackupExporter()
            assert 123 in ex._last_export

    def test_save(self, exporter):
        exporter._last_export[42] = datetime.now()
        exporter._save_rate_limits()
        assert exporter.RATE_LIMIT_FILE.exists()


class TestExportUserContext:

    @pytest.mark.asyncio
    async def test_rate_limited(self, exporter):
        exporter._last_export[123] = datetime.now()
        result = await exporter.export_user_context(123, force=False)
        assert result is None

    @pytest.mark.asyncio
    async def test_force_bypass(self, exporter, tmp_path):
        exporter._last_export[123] = datetime.now()
        user_silo = tmp_path / "user_silo"
        user_silo.mkdir()
        (user_silo / "context.txt").write_text("test data")
        with patch("src.backup.export.ScopeManager") as sm:
            sm.get_user_home.return_value = user_silo
            result = await exporter.export_user_context(123, force=True)
            assert result is not None
            assert result.exists()

    @pytest.mark.asyncio
    async def test_empty_silo(self, exporter, tmp_path):
        user_silo = tmp_path / "empty_silo"
        user_silo.mkdir()
        with patch("src.backup.export.ScopeManager") as sm:
            sm.get_user_home.return_value = user_silo
            result = await exporter.export_user_context(123, force=True)
            assert result is None


class TestSendUserBackupDM:

    @pytest.mark.asyncio
    async def test_no_bot(self):
        with patch.object(BackupExporter, "RATE_LIMIT_FILE", Path("/tmp/nofile.json")):
            ex = BackupExporter(bot=None)
            result = await ex.send_user_backup_dm(123)
            assert result is False

    @pytest.mark.asyncio
    async def test_no_export(self, exporter):
        with patch.object(exporter, "export_user_context", new_callable=AsyncMock, return_value=None):
            result = await exporter.send_user_backup_dm(123)
            assert result is False

    @pytest.mark.asyncio
    async def test_success(self, exporter, tmp_path):
        export_file = tmp_path / "export.json"
        export_file.write_text("{}")
        with patch.object(exporter, "export_user_context", new_callable=AsyncMock, return_value=export_file):
            user = MagicMock()
            dm = MagicMock()
            dm.send = AsyncMock()
            user.create_dm = AsyncMock(return_value=dm)
            exporter.bot.fetch_user = AsyncMock(return_value=user)
            result = await exporter.send_user_backup_dm(123)
            assert result is True
            dm.send.assert_called_once()


class TestExportAllUsersOnReset:

    @pytest.mark.asyncio
    async def test_no_users_dir(self, exporter, tmp_path):
        with patch("src.backup.export.data_dir", return_value=tmp_path / "nonexistent"):
            result = await exporter.export_all_users_on_reset()
            assert result == 0

    @pytest.mark.asyncio
    async def test_with_users(self, exporter, tmp_path):
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        (users_dir / "123").mkdir()
        with patch("src.backup.export.data_dir", return_value=tmp_path):
            with patch.object(exporter, "send_user_backup_dm", new_callable=AsyncMock, return_value=True):
                result = await exporter.export_all_users_on_reset()
                assert result == 1


class TestExportMasterBackup:

    @pytest.mark.asyncio
    async def test_creates_file(self, exporter, tmp_path):
        result = await exporter.export_master_backup()
        assert result is not None
        assert result.exists()
        data = json.loads(result.read_text())
        assert data["type"] == "master_backup"
