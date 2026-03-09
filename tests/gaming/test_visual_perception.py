"""
Tests for visual perception in gaming.
Ensures screenshot capture and vision integration work correctly.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import base64


@pytest.fixture
def mock_bridge():
    """Create a mock MineflayerBridge."""
    bridge = MagicMock()
    bridge.get_screenshot = AsyncMock()
    bridge.execute = AsyncMock()
    bridge.get_status = AsyncMock()
    return bridge


@pytest.mark.asyncio
async def test_get_screenshot_returns_base64():
    """Verify get_screenshot returns base64 image data."""
    from src.gaming.mineflayer_bridge import MineflayerBridge, BridgeResponse
    
    bridge = MineflayerBridge()
    
    # Mock execute to return screenshot data
    mock_data = {
        "success": True,
        "image": "aGVsbG8gd29ybGQ=",  # base64 for "hello world"
        "format": "jpeg"
    }
    bridge.execute = AsyncMock(return_value=BridgeResponse(True, mock_data))
    
    result = await bridge.get_screenshot()
    
    assert result == "aGVsbG8gd29ybGQ="
    bridge.execute.assert_called_once_with("get_screenshot", timeout=10)


@pytest.mark.asyncio
async def test_get_screenshot_handles_failure():
    """Verify get_screenshot returns None on failure."""
    from src.gaming.mineflayer_bridge import MineflayerBridge, BridgeResponse
    
    bridge = MineflayerBridge()
    bridge.execute = AsyncMock(return_value=BridgeResponse(False, error="Viewer not ready"))
    
    result = await bridge.get_screenshot()
    
    assert result is None


@pytest.mark.asyncio
async def test_observe_includes_screenshot(mock_bridge):
    """Verify _observe captures screenshot in game state."""
    from src.gaming.agent import GamingAgent
    
    # Mock bot
    mock_bot = MagicMock()
    
    agent = GamingAgent(mock_bot)
    agent.bridge = mock_bridge
    
    # Setup mock returns
    mock_bridge.get_status.return_value = MagicMock(
        success=True,
        data={"health": 20, "food": 20, "position": {"x": 0, "y": 64, "z": 0}, "inventory": []}
    )
    mock_bridge.execute.return_value = MagicMock(
        success=True,
        data={"entities": [], "hostiles_nearby": False, "isDay": True}
    )
    mock_bridge.get_screenshot.return_value = "test_screenshot_base64"
    
    state = await agent._observe()
    
    assert "screenshot" in state
    assert state["screenshot"] == "test_screenshot_base64"


@pytest.mark.asyncio
async def test_think_passes_images_to_cognition():
    """Verify _think passes screenshot to CognitionEngine."""
    from src.gaming.agent import GamingAgent
    
    mock_bot = MagicMock()
    mock_cognition = MagicMock()
    mock_cognition.process = AsyncMock(return_value="I'll explore. ACTION: explore")
    mock_bot.cognition = mock_cognition  # Unified cognition on bot
    
    agent = GamingAgent(mock_bot)
    
    state = {
        "health": 20,
        "food": 20,
        "position": {"x": 0, "y": 64, "z": 0},
        "nearby_entities": [],
        "hostiles_nearby": False,
        "is_day": True,
        "inventory": [],
        "pending_chats": [],
        "screenshot": "base64_image_data"
    }
    
    action = await agent._think(state)
    
    # Verify images were passed - now as list of base64 strings
    call_kwargs = mock_cognition.process.call_args.kwargs
    assert "images" in call_kwargs
    assert call_kwargs["images"] is not None
    assert len(call_kwargs["images"]) == 1
    assert call_kwargs["images"][0] == "base64_image_data"  # Just the string, not a dict


@pytest.mark.asyncio
async def test_think_works_without_screenshot():
    """Verify _think works when no screenshot is available."""
    from src.gaming.agent import GamingAgent
    
    mock_bot = MagicMock()
    mock_cognition = MagicMock()
    mock_cognition.process = AsyncMock(return_value="ACTION: wander")
    mock_bot.cognition = mock_cognition  # Unified cognition on bot
    
    agent = GamingAgent(mock_bot)
    
    state = {
        "health": 20,
        "food": 20,
        "position": {"x": 0, "y": 64, "z": 0},
        "nearby_entities": [],
        "hostiles_nearby": False,
        "is_day": True,
        "inventory": [],
        "pending_chats": [],
        "screenshot": None  # No screenshot
    }
    
    action = await agent._think(state)
    
    call_kwargs = mock_cognition.process.call_args.kwargs
    # images should be None when no screenshot
    assert call_kwargs.get("images") is None
