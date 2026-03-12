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
    # Stream audio returns an async generator
    async def mock_stream_audio(*args, **kwargs):
        yield b"fake_audio_data"
    
    manager.synthesizer.stream_audio = MagicMock(side_effect=mock_stream_audio)
    
    # Mock Discord Audio Source
    with patch("src.voice.manager.RawPCMSource") as mock_source_cls:
        mock_source = MagicMock()
        mock_source_cls.return_value = mock_source
        
        # We need to await speak and allow the background feed_task to run
        await manager.speak(guild_id, "Hello World")
        
        # Let the event loop run once so the feed_task executes
        import asyncio
        await asyncio.sleep(0.01)
        
        # Verify
        manager.synthesizer.stream_audio.assert_called_with("Hello World")
        mock_vc.play.assert_called_once()
        mock_source.feed.assert_called_with(b"fake_audio_data")
        mock_source.mark_finished.assert_called_once()

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
