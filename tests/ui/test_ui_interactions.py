import pytest
from unittest.mock import MagicMock, AsyncMock
from src.ui.views import ResponseFeedbackView
import discord

@pytest.fixture
def mock_interaction():
    interaction = MagicMock(spec=discord.Interaction)
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.user = MagicMock()
    interaction.guild = MagicMock()
    interaction.guild.id = 123
    return interaction

@pytest.mark.asyncio
async def test_feedback_like(mock_interaction):
    view = ResponseFeedbackView(MagicMock(), "text")
    await view.like_button.callback(mock_interaction)
    mock_interaction.response.send_message.assert_called_with("Thanks for the feedback! (Logged: Positive)", ephemeral=True)

@pytest.mark.asyncio
async def test_feedback_dislike(mock_interaction):
    view = ResponseFeedbackView(MagicMock(), "text")
    await view.dislike_button.callback(mock_interaction)
    mock_interaction.response.send_message.assert_called()

@pytest.mark.asyncio
async def test_tts_dm(mock_interaction, tmp_path):
    """TTS in DMs should generate and upload audio file (no voice channel)."""
    mock_interaction.guild = None
    bot = MagicMock()
    bot.voice_manager = MagicMock()

    audio_file = tmp_path / "test.wav"
    audio_file.write_text("audio data")
    bot.voice_manager.get_audio_path = AsyncMock(return_value=str(audio_file))

    view = ResponseFeedbackView(bot, "text")
    await view.tts_button.callback(mock_interaction)
    # Should NOT block — should defer and upload
    mock_interaction.response.defer.assert_awaited()
    mock_interaction.followup.send.assert_awaited()

@pytest.mark.asyncio
async def test_tts_no_voice_manager(mock_interaction):
    bot = MagicMock()
    del bot.voice_manager # Ensure attribute missing
    view = ResponseFeedbackView(bot, "text")
    await view.tts_button.callback(mock_interaction)
    mock_interaction.response.send_message.assert_called()
    args, _ = mock_interaction.response.send_message.call_args
    assert "Voice System Unavailable" in args[0]

@pytest.mark.asyncio
async def test_tts_toggle_off(mock_interaction):
    bot = MagicMock()
    bot.voice_manager = MagicMock()
    # join_channel is awaited
    bot.voice_manager.join_channel = AsyncMock()
    
    view = ResponseFeedbackView(bot, "text")
    
    # Simulate existing audio msg
    mock_msg = MagicMock()
    mock_msg.delete = AsyncMock()
    view.audio_msg = mock_msg
    
    await view.tts_button.callback(mock_interaction)
    mock_msg.delete.assert_awaited()
    assert view.audio_msg is None

@pytest.mark.asyncio
async def test_tts_play_flow(mock_interaction, tmp_path):
    bot = MagicMock()
    bot.voice_manager = MagicMock()
    
    # helper file
    audio_file = tmp_path / "test.wav"
    audio_file.write_text("audio data")
    
    bot.voice_manager.get_audio_path = AsyncMock(return_value=str(audio_file))
    bot.voice_manager.active_connections = [123] # Guild ID
    bot.voice_manager.speak = AsyncMock()
    bot.voice_manager.join_channel = AsyncMock()
    
    # User in voice
    mock_interaction.user.voice.channel = MagicMock()
    
    view = ResponseFeedbackView(bot, "text")
    await view.tts_button.callback(mock_interaction)
    
    bot.voice_manager.speak.assert_awaited()
    mock_interaction.followup.send.assert_awaited()

@pytest.mark.asyncio
async def test_tts_auto_join(mock_interaction):
    bot = MagicMock()
    bot.voice_manager = MagicMock()
    bot.voice_manager.active_connections = [] # Not connected
    bot.voice_manager.join_channel = AsyncMock()
    bot.voice_manager.get_audio_path = AsyncMock(return_value=None)
    
    mock_interaction.user.voice.channel = MagicMock()
    
    view = ResponseFeedbackView(bot, "text")
    await view.tts_button.callback(mock_interaction)
    
    bot.voice_manager.join_channel.assert_awaited()
