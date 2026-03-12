"""
Ernos Glasses STT — Speech-to-Text using SpeechRecognition.

Uses Google's free speech recognition API (no API key needed).
Accumulates raw PCM audio chunks, converts to WAV, and transcribes.
"""
import asyncio
import io
import logging
import struct
import wave

import speech_recognition as sr

logger = logging.getLogger("Glasses.STT")


class AudioAccumulator:
    """
    Accumulates raw PCM audio chunks and converts to WAV for transcription.
    
    Expected input: raw PCM, 16kHz, 16-bit, mono.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.chunks: list[bytes] = []
        self._total_bytes = 0

    def add_chunk(self, data: bytes):
        """Add a raw PCM audio chunk."""
        self.chunks.append(data)
        self._total_bytes += len(data)

    def clear(self):
        """Reset the accumulator."""
        self.chunks.clear()
        self._total_bytes = 0

    @property
    def has_audio(self) -> bool:
        """Check if we have enough audio to transcribe (at least 500ms)."""
        min_bytes = self.sample_rate * self.sample_width * self.channels // 2  # 500ms
        return self._total_bytes >= min_bytes

    @property
    def duration_ms(self) -> int:
        """Duration of accumulated audio in milliseconds."""
        if self._total_bytes == 0:
            return 0
        return int(self._total_bytes / (self.sample_rate * self.sample_width * self.channels) * 1000)

    def to_wav_bytes(self) -> bytes:
        """Convert accumulated PCM chunks to a WAV file in memory."""
        pcm_data = b"".join(self.chunks)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.sample_width)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_data)
        return buf.getvalue()


async def transcribe(accumulator: AudioAccumulator) -> str:
    """
    Transcribe accumulated audio using Google Speech Recognition (free, no key needed).

    Args:
        accumulator: AudioAccumulator with PCM audio data.

    Returns:
        Transcribed text, or empty string on failure.
    """
    if not accumulator.has_audio:
        logger.debug("Not enough audio to transcribe")
        return ""

    duration = accumulator.duration_ms
    logger.info(f"Transcribing {duration}ms of audio...")

    try:
        wav_bytes = accumulator.to_wav_bytes()

        recognizer = sr.Recognizer()
        audio_data = sr.AudioData(
            b"".join(accumulator.chunks),
            sample_rate=accumulator.sample_rate,
            sample_width=accumulator.sample_width,
        )

        # Run in thread to avoid blocking
        text = await asyncio.to_thread(
            recognizer.recognize_google, audio_data
        )

        logger.info(f"Transcription ({duration}ms): \"{text}\"")
        return text

    except sr.UnknownValueError:
        logger.debug("Speech not understood")
        return ""
    except sr.RequestError as e:
        logger.error(f"Google STT request failed: {e}")
        return ""
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return ""
