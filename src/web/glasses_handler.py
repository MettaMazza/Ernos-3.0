"""
Ernos Glasses Handler — WebSocket bridge for Meta Ray-Ban smart glasses.

Handles the full pipeline:
  1. Receive binary PCM audio chunks from glasses mic
  2. Receive JPEG frames from glasses camera
  3. On end-of-speech: transcribe audio → text
  4. Process through full Ernos Cognition Engine (with visual context)
  5. Synthesize response → stream PCM audio back to glasses speaker

Protocol:
  Client → Server:
    Binary frames:  Raw PCM audio (16kHz, 16-bit, mono, 100ms chunks)
    JSON:           {"type": "frame", "jpeg": "<base64>"}
    JSON:           {"type": "end_of_speech"}
    JSON:           {"type": "ping"}

  Server → Client:
    Binary frames:  Raw PCM audio response (24kHz, 16-bit, mono)
    JSON:           {"type": "text", "content": "..."}
    JSON:           {"type": "thinking"}
    JSON:           {"type": "done"}
    JSON:           {"type": "pong"}
    JSON:           {"type": "error", "message": "..."}
"""
import asyncio
import base64
import json
import logging
import time
from collections import deque
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from src.web.stt import AudioAccumulator, transcribe
from src.web.tts import synthesize_streaming

logger = logging.getLogger("Glasses.Handler")

# Ring buffer size for camera frames
MAX_FRAME_BUFFER = 3


class GlassesSession:
    """Manages state for a single glasses WebSocket connection."""

    def __init__(self, user_id: str, username: str, discord_id: str = ""):
        self.user_id = user_id
        self.username = username
        self.discord_id = discord_id
        self.audio = AudioAccumulator(sample_rate=16000, channels=1, sample_width=2)
        self.frames: deque = deque(maxlen=MAX_FRAME_BUFFER)
        self.is_processing = False
        self.connected_at = time.time()
        self.turns_processed = 0

    def add_frame(self, jpeg_b64: str):
        """Store a camera frame (base64 JPEG)."""
        try:
            jpeg_bytes = base64.b64decode(jpeg_b64)
            self.frames.append(jpeg_bytes)
        except Exception as e:
            logger.warning(f"Invalid JPEG frame: {e}")

    @property
    def latest_frame(self) -> Optional[bytes]:
        """Get the most recent camera frame, if any."""
        return self.frames[-1] if self.frames else None


async def handle_glasses_session(websocket: WebSocket, bot):
    """
    Main handler for a glasses WebSocket connection.

    Authenticates via JWT token, then runs the audio/video processing loop.
    """
    await websocket.accept()

    # ─── Authentication ──────────────────────────────────────────
    # Expect token as query param: /ws/glasses?token=JWT
    token = websocket.query_params.get("token")
    if not token:
        await websocket.send_json({"type": "error", "message": "Authentication required. Pass ?token=JWT"})
        await websocket.close(code=4001, reason="No auth token")
        return

    # Validate JWT
    try:
        from src.web.auth import verify_token
        is_valid, payload = verify_token(token)
        if not is_valid or not payload:
            await websocket.send_json({"type": "error", "message": "Invalid or expired token"})
            await websocket.close(code=4001, reason="Auth failed")
            return
        # Prefer discord_id for hippocampus recall — links glasses context
        # to the user's private DM conversation history
        discord_id = payload.get("discord_id", "")
        user_id = discord_id if discord_id else payload.get("sub", "glasses-user")
        username = payload.get("email", "Glasses User")
    except Exception as e:
        logger.warning(f"Glasses auth failed: {e}")
        await websocket.send_json({"type": "error", "message": f"Invalid token: {e}"})
        await websocket.close(code=4001, reason="Auth failed")
        return

    session = GlassesSession(user_id=user_id, username=username, discord_id=discord_id)
    logger.info(f"🕶️ Glasses connected: {username} ({user_id})")

    await websocket.send_json({
        "type": "connected",
        "user": username,
        "message": "Ernos glasses bridge active. Speak or send frames."
    })

    # ─── Main Loop ───────────────────────────────────────────────
    try:
        while True:
            message = await websocket.receive()

            # Handle disconnect message
            if message.get("type") == "websocket.disconnect":
                break

            # Binary frame = raw PCM audio
            if "bytes" in message and message["bytes"]:
                if not session.is_processing:
                    session.audio.add_chunk(message["bytes"])

            # Text frame = JSON control message
            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")

                if msg_type == "frame":
                    # Camera frame
                    jpeg_b64 = data.get("jpeg", "")
                    if jpeg_b64:
                        session.add_frame(jpeg_b64)

                elif msg_type == "end_of_speech":
                    mode = data.get("mode", "full")
                    if session.audio.has_audio and not session.is_processing:
                        if mode == "wake_word":
                            # Quick transcription check for wake word only
                            await _check_wake_word(websocket, session)
                        else:
                            await _process_turn(websocket, bot, session)

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"🕶️ Glasses disconnected: {username} ({session.turns_processed} turns)")
    except RuntimeError as e:
        # Starlette raises this if receive() is called after disconnect
        if "disconnect" in str(e).lower():
            logger.info(f"🕶️ Glasses disconnected: {username} ({session.turns_processed} turns)")
        else:
            logger.error(f"Glasses session runtime error: {e}")
    except Exception as e:
        logger.error(f"Glasses session error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


async def _check_wake_word(websocket: WebSocket, session: GlassesSession):
    """
    Quick wake word check: transcribe audio and look for 'Ernie'.
    No full cognition — just a fast Whisper transcription.
    """
    try:
        text = await transcribe(session.audio)
        session.audio.clear()

        if not text:
            await websocket.send_json({"type": "done"})
            return

        # Check for wake word variants
        normalized = text.strip().lower()
        wake_words = ["ernie", "erny", "earnie", "erne", "hey ernie", "hey erny"]
        detected = any(w in normalized for w in wake_words)

        if detected:
            logger.info(f"🕶️ Wake word detected: \"{text}\"")
            # Strip the wake word from the text and send the rest as content
            remaining = normalized
            for w in wake_words:
                remaining = remaining.replace(w, "").strip()
            await websocket.send_json({
                "type": "wake_word_detected",
                "remaining_text": remaining.strip(", .!?")
            })
        else:
            # Not a wake word — discard silently
            await websocket.send_json({"type": "done"})

    except Exception as e:
        logger.error(f"Wake word check error: {e}")
        session.audio.clear()
        await websocket.send_json({"type": "done"})


async def _process_turn(websocket: WebSocket, bot, session: GlassesSession):
    """
    Process a complete speech turn:
      1. Transcribe audio
      2. Run through Ernos cognition
      3. Synthesize and stream response audio
    """
    session.is_processing = True

    try:
        # ─── Step 1: Transcribe ──────────────────────────────────
        await websocket.send_json({"type": "thinking"})

        text = await transcribe(session.audio)
        session.audio.clear()

        if not text:
            await websocket.send_json({"type": "done"})
            return

        logger.info(f"🕶️ [{session.username}] Said: \"{text}\"")

        # ─── Step 2: Prepare visual context ──────────────────────
        images = None
        if session.latest_frame:
            images = [session.latest_frame]
            logger.info(f"🕶️ Attaching camera frame ({len(session.latest_frame)} bytes)")

        # ─── Step 3: Process through Ernos ───────────────────────
        # Run keepalive pings concurrently to prevent WebSocket timeout
        # during long cognition (can be 18+ seconds)
        from src.web.web_chat_handler import handle_web_message

        async def _keepalive():
            """Send pings + thinking signals every 5s during processing."""
            try:
                while True:
                    await asyncio.sleep(5)
                    await websocket.send_json({"type": "thinking"})
            except (asyncio.CancelledError, Exception):
                pass

        keepalive_task = asyncio.create_task(_keepalive())
        try:
            response_text, files = await handle_web_message(
                bot=bot,
                content=text,
                user_id=session.user_id,
                username=session.username,
                websocket=None,  # Don't stream text; we stream audio instead
                interaction_mode="default",  # Full Ernos personality
                images=images,
                platform="glasses",
            )
        finally:
            keepalive_task.cancel()

        if not response_text:
            response_text = "I didn't catch that. Could you say it again?"

        logger.info(f"🕶️ [{session.username}] Ernos: \"{response_text[:80]}...\"")

        # Send text version (for on-screen display if app supports it)
        await websocket.send_json({"type": "text", "content": response_text})

        # ─── Mirror to Chat tab and Discord DMs ──────────────────
        try:
            # Mirror to active Chat tab WebSocket
            from src.web.web_server import get_active_connections
            connections = get_active_connections()
            chat_ws = connections.get(session.user_id)
            if chat_ws:
                try:
                    await chat_ws.send_json({
                        "type": "message",
                        "role": "user",
                        "content": f"🕶️ {text}",
                        "source": "glasses",
                    })
                    await chat_ws.send_json({
                        "type": "message",
                        "role": "assistant",
                        "content": response_text,
                        "source": "glasses",
                    })
                except Exception:
                    pass  # Chat tab may have disconnected

            # Mirror to Discord DMs if user has linked Discord
            if session.discord_id and bot:
                try:
                    discord_user = bot.get_user(int(session.discord_id))
                    if discord_user:
                        dm = await discord_user.create_dm()
                        await dm.send(f"🕶️ *You said (via glasses):* {text}\n\n{response_text}")
                    else:
                        logger.debug(f"Discord user {session.discord_id} not in cache")
                except Exception as mirror_err:
                    logger.warning(f"Discord DM mirror failed: {mirror_err}")
        except Exception as mirror_err:
            logger.debug(f"Chat mirror failed: {mirror_err}")

        # ─── Step 4: Synthesize and stream audio ─────────────────
        chunks_sent = 0
        async for audio_chunk in synthesize_streaming(response_text):
            await websocket.send_bytes(audio_chunk)
            chunks_sent += 1
            # Small yield to prevent starving the event loop
            if chunks_sent % 10 == 0:
                await asyncio.sleep(0)

        await websocket.send_json({"type": "done"})
        session.turns_processed += 1

        logger.info(
            f"🕶️ Turn {session.turns_processed} complete for {session.username} "
            f"({chunks_sent} audio chunks sent)"
        )

    except (WebSocketDisconnect, RuntimeError) as e:
        # Client disconnected during processing — this is normal
        logger.info(f"🕶️ Client disconnected during turn: {session.username}")
    except Exception as e:
        logger.error(f"Turn processing error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": f"Processing error: {str(e)[:200]}"})
        except Exception:
            pass  # Can't send error if connection is already dead

    finally:
        session.is_processing = False
