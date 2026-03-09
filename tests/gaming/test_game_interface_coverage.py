"""
Coverage tests for gaming/game_interface.py — targets uncovered lines 110-174.

Tests: GameState, GameAction, GameEngineInterface (via MinecraftEngine),
       MinecraftEngine.get_state, execute_action, get_available_actions,
       connect, disconnect, game_name, is_connected.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.gaming.game_interface import GameState, GameAction, MinecraftEngine


# ──────────────────────────────────────
# Data classes
# ──────────────────────────────────────

class TestGameState:
    def test_default_state(self):
        state = GameState()
        assert state.player_health == 100.0
        assert state.player_position == {"x": 0, "y": 0, "z": 0}
        assert state.player_inventory == []
        assert state.nearby_entities == []
        assert state.current_biome == "unknown"
        assert state.time_of_day == "day"
        assert state.weather == "clear"
        assert state.custom == {}

    def test_custom_state(self):
        state = GameState(
            player_health=15.0,
            player_position={"x": 10, "y": 64, "z": 20},
            current_biome="forest"
        )
        assert state.player_health == 15.0
        assert state.current_biome == "forest"


class TestGameAction:
    def test_default_action(self):
        action = GameAction(action_type="move")
        assert action.action_type == "move"
        assert action.parameters == {}
        assert action.priority == 5

    def test_custom_action(self):
        action = GameAction(action_type="attack", parameters={"entity": "zombie"}, priority=10)
        assert action.parameters == {"entity": "zombie"}
        assert action.priority == 10


# ──────────────────────────────────────
# MinecraftEngine
# ──────────────────────────────────────

class TestMinecraftEngineInit:
    def test_no_bridge(self):
        engine = MinecraftEngine()
        assert engine._bridge is None
        assert engine._connected is False

    def test_with_bridge(self):
        bridge = MagicMock()
        engine = MinecraftEngine(bridge=bridge)
        assert engine._bridge is bridge


class TestMinecraftEngineGetState:
    @pytest.mark.asyncio
    async def test_no_bridge(self):
        engine = MinecraftEngine()
        state = await engine.get_state()
        assert isinstance(state, GameState)
        assert state.player_health == 100.0

    @pytest.mark.asyncio
    async def test_with_bridge_success(self):
        bridge = AsyncMock()
        bridge.get_bot_state = AsyncMock(return_value={
            "position": {"x": 5, "y": 64, "z": 10},
            "health": 18,
            "inventory": [{"name": "iron"}],
            "nearby_entities": [{"name": "pig"}],
            "nearby_blocks": [],
            "biome": "plains",
            "time": 6000,
            "weather": "rain"
        })
        engine = MinecraftEngine(bridge=bridge)
        state = await engine.get_state()
        assert state.player_health == 18
        assert state.player_position == {"x": 5, "y": 64, "z": 10}
        assert state.current_biome == "plains"
        assert state.time_of_day == "day"
        assert state.weather == "rain"

    @pytest.mark.asyncio
    async def test_nighttime(self):
        bridge = AsyncMock()
        bridge.get_bot_state = AsyncMock(return_value={
            "time": 15000
        })
        engine = MinecraftEngine(bridge=bridge)
        state = await engine.get_state()
        assert state.time_of_day == "night"

    @pytest.mark.asyncio
    async def test_bridge_no_get_bot_state(self):
        """Bridge without get_bot_state method."""
        bridge = MagicMock(spec=[])
        engine = MinecraftEngine(bridge=bridge)
        state = await engine.get_state()
        assert isinstance(state, GameState)

    @pytest.mark.asyncio
    async def test_bridge_error(self):
        bridge = AsyncMock()
        bridge.get_bot_state = AsyncMock(side_effect=Exception("Bridge error"))
        engine = MinecraftEngine(bridge=bridge)
        state = await engine.get_state()
        assert isinstance(state, GameState)
        assert state.player_health == 100.0  # default


class TestMinecraftEngineExecuteAction:
    @pytest.mark.asyncio
    async def test_no_bridge(self):
        engine = MinecraftEngine()
        action = GameAction(action_type="move")
        result = await engine.execute_action(action)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_success(self):
        bridge = AsyncMock()
        bridge.execute_action = AsyncMock(return_value={"success": True, "message": "Done"})
        bridge.get_bot_state = AsyncMock(return_value={})
        engine = MinecraftEngine(bridge=bridge)
        action = GameAction(action_type="mine", parameters={"block": "stone"})
        result = await engine.execute_action(action)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_bridge_no_execute_action(self):
        bridge = MagicMock(spec=[])
        engine = MinecraftEngine(bridge=bridge)
        action = GameAction(action_type="move")
        result = await engine.execute_action(action)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_error(self):
        bridge = AsyncMock()
        bridge.execute_action = AsyncMock(side_effect=Exception("Error"))
        engine = MinecraftEngine(bridge=bridge)
        action = GameAction(action_type="attack")
        result = await engine.execute_action(action)
        assert result["success"] is False


class TestMinecraftEngineGetAvailableActions:
    @pytest.mark.asyncio
    async def test_returns_action_list(self):
        engine = MinecraftEngine()
        actions = await engine.get_available_actions()
        assert isinstance(actions, list)
        assert "move" in actions
        assert "mine" in actions
        assert "craft" in actions
        assert len(actions) >= 10


class TestMinecraftEngineConnect:
    @pytest.mark.asyncio
    async def test_connect_success(self):
        bridge = AsyncMock()
        bridge.connect = AsyncMock()
        engine = MinecraftEngine(bridge=bridge)
        result = await engine.connect({"host": "localhost", "port": 25565})
        assert result is True
        assert engine._connected is True

    @pytest.mark.asyncio
    async def test_connect_no_bridge(self):
        engine = MinecraftEngine()
        result = await engine.connect({})
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_error(self):
        bridge = AsyncMock()
        bridge.connect = AsyncMock(side_effect=Exception("Connection refused"))
        engine = MinecraftEngine(bridge=bridge)
        result = await engine.connect({"host": "badhost"})
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_bridge_no_connect_method(self):
        bridge = MagicMock(spec=[])
        engine = MinecraftEngine(bridge=bridge)
        result = await engine.connect({})
        assert result is False


class TestMinecraftEngineDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_with_bridge(self):
        bridge = AsyncMock()
        bridge.disconnect = AsyncMock()
        engine = MinecraftEngine(bridge=bridge)
        engine._connected = True
        await engine.disconnect()
        assert engine._connected is False

    @pytest.mark.asyncio
    async def test_disconnect_no_bridge(self):
        engine = MinecraftEngine()
        await engine.disconnect()
        assert engine._connected is False

    @pytest.mark.asyncio
    async def test_disconnect_bridge_no_method(self):
        bridge = MagicMock(spec=[])
        engine = MinecraftEngine(bridge=bridge)
        engine._connected = True
        await engine.disconnect()
        assert engine._connected is False


class TestMinecraftEngineProperties:
    def test_game_name(self):
        engine = MinecraftEngine()
        assert engine.game_name == "minecraft"

    def test_is_connected_false(self):
        engine = MinecraftEngine()
        assert engine.is_connected is False

    def test_is_connected_true(self):
        engine = MinecraftEngine()
        engine._connected = True
        assert engine.is_connected is True
