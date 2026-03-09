import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from src.bot.cogs.support import SupportCog
from config import settings

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.user.id = 12345
    return bot

@pytest.fixture
def support_cog(mock_bot):
    with patch('config.settings.SUPPORT_CHANNEL_ID', 999):
        cog = SupportCog(mock_bot)
        cog.support_channel_id = 999
        return cog

@pytest.mark.asyncio
async def test_tool_manifest_injection(support_cog):
    """Test that the system prompt includes the tool manifest."""
    message = AsyncMock(spec=discord.Message)
    message.author.bot = False
    message.content = "I need a human!"
    message.guild = MagicMock()
    message.channel.id = 999  # Matches SUPPORT_CHANNEL_ID
    
    # Mock create_thread
    thread = AsyncMock(spec=discord.Thread)
    thread.name = "Support - User"
    thread.id = 888
    message.create_thread.return_value = thread
    
    # Mock engine to capture system_context
    class MockEngine:
        def __init__(self):
            self.call_args = None
        async def process(self, *args, **kwargs):
            self.call_args = kwargs
            return ("AI Response", [])
            
    engine = MockEngine()
    support_cog.bot.cognition = engine
    support_cog.bot.hippocampus = None
    
    # Mock PromptManager to return a specific tool manifest
    # We patch the instance created in __init__
    support_cog.prompt_manager._generate_tool_manifest = MagicMock(return_value="[TOOL: escalate_ticket(reason, priority)]")
    
    # Mock file reading
    with patch("pathlib.Path.read_text", return_value="Mock Content"), \
         patch("pathlib.Path.exists", return_value=True):
        # Execute
        await support_cog.on_message(message)
    
    # Verification
    assert engine.call_args is not None
    system_context = engine.call_args['system_context']
    
    # Check if the tool manifest is present
    assert "[TOOL: escalate_ticket(reason, priority)]" in system_context
    assert "=== OFFICIAL USER MANUAL & COMMANDS ===" in system_context
    assert "=== SUPPORT MODE ACTIVATED ===" in system_context
