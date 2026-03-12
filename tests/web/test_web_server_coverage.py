"""
Tests for src/web/web_server.py — FastAPI REST + WebSocket endpoints.

Covers: health, status, auth_register, auth_login, auth_refresh, auth_me,
        patreon_auth_url, patreon_callback, websocket_chat, websocket_game,
        set_bot, _get_auth_user, start_web_server, get_active_connections.
"""
import json
import time
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock
from starlette.testclient import TestClient
from starlette.websockets import WebSocketState


# ── Setup ─────────────────────────────────────────────────

@pytest.fixture
def client():
    """TestClient for the FastAPI app."""
    from src.web.web_server import app
    return TestClient(app)


@pytest.fixture
def auth_token():
    """Create a valid auth token for testing."""
    from src.web.auth import create_token
    return create_token(user_id="test-user", tier=1, email="test@example.com")


@pytest.fixture(autouse=True)
def reset_bot():
    """Reset global bot reference."""
    import src.web.web_server as mod
    mod._bot = None
    mod._active_connections = {}
    yield
    mod._bot = None
    mod._active_connections = {}


# ── set_bot ───────────────────────────────────────────────

class TestSetBot:
    def test_sets_global_bot(self):
        from src.web.web_server import set_bot, _bot
        import src.web.web_server as mod
        bot = MagicMock()
        set_bot(bot)
        assert mod._bot is bot


# ── get_active_connections ───────────────────────────────

class TestGetActiveConnections:
    def test_returns_dict(self):
        from src.web.web_server import get_active_connections
        conns = get_active_connections()
        assert isinstance(conns, dict)


# ── _get_auth_user ────────────────────────────────────────

class TestGetAuthUser:
    def test_returns_none_without_header(self, client):
        from src.web.web_server import _get_auth_user
        request = MagicMock()
        request.headers = {}
        result = _get_auth_user(request)
        assert result is None

    def test_returns_none_for_invalid_scheme(self, client):
        from src.web.web_server import _get_auth_user
        request = MagicMock()
        request.headers = {"Authorization": "Basic abc123"}
        result = _get_auth_user(request)
        assert result is None

    def test_returns_none_for_invalid_token(self, client):
        from src.web.web_server import _get_auth_user
        request = MagicMock()
        request.headers = {"Authorization": "Bearer invalid.token.here"}
        result = _get_auth_user(request)
        assert result is None

    def test_returns_payload_for_valid_token(self, client, auth_token):
        from src.web.web_server import _get_auth_user
        request = MagicMock()
        request.headers = {"Authorization": f"Bearer {auth_token}"}
        result = _get_auth_user(request)
        assert result is not None
        assert result["sub"] == "test-user"


# ── Health ────────────────────────────────────────────────

class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data


# ── Status ────────────────────────────────────────────────

class TestStatus:
    def test_status_no_bot(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "starting"

    def test_status_with_bot(self, client):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.start_time = time.time() - 100
        bot.processing_users = set()
        active_engine = MagicMock()
        active_engine.name = "gpt-4"
        bot.engine_manager.get_active_engine.return_value = active_engine
        mod._bot = bot

        resp = client.get("/api/status")
        data = resp.json()
        assert data["status"] == "online"
        assert data["engine"] == "gpt-4"
        assert data["uptime_seconds"] >= 99

    def test_status_engine_error(self, client):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.start_time = time.time()
        bot.processing_users = set()
        bot.engine_manager.get_active_engine.side_effect = Exception("no engine")
        mod._bot = bot

        resp = client.get("/api/status")
        data = resp.json()
        assert data["status"] == "online"
        assert data["engine"] is None


# ── Auth Register ─────────────────────────────────────────

class TestAuthRegister:
    def test_successful_register(self, client, tmp_path):
        with patch("src.web.web_server.register", return_value=(True, "Created!", "web-abc123")):
            resp = client.post("/api/auth/register", json={
                "email": "new@example.com", "password": "password123"
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "web-abc123"
        assert "access_token" in data
        assert "refresh_token" in data

    def test_register_failure(self, client):
        with patch("src.web.web_server.register", return_value=(False, "Email exists", None)):
            resp = client.post("/api/auth/register", json={
                "email": "dup@example.com", "password": "password123"
            })
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_register_invalid_json(self, client):
        resp = client.post("/api/auth/register", content="not json", headers={"Content-Type": "text/plain"})
        assert resp.status_code in (400, 422)


# ── Auth Login ────────────────────────────────────────────

class TestAuthLogin:
    def test_successful_login(self, client):
        account_data = {
            "user_id": "web-123", "email": "test@example.com",
            "username": "test", "tier": 0,
            "linked_discord_id": "", "linked_patreon_id": "",
        }
        with patch("src.web.web_server.login", return_value=(True, "Success!", account_data)):
            resp = client.post("/api/auth/login", json={
                "email": "test@example.com", "password": "password123"
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["user_id"] == "web-123"

    def test_login_failure(self, client):
        with patch("src.web.web_server.login", return_value=(False, "Invalid credentials", None)):
            resp = client.post("/api/auth/login", json={
                "email": "bad@example.com", "password": "wrong"
            })
        assert resp.status_code == 401

    def test_login_invalid_json(self, client):
        resp = client.post("/api/auth/login", content="not json", headers={"Content-Type": "text/plain"})
        assert resp.status_code in (400, 422)


# ── Auth Refresh ──────────────────────────────────────────

class TestAuthRefresh:
    def test_successful_refresh(self, client):
        from src.web.auth import create_token
        refresh = create_token(user_id="u1", token_type="refresh")
        resp = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_invalid_refresh(self, client):
        resp = client.post("/api/auth/refresh", json={"refresh_token": "invalid"})
        assert resp.status_code == 401

    def test_refresh_invalid_json(self, client):
        resp = client.post("/api/auth/refresh", content="not json", headers={"Content-Type": "text/plain"})
        assert resp.status_code in (400, 422)


# ── Auth Me ───────────────────────────────────────────────

class TestAuthMe:
    def test_returns_user_info(self, client, auth_token):
        account_data = {
            "user_id": "test-user", "email": "test@example.com",
            "username": "test", "tier": 1,
            "linked_discord_id": "", "linked_patreon_id": "",
            "created_at": time.time(),
        }
        with patch("src.web.web_server.get_account", return_value=account_data):
            resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["user_id"] == "test-user"

    def test_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_account_not_found(self, client, auth_token):
        with patch("src.web.web_server.get_account", return_value=None):
            resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 404

    def test_flux_status_included(self, client, auth_token):
        account_data = {
            "user_id": "test-user", "email": "test@x.com", "username": "t",
            "tier": 1, "linked_discord_id": "", "linked_patreon_id": "",
            "created_at": 0,
        }
        mock_fc = MagicMock()
        mock_fc.get_status.return_value = {"remaining": 10, "limit": 20, "tier": 1}
        with patch("src.web.web_server.get_account", return_value=account_data):
            with patch("src.core.flux_capacitor.FluxCapacitor", return_value=mock_fc):
                resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {auth_token}"})
        data = resp.json()
        assert data["flux"] is not None or data["flux"] == {"remaining": 10, "limit": 20, "tier": 1}

    def test_flux_error_handled(self, client, auth_token):
        account_data = {
            "user_id": "test-user", "email": "t@x.com", "username": "t",
            "tier": 0, "linked_discord_id": "", "linked_patreon_id": "",
            "created_at": 0,
        }
        with patch("src.web.web_server.get_account", return_value=account_data):
            with patch("src.core.flux_capacitor.FluxCapacitor", side_effect=ImportError):
                resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200
        assert resp.json()["flux"] is None


# ── Patreon Auth URL ──────────────────────────────────────

class TestPatreonAuthUrl:
    def test_unauthenticated(self, client):
        resp = client.get("/api/auth/patreon")
        assert resp.status_code == 401

    def test_not_configured(self, client, auth_token):
        with patch("src.web.web_server.patreon_module") as mock_pat:
            mock_pat.is_configured.return_value = False
            resp = client.get("/api/auth/patreon", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 503

    def test_success(self, client, auth_token):
        with patch("src.web.web_server.patreon_module") as mock_pat:
            mock_pat.is_configured.return_value = True
            mock_pat.get_auth_url.return_value = "https://patreon.com/oauth?test"
            resp = client.get("/api/auth/patreon", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200
        assert "auth_url" in resp.json()


# ── Patreon Callback ──────────────────────────────────────

class TestPatreonCallback:
    def test_missing_params(self, client):
        resp = client.get("/api/auth/patreon/callback")
        assert resp.status_code == 400

    def test_missing_code(self, client):
        resp = client.get("/api/auth/patreon/callback?state=user1")
        assert resp.status_code == 400

    def test_success_redirect(self, client):
        with patch("src.web.web_server.patreon_module") as mock_pat:
            mock_pat.process_callback = AsyncMock(return_value=(True, "Linked", "supporter"))
            resp = client.get(
                "/api/auth/patreon/callback?code=abc&state=user1",
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "patreon-linked" in resp.headers.get("location", "")

    def test_failure(self, client):
        with patch("src.web.web_server.patreon_module") as mock_pat:
            mock_pat.process_callback = AsyncMock(return_value=(False, "Invalid code", None))
            resp = client.get("/api/auth/patreon/callback?code=bad&state=user1")
        assert resp.status_code == 400


# ── WebSocket Chat ────────────────────────────────────────

class TestWebSocketChat:
    def test_connect_anonymous(self, client):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect("/ws/chat") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["authenticated"] is False

    def test_connect_authenticated(self, client, auth_token):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["authenticated"] is True
            assert data["user"]["user_id"] == "test-user"

    def test_connect_invalid_token(self, client):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect("/ws/chat?token=invalid.jwt.token") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["authenticated"] is False

    def test_ping_pong(self, client, auth_token):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_invalid_json(self, client, auth_token):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
            ws.receive_json()  # connected
            ws.send_text("not valid json{{{")
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Invalid JSON" in data["message"]

    def test_empty_message_ignored(self, client, auth_token):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"type": "message", "content": ""})
            # Should not get a response for empty message, send ping to verify
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_message_too_long(self, client, auth_token):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"type": "message", "content": "x" * 10001})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "too long" in data["message"].lower()

    def test_unknown_message_type_ignored(self, client, auth_token):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"type": "unknown_type"})
            # Should not crash, send ping to verify
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"

    def test_mode_switch_to_core(self, client, auth_token):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"type": "message", "content": "/self"})
            data = ws.receive_json()
            assert data["type"] == "system"
            assert "core" in data["message"].lower()

    def test_mode_switch_to_professional(self, client, auth_token):
        import src.web.web_server as mod
        mod._bot = MagicMock()
        mod._bot.engine_manager.get_active_engine.return_value = None

        with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
            ws.receive_json()  # connected
            ws.send_json({"type": "message", "content": "/professional"})
            data = ws.receive_json()
            assert data["type"] == "system"
            assert "professional" in data["message"].lower()

    def test_message_processing(self, client, auth_token):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.engine_manager.get_active_engine.return_value = None
        mod._bot = bot

        with patch("src.web.web_chat_handler.handle_web_message", new_callable=AsyncMock,
                    return_value=("Bot response!", [])):
            with patch("src.core.flux_capacitor.FluxCapacitor") as mock_fc_cls:
                mock_fc = MagicMock()
                mock_fc.consume.return_value = (True, None)
                mock_fc.get_status.return_value = {"remaining": 19, "limit": 20, "tier": 1}
                mock_fc_cls.return_value = mock_fc

                with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
                    ws.receive_json()  # connected
                    ws.send_json({"type": "message", "content": "hello"})
                    thinking = ws.receive_json()
                    assert thinking["type"] == "thinking"
                    response = ws.receive_json()
                    assert response["type"] == "response"
                    assert response["content"] == "Bot response!"

    def test_message_with_files(self, client, auth_token):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.engine_manager.get_active_engine.return_value = None
        mod._bot = bot

        from pathlib import Path
        with patch("src.web.web_chat_handler.handle_web_message", new_callable=AsyncMock,
                    return_value=("Here's an image", [Path("/tmp/image.png")])):
            with patch("src.core.flux_capacitor.FluxCapacitor") as mock_fc_cls:
                mock_fc = MagicMock()
                mock_fc.consume.return_value = (True, None)
                mock_fc.get_status.return_value = {"remaining": 19, "limit": 20, "tier": 1}
                mock_fc_cls.return_value = mock_fc

                with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
                    ws.receive_json()  # connected
                    ws.send_json({"type": "message", "content": "draw something"})
                    ws.receive_json()  # thinking
                    response = ws.receive_json()
                    assert response["type"] == "response"
                    assert len(response["files"]) == 1

    def test_flux_rate_limited(self, client, auth_token):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.engine_manager.get_active_engine.return_value = None
        mod._bot = bot

        with patch("src.core.flux_capacitor.FluxCapacitor") as mock_fc_cls:
            mock_fc = MagicMock()
            mock_fc.consume.return_value = (False, "Rate limited!")
            mock_fc_cls.return_value = mock_fc

            with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
                ws.receive_json()  # connected
                ws.send_json({"type": "message", "content": "hello"})
                data = ws.receive_json()
                assert data["type"] == "error"
                assert data["message"] == "RATE_LIMITED"

    def test_flux_warning(self, client, auth_token):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.engine_manager.get_active_engine.return_value = None
        mod._bot = bot

        with patch("src.web.web_chat_handler.handle_web_message", new_callable=AsyncMock,
                    return_value=("response", [])):
            with patch("src.core.flux_capacitor.FluxCapacitor") as mock_fc_cls:
                mock_fc = MagicMock()
                mock_fc.consume.return_value = (True, "Running low!")
                mock_fc.get_status.return_value = {"remaining": 2, "limit": 20, "tier": 1}
                mock_fc_cls.return_value = mock_fc

                with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
                    ws.receive_json()  # connected
                    ws.send_json({"type": "message", "content": "hello"})
                    flux_warn = ws.receive_json()
                    assert flux_warn["type"] == "flux"
                    assert flux_warn["warning"] == "Running low!"

    def test_anon_rate_limit(self, client):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.engine_manager.get_active_engine.return_value = None
        mod._bot = bot

        # Reset anon counters
        if hasattr(mod.websocket_chat, "_anon_counters"):
            mod.websocket_chat._anon_counters = {}

        with patch("src.web.web_chat_handler.handle_web_message", new_callable=AsyncMock,
                    return_value=("response", [])):
            with client.websocket_connect("/ws/chat") as ws:
                ws.receive_json()  # connected
                # Send 5 messages (the limit)
                for i in range(5):
                    ws.send_json({"type": "message", "content": f"msg {i}"})
                    ws.receive_json()  # thinking
                    ws.receive_json()  # response

                # 6th message should be rate limited
                ws.send_json({"type": "message", "content": "too many"})
                data = ws.receive_json()
                assert data["type"] == "error"
                assert data["message"] == "RATE_LIMITED"
                assert data.get("prompt_signup") is True

    def test_processing_error(self, client, auth_token):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.engine_manager.get_active_engine.return_value = None
        mod._bot = bot

        with patch("src.web.web_chat_handler.handle_web_message", new_callable=AsyncMock,
                    side_effect=Exception("engine crashed")):
            with patch("src.core.flux_capacitor.FluxCapacitor") as mock_fc_cls:
                mock_fc = MagicMock()
                mock_fc.consume.return_value = (True, None)
                mock_fc_cls.return_value = mock_fc

                with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
                    ws.receive_json()  # connected
                    ws.send_json({"type": "message", "content": "hello"})
                    ws.receive_json()  # thinking
                    data = ws.receive_json()
                    assert data["type"] == "error"
                    assert "Processing error" in data["message"]

    def test_flux_check_error_handled(self, client, auth_token):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.engine_manager.get_active_engine.return_value = None
        mod._bot = bot

        with patch("src.web.web_chat_handler.handle_web_message", new_callable=AsyncMock,
                    return_value=("response", [])):
            with patch("src.core.flux_capacitor.FluxCapacitor", side_effect=ImportError("no flux")):
                with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
                    ws.receive_json()  # connected
                    ws.send_json({"type": "message", "content": "hello"})
                    ws.receive_json()  # thinking
                    data = ws.receive_json()
                    assert data["type"] == "response"

    def test_engine_name_on_connect(self, client, auth_token):
        import src.web.web_server as mod
        bot = MagicMock()
        engine = MagicMock()
        engine.name = "gpt-4o"
        bot.engine_manager.get_active_engine.return_value = engine
        mod._bot = bot

        with client.websocket_connect(f"/ws/chat?token={auth_token}") as ws:
            data = ws.receive_json()
            assert data["engine"] == "gpt-4o"


# ── WebSocket Game ────────────────────────────────────────

class TestWebSocketGame:
    def test_game_offline(self, client):
        import src.web.web_server as mod
        mod._bot = None

        with client.websocket_connect("/ws/game") as ws:
            data = ws.receive_json()
            assert data["type"] == "offline"

    def test_game_bot_no_gaming_agent(self, client):
        import src.web.web_server as mod
        bot = MagicMock(spec=[])  # No gaming_agent attr
        mod._bot = bot

        with client.websocket_connect("/ws/game") as ws:
            data = ws.receive_json()
            assert data["type"] == "offline"

    def test_game_not_running(self, client):
        import src.web.web_server as mod
        bot = MagicMock()
        bot.gaming_agent.is_running = False
        mod._bot = bot

        with client.websocket_connect("/ws/game") as ws:
            data = ws.receive_json()
            assert data["type"] == "offline"


# ── start_web_server ──────────────────────────────────────

class TestStartWebServer:
    @pytest.mark.asyncio
    async def test_starts_server(self):
        from src.web.web_server import start_web_server
        bot = MagicMock()

        mock_server = MagicMock()
        mock_server.serve = AsyncMock()

        with patch("src.web.web_server.uvicorn.Config") as mock_config:
            with patch("src.web.web_server.uvicorn.Server", return_value=mock_server):
                await start_web_server(bot, port=9999)
                mock_config.assert_called_once()
                mock_server.serve.assert_called_once()

    @pytest.mark.asyncio
    async def test_default_port(self):
        from src.web.web_server import start_web_server
        bot = MagicMock()

        mock_server = MagicMock()
        mock_server.serve = AsyncMock()

        with patch.dict("os.environ", {}, clear=False):
            with patch("src.web.web_server.uvicorn.Config") as mock_config:
                with patch("src.web.web_server.uvicorn.Server", return_value=mock_server):
                    await start_web_server(bot)
                    config_call = mock_config.call_args
                    assert config_call.kwargs.get("port", 8420) == 8420 or config_call[1].get("port", 8420) == 8420
