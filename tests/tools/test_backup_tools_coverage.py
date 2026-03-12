"""
Tests for Backup Tools
Targeting 95%+ coverage for src/tools/backup_tools.py
"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from src.tools.backup_tools import request_my_backup, verify_backup, restore_my_context


class TestRequestMyBackup:
    """Tests for request_my_backup tool."""
    
    @pytest.mark.asyncio
    async def test_request_my_backup_no_user_id(self):
        """Test error when no user ID provided."""
        result = await request_my_backup()
        assert "Error" in result
        assert "User ID required" in result
    
    @pytest.mark.asyncio
    async def test_request_my_backup_success(self):
        """Test successful backup request."""
        mock_instance = MagicMock()
        mock_instance.export_user_context = AsyncMock(return_value="/path/to/backup.json")
        
        with patch('src.tools.backup_tools.BackupManager', return_value=mock_instance):
            result = await request_my_backup(user_id=123)
            
            assert "exported" in result.lower() or "📦" in result
    
    @pytest.mark.asyncio
    async def test_request_my_backup_rate_limited(self):
        """Test rate limited response."""
        mock_instance = MagicMock()
        mock_instance.export_user_context = AsyncMock(return_value=None)
        
        with patch('src.tools.backup_tools.BackupManager', return_value=mock_instance):
            result = await request_my_backup(user_id=123)
            
            assert "rate limited" in result.lower() or "⏳" in result


class TestVerifyBackup:
    """Tests for verify_backup tool."""
    
    @pytest.mark.asyncio
    async def test_verify_backup_no_data(self):
        """Test error when no backup data provided."""
        result = await verify_backup()
        assert "Error" in result
        assert "required" in result.lower()
    
    @pytest.mark.asyncio
    async def test_verify_backup_invalid_json(self):
        """Test error for invalid JSON."""
        result = await verify_backup(backup_json="not valid json {{{")
        assert "Error" in result
        assert "Invalid" in result
    
    @pytest.mark.asyncio
    async def test_verify_backup_valid(self):
        """Test valid backup verification."""
        backup_data = {
            "user_id": 123,
            "exported_at": "2026-02-06",
            "file_count": 5,
            "context": {"key": "value"}
        }
        
        mock_instance = MagicMock()
        mock_instance.verify_backup.return_value = (True, "Checksum valid")
        
        with patch('src.tools.backup_tools.BackupManager', return_value=mock_instance):
            result = await verify_backup(backup_json=json.dumps(backup_data))
            
            assert "Verified" in result
            assert "123" in result  # User ID
    
    @pytest.mark.asyncio
    async def test_verify_backup_invalid(self):
        """Test invalid backup verification."""
        backup_data = {"corrupted": True}
    
        mock_instance = MagicMock()
        mock_instance.verify_backup.return_value = (False, "Checksum mismatch")
        
        with patch('src.tools.backup_tools.BackupManager', return_value=mock_instance):
            result = await verify_backup(backup_json=json.dumps(backup_data))

            assert "Invalid" in result
            assert "Checksum mismatch" in result


class TestRestoreMyContext:
    """Tests for restore_my_context tool."""
    
    @pytest.mark.asyncio
    async def test_restore_no_user_id(self):
        """Test error when no user ID provided."""
        result = await restore_my_context(backup_json="{}")
        assert "Error" in result
        assert "required" in result.lower()
    
    @pytest.mark.asyncio
    async def test_restore_no_backup_data(self):
        """Test error when no backup data provided."""
        result = await restore_my_context(user_id=123)
        assert "Error" in result
        assert "required" in result.lower()
    
    @pytest.mark.asyncio
    async def test_restore_invalid_json(self):
        """Test error for invalid JSON."""
        result = await restore_my_context(user_id=123, backup_json="not valid json")
        assert "Error" in result
        assert "Invalid" in result
    
    @pytest.mark.asyncio
    async def test_restore_success(self):
        """Test successful restore."""
        backup_data = {"user_id": 123, "context": {}}
        
        with patch('src.tools.backup_tools.BackupManager') as mock_mgr, \
             patch('src.bot.globals') as mock_globals:
            mock_globals.bot = MagicMock()
            
            mock_instance = MagicMock()
            mock_instance.import_user_context = AsyncMock(return_value=(True, "5 files restored"))
            mock_mgr.return_value = mock_instance
            
            result = await restore_my_context(user_id=123, backup_json=json.dumps(backup_data))
            
            assert "restored" in result.lower()
    
    @pytest.mark.asyncio
    async def test_restore_failure(self):
        """Test failed restore."""
        backup_data = {"user_id": 456, "context": {}}  # Wrong user
        
        with patch('src.tools.backup_tools.BackupManager') as mock_mgr, \
             patch('src.bot.globals') as mock_globals:
            mock_globals.bot = MagicMock()
            
            mock_instance = MagicMock()
            mock_instance.import_user_context = AsyncMock(
                return_value=(False, "User ID mismatch")
            )
            mock_mgr.return_value = mock_instance
            
            result = await restore_my_context(user_id=123, backup_json=json.dumps(backup_data))
            
            # Should return the failure message
            # The tool might return "Error: access denied" or "mismatch"
            assert "mismatch" in result.lower() or "access denied" in result.lower()
