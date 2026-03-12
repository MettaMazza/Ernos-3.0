"""
Ernos Web Server — FastAPI + WebSocket bridge.

Runs alongside the Discord bot, exposing Ernos's cognition engine
over WebSocket for the web chat interface.

Port: 8420 (configurable via WEB_PORT env var)

Auth endpoints:
  POST /api/auth/register     — Create account
  POST /api/auth/login        — Login → JWT
  POST /api/auth/refresh      — Refresh access token
  GET  /api/auth/me           — Current user info + tier
  GET  /api/auth/patreon      — Get Patreon OAuth URL
  GET  /api/auth/patreon/callback — Patreon OAuth callback
"""
import asyncio
import json
import logging
import os
import time
from typing import Dict, Set
from urllib.parse import parse_qs

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.websockets import WebSocketState
import uvicorn

from src.web.auth import create_token, verify_token, refresh_access_token
from src.web.accounts import register, login, get_account, update_tier, generate_discord_code, verify_discord_code
from src.web import patreon as patreon_module
from src.web.file_server import router as file_router

logger = logging.getLogger("Web.Server")

# ═══════════════════════════════════════════════════════════════════════
# FastAPI Application
# ═══════════════════════════════════════════════════════════════════════

app = FastAPI(title="Ernos Web API", version="2.0")
app.include_router(file_router)

# CORS — allow the Netlify frontend + local dev (including file:// origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://funny-cocada-0ff704.netlify.app",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8420",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8420",
        "null",  # file:// origins send "null"
    ],
    allow_origin_regex=r".*",  # Allow all origins during dev (tighten for prod)
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Global reference to bot (set during startup)
_bot = None
_active_connections: Dict[str, WebSocket] = {}


def set_bot(bot):
    """Set the bot reference. Called from main.py during startup."""
    global _bot
    _bot = bot
    logger.info("Web server: bot reference set")


# ═══════════════════════════════════════════════════════════════════════
# Helper: Extract and verify token from request
# ═══════════════════════════════════════════════════════════════════════

def _get_auth_user(request: Request):
    """Extract user from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    is_valid, payload = verify_token(token)
    if not is_valid:
        return None
    return payload


# ═══════════════════════════════════════════════════════════════════════
# REST Endpoints — Health & Status
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    """Health check for frontend connection indicator."""
    return {"status": "ok", "timestamp": time.time()}


@app.get("/api/status")
async def status():
    """Bot status — uptime, active engine, persona info."""
    if not _bot:
        return {"status": "starting", "engine": None}

    uptime = time.time() - getattr(_bot, "start_time", time.time())
    engine = None
    try:
        active = _bot.engine_manager.get_active_engine()
        engine = active.name if active else None
    except Exception:
        pass

    return {
        "status": "online",
        "uptime_seconds": int(uptime),
        "engine": engine,
        "processing_users": len(getattr(_bot, "processing_users", set())),
    }


# ═══════════════════════════════════════════════════════════════════════
# REST Endpoints — Auth
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/auth/register")
async def auth_register(request: Request):
    """Create a new account."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    email = data.get("email", "")
    password = data.get("password", "")
    username = data.get("username", "")

    success, message, user_id = register(email, password, username)
    if not success:
        return JSONResponse({"error": message}, status_code=400)

    # Auto-login: create tokens
    access_token = create_token(user_id=user_id, tier=0, email=email)
    refresh_tok = create_token(user_id=user_id, tier=0, email=email, token_type="refresh")

    return {
        "message": message,
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": refresh_tok,
    }


@app.post("/api/auth/login")
async def auth_login(request: Request):
    """Login and receive JWT tokens."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    email = data.get("email", "")
    password = data.get("password", "")

    success, message, account = login(email, password)
    if not success:
        return JSONResponse({"error": message}, status_code=401)

    # Create tokens
    access_token = create_token(
        user_id=account["user_id"],
        tier=account.get("tier", 0),
        email=account.get("email", ""),
        linked_discord_id=account.get("linked_discord_id", ""),
        linked_patreon_id=account.get("linked_patreon_id", ""),
    )
    refresh_tok = create_token(
        user_id=account["user_id"],
        tier=account.get("tier", 0),
        email=account.get("email", ""),
        token_type="refresh",
    )

    return {
        "message": message,
        "user": account,
        "access_token": access_token,
        "refresh_token": refresh_tok,
    }


@app.post("/api/auth/refresh")
async def auth_refresh(request: Request):
    """Refresh an access token."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    refresh_tok = data.get("refresh_token", "")
    new_access = refresh_access_token(refresh_tok)
    if not new_access:
        return JSONResponse({"error": "Invalid or expired refresh token"}, status_code=401)

    return {"access_token": new_access}


@app.get("/api/auth/me")
async def auth_me(request: Request):
    """Get current authenticated user info."""
    user = _get_auth_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # Fetch fresh account data
    account = get_account(user["sub"])
    if not account:
        return JSONResponse({"error": "Account not found"}, status_code=404)

    # Include flux status
    flux_status = None
    try:
        from src.core.flux_capacitor import FluxCapacitor
        fc = FluxCapacitor()
        flux_status = fc.get_status(hash(user["sub"]))
    except Exception:
        pass

    return {
        "user": account,
        "flux": flux_status,
    }


# ═══════════════════════════════════════════════════════════════════════
# REST Endpoints — Patreon OAuth
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/auth/patreon")
async def patreon_auth_url(request: Request):
    """Get Patreon OAuth URL for linking."""
    user = _get_auth_user(request)
    if not user:
        return JSONResponse({"error": "Login first to link Patreon"}, status_code=401)

    if not patreon_module.is_configured():
        return JSONResponse(
            {"error": "Patreon integration not configured. Set PATREON_CLIENT_ID and PATREON_CLIENT_SECRET."},
            status_code=503,
        )

    # Use user_id as state for CSRF + account linking
    url = patreon_module.get_auth_url(state=user["sub"])
    return {"auth_url": url}


@app.get("/api/auth/patreon/callback")
async def patreon_callback(request: Request):
    """Patreon OAuth callback — exchanges code for token, sets tier."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")  # user_id

    if not code or not state:
        return JSONResponse({"error": "Missing code or state"}, status_code=400)

    success, message, tier = await patreon_module.process_callback(
        code=code,
        user_id=state,
    )

    if success:
        # Redirect back to frontend with success
        return RedirectResponse(
            url=f"https://funny-cocada-0ff704.netlify.app/#patreon-linked&tier={tier}",
            status_code=302,
        )
    else:
        return JSONResponse({"error": message}, status_code=400)


# ═══════════════════════════════════════════════════════════════════════
# REST Endpoints — Discord Account Linking (Verified)
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/auth/discord/request")
async def discord_link_request(request: Request):
    """
    Request a Discord verification code.

    Sends a 6-digit code to the user's Discord DMs via the Ernos bot.
    Requires authenticated JWT.

    Body: {"discord_id": "1234567890"}
    """
    user = _get_auth_user(request)
    if not user:
        return JSONResponse({"error": "Login required"}, status_code=401)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    discord_id = str(data.get("discord_id", "")).strip()
    if not discord_id or not discord_id.isdigit():
        return JSONResponse({"error": "Invalid Discord ID. Use your numeric Discord User ID."}, status_code=400)

    # Generate code
    code = generate_discord_code(user_id=user["sub"], discord_id=discord_id)

    # Send DM via Ernos bot
    dm_sent = False
    if _bot:
        try:
            discord_user = await _bot.fetch_user(int(discord_id))
            if discord_user:
                await discord_user.send(
                    f"🌱 **ErnOS Verification Code**\n\n"
                    f"Your verification code is: **{code}**\n\n"
                    f"Enter this code in the ErnOS app to link your Discord account.\n"
                    f"This code expires in 5 minutes.\n\n"
                    f"If you didn't request this, you can safely ignore it."
                )
                dm_sent = True
                logger.info(f"Discord verification DM sent to {discord_id}")
        except Exception as e:
            logger.warning(f"Failed to send Discord DM to {discord_id}: {e}")

    if not dm_sent:
        return JSONResponse(
            {"error": "Couldn't send DM. Make sure Ernos is in a shared server with you and your DMs are open."},
            status_code=400,
        )

    return {"message": "Verification code sent to your Discord DMs. Check your messages!"}


@app.post("/api/auth/discord/verify")
async def discord_link_verify(request: Request):
    """
    Verify a Discord linking code and complete the link.

    Body: {"discord_id": "1234567890", "code": "123456"}

    On success, returns a new JWT with the discord_id included.
    """
    user = _get_auth_user(request)
    if not user:
        return JSONResponse({"error": "Login required"}, status_code=401)

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    discord_id = str(data.get("discord_id", "")).strip()
    code = str(data.get("code", "")).strip()

    if not discord_id or not code:
        return JSONResponse({"error": "discord_id and code are required"}, status_code=400)

    # Verify the code
    success, message = verify_discord_code(
        user_id=user["sub"],
        discord_id=discord_id,
        code=code,
    )

    if not success:
        return JSONResponse({"error": message}, status_code=400)

    # Fetch account for new token (may not exist for pre-existing token users)
    account = get_account(user["sub"])

    # Issue fresh JWT with discord_id — use account data if available, else JWT payload
    new_token = create_token(
        user_id=user["sub"],
        tier=account.get("tier", 0) if account else user.get("tier", 0),
        email=account.get("email", "") if account else user.get("email", ""),
        linked_discord_id=discord_id,
        linked_patreon_id=account.get("linked_patreon_id", "") if account else user.get("patreon_id", ""),
    )

    return {
        "message": message,
        "access_token": new_token,
        "discord_id": discord_id,
    }


# ═══════════════════════════════════════════════════════════════════════
# WebSocket Chat Endpoint (Auth-enforced)
# ═══════════════════════════════════════════════════════════════════════

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    Real-time chat with Ernos via WebSocket.

    Authentication:
        Connect with ?token=JWT to chat (required).
        Anonymous connections get read-only access (no chat).

    Protocol:
        Client → Server: {"type": "message", "content": "..."}
        Server → Client: {"type": "response", "content": "...", "files": [...]}
        Server → Client: {"type": "thinking", "step": N}
        Server → Client: {"type": "error", "message": "..."}
        Server → Client: {"type": "connected", "engine": "...", "user": {...}}
        Server → Client: {"type": "flux", "remaining": N, "limit": N, "tier": N}
    """
    await websocket.accept()

    # Authenticate via token query param
    token = websocket.query_params.get("token", "")
    user_id = None
    username = "Web User"
    tier = 0
    authenticated = False

    if token:
        is_valid, payload = verify_token(token)
        if is_valid:
            user_id = payload["sub"]
            tier = payload.get("tier", 0)
            username = payload.get("email", "Web User").split("@")[0]
            authenticated = True
        else:
            # Invalid token — still connect but read-only
            logger.warning("WebSocket connected with invalid token")

    if not user_id:
        user_id = f"anon-{id(websocket)}"

    _active_connections[user_id] = websocket
    logger.info(f"WebSocket connected: {user_id} (auth={authenticated}, tier={tier})")

    # Send connection confirmation
    try:
        engine_name = None
        try:
            active = _bot.engine_manager.get_active_engine()
            engine_name = active.name if active else "unknown"
        except Exception:
            pass

        await websocket.send_json({
            "type": "connected",
            "engine": engine_name,
            "message": "Connected to Ernos",
            "authenticated": authenticated,
            "user": {
                "user_id": user_id,
                "username": username,
                "tier": tier,
            } if authenticated else None,
        })
    except Exception:
        pass

    try:
        while True:
            # Receive message
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type != "message":
                continue

            # ── Anonymous rate limit (simple in-memory counter) ──
            # Authenticated users use the flux capacitor below.
            # Anonymous users get a generous but limited allowance.
            if not authenticated:
                from collections import defaultdict
                import time as _time

                # Simple per-IP/connection rate limit for anonymous users
                if not hasattr(websocket_chat, "_anon_counters"):
                    websocket_chat._anon_counters = {}  # {user_id: [timestamps]}

                now = _time.time()
                ANON_WINDOW = 900  # 15 minutes
                ANON_LIMIT = 5    # messages per window

                history = websocket_chat._anon_counters.get(user_id, [])
                # Prune old timestamps
                history = [t for t in history if now - t < ANON_WINDOW]

                if len(history) >= ANON_LIMIT:
                    await websocket.send_json({
                        "type": "error",
                        "message": "RATE_LIMITED",
                        "detail": (
                            "You've used your free visitor messages! "
                            "Create a free account to reset your limit and unlock more features."
                        ),
                        "prompt_signup": True,
                    })
                    continue

                history.append(now)
                websocket_chat._anon_counters[user_id] = history

            # ── Flux capacitor rate check (authenticated users) ──
            if authenticated:
                try:
                    from src.core.flux_capacitor import FluxCapacitor
                    fc = FluxCapacitor(_bot)
                    allowed, warning = fc.consume(hash(user_id))
                    if not allowed:
                        await websocket.send_json({
                            "type": "error",
                            "message": "RATE_LIMITED",
                            "detail": warning or "Message limit reached. Wait for your cycle to reset.",
                        })
                        continue
                    if warning:
                        await websocket.send_json({
                            "type": "flux",
                            "warning": warning,
                        })
                except Exception as e:
                    logger.debug(f"Flux check skipped: {e}")

            content = data.get("content", "").strip()
            if not content:
                continue

            # ── Input size limit (prevent abuse) ──
            if len(content) > 10000:
                await websocket.send_json({
                    "type": "error",
                    "message": "Message too long. Maximum 10,000 characters.",
                })
                continue

            # ── Persona mode switching (natural language) ──────
            # Per-session mode: defaults to "professional" for web visitors.
            # Users can say "/self", "be yourself", etc. to get the real Ernos.
            if not hasattr(websocket_chat, "_session_modes"):
                websocket_chat._session_modes = {}  # {user_id: "professional"|"default"}

            session_mode = websocket_chat._session_modes.get(user_id, "professional")

            # Check for mode-switching phrases
            content_lower = content.lower().strip()
            SWITCH_TO_CORE = [
                "/self", "be yourself", "speak as yourself",
                "drop the professional mode", "relax", "real ernos",
                "talk normally", "you don't need to be professional",
                "show me the real you", "core mode",
            ]
            SWITCH_TO_PROFESSIONAL = [
                "/professional", "professional mode", "be professional",
                "back to professional",
            ]

            mode_switched = False
            if any(content_lower == phrase or content_lower.startswith(phrase + " ") for phrase in SWITCH_TO_CORE):
                websocket_chat._session_modes[user_id] = "default"
                session_mode = "default"
                mode_switched = True
                await websocket.send_json({
                    "type": "system",
                    "message": "Switched to core personality mode. You're talking to the real Ernos now.",
                })
            elif any(content_lower == phrase or content_lower.startswith(phrase + " ") for phrase in SWITCH_TO_PROFESSIONAL):
                websocket_chat._session_modes[user_id] = "professional"
                session_mode = "professional"
                mode_switched = True
                await websocket.send_json({
                    "type": "system",
                    "message": "Switched to professional mode.",
                })

            # If the message was ONLY a switch command, don't process further
            if mode_switched and content_lower in SWITCH_TO_CORE + SWITCH_TO_PROFESSIONAL:
                continue

            # Send thinking indicator
            await websocket.send_json({"type": "thinking", "step": 0})

            # Process through Ernos cognition
            try:
                from src.web.web_chat_handler import handle_web_message

                response_text, files = await handle_web_message(
                    bot=_bot,
                    content=content,
                    user_id=user_id,
                    username=username,
                    websocket=websocket,
                    interaction_mode=session_mode,
                )

                # Send response
                if websocket.client_state == WebSocketState.CONNECTED:
                    file_urls = []
                    if files:
                        for f in files:
                            file_urls.append(str(f))

                    await websocket.send_json({
                        "type": "response",
                        "content": response_text or "I couldn't generate a response.",
                        "files": file_urls,
                    })

                    # Send flux status update
                    try:
                        fc = FluxCapacitor(_bot)
                        flux_status = fc.get_status(hash(user_id))
                        await websocket.send_json({
                            "type": "flux",
                            "remaining": flux_status.get("remaining", 0),
                            "limit": flux_status.get("limit", 20),
                            "tier": flux_status.get("tier", 0),
                        })
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"Chat processing error for {user_id}: {e}", exc_info=True)
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Processing error: {str(e)[:200]}",
                    })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {user_id}: {e}")
    finally:
        _active_connections.pop(user_id, None)



# ═══════════════════════════════════════════════════════════════════════
# WebSocket Game State Endpoint (read-only, unauthenticated)
# ═══════════════════════════════════════════════════════════════════════

@app.websocket("/ws/game")
async def websocket_game(websocket: WebSocket):
    """
    Real-time Minecraft game state stream.

    No authentication required (read-only observation).
    Sends game state every ~2 seconds while a session is active.

    Protocol:
        Server → Client: {"type": "state", "data": {...}}
        Server → Client: {"type": "offline", "message": "..."}
        Client → Server: {"type": "ping"} → {"type": "pong"}
    """
    await websocket.accept()
    logger.info("Game viewer connected")

    try:
        while True:
            # Check for client messages (ping/disconnect)
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=2.0
                )
                try:
                    data = json.loads(raw)
                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass
            except asyncio.TimeoutError:
                pass  # Normal — timeout means it's time to send state

            # Check if gaming session is active
            if not _bot or not hasattr(_bot, "gaming_agent") or not _bot.gaming_agent.is_running:
                await websocket.send_json({
                    "type": "offline",
                    "message": "Not currently playing",
                })
                continue

            # Get game state from the bridge
            agent = _bot.gaming_agent
            try:
                state_data = {}

                if agent.bridge and hasattr(agent.bridge, "get_bot_state"):
                    raw_state = await agent.bridge.get_bot_state()
                    if raw_state:
                        pos = raw_state.get("position", {})
                        state_data = {
                            "position": {
                                "x": round(pos.get("x", 0), 1),
                                "y": round(pos.get("y", 0), 1),
                                "z": round(pos.get("z", 0), 1),
                            },
                            "health": raw_state.get("health", 20),
                            "food": raw_state.get("food", 20),
                            "inventory": raw_state.get("inventory", [])[:36],
                            "biome": raw_state.get("biome", "unknown"),
                            "weather": raw_state.get("weather", "clear"),
                            "time": raw_state.get("time", 0),
                            "nearby_entities": raw_state.get("nearby_entities", [])[:20],
                        }

                # Add agent-level info
                state_data["game"] = agent.game_name or "minecraft"
                state_data["current_goal"] = agent._current_goal or "Idle"
                state_data["following"] = agent._following_player
                state_data["action_log"] = [
                    str(a) for a in (agent._goal_actions or [])[-10:]
                ]

                await websocket.send_json({
                    "type": "state",
                    "data": state_data,
                })

            except Exception as e:
                logger.debug(f"Game state error: {e}")
                await websocket.send_json({
                    "type": "state",
                    "data": {
                        "game": agent.game_name or "minecraft",
                        "current_goal": agent._current_goal or "Idle",
                        "error": str(e)[:100],
                    },
                })

    except WebSocketDisconnect:
        logger.info("Game viewer disconnected")
    except Exception as e:
        logger.debug(f"Game WebSocket error: {e}")


# ═══════════════════════════════════════════════════════════════════════
# WebSocket Glasses Endpoint (Meta Ray-Ban smart glasses)
# ═══════════════════════════════════════════════════════════════════════

@app.websocket("/ws/glasses")
async def websocket_glasses(websocket: WebSocket):
    """
    Real-time voice + vision bridge for Meta Ray-Ban smart glasses.

    Authentication:
        Connect with ?token=JWT (required).

    Protocol:
        Client → Server: Binary frames (PCM audio 16kHz)
        Client → Server: {"type": "frame", "jpeg": "<base64>"}
        Client → Server: {"type": "end_of_speech"}
        Server → Client: Binary frames (PCM audio 24kHz)
        Server → Client: {"type": "text", "content": "..."}
        Server → Client: {"type": "thinking"}
        Server → Client: {"type": "done"}
    """
    from src.web.glasses_handler import handle_glasses_session
    await handle_glasses_session(websocket, _bot)


# ═══════════════════════════════════════════════════════════════════════
# Server Startup
# ═══════════════════════════════════════════════════════════════════════

async def start_web_server(bot, port: int = None):
    """
    Start the FastAPI web server as a background task.

    Called from main.py after bot initialization.
    """
    set_bot(bot)
    port = port or int(os.environ.get("WEB_PORT", "8420"))

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        ws_ping_interval=None,  # No ping — Ernos thinks as long as it needs
        ws_ping_timeout=None,   # No timeout
    )
    server = uvicorn.Server(config)

    logger.info(f"🌐 Ernos Web Server starting on port {port}")
    logger.info(f"   WebSocket: ws://localhost:{port}/ws/chat")
    logger.info(f"   Glasses:   ws://localhost:{port}/ws/glasses")
    logger.info(f"   Auth:      http://localhost:{port}/api/auth/...")
    logger.info(f"   Health:    http://localhost:{port}/api/health")
    logger.info(f"   Files:     http://localhost:{port}/files/")

    # Run in background — don't block the Discord bot
    await server.serve()


def get_active_connections() -> Dict[str, WebSocket]:
    """Get all active WebSocket connections."""
    return _active_connections
