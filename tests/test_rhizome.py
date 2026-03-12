"""
Tests for v3.4 Rhizome: Platform Adapters, Game Interface,
Perception Engine, and Home Assistant.
"""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime


# ──────────────────────────────────────────────────────────────
# Platform Adapter Tests
# ──────────────────────────────────────────────────────────────

class TestTelegramAdapter:
    """Tests for Telegram channel adapter."""

    @pytest.mark.asyncio
    async def test_normalize_private(self):
        from src.channels.telegram_adapter import TelegramAdapter
        adapter = TelegramAdapter()
        
        # Mock telegram message
        msg = MagicMock()
        msg.from_user.id = 12345
        msg.from_user.username = "alice"
        msg.text = "Hello Ernos!"
        msg.caption = None
        msg.chat.id = 67890
        msg.chat.type = "private"
        msg.photo = None
        msg.document = None
        msg.message = msg  # self-reference for getattr
        
        result = await adapter.normalize(msg)
        assert result.content == "Hello Ernos!"
        assert result.author_id == "12345"
        assert result.is_dm is True

    @pytest.mark.asyncio
    async def test_normalize_group(self):
        from src.channels.telegram_adapter import TelegramAdapter
        adapter = TelegramAdapter()
        
        msg = MagicMock()
        msg.from_user.id = 12345
        msg.from_user.username = "bob"
        msg.text = "Hey everyone"
        msg.caption = None
        msg.chat.id = 99999
        msg.chat.type = "group"
        msg.photo = None
        msg.document = None
        msg.message = msg
        
        result = await adapter.normalize(msg)
        assert result.is_dm is False

    def test_platform_name(self):
        from src.channels.telegram_adapter import TelegramAdapter
        assert TelegramAdapter().platform_name == "telegram"


class TestMatrixAdapter:
    """Tests for Matrix channel adapter."""

    @pytest.mark.asyncio
    async def test_normalize_text(self):
        from src.channels.matrix_adapter import MatrixAdapter
        adapter = MatrixAdapter()
        
        event = {
            "sender": "@alice:matrix.org",
            "content": {"msgtype": "m.text", "body": "Hello!"},
            "room_id": "!abc123:matrix.org",
            "is_direct": True
        }
        
        result = await adapter.normalize(event)
        assert result.content == "Hello!"
        assert result.author_name == "alice"
        assert result.is_dm is True

    @pytest.mark.asyncio
    async def test_format_mentions(self):
        from src.channels.matrix_adapter import MatrixAdapter
        adapter = MatrixAdapter()
        result = await adapter.format_mentions("Hey @alice:matrix.org check this")
        assert "@alice" in result
        assert "matrix.org" not in result

    def test_platform_name(self):
        from src.channels.matrix_adapter import MatrixAdapter
        assert MatrixAdapter().platform_name == "matrix"


class TestWebAdapter:
    """Tests for Web channel adapter."""

    @pytest.mark.asyncio
    async def test_normalize(self):
        from src.channels.web_adapter import WebAdapter
        adapter = WebAdapter()
        
        data = {
            "user_id": "web_123",
            "username": "WebUser",
            "message": "Hi from web!",
            "session_id": "sess_abc"
        }
        
        result = await adapter.normalize(data)
        assert result.content == "Hi from web!"
        assert result.is_dm is True
        assert result.platform == "web"

    @pytest.mark.asyncio
    async def test_response_queue(self):
        from src.channels.web_adapter import WebAdapter
        from src.channels.types import OutboundResponse
        
        adapter = WebAdapter()
        response = OutboundResponse(content="Hello back!")
        await adapter.send_response(response, "session_1")
        
        responses = adapter.get_responses("session_1")
        assert len(responses) == 1
        assert responses[0] == "Hello back!"
        
        # Queue should be cleared after retrieval
        assert adapter.get_responses("session_1") == []

    def test_platform_name(self):
        from src.channels.web_adapter import WebAdapter
        assert WebAdapter().platform_name == "web"


# ──────────────────────────────────────────────────────────────
# Game Interface Tests
# ──────────────────────────────────────────────────────────────

class TestGameInterface:
    """Tests for game engine abstraction."""

    def test_game_state_defaults(self):
        from src.gaming.game_interface import GameState
        state = GameState()
        assert state.player_health == 100.0
        assert state.current_biome == "unknown"

    def test_game_action_creation(self):
        from src.gaming.game_interface import GameAction
        action = GameAction(action_type="mine", parameters={"block": "stone"})
        assert action.action_type == "mine"
        assert action.priority == 5

    def test_minecraft_engine_creation(self):
        from src.gaming.game_interface import MinecraftEngine
        engine = MinecraftEngine()
        assert engine.game_name == "minecraft"
        assert engine.is_connected is False

    @pytest.mark.asyncio
    async def test_minecraft_engine_no_bridge(self):
        from src.gaming.game_interface import MinecraftEngine, GameState
        engine = MinecraftEngine()
        state = await engine.get_state()
        assert isinstance(state, GameState)

    @pytest.mark.asyncio
    async def test_available_actions(self):
        from src.gaming.game_interface import MinecraftEngine
        engine = MinecraftEngine()
        actions = await engine.get_available_actions()
        assert "mine" in actions
        assert "craft" in actions


# ──────────────────────────────────────────────────────────────
# Perception Engine Tests
# ──────────────────────────────────────────────────────────────

class TestPerceptionEngine:
    """Tests for multi-modal perception."""

    def test_ingest_text(self):
        from src.lobes.interaction.perception import PerceptionEngine
        pe = PerceptionEngine()
        inp = pe.ingest("text", "discord", "Hello world")
        assert inp.modality == "text"
        assert inp.source == "discord"

    def test_context_building(self):
        from src.lobes.interaction.perception import PerceptionEngine
        pe = PerceptionEngine()
        pe.ingest("text", "discord", "msg 1")
        pe.ingest("text", "discord", "msg 2")
        pe.ingest("image", "discord", b"fake_image")
        
        ctx = pe.get_context(window_seconds=60)
        assert len(ctx.inputs) == 3
        assert ctx.dominant_modality == "text"

    def test_buffer_summary(self):
        from src.lobes.interaction.perception import PerceptionEngine
        pe = PerceptionEngine()
        pe.ingest("text", "discord", "msg")
        pe.ingest("audio", "voice", b"audio_bytes")
        
        summary = pe.get_buffer_summary()
        assert "1 text" in summary
        assert "1 audio" in summary

    def test_empty_context(self):
        from src.lobes.interaction.perception import PerceptionEngine
        pe = PerceptionEngine()
        ctx = pe.get_context()
        assert len(ctx.inputs) == 0

    def test_buffer_cap(self):
        from src.lobes.interaction.perception import PerceptionEngine
        pe = PerceptionEngine()
        for i in range(210):
            pe.ingest("text", "test", f"msg {i}")
        assert len(pe._input_buffer) == 200


# ──────────────────────────────────────────────────────────────
# Home Assistant Tests
# ──────────────────────────────────────────────────────────────

class TestHomeAssistant:
    """Tests for smart home integration."""

    def test_not_configured(self):
        from src.tools.home_assistant import HomeAssistantClient
        ha = HomeAssistantClient()
        assert ha.is_configured is False

    def test_configured(self):
        from src.tools.home_assistant import HomeAssistantClient
        ha = HomeAssistantClient(url="http://localhost:8123", token="test_token")
        assert ha.is_configured is True

    def test_sensor_summary_empty(self):
        from src.tools.home_assistant import HomeAssistantClient
        ha = HomeAssistantClient()
        summary = ha.get_sensor_summary()
        assert "No sensor data" in summary

    def test_sensor_summary_with_data(self):
        from src.tools.home_assistant import HomeAssistantClient
        ha = HomeAssistantClient()
        ha._entity_cache = {
            "sensor.temperature": {
                "entity_id": "sensor.temperature",
                "state": "72",
                "attributes": {
                    "friendly_name": "Living Room Temp",
                    "unit_of_measurement": "°F"
                }
            }
        }
        summary = ha.get_sensor_summary()
        assert "Living Room Temp" in summary
        assert "72°F" in summary

    def test_room_context(self):
        from src.tools.home_assistant import HomeAssistantClient
        ha = HomeAssistantClient()
        ha._entity_cache = {
            "light.bedroom": {
                "entity_id": "light.bedroom",
                "state": "on",
                "attributes": {"friendly_name": "Bedroom Light", "area": "bedroom"}
            }
        }
        rooms = ha.get_room_context()
        assert "bedroom" in rooms
        assert len(rooms["bedroom"]["lights"]) == 1
