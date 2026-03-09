import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from src.bot.cogs.support import SupportCog
from config import settings

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 12345
    # SupportCog checks bot.cognition directly now
    bot.cognition = MagicMock() 
    return bot

@pytest.fixture
def support_cog(mock_bot):
    with patch('config.settings.SUPPORT_CHANNEL_ID', 999):
        cog = SupportCog(mock_bot)
        cog.support_channel_id = 999
        return cog

@pytest.mark.asyncio
async def test_new_ticket_creation(support_cog):
    """Test that a message in the support channel creates a thread."""
    message = AsyncMock(spec=discord.Message)
    message.author.bot = False
    message.content = "Help me!"
    message.guild = MagicMock()
    message.channel.id = 999  # Matches SUPPORT_CHANNEL_ID
    
    # Mock create_thread
    thread = AsyncMock(spec=discord.Thread)
    thread.name = "Support - User"
    thread.id = 888
    message.create_thread.return_value = thread
    
    # Mock engine using a class to guarantee awaitable behavior
    class MockEngine:
        def __init__(self):
            self.call_args = None
        async def process(self, *args, **kwargs):
            self.call_args = kwargs
            return ("AI Response", [])
            
    engine = MockEngine()
    # INJECT INTO bot.cognition NOT engine_manager
    support_cog.bot.cognition = engine
    # Disable Hippocampus RAG for this test
    support_cog.bot.hippocampus = None
    
    # Mock file reading (identity/manual)
    with patch("pathlib.Path.read_text", return_value="Mock Content"), \
         patch("pathlib.Path.exists", return_value=True):
        # Execute
        await support_cog.on_message(message)
    
    # Assertions
    message.create_thread.assert_called_once()
    thread.send.assert_called() # Greeting + Response
    
    # Check context passed to engine has NO history (is_new=True)
    assert engine.call_args is not None, "Engine should be called"
    kwargs = engine.call_args
    assert kwargs['context'] == ""
    assert kwargs['input_text'] == "Help me!"

@pytest.mark.asyncio
async def test_thread_reply(support_cog):
    """Test that a message in a support thread triggers a reply."""
    message = AsyncMock(spec=discord.Message)
    message.author.bot = False
    message.content = "Still broken"
    message.guild = MagicMock()
    
    # Message is in a Thread
    message.channel = AsyncMock(spec=discord.Thread)
    message.channel.parent_id = 999 # Matches SUPPORT_CHANNEL_ID
    message.channel.id = 888
    
    # Mock history
    history_msg = MagicMock(spec=discord.Message)
    history_msg.author.name = "Assistant"
    history_msg.content = "Did you try X?"
    history_msg.author == support_cog.bot.user # Mock equality logic?
    # Simple mock:
    history_msg.author = support_cog.bot.user
    
    async def mock_history(**kwargs):
        yield history_msg
    message.channel.history = mock_history
    
    # Mock engine
    class MockEngineRef:
        def __init__(self):
            self.call_args = None
        async def process(self, *args, **kwargs):
            self.call_args = kwargs
            return ("Try Y.", [])

    engine = MockEngineRef()
    # INJECT INTO bot.cognition
    support_cog.bot.cognition = engine
    
    # Mock file reading (identity/manual)
    with patch("pathlib.Path.read_text", return_value="Mock Content"), \
         patch("pathlib.Path.exists", return_value=True):
        # Execute
        await support_cog.on_message(message)
    
    # Assertions
    message.create_thread.assert_not_called()
    message.channel.send.assert_called_with("Try Y.")
    
    # Check context passed to engine HAS history
    assert engine.call_args is not None
    kwargs = engine.call_args
    assert "[Assistant]: Did you try X?" in kwargs['context']

@pytest.mark.asyncio
async def test_ignore_other_channels(support_cog):
    """Test that messages in other channels are ignored."""
    message = AsyncMock(spec=discord.Message)
    message.author.bot = False
    message.channel.id = 111 # Random channel
    message.guild = MagicMock()
    
    await support_cog.on_message(message)
    
    message.create_thread.assert_not_called()
    # Verify cognition NOT called
    assert not isinstance(support_cog.bot.cognition, MagicMock) or not support_cog.bot.cognition.process.called
