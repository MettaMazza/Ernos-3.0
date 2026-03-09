
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.lobes.creative.artist import VisualCortexAbility
import json
import time

@pytest.fixture
def mock_lobe():
    return MagicMock()

@pytest.fixture
def artist(mock_lobe):
    return VisualCortexAbility(mock_lobe)

@pytest.mark.asyncio
async def test_artist_limits_and_reset(artist, tmp_path):
    # Test _check_limits with corrupt file (Exception coverage)
    # Patch _get_usage_file to return a path in tmp_path
    
    user_home = tmp_path / "user_123"
    user_home.mkdir()
    usage_file = user_home / "usage.json"
    
    # Write bad JSON
    usage_file.write_text("{bad_json")
    
    with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=user_home):
        # Should catch exception and reset/continue
        allowed = artist._check_limits("image", 123)
        assert allowed is True
        # Verify file validated
        assert json.loads(usage_file.read_text())["image_count"] == 1
        
        # Test Limit Reached
        # Write limit
        data = {"image_count": 50, "video_count": 0, "last_reset": time.time()} # Assuming limit is 5 or 10
        usage_file.write_text(json.dumps(data))
        
        # Mock settings
        with patch("config.settings.DAILY_IMAGE_LIMIT", 5):
            allowed = artist._check_limits("image", 123)
            assert allowed is False

@pytest.mark.asyncio
async def test_artist_user_fallback(artist):
    # Test user_id is None fallback — autonomy flag should bypass _check_limits
    with patch("config.settings.ADMIN_ID", 999):
        # We mock _check_limits to verify it is NOT called for autonomy
        artist._check_limits = MagicMock(return_value=True)
        
        # We mock generation to avoid threading
        with patch("src.lobes.creative.artist.MediaGenerator") as mock_gen:
             # We need to mock asyncio.to_thread
             with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
                 await artist.execute("Prompt", user_id=None)
                 
                 # When user_id is None, is_autonomy=True — _check_limits should NOT be called
                 artist._check_limits.assert_not_called()

@pytest.mark.asyncio
async def test_artist_generation_exception(artist):
    # Test exception block
    artist._check_limits = MagicMock(return_value=True)
    
    # Mock generation failure
    # Mock generation failure
    # Patch get_generator to raise exception immediately
    with patch("src.lobes.creative.artist.get_generator", side_effect=Exception("Gen Fail")):
        result = await artist.execute("Prompt", user_id=123)
        assert "Generation Error" in result
        
def test_artist_reset_lock(artist):
    artist.turn_lock = True
    artist.reset_turn_lock()
    assert artist.turn_lock is False
