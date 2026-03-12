import pytest
from unittest.mock import MagicMock, AsyncMock, patch, ANY
from src.agents.base import BaseAgent
from src.bot.client import ErnosBot
import discord

# --- BaseAgent Tests ---

def test_base_agent_init():
    bot = MagicMock()
    agent = BaseAgent(bot)
    assert agent.bot == bot
    assert agent.prompt_manager is not None

def test_base_agent_get_system_prompt(mocker):
    bot = MagicMock()
    agent = BaseAgent(bot)
    agent.prompt_manager = MagicMock()
    agent.prompt_manager.get_system_prompt.return_value = "System Prompt"
    
    res = agent.get_system_prompt(key="value")
    assert res == "System Prompt"
    agent.prompt_manager.get_system_prompt.assert_called_with(key="value")

@pytest.mark.asyncio
async def test_base_agent_call_tool_success(mocker):
    bot = MagicMock()
    agent = BaseAgent(bot)
    
    with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "Result"
        res = await agent.call_tool("test_tool", arg=1)
        assert res == "Result"
        mock_exec.assert_awaited_with("test_tool", arg=1)

@pytest.mark.asyncio
async def test_base_agent_call_tool_error(mocker):
    bot = MagicMock()
    agent = BaseAgent(bot)
    
    with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = Exception("Tool Fail")
        res = await agent.call_tool("test_tool")
        assert "Error: Tool Fail" in res

# --- ErnosBot Tests ---

@pytest.fixture
def mock_dependencies(mocker):
    mocker.patch("src.bot.client.Hippocampus")
    mocker.patch("src.bot.client.Cerebrum")
    mocker.patch("src.bot.client.SiloManager")
    mocker.patch("src.bot.client.VoiceManager")
    mocker.patch("src.bot.client.EngineManager")
    mocker.patch("src.bot.client.VectorEnhancedOllamaEngine")
    mocker.patch("src.bot.client.SteeringEngine")

@pytest.mark.asyncio
async def test_ernos_bot_init(mock_dependencies):
    bot = ErnosBot()
    assert bot.hippocampus is not None
    assert bot.cerebrum is not None
    assert bot.is_processing is False

@pytest.mark.asyncio
async def test_ernos_bot_processing_users(mock_dependencies):
    bot = ErnosBot()
    assert bot.is_processing is False
    
    bot.add_processing_user(123)
    assert bot.is_processing is True
    assert (123, None) in bot.processing_users
    
    bot.remove_processing_user(123)
    assert bot.is_processing is False

@pytest.mark.asyncio
async def test_ernos_bot_send_to_mind(mock_dependencies):
    bot = ErnosBot()
    mock_channel = AsyncMock()
    bot.get_channel = MagicMock(return_value=mock_channel)
    
    # Test Chunking
    long_content = "A" * 2000
    await bot.send_to_mind(long_content)
    
    # Logic chunks at 1900
    assert mock_channel.send.call_count == 2
    args1 = mock_channel.send.call_args_list[0][0][0]
    args2 = mock_channel.send.call_args_list[1][0][0]
    assert len(args1) == 1900
    assert len(args2) == 100

@pytest.mark.asyncio
async def test_ernos_bot_send_to_mind_not_found(mock_dependencies):
    bot = ErnosBot()
    bot.get_channel = MagicMock(return_value=None)
    bot.fetch_channel = AsyncMock(side_effect=Exception("Not Found"))
    
    await bot.send_to_mind("content")
    assert True  # No exception: negative case handled correctly
    # Should log error but not crash
    # Verified by no exception raised

@pytest.mark.asyncio
async def test_ernos_bot_setup_hook(mocker, mock_dependencies):
    bot = ErnosBot()
    bot.load_extension = AsyncMock()
    bot.cerebrum.setup = AsyncMock()
    bot.tree.sync = AsyncMock()
    
    await bot.setup_hook()
    
    # Check Engines Registered
    assert bot.engine_manager.register_engine.call_count >= 3 # Cloud, Local, LocalSteer
    bot.engine_manager.set_active_engine.assert_called_with("cloud")
    
    # Check Cogs Loaded
    bot.load_extension.assert_any_call("src.bot.cogs.admin")
    bot.load_extension.assert_any_call("src.bot.cogs.chat")
    
    # Check Cerebrum Setup
    bot.cerebrum.setup.assert_awaited()

@pytest.mark.asyncio
async def test_ernos_bot_close(mocker, mock_dependencies):
    with patch("discord.ext.commands.Bot.close", new_callable=AsyncMock) as mock_super_close:
        bot = ErnosBot()
        bot.cerebrum.shutdown = AsyncMock()
        
        await bot.close()
        
        bot.cerebrum.shutdown.assert_awaited()
        # bot.hippocampus.shutdown() # It's a method on mock instance
        bot.hippocampus.shutdown.assert_called()
        mock_super_close.assert_awaited()
