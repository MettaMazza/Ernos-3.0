import pytest
import discord
from unittest.mock import MagicMock, AsyncMock, patch
from src.voice.manager import VoiceManager
from src.engines.ollama import OllamaEngine

@pytest.mark.asyncio
async def test_voice_manager_speak():
    # Setup
    mock_bot = MagicMock()
    manager = VoiceManager(mock_bot)
    
    # Mock active connection
    guild_id = 123
    mock_vc = MagicMock()
    mock_vc.is_connected.return_value = True
    mock_vc.is_playing.return_value = False
    manager.active_connections[guild_id] = mock_vc
    
    # Mock Synthesizer
    manager.synthesizer.generate_audio = AsyncMock(return_value="test.mp3")
    
    # Mock Discord Audio
    # Patch globally to avoid import issues
    with patch("discord.FFmpegPCMAudio") as mock_ffmpeg_cls:
        mock_ffmpeg_cls.return_value = MagicMock()
        await manager.speak(guild_id, "Hello World")
        
        # Verify
        from unittest.mock import ANY
        manager.synthesizer.generate_audio.assert_called_with("Hello World", ANY)
        mock_vc.play.assert_called_once()

@pytest.mark.asyncio
async def test_ollama_multimodal_param():
    engine = OllamaEngine("llava")
    engine._client = MagicMock()
    engine._client.generate.return_value = {"response": "A cat"}
    
    # Execute
    images = [b"fake_image_bytes"]
    resp = engine.generate_response("Describe this", images=images)
    
    # Verify
    engine._client.generate.assert_called_with(
        model="llava",
        prompt="Describe this",
        system=None,
        images=images,
        options={
            "num_predict": engine._num_predict,
        }
    )
    assert resp == "A cat"
