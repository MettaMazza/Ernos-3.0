import logging
import asyncio
import os
import numpy as np
import soundfile as sf
from config import settings
import time

try:
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False

logger = logging.getLogger("Voice.Synthesizer")

import re

# Suppress noisy phonemizer warnings
logging.getLogger("phonemizer").setLevel(logging.ERROR)

class AudioSynthesizer:
    def __init__(self):
        self.kokoro = None
        if KOKORO_AVAILABLE:
            try:
                # Initialize Kokoro with paths from settings
                if not os.path.exists(settings.KOKORO_MODEL_PATH):
                    logger.error(f"Kokoro Model not found at: {settings.KOKORO_MODEL_PATH}")
                    return
                if not os.path.exists(settings.KOKORO_VOICES_PATH):
                    logger.error(f"Kokoro Voices not found at: {settings.KOKORO_VOICES_PATH}")
                    return

                logger.info("Initializing Kokoro ONNX...")
                self.kokoro = Kokoro(settings.KOKORO_MODEL_PATH, settings.KOKORO_VOICES_PATH)
                logger.info(f"Kokoro Initialized. Default Voice: {settings.KOKORO_DEFAULT_VOICE}")
            except Exception as e:
                logger.error(f"Failed to initialize Kokoro: {e}")
        else:
            logger.warning("kokoro-onnx not installed. Voice generation disabled.")

    def _sanitize_text(self, text: str) -> str:
        """Strips emojis, markdown, and non-spoken characters."""
        # Remove URLs
        text = re.sub(r'http\S+', '', text)
        # Remove markdown characters
        text = re.sub(r'[\#\*\_\(\)\[\]]', '', text)
        # Remove ALL Unicode emojis and symbol blocks
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # Emoticons
            "\U0001F300-\U0001F5FF"  # Misc symbols & pictographs
            "\U0001F680-\U0001F6FF"  # Transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # Flags
            "\U0001F900-\U0001F9FF"  # Supplemental symbols
            "\U0001FA00-\U0001FA6F"  # Chess, extended-A
            "\U0001FA70-\U0001FAFF"  # Extended-A continued
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0000257F"  # Enclosed chars & box drawing
            "\U0000FE00-\U0000FE0F"  # Variation selectors
            "\U0000200D"             # Zero-width joiner
            "\U00002600-\U000026FF"  # Misc symbols (sun, stars, sparkles)
            "\U00002300-\U000023FF"  # Misc technical
            "\U00002B50-\U00002B55"  # Stars
            "\U000023CF-\U000023F3"  # APL/keyboard symbols
            "\U0000203C-\U00003299"  # CJK symbols & enclosed
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def generate_audio(self, text: str, output_path: str) -> str:
        """
        Generates audio using Kokoro ONNX and saves to output_path.
        """
        if not text:
            return None
        
        # Sanitize
        text = self._sanitize_text(text)
        if not text:
            logger.warning("Text empty after sanitization.")
            return None

        if not self.kokoro:
            logger.error("Kokoro engine not available.")
            return None

        try:
            # Run in executor to avoid blocking main loop
            # Kokoro.create returns (samples, sample_rate)
            logger.info(f"Synthesizing: '{text[:30]}...' ({settings.KOKORO_DEFAULT_VOICE})")
            
            # Using default voice 'am_michael' from settings
            samples, sample_rate = await asyncio.to_thread(
                self.kokoro.create,
                text,
                voice=settings.KOKORO_DEFAULT_VOICE,
                speed=1.0,
                lang="en-us"
            )
            
            # Save using soundfile
            await asyncio.to_thread(
                sf.write,
                output_path,
                samples,
                sample_rate
            )
            
            logger.info(f"Audio saved to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"TTS Generation failed: {e}")
            return None

    async def stream_audio(self, text: str):
        """Generates and yields raw PCM chunks (int16, 24kHz)."""
        if not text: return
        text = self._sanitize_text(text)
        if not text: return
        
        if not self.kokoro:
            logger.error("Kokoro engine not available for streaming.")
            return

        try:
            # Note: For real streaming, we would use kokoro.create_stream if available.
            # Currently, we generate the full array and yield chunks to simulate the interface.
            samples, _ = await asyncio.to_thread(
                self.kokoro.create, text, voice=settings.KOKORO_DEFAULT_VOICE, speed=1.0, lang="en-us"
            )
            # Convert float32 to int16
            int_samples = (samples * 32767).astype(np.int16)
            
            # Yield in 960-byte (480 sample) chunks to match RawPCMSource requirements
            chunk_size = 480
            for i in range(0, len(int_samples), chunk_size):
                yield int_samples[i:i + chunk_size].tobytes()
        except Exception as e:
            logger.error(f"TTS Stream failed: {e}")
