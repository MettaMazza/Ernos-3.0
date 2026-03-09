import pytest
import discord
from unittest.mock import MagicMock, AsyncMock, patch
from src.voice.manager import VoiceManager
from src.voice.synthesizer import AudioSynthesizer
from src.voice.transcriber import AudioTranscriber

# --- Synthesizer Tests ---

@pytest.mark.asyncio
async def test_synthesizer_init():
    # To test KOKORO_AVAILABLE=False check without reloading modules,
    # we can mock os.path.exists to return False for the model path.
    # This causes the init to fail gracefully and leave self.kokoro as None.
    with patch("os.path.exists", return_value=False):
        # We also need to silence the error log to avoid noise
        with patch("src.voice.synthesizer.logger.error"):
            # Ensure we are testing assuming imports worked but file check fails
            # OR we can try patching the global if module object matches.
            # Let's try the os.path approach first as it's cleaner.
            import src.voice.synthesizer
            # If KOKORO_AVAILABLE defaults to True (installed), this test relies
            # on the try/except block in __init__.
            
            synth = AudioSynthesizer()
            assert synth.kokoro is None
            
            # Test generate fallback
            res = await synth.generate_audio("test", "out.mp3")
            assert res is None

@pytest.mark.asyncio
async def test_synthesizer_kokoro():
    import sys
    import importlib
    
    mock_kokoro_module = MagicMock()
    mock_kokoro_class = MagicMock()
    mock_kokoro_instance = MagicMock()
    mock_kokoro_class.return_value = mock_kokoro_instance
    mock_kokoro_module.Kokoro = mock_kokoro_class
    
    # Simulate kokoro_onnx being installed
    with patch.dict(sys.modules, {"kokoro_onnx": mock_kokoro_module}):
        import src.voice.synthesizer
        # Reload to pick up the "installed" module
        importlib.reload(src.voice.synthesizer)
        
        # Now KOKORO_AVAILABLE should be True and Kokoro defined
        
        # Patch os.path.exists to allow init to proceed
        with patch("os.path.exists", return_value=True):
            # Patch sf.write AND open
            with patch("src.voice.synthesizer.sf.write") as mock_write, \
                 patch("builtins.open", new_callable=MagicMock):
                 
                 mock_kokoro_instance.create.return_value = (b'audio', 24000)
                 
                 synth = src.voice.synthesizer.AudioSynthesizer()
                 
                 # Verify Kokoro was initialized
                 mock_kokoro_class.assert_called()
                 assert synth.kokoro is mock_kokoro_instance
                 
                 # Test generation
                 res = await synth.generate_audio("test", "out.mp3")
                 assert res == "out.mp3"
                 mock_write.assert_called()
                 
                 # Test empty text
                 assert await synth.generate_audio("", "out.mp3") is None
            assert await synth.generate_audio("", "out.mp3") is None


# --- Transcriber Tests ---

@pytest.mark.asyncio
async def test_transcriber():
    # Strategy: Patch sys.modules["speech_recognition"] AND reload the transcriber module.
    # This forces transcriber to re-import the mocked speech_recognition.
    import sys
    import importlib
    from unittest.mock import patch, MagicMock, AsyncMock
    
    mock_sr = MagicMock()
    mock_recog = MagicMock()
    mock_sr.Recognizer.return_value = mock_recog
    mock_sr.AudioFile.return_value.__enter__.return_value = MagicMock()
    
    # Patch sys.modules to return our mock for 'speech_recognition'
    with patch.dict(sys.modules, {"speech_recognition": mock_sr}):
        # We must also ensure 'src.voice.transcriber' is reloaded to pick up the change
        import src.voice.transcriber
        importlib.reload(src.voice.transcriber)
        
        try:
            # Patch loop
            with patch("asyncio.get_event_loop") as mock_loop:
                 mock_loop.return_value.run_in_executor = AsyncMock(return_value="Transcribed Text")
                 
                 transcriber = src.voice.transcriber.AudioTranscriber()
                 res = await transcriber.transcribe("file.wav")
                 assert "Transcribed Text" in res
        finally:
             # Cleanup: reload again to restore real module logic if needed by other tests?
             # Or just leave it. Pytest run is fine.
             pass


@pytest.mark.asyncio
async def test_transcriber_exceptions():
    import sys
    import importlib
    
    mock_sr = MagicMock()
    mock_recog = MagicMock()
    mock_sr.Recognizer.return_value = mock_recog
    mock_sr.AudioFile.return_value.__enter__.return_value = MagicMock()
    
    # Define Exceptions
    class MockUnknownValueError(Exception): pass
    class MockRequestError(Exception): pass
    mock_sr.UnknownValueError = MockUnknownValueError
    mock_sr.RequestError = MockRequestError
    
    with patch.dict(sys.modules, {"speech_recognition": mock_sr}):
        import src.voice.transcriber
        importlib.reload(src.voice.transcriber)
        
        transcriber = src.voice.transcriber.AudioTranscriber()
        
        # Test UnknownValueError
        with patch("asyncio.get_event_loop") as mock_loop:
             mock_loop.return_value.run_in_executor = AsyncMock(side_effect=MockUnknownValueError())
             res = await transcriber.transcribe("file_bad.wav")
             assert "[Audio Unintelligible]" in res
             
        # Test RequestError
        with patch("asyncio.get_event_loop") as mock_loop:
             mock_loop.return_value.run_in_executor = AsyncMock(side_effect=MockRequestError("Network Error"))
             res = await transcriber.transcribe("file_bad.wav")
             assert "Network Error" in res
             
        # Test RequestError
        with patch("asyncio.get_event_loop") as mock_loop:
             mock_loop.return_value.run_in_executor = AsyncMock(side_effect=MockRequestError("API Down"))
             res = await transcriber.transcribe("file_error.wav")
             assert "Transcription Service Error" in res
             
        # Test Generic Exception
             mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("Boom"))
             res = await transcriber.transcribe("file_crash.wav")
             assert "Transcription Failed" in res

# --- Voice Manager Tests ---

@pytest.mark.asyncio
async def test_voice_manager_connection():
    bot = MagicMock()
    manager = VoiceManager(bot)
    
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.guild.id = 123
    channel.connect = AsyncMock()
    
    # Test Join
    vc = await manager.join_channel(channel)
    assert 123 in manager.active_connections
    channel.connect.assert_awaited()
    
    # Test Join Existing
    vc2 = await manager.join_channel(channel)
    assert vc == vc2
    assert channel.connect.call_count == 1 # Shouldn't connect again
    
    # Test Join Failure
    channel.connect.side_effect = Exception("Fail")
    channel.guild.id = 456
    assert await manager.join_channel(channel) is None

@pytest.mark.asyncio
async def test_voice_manager_leave():
    bot = MagicMock()
    manager = VoiceManager(bot)
    
    vc = AsyncMock()
    manager.active_connections[123] = vc
    
    await manager.leave_channel(123)
    assert 123 not in manager.active_connections
    vc.disconnect.assert_awaited()

@pytest.mark.asyncio
async def test_voice_manager_speak_edge_cases():
    bot = MagicMock()
    manager = VoiceManager(bot)
    
    # Not connected
    await manager.speak(999, "test") # Should log warning and return
    
    # Connected but disconnected socket
    vc = MagicMock()
    vc.is_connected.return_value = False
    manager.active_connections[123] = vc
    await manager.speak(123, "test") 
    
    # Connected and playing
    vc.is_connected.return_value = True
    vc.is_playing.return_value = True
    with patch.object(manager.synthesizer, 'generate_audio', AsyncMock(return_value="audio.mp3")):
         # Patch the real class globally to avoid import resolution issues
         with patch("discord.FFmpegPCMAudio") as mock_ffmpeg:
             await manager.speak(123, "test")
             vc.stop.assert_called()
             vc.play.assert_called() # Should interrupt and play
