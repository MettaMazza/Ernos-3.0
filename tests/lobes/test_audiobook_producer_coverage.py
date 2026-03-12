import pytest
import numpy as np
import os
from unittest.mock import MagicMock, AsyncMock, patch

from src.lobes.creative.audiobook_producer import (
    Segment,
    parse_script,
    chunk_text,
    generate_silence,
    normalize_audio,
    overlay_audio,
    AudiobookProducer
)


class TestAudiobookScriptParser:
    def test_parse_narrate_multiline(self):
        script = '''[NARRATE] This is line one.
This is line two.
"Quote line on new line"
[PAUSE: 1s]'''
        segments = parse_script(script)
        assert len(segments) == 3
        assert segments[0].kind == "NARRATE"
        assert segments[0].text == "This is line one. This is line two."
        assert segments[1].kind == "NARRATE"
        assert segments[1].text == "Quote line on new line"
        assert segments[2].kind == "PAUSE"
        assert segments[2].duration == 1.0

    def test_parse_voice_and_dialogue(self):
        script = '''
        [VOICE: "Alice" | Soft and sweet]
        "Hello there!"
        "How are you?"
        '''
        segments = parse_script(script)
        assert len(segments) == 2
        assert segments[0].kind == "VOICE"
        assert segments[0].character == "Alice"
        assert segments[0].text == "Hello there!"
        assert segments[1].kind == "VOICE"
        assert segments[1].character == "Alice"
        assert segments[1].text == "How are you?"

    def test_parse_dialogue_without_character(self):
        script = '''"I am speaking but no one knows who I am."'''
        segments = parse_script(script)
        assert len(segments) == 1
        assert segments[0].kind == "NARRATE"
        assert segments[0].text == "I am speaking but no one knows who I am."

    def test_parse_multiline_quote(self):
        script = '''"This is a very long quote
that spans down
and even further."'''
        segments = parse_script(script)
        assert len(segments) == 1
        assert segments[0].kind == "NARRATE"
        assert segments[0].text == "This is a very long quote that spans down and even further."

    def test_parse_music_and_sfx(self):
        script = '''
        [MUSIC: Epic orchestral, 10]
        [SFX: explosion, 2s]
        [BG_MUSIC: tense ambient, 5s]
        [BG_SFX: rain, 1s]
        [BG_MUSIC: too long, 50]
        [BG_SFX: too long, 50]
        '''
        segments = parse_script(script)
        assert len(segments) == 6
        assert segments[0].kind == "MUSIC"
        assert segments[0].text == "Epic orchestral"
        assert segments[0].duration == 10.0
        
        assert segments[1].kind == "SFX"
        assert segments[1].text == "explosion"
        assert segments[1].duration == 2.0
        
        assert segments[2].kind == "BG_MUSIC"
        assert segments[2].text == "tense ambient"
        assert segments[2].duration == 5.0
        
        assert segments[3].kind == "BG_SFX"
        assert segments[3].text == "rain"
        assert segments[3].duration == 1.0

    def test_parse_untagged_text(self):
        script = '''Just some normal text here.'''
        segments = parse_script(script)
        assert len(segments) == 1
        assert segments[0].kind == "NARRATE"
        assert segments[0].text == "Just some normal text here."

    def test_parse_empty_lines_ignored(self):
        script = '''
        
        [PAUSE: 2.5]
        
        '''
        segments = parse_script(script)
        assert len(segments) == 1
        assert segments[0].kind == "PAUSE"
        assert segments[0].duration == 2.5


class TestTextChunker:
    def test_short_text(self):
        chunks = chunk_text("Hello world", max_chars=400)
        assert chunks == ["Hello world"]

    def test_sentence_split(self):
        text = "Hello world. " * 50  # Very long
        chunks = chunk_text(text, max_chars=100)
        assert len(chunks) > 1
        assert all(len(c) <= 100 for c in chunks)

    def test_force_word_split(self):
        # A single word that exceeds max_chars
        text = "A" * 500
        chunks = chunk_text(text, max_chars=400)
        assert len(chunks) == 2
        # `chunk_text` logic adds length checks; verify actual lengths produced
        assert chunks[0] == "A" * 400
        assert chunks[1] == "A" * 100

    def test_force_single_word_split_with_others(self):
        text = "Hello " + "A"*450 + " World"
        chunks = chunk_text(text, max_chars=400)
        assert len(chunks) > 1
        assert all(len(c) <= 400 for c in chunks)

    def test_chunk_edge_cases(self):
        # Precise boundary alignment
        text = "A" * 300 + " " + "B" * 100
        chunks = chunk_text(text, max_chars=400)
        assert len(chunks) == 2
        
        # Line 248-249 trigger (add word when sub exists but exceeds cap)
        text = "short " + "x" * 100 + " precise"
        chunks = chunk_text(text, max_chars=100)
        assert len(chunks) == 3


class TestAudioHelpers:
    def test_generate_silence(self):
        silence = generate_silence(0.5, 24000)
        assert len(silence) == 12000
        assert np.all(silence == 0)

    def test_normalize_audio(self):
        # Empty
        assert len(normalize_audio(np.array([]))) == 0
        
        # Exact silence
        silence = np.zeros(100)
        np.testing.assert_array_equal(normalize_audio(silence), silence)

        # Signal
        signal = np.ones(100) * 0.1
        normalized = normalize_audio(signal, target_db=-20.0)
        assert len(normalized) == 100
        rms = np.sqrt(np.mean(normalized ** 2))
        current_db = 20 * np.log10(rms)
        assert np.isclose(current_db, -20.0, atol=0.1)

    def test_overlay_audio(self):
        base = np.zeros(100, dtype=np.float32)
        overlay = np.ones(50, dtype=np.float32) * 0.5
        
        # Simple overlay
        mixed = overlay_audio(base.copy(), overlay, offset=10)
        assert len(mixed) == 100
        np.testing.assert_array_equal(mixed[:10], np.zeros(10))
        np.testing.assert_array_equal(mixed[10:60], np.ones(50) * 0.5)
        np.testing.assert_array_equal(mixed[60:], np.zeros(40))

        # Extends beyond base
        mixed_extend = overlay_audio(base.copy(), overlay.copy(), offset=80)
        assert len(mixed_extend) == 130
        assert mixed_extend[80] == 0.5

        # Negative offset cap
        mixed_neg = overlay_audio(base.copy(), overlay.copy(), offset=-10)
        assert mixed_neg[0] == 0.5

    def test_overlay_audio_memory_cap(self, monkeypatch):
        import src.lobes.creative.audiobook_producer as module
        monkeypatch.setattr(module, "MAX_SAMPLES", 100)
        
        base = np.zeros(50, dtype=np.float32)
        overlay = np.ones(60, dtype=np.float32)
        
        # offset 50 + len 60 = 110 > MAX_SAMPLES (100)
        clipped = overlay_audio(base, overlay, offset=50)
        assert len(clipped) == 100
        
        # Offset beyond cap
        skipped = overlay_audio(base, overlay, offset=110)
        assert len(skipped) == 50  # Returns original base

        # Offset negative fallback test
        neg_capped = overlay_audio(base, overlay, offset=-1)
        assert len(neg_capped) == 60


class TestAudiobookProducer:
    @pytest.fixture
    def mock_bot(self):
        b = MagicMock()
        b.voice_manager = MagicMock()
        
        synth = MagicMock()
        synth.kokoro = MagicMock()
        synth.kokoro.create.return_value = (np.zeros(24000, dtype=np.float32), 24000)
        synth._sanitize_text = lambda x: x
        
        b.voice_manager.synthesizer = synth
        return b

    @pytest.fixture
    def producer(self, mock_bot):
        return AudiobookProducer(mock_bot)

    @pytest.mark.asyncio
    @patch('src.lobes.creative.audiobook_producer.sf.write')
    @patch('src.lobes.creative.audio_utils.wav_to_mp3')
    async def test_produce_success(self, mock_mp3, mock_write, producer, tmp_path):
        mock_gen = MagicMock()
        mock_gen.generate_speech.return_value = "dummy.wav"
        mock_gen.generate_music.return_value = "dummy_music.wav"
        mock_mp3.return_value = "dummy.mp3"

        script = """
        [NARRATE] Welcome
        [VOICE: "Hero" | brave]
        "I will fight!"
        "And win!"
        [MUSIC: battle, 1s]
        [BG_MUSIC: tense, 1s]
        [SFX: sword, 1s]
        """
        
        # Override file reading and generator module loading
        with patch('src.lobes.creative.audiobook_producer.sf.read') as mock_read, \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch('src.lobes.creative.generators.get_generator', return_value=mock_gen):
            mock_read.return_value = (np.zeros(24000, dtype=np.float32), 24000)
            res = await producer.produce(script, str(tmp_path / "out.mp3"))
        
        assert res == "dummy.mp3"
        mock_write.assert_called_once()
        mock_gen.unload_musicgen.assert_called_once()

    @pytest.mark.asyncio
    async def test_produce_empty_script(self, producer):
        res = await producer.produce("", "out.mp3")
        assert "Error: Script produced no segments" in res

    @pytest.mark.asyncio
    async def test_produce_all_failed(self, producer, tmp_path):
        """Fallback to Qwen or return empty silent chunks"""
        # Break all engines
        producer.bot.voice_manager.synthesizer.kokoro.create.side_effect = Exception("Fail")
        with patch('src.lobes.creative.generators.get_generator') as mock_get_gen:
            mock_gen = MagicMock()
            mock_gen.generate_speech.return_value = "fail.mp3"
            mock_get_gen.return_value = mock_gen
            
            with patch('src.lobes.creative.audiobook_producer.sf.read') as mock_read, patch('os.path.exists', return_value=True):
                mock_read.return_value = (np.zeros(24000, dtype=np.float32), 24000)
                res = await producer.produce("[NARRATE] Only this", str(tmp_path / "out.mp3"))
        
        # Will output fallback Qwen
        assert isinstance(res, str)

    @pytest.mark.asyncio
    async def test_produce_segment_cap(self, producer, tmp_path):
        producer.MAX_SEGMENTS = 5
        # Return 10 segments so it clips to 5
        mock_segs = [MagicMock(kind="NARRATE", text="test") for _ in range(10)]
        with patch('src.lobes.creative.audiobook_producer.parse_script', return_value=mock_segs), \
             patch('src.lobes.creative.audiobook_producer.sf.write'), patch('src.lobes.creative.audio_utils.wav_to_mp3'), \
             patch('src.lobes.creative.generators.get_generator'):
            res = await producer.produce("dummy", str(tmp_path / "out.mp3"))
            assert res is not None
        
    @pytest.mark.asyncio
    async def test_produce_fg_time_budget(self, producer, tmp_path):
        producer.MAX_FG_SAMPLES = 100
        mock_segs = [MagicMock(kind="NARRATE", text="test1"), MagicMock(kind="NARRATE", text="test2")]
        producer._render_segment = AsyncMock(return_value=np.zeros(200, dtype=np.float32))
        with patch('src.lobes.creative.audiobook_producer.parse_script', return_value=mock_segs), \
             patch('src.lobes.creative.audiobook_producer.sf.write'), patch('src.lobes.creative.audio_utils.wav_to_mp3'), \
             patch('src.lobes.creative.generators.get_generator'):
            res = await producer.produce("dummy", str(tmp_path / "out.mp3"))
        assert getattr(producer._render_segment, "call_count", 0) == 1

    @pytest.mark.asyncio
    async def test_produce_bg_layer_cap(self, producer, tmp_path):
        producer.MAX_BG_LAYERS = 1
        mock_segs = [MagicMock(kind="BG_MUSIC", text="test"), MagicMock(kind="BG_MUSIC", text="test"), MagicMock(kind="BG_MUSIC", text="test")]
        producer._render_bg_segment = AsyncMock(return_value=np.zeros(100, dtype=np.float32))
        with patch('src.lobes.creative.audiobook_producer.parse_script', return_value=mock_segs), \
             patch('src.lobes.creative.audiobook_producer.sf.write'), patch('src.lobes.creative.audio_utils.wav_to_mp3'), \
             patch('src.lobes.creative.generators.get_generator'):
            await producer.produce("dummy", str(tmp_path / "out.mp3"))
        assert getattr(producer._render_bg_segment, "call_count", 0) == 1

    @pytest.mark.asyncio
    async def test_render_bg_music_sfx(self, producer):
        producer._voice_cache_dir = "/tmp"
        mock_gen = MagicMock()
        
        with patch('src.lobes.creative.audiobook_producer.sf.read') as mock_read, \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch('src.lobes.creative.generators.get_generator', return_value=mock_gen):
            mock_read.return_value = (np.zeros(24000, dtype=np.float32), 24000)
            
            # BG MUSIC
            bg_music = await producer._render_bg_segment(Segment("BG_MUSIC", "test", duration=1.0))
            assert bg_music is not None
            
            # BG SFX
            bg_sfx = await producer._render_bg_segment(Segment("BG_SFX", "test", duration=1.0))
            assert bg_sfx is not None
        
        # Force background engine empty response
        producer._render_music = AsyncMock(return_value=generate_silence(0.5, 24000))
        bg_empty = await producer._render_bg_segment(Segment("BG_MUSIC", "empty", duration=1.0))
        assert bg_empty is not None

    @pytest.mark.asyncio
    async def test_render_narration_fallback_qwen(self, producer):
        # Remove kokoro
        producer.bot.voice_manager.synthesizer.kokoro = None
        producer._render_dialogue = AsyncMock(return_value=np.zeros(24000))
        
        res = await producer._render_narration("Test")
        producer._render_dialogue.assert_called_once()

    def test_resample(self, producer):
        audio = np.ones(24000)
        # Same rate
        np.testing.assert_array_equal(producer._resample(audio, 24000, 24000), audio)
        
        # Stereo to mono + resample
        stereo = np.ones((24000, 2))
        resampled = producer._resample(stereo, 24000, 12000)
        assert len(resampled) == 12000

    @pytest.mark.asyncio
    async def test_render_dialogue_cache_miss_and_hit(self, producer):
        producer._voice_cache_dir = "/tmp"
        mock_gen = MagicMock()
        mock_gen.generate_speech.return_value = "dummy.wav"

        with patch('src.lobes.creative.audiobook_producer.sf.read') as mock_read, \
             patch('os.path.exists', return_value=True), \
             patch('os.remove'), \
             patch('shutil.copy2'), \
             patch('src.lobes.creative.generators.get_generator', return_value=mock_gen):
            mock_read.return_value = (np.zeros(24000, dtype=np.float32), 24000)
            
            # First call (design)
            await producer._render_dialogue("Test", "Bob", "Voice")
            assert "Bob" in producer._voice_cache
            
            # Second call (clone)
            await producer._render_dialogue("Test", "Bob", "Voice")

    def test_cleanup_voice_cache(self, producer, tmp_path):
        producer._voice_cache_dir = str(tmp_path)
        
        ref = tmp_path / "ref_bob.wav"
        ref.write_text("audio")
        
        tmp = tmp_path / "seg_bob_123.wav"
        tmp.write_text("audio")
        
        producer._cleanup_voice_cache()
        assert ref.exists()
        assert not tmp.exists()

    def test_cleanup_voice_cache_exception(self, producer, monkeypatch):
        # Trigger 697 if `not self._voice_cache_dir`
        producer._voice_cache_dir = ""
        producer._cleanup_voice_cache()

        # Build mock files for iterdir where unlink throws OSError to cover line 706
        producer._voice_cache_dir = "/tmp"
        mock_file1 = MagicMock()
        mock_file1.name = "cache_file.wav"
        mock_file1.unlink.side_effect = OSError("Access denied")
        
        with patch('pathlib.Path.iterdir', return_value=[mock_file1]):
            producer._cleanup_voice_cache()

        # iterdir crash 708
        producer._voice_cache_dir = "/some/cache"
        with patch('pathlib.Path.iterdir', side_effect=Exception("Iter crash")):
            producer._cleanup_voice_cache()

    @pytest.mark.asyncio
    @patch('src.lobes.creative.generators.get_generator')
    async def test_produce_cleanup_exceptions(self, mock_gen_factory, producer, tmp_path):
        """Coverage for specific try/except blocks in generators and OS actions."""
        # Setup mock gen that raises on unload
        mock_gen = MagicMock()
        mock_gen.unload_musicgen.side_effect = Exception("Unload failed")
        mock_gen_factory.return_value = mock_gen
        
        script = "[NARRATE] Just one line."
        with patch('src.lobes.creative.audiobook_producer.sf.read') as mock_read, \
             patch('src.lobes.creative.audiobook_producer.sf.write'), \
             patch('src.lobes.creative.audio_utils.wav_to_mp3'):
            mock_read.return_value = (np.zeros(24000, dtype=np.float32), 24000)
            res = await producer.produce(script, str(tmp_path / "out.mp3"))
        # Should gracefully ignore unload fail
        assert res.endswith("out.mp3")

    @pytest.mark.asyncio
    async def test_segment_exceptions_and_limits(self, producer, tmp_path):
        # Force a segment render exception locally
        producer._render_segment = AsyncMock(side_effect=Exception("Render boom"))
        script = "[NARRATE] Line 1\\n[PAUSE: 1s]"
        with patch('src.lobes.creative.audiobook_producer.sf.write'), \
             patch('src.lobes.creative.audio_utils.wav_to_mp3'):
             # Line 412-417 branch (catch exception, add silence dummy)
             res = await producer.produce(script, str(tmp_path / "err.mp3"))
        assert res.endswith("err.mp3")

    @pytest.mark.asyncio
    @patch('src.lobes.creative.generators.get_generator')
    async def test_render_music_exceptions(self, mock_gen_factory, producer):
        # Force SF/OS exception in music remove path
        producer._voice_cache_dir = "/tmp"
        mock_gen = MagicMock()
        mock_gen.generate_music.return_value = "music.wav"
        mock_gen_factory.return_value = mock_gen
        
        # Test 1: Exception during generate (returns silence)
        mock_gen.generate_music.side_effect = Exception("Internal gen crash")
        clip = await producer._render_music("Prompt", 1.0)
        assert len(clip) == 24000
        
        # Test 2: Generate returns None (invalid audio path)
        mock_gen.generate_music.side_effect = None
        mock_gen.generate_music.return_value = None
        clip3 = await producer._render_music("Prompt", 1.0)
        assert len(clip3) == 24000
        
        # Test 3: Exception removing file (suppressed)
        mock_gen.generate_music.return_value = "music.wav"
        with patch('src.lobes.creative.audiobook_producer.sf.read', return_value=(np.zeros(24000, np.float32), 24000)), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove', side_effect=OSError("No delete")):
             clip = await producer._render_music("Prompt bg", 1.0)
             assert len(clip) > 0
             
    @pytest.mark.asyncio
    async def test_render_segment_invalid_kind(self, producer):
        # Kind UNKNOWN coverage
        from src.lobes.creative.audiobook_producer import Segment
        seg = Segment(kind="UNKNOWN", text="Test")
        res = await producer._render_segment(seg)
        assert res is None

        # Kind PAUSE line 487 coverage
        seg_pause = Segment(kind="PAUSE", duration=0.2)
        res_pause = await producer._render_segment(seg_pause)
        assert res_pause is not None

    @pytest.mark.asyncio
    @patch('src.lobes.creative.generators.get_generator')
    async def test_render_dialogue_exceptions(self, mock_gen_factory, producer):
        # Force OS remove exception in dialogue loop
        producer._voice_cache_dir = "/tmp"
        mock_gen = MagicMock()
        mock_gen.generate_speech.return_value = "dialogue.wav"
        mock_gen_factory.return_value = mock_gen
        
        with patch('src.lobes.creative.audiobook_producer.sf.read') as mock_read, \
             patch('os.path.exists', return_value=True), \
             patch('os.remove', side_effect=OSError("No delete")), \
             patch('shutil.copy2'):
             mock_read.return_value = (np.zeros(24000, np.float32), 24000)
             clip = await producer._render_dialogue("Text", "Bob3", "Voice")
             assert clip is not None

        # Force unreadable generated speech
        with patch('src.lobes.creative.audiobook_producer.sf.read', side_effect=Exception("Bad file format")), \
             patch('os.path.exists', return_value=True):
             clip = await producer._render_dialogue("Text", "BobException", "Voice")
             # Should return generic silence fallback
             assert clip is not None

    @pytest.mark.asyncio
    @patch('src.lobes.creative.generators.get_generator')
    async def test_design_voice_delete_exception(self, mock_gen_factory, producer):
        producer._voice_cache_dir = "/tmp"
        mock_gen = MagicMock()
        mock_gen.generate_speech.return_value = "dialogue.wav"
        mock_gen_factory.return_value = mock_gen
        
        # Override file logic completely
        with patch('src.lobes.creative.audiobook_producer.sf.read', return_value=(np.zeros(24000, np.float32), 24000)), \
             patch('os.path.exists', return_value=True), \
             patch('os.path.join', return_value="/tmp/some_voice.wav"), \
             patch('os.remove', side_effect=OSError("No delete")), \
             patch('shutil.copy2'):
             
             # Call first time to create entry (covers 620-621 with OSError mocked)
             clip = await producer._render_dialogue("Text", "DesignExcept2", "Voice")
             assert clip is not None

    @pytest.mark.asyncio
    @patch('src.lobes.creative.generators.get_generator')
    async def test_no_audio_produced_error(self, mock_gen_factory, producer, tmp_path):
        # Return empty foreground clip array gracefully bypassing exceptions
        script = "[NARRATE] Dummy"
        producer._render_segment = AsyncMock(return_value=None)
        res = await producer.produce(script, str(tmp_path / "out.mp3"))
        assert "Error: No audio segments were generated." in res

    @pytest.mark.asyncio
    async def test_narration_exception_log(self, producer):
        # Override kokoro to throw explicitly inside loop
        producer.bot.voice_manager.synthesizer.kokoro.create.side_effect = Exception("Boom")
        clip = await producer._render_narration("Text")
        # Should yield silence due to fallback error list handling
        assert clip is not None
