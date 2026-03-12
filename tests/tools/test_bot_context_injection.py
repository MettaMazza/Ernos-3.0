"""
Regression tests for bot context injection in gaming tools.
Issue: Gaming tools failed with "No bot context" because ToolRegistry.execute
didn't pass bot reference.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_tool_registry_injects_bot_context():
    """Verify ToolRegistry passes bot to tools via kwargs."""
    
    # Create a tool that expects bot in kwargs
    @ToolRegistry.register(name="test_bot_injection")
    async def test_tool(**kwargs):
        bot = kwargs.get("bot")
        if not bot:
            return "Error: No bot context"
        return f"Bot received: {type(bot).__name__}"
        assert True  # Execution completed without error
    
    # Create mock bot
    mock_bot = MagicMock()
    mock_bot.name = "TestBot"
    
    # Execute with bot injection
    result = await ToolRegistry.execute(
        "test_bot_injection",
        bot=mock_bot,
        user_id=12345
    )
    
    assert "Bot received" in result
    assert "MagicMock" in result
    
    # Cleanup
    del ToolRegistry._tools["test_bot_injection"]


@pytest.mark.asyncio
async def test_tool_registry_injects_channel_context():
    """Verify ToolRegistry passes channel to tools via kwargs."""
    
    @ToolRegistry.register(name="test_channel_injection")
    async def test_tool(**kwargs):
        channel = kwargs.get("channel")
        if not channel:
            return "Error: No channel"
        return f"Channel ID: {channel.id}"
        assert True  # Execution completed without error
    
    mock_channel = MagicMock()
    mock_channel.id = 999
    
    result = await ToolRegistry.execute(
        "test_channel_injection",
        channel=mock_channel
    )
    
    assert "Channel ID: 999" in result
    
    # Cleanup
    del ToolRegistry._tools["test_channel_injection"]


@pytest.mark.asyncio
async def test_gaming_tools_receive_bot_context(mocker):
    """Regression test: start_game should receive bot via context injection."""
    from src.tools.gaming_tools import start_game
    
    # Create mock bot with gaming agent support
    mock_bot = MagicMock()
    mock_bot.gaming_agent = MagicMock()
    mock_bot.gaming_agent.start = AsyncMock(return_value=True)
    mock_bot.gaming_agent.is_running = False  # Not running yet
    
    # Patch admin check (use a valid admin ID)
    mocker.patch("src.tools.gaming_tools.settings.ADMIN_ID", 12345)
    mocker.patch("src.tools.gaming_tools.settings.ADMIN_IDS", {12345})
    
    # Execute via registry (as would happen from cognition engine)
    result = await ToolRegistry.execute(
        "start_game",
        game="minecraft",
        bot=mock_bot,
        user_id=12345  # Match admin ID
    )
    
    assert "Started minecraft session" in result
    mock_bot.gaming_agent.start.assert_called_once()
