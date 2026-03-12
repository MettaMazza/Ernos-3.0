# Codebase Audit Report: `src/voice/`

This document details the line-by-line granular analysis of the `src/voice/` module in the Ernos 3.0 codebase.

## Objective Protocol
- Zero Assumptions
- Direct Code Extraction
- Granular Findings 

---

### File: `src/voice/__init__.py`
**Overview:** This file indicates `src/voice/` is a Python module.
**Finding:** It is completely empty.

### File: `src/voice/manager.py`
**Overview:** Manages Discord voice connections and audio playback via Kokoro TTS.

#### 1. `RawPCMSource` Definition
- **Functionality:** Extends `discord.AudioSource` to provide a streamable PCM source. It initializes with `self._buffer = asyncio.Queue()` to hold PCM chunks.
- **Reading Chunk Logic:** Reads 20ms audio frames (`3840` bytes for 48kHz, 16-bit, stereo) in its `read()` method.
- **Quote:** `"Read 20ms of audio (3840 bytes at 48kHz, 16-bit, stereo)."` and `end = min(self._offset + remaining, len(self._current_chunk))`
- **Padding Behavior:** Pads with silence if the queue is empty instead of stopping immediately, except if marked finished.
- **Quote:** `result += b"\x00" * (FRAME_SIZE - len(result))`

#### 2. `VoiceManager` class
- **Functionality:** Maintains a dictionary `self.active_connections: dict[int, discord.VoiceClient]` mapping discord guild IDs to `discord.VoiceClient` instances.
- **Joining Channels:** `join_channel` moves the bot if already connected in the guild, otherwise connects via `await channel.connect()`.
- **Quote:** `if vc.channel.id != channel.id: await vc.move_to(channel)`
- **Speech Synthesis Playback:** Centralized in the `speak` method which interrupts any existing playback (`if vc.is_playing(): vc.stop()`) and streams the `RawPCMSource`.
- **Cache Mechanism:** Implements a cache for generated audio files via `get_audio_path`. The cache sets up a directory depending on the environment (test or production).
- **Security/Test Path Logic:** Detects if running in a pytest context via `sys.modules`.
- **Quote:** `cache_dir = os.path.join(base_dir, "tests", "tmp") if "pytest" in sys.modules else os.path.join(base_dir, "memory", "cache", "tts")`
- **Cache Cleanup:** Deletes cached wav files older than a specified duration (`max_age_hours=24`).
- **Quote:** `file_age = now - os.path.getmtime(filepath); if file_age > (max_age_hours * 3600): os.remove(filepath)`

---

### File: `src/voice/synthesizer.py`
**Overview:** Wraps Kokoro ONNX to generate raw text-to-speech audio bytes and files.

#### 1. Import Handling
- **Functionality:** Imports `kokoro_onnx`. If the import fails, disables voice functionality but does not crash the application.
- **Quote:** `except ImportError: KOKORO_AVAILABLE = False`

#### 2. Text Sanitization
- **Functionality:** The `_sanitize_text` method removes URLs via regex, strips specific markdown characters, and systematically strips ALL unicode block emojis and symbols with a hardcoded regex pattern.
- **Quote:** `text = re.sub(r'http\S+', '', text)` and `text = emoji_pattern.sub('', text)`

#### 3. Audio Generation (`generate_audio`)
- **Functionality:** Dispatches the Kokoro generation process to an executor thread to prevent blocking the main asyncio event loop.
- **Threading/Concurrency:** `await asyncio.to_thread` wraps the synchronous `self.kokoro.create` and `sf.write` calls.
- **Quote:** `samples, sample_rate = await asyncio.to_thread(self.kokoro.create, text, voice=settings.KOKORO_DEFAULT_VOICE, speed=1.0, lang="en-us")`

#### 4. Audio Streaming (`stream_audio`)
- **Functionality:** Returns an async generator yielding 960-byte chunks of int16 audio for Discord streaming.
- **Type Conversion:** Multiplies the `float32` sample array by 32767 and converts to `int16`.
- **Quote:** `int_samples = (samples * 32767).astype(np.int16)` and `yield int_samples[i:i + chunk_size].tobytes()`

---

### File: `src/voice/transcriber.py`
**Overview:** Implements speech-to-text using `speech_recognition` module.

#### 1. Initializer
- **Functionality:** Instantiates `sr.Recognizer()`.
- **Quote:** `self.recognizer = sr.Recognizer()`

#### 2. Transcribing Audio
- **Functionality:** Reads from an audio file and executes Google Web Speech API for transcription.
- **Threading/Concurrency:** Employs `loop.run_in_executor` to execute the blocking synchronous `recognize_google` function natively as an async operation.
- **Quote:** `with sr.AudioFile(audio_path) as source: audio = self.recognizer.record(source)` and `text = await loop.run_in_executor(None, self.recognizer.recognize_google, audio)`
- **Error Handling:** Returns clear string tags upon errors rather than raising exceptions up the stack.
- **Quote:** `except sr.UnknownValueError: return "[Audio Unintelligible]"` and `except sr.RequestError as e: return f"[Transcription Service Error: {e}]"`
