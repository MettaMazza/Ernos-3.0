"""
Audio utilities — WAV→MP3 conversion and segment chaining for Ernos.
"""
import logging
import os
import subprocess
import numpy as np

logger = logging.getLogger("AudioUtils")


def wav_to_mp3(wav_path: str, bitrate: str = "192k") -> str:
    """
    Convert WAV to MP3 using ffmpeg for Discord-friendly file sizes.
    
    Args:
        wav_path: Path to source WAV file
        bitrate: MP3 bitrate (default 192k, good quality/size balance)
    
    Returns:
        Path to the converted MP3 file
    """
    mp3_path = wav_path.rsplit(".", 1)[0] + ".mp3"
    
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-b:a", bitrate, "-q:a", "2", mp3_path],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error(f"ffmpeg conversion failed: {result.stderr[:300]}")
            return wav_path  # Fallback: return original WAV
        
        # Clean up WAV
        try:
            os.remove(wav_path)
        except OSError as e:
            logger.warning(f"Suppressed {type(e).__name__}: {e}")
        
        logger.info(f"Converted {wav_path} → {mp3_path}")
        return mp3_path
        
    except FileNotFoundError:
        logger.warning("ffmpeg not found — returning WAV directly")
        return wav_path
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg conversion timed out")
        return wav_path


def chain_audio_segments(segments: list, sample_rate: int, crossfade_sec: float = 2.0) -> np.ndarray:
    """
    Chain multiple audio segments with crossfade for seamless longer compositions.
    
    Used when requested duration exceeds MusicGen's single-pass limit (~30s).
    Each segment overlaps by crossfade_sec for smooth transitions.
    
    Args:
        segments: List of numpy arrays (audio waveforms)
        sample_rate: Audio sample rate (e.g. 32000)
        crossfade_sec: Seconds of overlap between segments
    
    Returns:
        Single concatenated audio numpy array
    """
    if len(segments) == 0:
        return np.array([], dtype=np.float32)
    if len(segments) == 1:
        return segments[0]
    
    crossfade_samples = int(crossfade_sec * sample_rate)
    
    result = segments[0]
    for i in range(1, len(segments)):
        seg = segments[i]
        
        if crossfade_samples > 0 and len(result) >= crossfade_samples and len(seg) >= crossfade_samples:
            # Linear crossfade
            fade_out = np.linspace(1.0, 0.0, crossfade_samples, dtype=np.float32)
            fade_in = np.linspace(0.0, 1.0, crossfade_samples, dtype=np.float32)
            
            # Apply crossfade to overlap region
            overlap = result[-crossfade_samples:] * fade_out + seg[:crossfade_samples] * fade_in
            
            result = np.concatenate([
                result[:-crossfade_samples],
                overlap,
                seg[crossfade_samples:],
            ])
        else:
            # No crossfade (segments too short)
            result = np.concatenate([result, seg])
    
    return result
