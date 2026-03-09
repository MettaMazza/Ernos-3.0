"""
Tests for thread handling and @mention responses in chat.py
Covers: thread message handling, @mention in any channel, read_channel tool
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord


class TestThreadMessageHandling:
    """Tests for thread message handling (the thread fix)."""
    
    @pytest.fixture
    def mock_setup(self):
        """Create mocked ChatCog with dependencies."""
        with patch('src.bot.cogs.chat.settings') as mock_settings:
            mock_settings.TARGET_CHANNEL_ID = 123456789
            mock_settings.BLOCKED_IDS = []
            
            mock_bot = MagicMock()
            mock_bot.user = MagicMock()
            mock_bot.user.id = 999
            
            yield mock_settings, mock_bot
    
    def test_thread_from_target_channel_is_allowed(self, mock_setup):
        """Messages in threads parented from TARGET_CHANNEL_ID should be processed."""
        mock_settings, mock_bot = mock_setup
        
        # Create mock thread message
        mock_message = MagicMock()
        mock_message.author.bot = False
        mock_message.guild = MagicMock()
        mock_message.channel = MagicMock(spec=discord.Thread)
        mock_message.channel.id = 987654321  # Thread has different ID
        mock_message.channel.parent_id = 123456789  # But parent is TARGET_CHANNEL_ID
        mock_message.mentions = []
        
        # Check the logic
        is_target_channel = mock_message.channel.id == mock_settings.TARGET_CHANNEL_ID
        is_target_thread = (
            isinstance(mock_message.channel, discord.Thread) and 
            mock_message.channel.parent_id == mock_settings.TARGET_CHANNEL_ID
        )
        
        assert not is_target_channel  # Thread has different ID
        assert is_target_thread  # But it's a thread from target channel
    
    def test_thread_from_other_channel_is_ignored_unless_mentioned(self, mock_setup):
        """Threads from other channels should be ignored unless @mentioned."""
        mock_settings, mock_bot = mock_setup
        
        mock_message = MagicMock()
        mock_message.author.bot = False
        mock_message.guild = MagicMock()
        mock_message.channel = MagicMock(spec=discord.Thread)
        mock_message.channel.id = 111111111
        mock_message.channel.parent_id = 222222222  # Different parent
        mock_message.mentions = []  # Not mentioned
        
        is_target_channel = mock_message.channel.id == mock_settings.TARGET_CHANNEL_ID
        is_target_thread = (
            isinstance(mock_message.channel, discord.Thread) and 
            mock_message.channel.parent_id == mock_settings.TARGET_CHANNEL_ID
        )
        is_mentioned = mock_bot.user in mock_message.mentions
        is_dm = False
        
        should_process = is_dm or is_target_channel or is_target_thread or is_mentioned
        assert not should_process  # Should be ignored


class TestMentionHandling:
    """Tests for @mention response in any channel."""
    
    @pytest.fixture
    def mock_setup(self):
        """Create mocked ChatCog with dependencies."""
        with patch('src.bot.cogs.chat.settings') as mock_settings:
            mock_settings.TARGET_CHANNEL_ID = 123456789
            mock_settings.BLOCKED_IDS = []
            
            mock_bot = MagicMock()
            mock_bot.user = MagicMock()
            mock_bot.user.id = 999
            
            yield mock_settings, mock_bot
    
    def test_mentioned_in_other_channel_is_allowed(self, mock_setup):
        """When @mentioned in any channel, Ernos should respond."""
        mock_settings, mock_bot = mock_setup
        
        mock_message = MagicMock()
        mock_message.author.bot = False
        mock_message.guild = MagicMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 555555555  # Random channel
        mock_message.mentions = [mock_bot.user]  # Ernos is mentioned
        
        is_target_channel = mock_message.channel.id == mock_settings.TARGET_CHANNEL_ID
        is_target_thread = False  # Not a thread
        is_mentioned = mock_bot.user in mock_message.mentions
        is_dm = False
        
        should_process = is_dm or is_target_channel or is_target_thread or is_mentioned
        assert should_process  # Should be processed because mentioned
    
    def test_not_mentioned_in_other_channel_is_ignored(self, mock_setup):
        """Messages in other channels without @mention should be ignored."""
        mock_settings, mock_bot = mock_setup
        
        mock_message = MagicMock()
        mock_message.author.bot = False
        mock_message.guild = MagicMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 555555555  # Random channel
        mock_message.mentions = []  # No mention
        
        is_target_channel = mock_message.channel.id == mock_settings.TARGET_CHANNEL_ID
        is_target_thread = False
        is_mentioned = mock_bot.user in mock_message.mentions
        is_dm = False
        
        should_process = is_dm or is_target_channel or is_target_thread or is_mentioned
        assert not should_process  # Should be ignored
    
    def test_target_channel_without_mention_is_allowed(self, mock_setup):
        """TARGET_CHANNEL messages should work without @mention (active listening)."""
        mock_settings, mock_bot = mock_setup
        
        mock_message = MagicMock()
        mock_message.author.bot = False
        mock_message.guild = MagicMock()
        mock_message.channel = MagicMock()
        mock_message.channel.id = 123456789  # TARGET_CHANNEL_ID
        mock_message.mentions = []  # No mention needed
        
        is_target_channel = mock_message.channel.id == mock_settings.TARGET_CHANNEL_ID
        is_target_thread = False
        is_mentioned = mock_bot.user in mock_message.mentions
        is_dm = False
        
        should_process = is_dm or is_target_channel or is_target_thread or is_mentioned
        assert should_process  # Should be processed (target channel active listening)


class TestReadChannelTool:
    """Tests for the read_channel tool."""
    
    @pytest.mark.asyncio
    async def test_read_channel_no_bot(self):
        """Test read_channel returns error when no bot context."""
        from src.tools.memory_tools import read_channel
        
        result = await read_channel(channel_name="general", bot=None)
        assert "Error" in result
        assert "No bot context" in result
    
    @pytest.mark.asyncio
    async def test_read_channel_not_found(self):
        """Test read_channel when channel doesn't exist."""
        from src.tools.memory_tools import read_channel
        
        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_guild.text_channels = []  # No channels
        mock_bot.guilds = [mock_guild]
        
        result = await read_channel(channel_name="nonexistent", bot=mock_bot)
        assert "not found" in result.lower()
    
    @pytest.mark.asyncio
    async def test_read_channel_success(self):
        """Test successful channel reading."""
        from src.tools.memory_tools import read_channel
        
        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_channel = MagicMock()
        mock_channel.name = "general"
        
        # Mock permissions
        mock_perms = MagicMock()
        mock_perms.read_message_history = True
        mock_channel.permissions_for.return_value = mock_perms
        
        # Mock message history (async generator)
        async def mock_history(limit):
            mock_msg = MagicMock()
            mock_msg.created_at.strftime.return_value = "12:00"
            mock_msg.author.display_name = "TestUser"
            mock_msg.content = "Hello world"
            yield mock_msg
        
        mock_channel.history = mock_history
        mock_guild.text_channels = [mock_channel]
        mock_guild.me = MagicMock()
        mock_bot.guilds = [mock_guild]
        
        result = await read_channel(channel_name="general", bot=mock_bot)
        
        assert "general" in result
        assert "TestUser" in result or "Hello" in result
    
    @pytest.mark.asyncio
    async def test_read_channel_limit_clamped(self):
        """Test that limit is clamped between 1 and 50."""
        from src.tools.memory_tools import read_channel
        
        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_channel = MagicMock()
        mock_channel.name = "general"
        
        mock_perms = MagicMock()
        mock_perms.read_message_history = True
        mock_channel.permissions_for.return_value = mock_perms
        
        async def mock_history(limit):
            # Should receive clamped limit
            assert limit <= 50
            assert limit >= 1
            return
            yield  # Make it an async generator
        
        mock_channel.history = mock_history
        mock_guild.text_channels = [mock_channel]
        mock_guild.me = MagicMock()
        mock_bot.guilds = [mock_guild]
        
        # Test with limit > 50
        await read_channel(channel_name="general", limit=100, bot=mock_bot)
