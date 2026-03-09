import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from src.main import main

@pytest.mark.asyncio
async def test_main_missing_token(mocker):
    mocker.patch("src.main.settings.DISCORD_TOKEN", "")
    mock_exit = mocker.patch("sys.exit")
    
    await main()
    mock_exit.assert_called_with(1)

@pytest.mark.asyncio
async def test_main_success(mocker):
    mocker.patch("src.main.settings.DISCORD_TOKEN", "valid_token")
    mock_bot_cls = mocker.patch("src.main.ErnosBot")
    mock_bot_instance = mock_bot_cls.return_value
    mock_bot_instance.start = AsyncMock()
    mock_bot_instance.close = AsyncMock()
    
    await main()
    
    mock_bot_instance.start.assert_called_with("valid_token")
    mock_bot_instance.close.assert_called()

@pytest.mark.asyncio
async def test_main_keyboard_interrupt(mocker):
    mocker.patch("src.main.settings.DISCORD_TOKEN", "valid_token")
    mock_bot_cls = mocker.patch("src.main.ErnosBot")
    mock_bot = mock_bot_cls.return_value
    mock_bot.start = AsyncMock(side_effect=KeyboardInterrupt)
    mock_bot.close = AsyncMock()
    
    # Check log call?
    mock_logger = mocker.patch("src.main.logger")
    
    await main()
    mock_logger.info.assert_any_call("Bot stopped by user.")
    mock_bot.close.assert_called()

@pytest.mark.asyncio
async def test_main_crash(mocker):
    mocker.patch("src.main.settings.DISCORD_TOKEN", "valid_token")
    mock_bot_cls = mocker.patch("src.main.ErnosBot")
    mock_bot = mock_bot_cls.return_value
    mock_bot.start = AsyncMock(side_effect=Exception("Boom"))
    mock_bot.close = AsyncMock()
    
    mock_logger = mocker.patch("src.main.logger")
    
    await main()
    # Check critical log
    # Argument call check
    args, _ = mock_logger.critical.call_args
    assert "Bot crash: Boom" in args[0]
    mock_bot.close.assert_called()
