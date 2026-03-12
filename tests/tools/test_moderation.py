"""Tests for moderation tools - timeout_user and check_moderation_status."""
import pytest
import json
import importlib
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestModerationTools:
    """Test timeout_user and check_moderation_status.
    
    The conftest autouse fixture mocks check_moderation_status globally.
    We must reload the module with our own patches to test the REAL functions.
    """
    
    @pytest.fixture(autouse=True)
    def reload_moderation(self):
        """Reload the moderation module to get un-mocked functions.
        After the test, reload again to restore conftest mocking."""
        import src.tools.moderation as mod
        importlib.reload(mod)
        yield mod
        importlib.reload(mod)
    
    @pytest.mark.asyncio
    async def test_timeout_user_first_strike(self, reload_moderation, tmp_path):
        """Test that timeout_user records first strike and returns 12h timeout."""
        mod = reload_moderation
        mock_file = tmp_path / "moderation.json"
        
        with patch.object(mod, "MODERATION_FILE", mock_file):
            result = await mod.timeout_user(123, "Rude behavior")
        
        assert "timed out for 12 hours" in result
        assert "Strike 1/3" in result
        assert mock_file.exists()
        
        data = json.loads(mock_file.read_text())
        assert "123" in data["users"]
        assert data["users"]["123"]["strikes"] == 1
        assert data["users"]["123"]["muted"] is False
    
    @pytest.mark.asyncio
    async def test_timeout_user_3_strikes(self, reload_moderation, tmp_path):
        """Test that 3rd strike results in permanent mute."""
        mod = reload_moderation
        mock_file = tmp_path / "moderation.json"
        
        # Pre-seed with 2 strikes
        data = {
            "users": {
                "456": {"strikes": 2, "timeout_until": None, "muted": False}
            }
        }
        mock_file.write_text(json.dumps(data))
        
        with patch.object(mod, "MODERATION_FILE", mock_file):
            result = await mod.timeout_user(456, "Strike 3")
        
        assert "PERMANENTLY MUTED" in result
        
        data = json.loads(mock_file.read_text())
        assert data["users"]["456"]["muted"] is True
        assert data["users"]["456"]["strikes"] == 3
    
    def test_check_moderation_status_allowed(self, reload_moderation, tmp_path):
        """Test allowing a user with no record."""
        mod = reload_moderation
        mock_file = tmp_path / "moderation.json"
        
        with patch.object(mod, "MODERATION_FILE", mock_file):
            status = mod.check_moderation_status(999)
        
        assert status["allowed"] is True
    
    def test_check_moderation_status_timeout_active(self, reload_moderation, tmp_path):
        """Test blocking a user with active timeout."""
        mod = reload_moderation
        mock_file = tmp_path / "moderation.json"
        
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        data = {
            "users": {
                "777": {"strikes": 1, "timeout_until": future, "muted": False}
            }
        }
        mock_file.write_text(json.dumps(data))
        
        with patch.object(mod, "MODERATION_FILE", mock_file):
            status = mod.check_moderation_status(777)
        
        assert status["allowed"] is False
        assert "Timeout active" in status["reason"]
    
    def test_check_moderation_status_timeout_expired(self, reload_moderation, tmp_path):
        """Test allowing a user with expired timeout."""
        mod = reload_moderation
        mock_file = tmp_path / "moderation.json"
        
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        data = {
            "users": {
                "888": {"strikes": 1, "timeout_until": past, "muted": False}
            }
        }
        mock_file.write_text(json.dumps(data))
        
        with patch.object(mod, "MODERATION_FILE", mock_file):
            status = mod.check_moderation_status(888)
        
        assert status["allowed"] is True
    
    def test_check_moderation_status_muted(self, reload_moderation, tmp_path):
        """Test blocking a permanently muted user."""
        mod = reload_moderation
        mock_file = tmp_path / "moderation.json"
        
        data = {
            "users": {
                "666": {"strikes": 3, "timeout_until": "PERMANENT", "muted": True}
            }
        }
        mock_file.write_text(json.dumps(data))
        
        with patch.object(mod, "MODERATION_FILE", mock_file):
            status = mod.check_moderation_status(666)
        
        assert status["allowed"] is False
        assert "Permanent Mute" in status["reason"]
