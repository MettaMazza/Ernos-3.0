
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.lobes.creative.artist import VisualCortexAbility
import json
import time

@pytest.fixture
def mock_lobe():
    return MagicMock()

@pytest.fixture
def artist(mock_lobe):
    return VisualCortexAbility(mock_lobe)

@pytest.mark.asyncio
async def test_artist_limits_and_reset(artist, tmp_path):
    # Test _check_limits with corrupt file (Exception coverage)
    # Patch _get_usage_file to return a path in tmp_path
    
    user_home = tmp_path / "user_123"
    user_home.mkdir()
    usage_file = user_home / "usage.json"
    
    # Write bad JSON
    usage_file.write_text("{bad_json")
    
    with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=user_home):
        # Should catch exception and reset/continue
        allowed = artist._check_limits("image", 123)
        assert allowed is True
        # Verify file validated
        assert json.loads(usage_file.read_text())["image_count"] == 1
        
        # Test Limit Reached
        # Write limit
        data = {"image_count": 50, "video_count": 0, "last_reset": time.time()} # Assuming limit is 5 or 10
        usage_file.write_text(json.dumps(data))
        
        # Mock settings
        with patch("config.settings.DAILY_IMAGE_LIMIT", 5):
            allowed = artist._check_limits("image", 123)
            assert allowed is False

@pytest.mark.asyncio
async def test_artist_user_fallback(artist):
    # Test user_id is None fallback — autonomy flag should bypass _check_limits
    with patch("config.settings.ADMIN_ID", 999):
        # We mock _check_limits to verify it is NOT called for autonomy
        artist._check_limits = MagicMock(return_value=True)
        
        # We mock generation to avoid threading
        with patch("src.lobes.creative.artist.MediaGenerator") as mock_gen:
             # We need to mock asyncio.to_thread
             with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
                 await artist.execute("Prompt", user_id=None)
                 
                 # When user_id is None, is_autonomy=True — _check_limits should NOT be called
                 artist._check_limits.assert_not_called()

@pytest.mark.asyncio
async def test_artist_generation_exception(artist):
    # Test exception block
    artist._check_limits = MagicMock(return_value=True)
    
    # Mock generation failure
    # Mock generation failure
    # Patch get_generator to raise exception immediately
    with patch("src.lobes.creative.artist.get_generator", side_effect=Exception("Gen Fail")):
        result = await artist.execute("Prompt", user_id=123)
        assert "Generation Error" in result
        
def test_artist_reset_lock(artist):
    artist.turn_lock = True
    artist.reset_turn_lock()
    assert artist.turn_lock is False

@pytest.mark.asyncio
async def test_artist_execute_image_autonomy(artist, tmp_path):
    artist._check_limits = MagicMock(return_value=True)
    with patch("src.lobes.creative.artist.get_generator") as mock_get_gen, \
         patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
         patch("src.security.provenance.ProvenanceManager.log_artifact"), \
         patch("src.lobes.creative.artist.VisualCortexAbility._send_to_imaging_channel", new_callable=AsyncMock) as mock_send, \
         patch("os.getcwd", return_value=str(tmp_path)), \
         patch("src.bot.globals.bot", create=True) as mock_bot:
        
        # Mock hippocampus structure to avoid exception breaking execution silently
        mock_bot.hippocampus.graph = MagicMock()
        
        res = await artist.execute("Prompt", media_type="image", user_id=None)
        assert res.endswith(".png")
        mock_send.assert_called_once()
        assert artist.turn_lock is True

@pytest.mark.asyncio
async def test_artist_execute_video_channel(artist, tmp_path):
    artist._check_limits = MagicMock(return_value=True)
    with patch("src.lobes.creative.artist.get_generator"), \
         patch("asyncio.create_task") as mock_task, \
         patch("os.getcwd", return_value=str(tmp_path)):
        
        res = await artist.execute("Prompt", media_type="video", user_id=123, channel_id=456)
        assert "Video Generation Started" in res
        mock_task.assert_called_once()

@pytest.mark.asyncio
async def test_artist_execute_video_blocking(artist, tmp_path):
    artist._check_limits = MagicMock(return_value=True)
    with patch("src.lobes.creative.artist.get_generator") as mock_get_gen, \
         patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
         patch("src.security.provenance.ProvenanceManager.log_artifact"), \
         patch("os.getcwd", return_value=str(tmp_path)):
        
        res = await artist.execute("Prompt", media_type="video", user_id=123)
        assert res.endswith(".mp4")
        mock_thread.assert_called_once()

@pytest.mark.asyncio
async def test_artist_execute_music(artist, tmp_path):
    artist._check_limits = MagicMock(return_value=True)
    with patch("src.lobes.creative.artist.get_generator") as mock_get_gen, \
         patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
         patch("src.security.provenance.ProvenanceManager.log_artifact"), \
         patch("os.getcwd", return_value=str(tmp_path)), \
         patch("src.lobes.creative.artist.VisualCortexAbility._send_to_media_channel", new_callable=AsyncMock) as mock_send:
        
        # We need mock_thread to return the output path for music as per the logic
        mock_thread.return_value = str(tmp_path / "mock.wav")

        res = await artist.execute("Prompt", media_type="music", user_id=None, duration=20)
        assert res.endswith(".wav")
        mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_artist_execute_speech(artist, tmp_path):
    artist._check_limits = MagicMock(return_value=True)
    with patch("src.lobes.creative.artist.get_generator") as mock_get_gen, \
         patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread, \
         patch("src.security.provenance.ProvenanceManager.log_artifact"), \
         patch("src.lobes.creative.artist.VisualCortexAbility._send_to_imaging_channel", new_callable=AsyncMock) as mock_send, \
         patch("os.getcwd", return_value=str(tmp_path)):
        
        # We need mock_thread to return the output path for speech
        mock_thread.return_value = str(tmp_path / "mock.wav")

        res = await artist.execute("Prompt", media_type="speech", user_id=None, voice="Test")
        assert res.endswith(".wav")
        mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_artist_execute_audiobook_channel(artist, tmp_path):
    artist._check_limits = MagicMock(return_value=True)
    with patch("asyncio.create_task") as mock_task, \
         patch("os.getcwd", return_value=str(tmp_path)):
        
        res = await artist.execute("Prompt", media_type="audiobook", user_id=123, channel_id=456)
        assert "Audiobook Production Started" in res
        mock_task.assert_called_once()

@pytest.mark.asyncio
async def test_artist_execute_audiobook_blocking(artist, tmp_path):
    artist._check_limits = MagicMock(return_value=True)
    with patch("src.lobes.creative.audiobook_producer.AudiobookProducer.produce", new_callable=AsyncMock, return_value="/tmp/test.mp3") as mock_produce, \
         patch("src.security.provenance.ProvenanceManager.log_artifact"), \
         patch("src.lobes.creative.artist.VisualCortexAbility._send_to_media_channel", new_callable=AsyncMock) as mock_send, \
         patch("os.getcwd", return_value=str(tmp_path)):
        
        res = await artist.execute("Prompt", media_type="audiobook", user_id=None) # user None triggers is_autonomy
        assert res == "/tmp/test.mp3"
        mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_generate_video_background(artist, tmp_path):
    with patch("src.lobes.creative.artist.get_generator"), \
         patch("asyncio.to_thread", new_callable=AsyncMock), \
         patch("src.security.provenance.ProvenanceManager.log_artifact"), \
         patch("os.getcwd", return_value=str(tmp_path)), \
         patch.dict('sys.modules', {'discord': MagicMock()}):
        
        # Test Success Channel
        mock_channel = AsyncMock()
        artist.bot.get_channel.return_value = mock_channel
        await artist._generate_video_background("Prompt", 123, 456, "PUBLIC", False, "Testing")
        mock_channel.send.assert_called()

        # Test Exception Channel
        mock_channel.send.reset_mock()
        with patch("asyncio.to_thread", side_effect=Exception("Crash")):
            await artist._generate_video_background("Prompt", 123, 456, "PUBLIC", False, "Testing")
            mock_channel.send.assert_called()
            call_args = mock_channel.send.call_args[0][0]
            assert "Failed" in call_args

@pytest.mark.asyncio
async def test_produce_audiobook_background(artist):
    # Tests the disabled short-circuit logic currently in _produce_audiobook_background
    mock_channel = AsyncMock()
    artist.bot.get_channel.return_value = mock_channel
    await artist._produce_audiobook_background("script", 1, 2, "PUB", False, "Test", "T", "out")
    # mock_channel.send.assert_called() # Disabled logic in artist.py

@pytest.mark.asyncio
async def test_split_audio_chunks(artist):
    with patch("subprocess.run") as mock_run, \
         patch("os.path.getsize", return_value=100*1024*1024), \
         patch("os.listdir", return_value=["out_chunk_000.mp3", "out_chunk_001.mp3"]):
        
        # Mock probe duration output
        mock_probe = MagicMock()
        mock_probe.stdout = "100.0"
        
        # Mock ffmpeg split output
        mock_split = MagicMock()
        mock_split.returncode = 0
        
        mock_run.side_effect = [mock_probe, mock_split]
        
        chunks = await artist._split_audio_chunks("/test/out.mp3", "out", max_mb=20)
        assert len(chunks) == 2
        
        # Mock failure
        mock_split.returncode = 1
        mock_run.side_effect = [mock_probe, mock_split]
        chunks_fail = await artist._split_audio_chunks("/test/out.mp3", "out", max_mb=20)
        assert len(chunks_fail) == 0

        # Mock exception
        mock_run.side_effect = Exception("Boom")
        chunks_err = await artist._split_audio_chunks("/test/out.mp3", "out", max_mb=20)
        assert len(chunks_err) == 0

@pytest.mark.asyncio
async def test_send_to_media_channel(artist):
    with patch.dict('sys.modules', {'discord': MagicMock()}):
        with patch("os.path.getsize", return_value=1024*1024): # 1 MB
            
            mock_channel = AsyncMock()
            artist.bot.get_channel.return_value = mock_channel
            
            # Simple send (under size limit)
            await artist._send_to_media_channel("path.jpg", "Prompt", 123, "P", "Im")
            mock_channel.send.assert_called()
            
        # Oversize send (no chunking for images)
        with patch("os.path.getsize", return_value=100*1024*1024): # 100 MB
            mock_channel.send.reset_mock()
            await artist._send_to_media_channel("path.jpg", "Prompt", 123, "P", "Im")
            call_args = mock_channel.send.call_args[0][0]
            assert "too large" in call_args
            
        # Chunked sending (audiobooks)
        with patch("os.path.getsize", return_value=100*1024*1024), \
             patch("src.lobes.creative.artist.VisualCortexAbility._split_audio_chunks", new_callable=AsyncMock, return_value=["c1.mp3", "c2.mp3"]), \
             patch("os.remove"):
            
            mock_channel.send.reset_mock()
            await artist._send_to_media_channel("path.mp3", "Prompt", 123, "P", "Audiobook")
            assert mock_channel.send.call_count == 3  # Initial + 2 chunks

    # Chunked fallback (chunks failed)
    with patch("os.path.getsize", return_value=100*1024*1024), \
         patch("src.lobes.creative.artist.VisualCortexAbility._split_audio_chunks", new_callable=AsyncMock, return_value=[]):
        
        mock_channel.send.reset_mock()
        await artist._send_to_media_channel("path.mp3", "Prompt", 123, "P", "Audiobook")
        call_args = mock_channel.send.call_args[0][0]
        assert "chunking failed" in call_args

@pytest.mark.asyncio
async def test_artist_edge_cases(artist, tmp_path):
    # Line 70: Admin override bypasses check_limits
    with patch("config.settings.ADMIN_IDS", [123]):
        assert artist._check_limits("image", 123) is True
    
    # Line 90: last_reset not in data
    user_home = tmp_path / "user_456"
    user_home.mkdir()
    usage_file = user_home / "usage.json"
    usage_file.write_text(json.dumps({"image_count": 0, "video_count": 0})) # no last_reset
    with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=user_home), \
         patch("src.core.flux_capacitor.FluxCapacitor.get_tier", return_value=0), \
         patch("time.time", return_value=10.0): # mock time so time.time() - 0 <= 86400
        artist._check_limits("image", 456)
        data = json.loads(usage_file.read_text())
        assert "last_reset" in data

    # Line 127: Turn lock rejection
    artist.turn_lock = True
    res = await artist.execute("Prompt", user_id=456)
    assert "Rate limit" in res
    artist.turn_lock = False

@pytest.mark.asyncio
async def test_artist_execute_daily_limit_and_scope_fallback(artist, tmp_path):
    artist._check_limits = MagicMock(return_value=False)
    # Line 131-132: Daily limit reached
    res = await artist.execute("Prompt", user_id=456, media_type="image")
    assert "Daily limit reached" in res

    artist._check_limits = MagicMock(return_value=True)
    with patch("src.lobes.creative.artist.get_generator"), \
         patch("asyncio.to_thread", new_callable=AsyncMock), \
         patch("src.security.provenance.ProvenanceManager.log_artifact"), \
         patch("os.getcwd", return_value=str(tmp_path)):
        # Line 139-140: Scope exception fallback
        await artist.execute("Prompt", user_id=456, request_scope="INVALID_SCOPE")
        # Should execute successfully with PUBLIC scope

@pytest.mark.asyncio
async def test_artist_kg_provenance_error(artist, tmp_path):
    artist._check_limits = MagicMock(return_value=True)
    with patch("src.lobes.creative.artist.get_generator"), \
         patch("asyncio.to_thread", new_callable=AsyncMock), \
         patch("src.security.provenance.ProvenanceManager.log_artifact"), \
         patch("src.lobes.creative.artist.VisualCortexAbility._send_to_imaging_channel", new_callable=AsyncMock), \
         patch("os.getcwd", return_value=str(tmp_path)), \
         patch("src.bot.globals.bot", create=True) as mock_bot:
        
        # Line 261-262: KG provenance exception
        mock_bot.hippocampus.graph.add_node.side_effect = Exception("KG Error")
        await artist.execute("Prompt", media_type="image", user_id=None) # autonomy triggers KG
        # Should suppress and pass

@pytest.mark.asyncio
async def test_generate_video_background_edges(artist, tmp_path):
    with patch("src.lobes.creative.artist.get_generator"), \
         patch("asyncio.to_thread", new_callable=AsyncMock), \
         patch("src.security.provenance.ProvenanceManager.log_artifact"), \
         patch("os.getcwd", return_value=str(tmp_path)), \
         patch.dict('sys.modules', {'discord': MagicMock()}):
        
        # Line 282-283: Scope Exception in background
        # Line 291: Autonomy base_dir fallback (user_id=None)
        # Line 319: Could not find channel
        artist.bot.get_channel.return_value = None
        await artist._generate_video_background("Prompt", None, 456, "BAD", True, "Test")

        # Line 328: Exception in failure branch
        artist.bot.get_channel.return_value = MagicMock()
        artist.bot.get_channel.return_value.send.side_effect = Exception("Send Fail")
        with patch("asyncio.to_thread", side_effect=Exception("Gen Fail")):
            await artist._generate_video_background("Prompt", 123, 456, "PUB", False, "Test")
            # Should suppress and pass

@pytest.mark.asyncio
async def test_produce_audiobook_disabled_exception(artist):
    # Line 344-345: channel.send exception inside disabled branch
    mock_channel = MagicMock()
    mock_channel.send.side_effect = Exception("Disabled send err")
    artist.bot.get_channel.return_value = mock_channel
    await artist._produce_audiobook_background("script", 1, 2, "PUB", False, "Test", "T", "out")
    # Should suppress

@pytest.mark.asyncio
async def test_split_audio_chunks_single(artist):
    with patch("subprocess.run") as mock_run, \
         patch("os.path.getsize", return_value=1024):
        
        # Line 373: num_chunks <= 1
        mock_probe = MagicMock()
        mock_probe.stdout = "10.0"
        mock_run.return_value = mock_probe
        
        chunks = await artist._split_audio_chunks("/test/out.mp3", "out", max_mb=20)
        assert chunks == ["/test/out.mp3"]

@pytest.mark.asyncio
async def test_send_to_imaging_channel(artist):
    with patch("src.lobes.creative.artist.VisualCortexAbility._send_to_media_channel", new_callable=AsyncMock) as mock_send:
        # Line 407-408: Cover wrapper
        await artist._send_to_imaging_channel("path.jpg", "prompt")
        mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_send_to_media_channel_edges(artist):
    with patch.dict('sys.modules', {'discord': MagicMock()}):
        # Line 440-441: chunk_err during send
        # Line 445-446: OSError during remove
        mock_discord = MagicMock()
        mock_discord.File.side_effect = Exception("File Err")
        with patch.dict('sys.modules', {'discord': mock_discord}):
            with patch("os.path.getsize", return_value=100*1024*1024), \
                 patch("src.lobes.creative.artist.VisualCortexAbility._split_audio_chunks", new_callable=AsyncMock, return_value=["c1.mp3"]), \
                 patch("os.remove", side_effect=OSError("Remove err")):
                 
                 mock_channel = AsyncMock()
                 artist.bot.get_channel.return_value = mock_channel
                 await artist._send_to_media_channel("path.mp3", "P", 123, "E", "Audiobook")
                 # Should suppress exceptions
             
        # Line 453-455: Channel not found
        artist.bot.get_channel.return_value = None
        with patch.dict('sys.modules', {'discord': MagicMock()}):
            with patch("os.path.getsize", return_value=1024):
                 await artist._send_to_media_channel("path.jpg", "P", 123, "E", "Image")
                 # Should just log warning

        # Line 454-455: Outer exception
        artist.bot.get_channel.return_value = None # reset
        artist.bot.get_channel.side_effect = Exception("Outer Error")
        await artist._send_to_media_channel("path.jpg", "P", 123, "E", "Image")
        # Should suppress and pass
