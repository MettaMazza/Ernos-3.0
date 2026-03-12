"""
Ernos Glasses TTS — Text-to-Speech using Kokoro ONNX.

Pre-loads Kokoro at import time and streams audio per sentence
for minimal latency during glasses/voice calls.
"""
import asyncio
import logging
import re

import numpy as np

logger = logging.getLogger("Glasses.TTS")

# Target output format for glasses app
OUTPUT_SAMPLE_RATE = 24000
OUTPUT_CHANNELS = 1
OUTPUT_SAMPLE_WIDTH = 2  # 16-bit
CHUNK_DURATION_MS = 100  # Stream in 100ms chunks
CHUNK_SAMPLES = OUTPUT_SAMPLE_RATE * CHUNK_DURATION_MS // 1000

# ─── Pre-load Kokoro at module level ─────────────────────────────
# This avoids lazy-loading on first call which adds 1-2s latency.
_synth = None

def _get_synth():
    """Get or create the pre-loaded AudioSynthesizer singleton."""
    global _synth
    if _synth is None:
        try:
            from src.voice.synthesizer import AudioSynthesizer
            _synth = AudioSynthesizer()
            if _synth.kokoro:
                logger.info("Kokoro TTS pre-loaded and ready for glasses streaming")
            else:
                logger.warning("Kokoro engine not available for glasses TTS")
        except Exception as e:
            logger.error(f"Failed to pre-load Kokoro: {e}")
    return _synth

# Trigger pre-load on import
try:
    _get_synth()
except Exception:
    pass  # Will retry on first call


def _split_sentences(text: str) -> list:
    """
    Split text into natural sentence boundaries for per-sentence TTS.
    Preserves punctuation for natural intonation.
    """
    # Split on sentence-ending punctuation followed by space or end
    parts = re.split(r'(?<=[.!?])\s+', text)
    # Merge very short fragments (< 10 chars) with the next sentence
    merged = []
    buffer = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if buffer:
            buffer += " " + part
        else:
            buffer = part
        # Only flush if we have a reasonable sentence length
        if len(buffer) >= 10:
            merged.append(buffer)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] += " " + buffer
        else:
            merged.append(buffer)
    return merged


async def synthesize_streaming(text: str):
    """
    Synthesize text to speech using Kokoro ONNX and stream as raw PCM chunks.

    Splits the response into sentences and synthesizes each one independently,
    streaming audio chunks as soon as each sentence is ready. This means the
    user hears the first sentence while later sentences are still being generated.

    Yields raw PCM audio: 24kHz, 16-bit, mono — matching the glasses app's expected format.
    """
    if not text:
        return

    synth = _get_synth()
    if not synth or not synth.kokoro:
        logger.error("Kokoro engine not available — cannot synthesize for glasses")
        return

    # Sanitize text
    clean_text = synth._sanitize_text(text)
    if not clean_text:
        logger.warning("Text empty after sanitization")
        return

    from config import settings

    sentences = _split_sentences(clean_text)
    logger.info(f"Synthesizing for glasses: '{clean_text[:50]}...' ({len(sentences)} sentences)")

    total_chunks = 0
    total_bytes = 0

    for i, sentence in enumerate(sentences):
        if not sentence.strip():
            continue

        try:
            # Generate audio for this sentence
            samples, sample_rate = await asyncio.to_thread(
                synth.kokoro.create,
                sentence,
                voice=settings.KOKORO_DEFAULT_VOICE,
                speed=1.0,
                lang="en-us",
            )

            # Resample to 24kHz if needed
            if sample_rate != OUTPUT_SAMPLE_RATE:
                ratio = OUTPUT_SAMPLE_RATE / sample_rate
                new_length = int(len(samples) * ratio)
                indices = np.linspace(0, len(samples) - 1, new_length)
                samples = np.interp(indices, np.arange(len(samples)), samples)

            # Convert float32 [-1, 1] to int16 PCM
            samples = np.clip(samples, -1.0, 1.0)
            pcm_samples = (samples * 32767).astype(np.int16)
            pcm_bytes = pcm_samples.tobytes()

            # Stream in chunks
            chunk_size = CHUNK_SAMPLES * OUTPUT_SAMPLE_WIDTH
            for j in range(0, len(pcm_bytes), chunk_size):
                chunk = pcm_bytes[j:j + chunk_size]
                yield chunk
                total_chunks += 1
                total_bytes += len(chunk)
                # Yield control periodically
                if total_chunks % 5 == 0:
                    await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"TTS sentence {i+1} failed: {e}")
            continue

    logger.info(f"Streamed {total_chunks} audio chunks ({total_bytes} bytes total)")
