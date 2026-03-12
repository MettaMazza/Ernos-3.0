"""
Tests for src/lobes/creative/audio_utils.py — WAV→MP3 conversion and segment chaining.
Covers lines 23-48 and 66-94 (all previously uncovered).
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock


class TestWavToMp3:
    """Tests for wav_to_mp3 function."""

    def test_successful_conversion(self, tmp_path):
        from src.lobes.creative.audio_utils import wav_to_mp3
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")

        mock_result = MagicMock(returncode=0)
        with patch("src.lobes.creative.audio_utils.subprocess.run", return_value=mock_result):
            result = wav_to_mp3(str(wav_file))
            assert result.endswith(".mp3")
            assert "test.mp3" in result

    def test_ffmpeg_failure_returns_wav(self, tmp_path):
        from src.lobes.creative.audio_utils import wav_to_mp3
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")

        mock_result = MagicMock(returncode=1, stderr="conversion error")
        with patch("src.lobes.creative.audio_utils.subprocess.run", return_value=mock_result):
            result = wav_to_mp3(str(wav_file))
            assert result == str(wav_file)

    def test_ffmpeg_not_found(self, tmp_path):
        from src.lobes.creative.audio_utils import wav_to_mp3
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")

        with patch("src.lobes.creative.audio_utils.subprocess.run", side_effect=FileNotFoundError):
            result = wav_to_mp3(str(wav_file))
            assert result == str(wav_file)

    def test_ffmpeg_timeout(self, tmp_path):
        import subprocess
        from src.lobes.creative.audio_utils import wav_to_mp3
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")

        with patch("src.lobes.creative.audio_utils.subprocess.run",
                    side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=120)):
            result = wav_to_mp3(str(wav_file))
            assert result == str(wav_file)

    def test_cleanup_wav_oserror(self, tmp_path):
        from src.lobes.creative.audio_utils import wav_to_mp3
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"fake wav")

        mock_result = MagicMock(returncode=0)
        with patch("src.lobes.creative.audio_utils.subprocess.run", return_value=mock_result):
            with patch("src.lobes.creative.audio_utils.os.remove", side_effect=OSError("perm denied")):
                result = wav_to_mp3(str(wav_file))
                assert result.endswith(".mp3")


class TestChainAudioSegments:
    """Tests for chain_audio_segments function."""

    def test_empty_segments(self):
        from src.lobes.creative.audio_utils import chain_audio_segments
        result = chain_audio_segments([], 32000)
        assert len(result) == 0

    def test_single_segment(self):
        from src.lobes.creative.audio_utils import chain_audio_segments
        seg = np.ones(1000, dtype=np.float32)
        result = chain_audio_segments([seg], 32000)
        np.testing.assert_array_equal(result, seg)

    def test_two_segments_with_crossfade(self):
        from src.lobes.creative.audio_utils import chain_audio_segments
        seg1 = np.ones(64000, dtype=np.float32)
        seg2 = np.ones(64000, dtype=np.float32) * 0.5
        result = chain_audio_segments([seg1, seg2], 32000, crossfade_sec=2.0)
        # 64000 + 64000 - 64000 crossfade samples = 64000
        assert len(result) == 64000 + 64000 - int(2.0 * 32000)

    def test_three_segments(self):
        from src.lobes.creative.audio_utils import chain_audio_segments
        segs = [np.ones(64000, dtype=np.float32) * i for i in range(1, 4)]
        result = chain_audio_segments(segs, 32000, crossfade_sec=1.0)
        xfade = int(1.0 * 32000)
        expected_len = 64000 + 64000 - xfade + 64000 - xfade
        assert len(result) == expected_len

    def test_short_segments_no_crossfade(self):
        from src.lobes.creative.audio_utils import chain_audio_segments
        # Segments shorter than crossfade — should concatenate without crossfade
        seg1 = np.ones(100, dtype=np.float32)
        seg2 = np.ones(100, dtype=np.float32) * 2
        result = chain_audio_segments([seg1, seg2], 32000, crossfade_sec=2.0)
        assert len(result) == 200

    def test_zero_crossfade(self):
        from src.lobes.creative.audio_utils import chain_audio_segments
        seg1 = np.ones(1000, dtype=np.float32)
        seg2 = np.ones(1000, dtype=np.float32)
        result = chain_audio_segments([seg1, seg2], 32000, crossfade_sec=0.0)
        assert len(result) == 2000
