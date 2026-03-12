import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.bot.cogs.chat import ChatListener
from src.lobes.interaction.social import SocialAbility
from src.memory.hippocampus import Hippocampus

@pytest.mark.asyncio
async def test_reaction_telemetry():
    """Verify that reaction events trigger Social stats and Timeline logging."""
    
    # 1. Setup Mock Bot Structure
    mock_bot = MagicMock()
    mock_bot.user.id = 999
    
    # Mock Hippocampus
    mock_hippo = MagicMock()
    mock_bot.hippocampus = mock_hippo
    
    # Mock Cerebrum & Social Ability
    mock_social = AsyncMock()
    mock_social.process_reaction.return_value = "POSITIVE"
    
    mock_lobe = MagicMock()
    mock_lobe.get_ability.return_value = mock_social
    
    mock_bot.cerebrum.lobes.get.return_value = mock_lobe
    
    # Mock Silo Manager
    mock_bot.silo_manager.check_quorum = AsyncMock()
    
    # 2. Init ChatCog
    cog = ChatListener(mock_bot)
    
    # 3. Create Mock Payload
    mock_payload = MagicMock()
    mock_payload.user_id = 123
    mock_payload.emoji = "❤️" # Positive
    mock_payload.message_id = 1001
    mock_payload.channel_id = 2001
    mock_payload.guild_id = None # DM
    
    # 4. Trigger Event
    await cog.on_raw_reaction_add(mock_payload)
    
    # 5. Verify Social Ability Called
    mock_social.process_reaction.assert_awaited_once_with(123, "❤️", 1001)
    
    # 6. Verify Hippocampus Called
    mock_hippo.observe_reaction.assert_called_once_with(
        user_id="123",
        emoji="❤️",
        sentiment="POSITIVE",
        message_id=1001,
        channel_id=2001,
        is_dm=True
    )

@pytest.mark.asyncio
async def test_social_sentiment_logic():
    """Verify SocialAbility correctly maps emojis to sentiment."""
    # We need to test the actual SocialAbility logic here
    # Mock file system to avoid writing real files
    
    with patch("src.lobes.interaction.social.Path") as MockPath:
        # Setup mock file reading
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = '{"positive_interactions": 0}'
        
        MockPath.return_value.__truediv__.return_value = mock_file
        
        # Init Ability
        # We need a mock lobe for the init
        ability = SocialAbility(MagicMock())
        
        # Test Positive
        sentiment = await ability.process_reaction(123, "❤️", 1)
        assert sentiment == "POSITIVE"
        
        # Verify write
        # Check that json.dumps was called with incremented count
        # This is a bit tricky to assert exact string, but we can check calls
        assert mock_file.write_text.called
        
        # Test Negative
        sentiment = await ability.process_reaction(123, "🚫", 2)
        assert sentiment == "NEGATIVE"

if __name__ == "__main__":
    pass
