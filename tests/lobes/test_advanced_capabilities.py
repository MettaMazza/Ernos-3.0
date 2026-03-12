import pytest
import json
import time
from unittest.mock import patch, mock_open, MagicMock
from src.lobes.creative.artist import VisualCortexAbility
from src.lobes.interaction.science import ScienceAbility

@pytest.mark.asyncio
async def test_science_execution():
    science = ScienceAbility(None)
    
    # Safe
    res = await science.execute("1 + 1")
    assert "2" in res
    
    # Unsafe (must use computational prefix to pass fast path)
    res = await science.execute("eval: import os; os.system('ls')")
    assert "not permitted" in res or "Math syntax error" in res or "Science Error" in res

@pytest.mark.asyncio
async def test_visual_cortex_generation():
    artist = VisualCortexAbility(None)
    
    # Mock ScopeManager to return a MagicMock path
    mock_home = MagicMock()
    mock_usage_file = MagicMock()
    mock_home.__truediv__.return_value = mock_usage_file
    mock_usage_file.exists.return_value = False
    
    with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=mock_home) as mock_get_scope:
        # Mock Generator
        with patch("src.lobes.creative.artist.get_generator") as mock_get_gen:
            mock_gen = mock_get_gen.return_value
            mock_gen.generate_image = MagicMock(return_value="/tmp/test.png")
            
            # Execute with User ID
            res = await artist.execute("Cybernetic cat", media_type="image", user_id=101)
            assert "generated_image_" in res
            
            # Verify Scope Resolution
            mock_get_scope.assert_called_with(101)
            
            # Verify Persistence on the scoped file
            mock_usage_file.write_text.assert_called()
            args, _ = mock_usage_file.write_text.call_args
            saved_data = json.loads(args[0])
            assert saved_data["image_count"] == 1

@pytest.mark.asyncio
async def test_rate_limit_enforcement():
    artist = VisualCortexAbility(None)
    
    # Setup mocks
    mock_home = MagicMock()
    mock_usage_file = MagicMock()
    mock_home.__truediv__.return_value = mock_usage_file
    
    # Limit reached state
    limit_data = json.dumps({"image_count": 4, "video_count": 0, "last_reset": time.time()})
    mock_usage_file.exists.return_value = True
    mock_usage_file.read_text.return_value = limit_data
    
    with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=mock_home):
        res = await artist.execute("Cat", media_type="image", user_id=999)
        assert "Daily limit reached" in res

@pytest.mark.asyncio
async def test_scope_isolation():
    """Verify that User A usage does not affect User B limit"""
    artist = VisualCortexAbility(None)
    
    # Mock ScopeManager to return different paths for different users
    user_a_file = MagicMock()
    user_b_file = MagicMock()
    
    user_a_file.exists.return_value = True
    user_a_file.read_text.return_value = json.dumps({"image_count": 4, "last_reset": time.time()}) # At limit
    
    user_b_file.exists.return_value = False # Fresh
    
    def get_home_side_effect(uid):
        m = MagicMock()
        target = user_a_file if uid == "A" else user_b_file
        m.__truediv__.return_value = target
        return m

    with patch("src.privacy.scopes.ScopeManager.get_user_home", side_effect=get_home_side_effect):
        # User A should be blocked
        res_a = await artist.execute("Prompt", user_id="A")
        assert "Daily limit reached" in res_a
        
        # User B should proceed (assuming generator works)
        with patch("src.lobes.creative.artist.get_generator"):
            res_b = await artist.execute("Prompt", user_id="B")
            assert "generated_image_" in res_b
            # Verify User B file was written (incremented)
            user_b_file.write_text.assert_called()

@pytest.mark.asyncio
async def test_turn_lock():
    artist = VisualCortexAbility(None)
    artist.turn_lock = True
    res = await artist.execute("Cat", user_id=123)
    assert "generation per turn allowed" in res
