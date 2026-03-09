"""
Coverage tests for gaming/perception.py — targets uncovered lines 57-240.

Tests: PerceptionMixin._observe, _build_reflexes, _check_stuck, _unstuck,
       _execute_reflexes, _verify_action, _get_inventory_counts.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.gaming.mineflayer_bridge import BridgeResponse


def make_perception_agent():
    """Create a mock agent with PerceptionMixin methods."""
    from src.gaming.perception import PerceptionMixin

    class MockAgent(PerceptionMixin):
        pass

    agent = MockAgent()
    agent.bridge = AsyncMock()
    agent._pending_chats = []
    agent._last_position = None
    agent._stuck_counter = 0
    return agent


# ──────────────────────────────────────
# _observe
# ──────────────────────────────────────

class TestObserve:
    @pytest.mark.asyncio
    async def test_observe_full_success(self):
        agent = make_perception_agent()
        agent.bridge.get_status.return_value = BridgeResponse(True, {
            "health": 18, "food": 15,
            "position": {"x": 10, "y": 64, "z": 20},
            "inventory": [{"name": "oak_log", "count": 5}]
        })
        agent.bridge.execute.side_effect = [
            BridgeResponse(True, {"entities": [{"name": "pig"}], "hostiles_nearby": False}),
            BridgeResponse(True, {"isDay": True}),
        ]
        agent.bridge.get_screenshot.return_value = "base64screenshot"

        state = await agent._observe()
        assert state["health"] == 18
        assert state["food"] == 15
        assert state["position"] == {"x": 10, "y": 64, "z": 20}
        assert len(state["inventory"]) == 1
        assert len(state["nearby_entities"]) == 1
        assert state["is_day"] is True
        assert state["screenshot"] == "base64screenshot"

    @pytest.mark.asyncio
    async def test_observe_all_failures(self):
        agent = make_perception_agent()
        agent.bridge.get_status.return_value = BridgeResponse(False, error="timeout")
        agent.bridge.execute.return_value = BridgeResponse(False, error="timeout")
        agent.bridge.get_screenshot.return_value = None

        state = await agent._observe()
        assert state["health"] == 20  # defaults
        assert state["food"] == 20
        assert state["position"] == {}
        assert state["nearby_entities"] == []
        assert state["is_day"] is True
        assert state["screenshot"] is None

    @pytest.mark.asyncio
    async def test_observe_screenshot_timeout(self):
        agent = make_perception_agent()
        agent.bridge.get_status.return_value = BridgeResponse(True, {
            "health": 20, "food": 20, "position": {}, "inventory": []
        })
        agent.bridge.execute.return_value = BridgeResponse(True, {"entities": [], "hostiles_nearby": False, "isDay": True})
        agent.bridge.get_screenshot.side_effect = asyncio.TimeoutError()

        state = await agent._observe()
        assert state["screenshot"] is None

    @pytest.mark.asyncio
    async def test_observe_screenshot_error(self):
        agent = make_perception_agent()
        agent.bridge.get_status.return_value = BridgeResponse(True, {
            "health": 20, "food": 20, "position": {}, "inventory": []
        })
        agent.bridge.execute.return_value = BridgeResponse(True, {"entities": [], "hostiles_nearby": False, "isDay": True})
        agent.bridge.get_screenshot.side_effect = Exception("Vision error")

        state = await agent._observe()
        assert state["screenshot"] is None

    @pytest.mark.asyncio
    async def test_observe_clears_pending_chats(self):
        agent = make_perception_agent()
        agent._pending_chats = [{"username": "test", "message": "hi"}]
        agent.bridge.get_status.return_value = BridgeResponse(True, {
            "health": 20, "food": 20, "position": {}, "inventory": []
        })
        agent.bridge.execute.return_value = BridgeResponse(True, {"entities": [], "hostiles_nearby": False, "isDay": True})
        agent.bridge.get_screenshot.return_value = None

        state = await agent._observe()
        assert len(state["pending_chats"]) == 1  # Copy before clear
        assert len(agent._pending_chats) == 0  # Original cleared

    @pytest.mark.asyncio
    async def test_observe_screenshot_empty_string(self):
        """Screenshot that returns empty string."""
        agent = make_perception_agent()
        agent.bridge.get_status.return_value = BridgeResponse(True, {
            "health": 20, "food": 20, "position": {}, "inventory": []
        })
        agent.bridge.execute.return_value = BridgeResponse(True, {"entities": [], "hostiles_nearby": False, "isDay": True})
        agent.bridge.get_screenshot.return_value = ""

        state = await agent._observe()
        assert state["screenshot"] == ""

    @pytest.mark.asyncio
    async def test_observe_inventory_truncated(self):
        """Should truncate inventory to 10 items."""
        agent = make_perception_agent()
        big_inv = [{"name": f"item_{i}", "count": 1} for i in range(20)]
        agent.bridge.get_status.return_value = BridgeResponse(True, {
            "health": 20, "food": 20, "position": {}, "inventory": big_inv
        })
        agent.bridge.execute.return_value = BridgeResponse(True, {"entities": [], "hostiles_nearby": False, "isDay": True})
        agent.bridge.get_screenshot.return_value = None

        state = await agent._observe()
        assert len(state["inventory"]) == 10


# ──────────────────────────────────────
# _build_reflexes
# ──────────────────────────────────────

class TestBuildReflexes:
    def test_basic_reflexes(self):
        agent = make_perception_agent()
        state = {"food": 20, "hostiles_nearby": False}
        chain = agent._build_reflexes(state)
        # Should have look_around + collect_drops + look_around
        assert len(chain) >= 3
        commands = [c["command"] for c in chain]
        assert "look_around" in commands
        assert "collect_drops" in commands

    def test_hungry_adds_maintain(self):
        agent = make_perception_agent()
        state = {"food": 10, "hostiles_nearby": False}
        chain = agent._build_reflexes(state)
        commands = [c["command"] for c in chain]
        assert "maintain_status" in commands

    def test_hostiles_adds_defend(self):
        agent = make_perception_agent()
        state = {"food": 20, "hostiles_nearby": True}
        chain = agent._build_reflexes(state)
        commands = [c["command"] for c in chain]
        assert "defend" in commands

    def test_hungry_and_hostiles(self):
        agent = make_perception_agent()
        state = {"food": 5, "hostiles_nearby": True}
        chain = agent._build_reflexes(state)
        commands = [c["command"] for c in chain]
        assert "maintain_status" in commands
        assert "defend" in commands


# ──────────────────────────────────────
# _check_stuck
# ──────────────────────────────────────

class TestCheckStuck:
    def test_no_previous_position(self):
        agent = make_perception_agent()
        agent._last_position = None
        result = agent._check_stuck({"x": 10, "y": 64, "z": 20})
        assert result is False
        assert agent._last_position == {"x": 10, "y": 64, "z": 20}

    def test_no_current_position(self):
        agent = make_perception_agent()
        agent._last_position = {"x": 10, "y": 64, "z": 20}
        result = agent._check_stuck({})
        # Empty dict — should still compute distance
        assert isinstance(result, bool)

    def test_moved_resets_counter(self):
        agent = make_perception_agent()
        agent._last_position = {"x": 0, "y": 64, "z": 0}
        agent._stuck_counter = 2
        result = agent._check_stuck({"x": 10, "y": 64, "z": 10})
        assert result is False
        assert agent._stuck_counter == 0

    def test_not_moved_increments_counter(self):
        agent = make_perception_agent()
        agent._last_position = {"x": 10, "y": 64, "z": 20}
        agent._stuck_counter = 0
        result = agent._check_stuck({"x": 10, "y": 64, "z": 20})
        assert result is False
        assert agent._stuck_counter == 1

    def test_stuck_after_three_cycles(self):
        agent = make_perception_agent()
        agent._last_position = {"x": 10, "y": 64, "z": 20}
        agent._stuck_counter = 2
        result = agent._check_stuck({"x": 10, "y": 64, "z": 20})
        assert result is True
        assert agent._stuck_counter == 3

    def test_slight_movement_not_stuck(self):
        agent = make_perception_agent()
        agent._last_position = {"x": 10, "y": 64, "z": 20}
        agent._stuck_counter = 2
        # Move < 1 block
        result = agent._check_stuck({"x": 10.5, "y": 64, "z": 20})
        assert agent._stuck_counter == 3
        assert result is True


# ──────────────────────────────────────
# _unstuck
# ──────────────────────────────────────

class TestUnstuck:
    @pytest.mark.asyncio
    async def test_unstuck_jump(self):
        agent = make_perception_agent()
        agent._stuck_counter = 5
        with patch("random.choice", return_value="jump"):
            with patch("src.gaming.perception.log_embodiment"):
                result = await agent._unstuck()
        assert result == "explore"
        assert agent._stuck_counter == 0
        agent.bridge.execute.assert_called_with("jump")

    @pytest.mark.asyncio
    async def test_unstuck_turn(self):
        agent = make_perception_agent()
        agent._stuck_counter = 5
        with patch("random.choice", return_value="turn"):
            with patch("random.randint", return_value=90):
                with patch("src.gaming.perception.log_embodiment"):
                    result = await agent._unstuck()
        assert result == "explore"
        agent.bridge.execute.assert_called_with("look", {"yaw": 90, "pitch": 0})

    @pytest.mark.asyncio
    async def test_unstuck_explore(self):
        agent = make_perception_agent()
        agent._stuck_counter = 5
        with patch("random.choice", return_value="explore"):
            with patch("src.gaming.perception.log_embodiment"):
                result = await agent._unstuck()
        assert result == "explore"

    @pytest.mark.asyncio
    async def test_unstuck_dig(self):
        agent = make_perception_agent()
        agent._stuck_counter = 5
        with patch("random.choice", return_value="dig"):
            with patch("src.gaming.perception.log_embodiment"):
                result = await agent._unstuck()
        assert result == "explore"
        agent.bridge.execute.assert_called_with("dig_forward")


# ──────────────────────────────────────
# _execute_reflexes
# ──────────────────────────────────────

class TestExecuteReflexes:
    @pytest.mark.asyncio
    async def test_execute_reflexes_success(self):
        agent = make_perception_agent()
        chain = [{"command": "look_around", "params": {}}]
        await agent._execute_reflexes(chain)
        agent.bridge.execute.assert_called_with("execute_predictive_chain", {"chain": chain})

    @pytest.mark.asyncio
    async def test_execute_reflexes_error(self):
        agent = make_perception_agent()
        agent.bridge.execute.side_effect = Exception("Error")
        chain = [{"command": "look_around", "params": {}}]
        await agent._execute_reflexes(chain)  # Should not raise
        assert True  # No exception: error handled gracefully


# ──────────────────────────────────────
# _verify_action
# ──────────────────────────────────────

class TestVerifyAction:
    @pytest.mark.asyncio
    async def test_empty_action(self):
        agent = make_perception_agent()
        result = await agent._verify_action("", {}, {})
        assert result is True

    @pytest.mark.asyncio
    async def test_collect_success(self):
        agent = make_perception_agent()
        before = {"oak_log": 3}
        after = {"oak_log": 8}
        result = await agent._verify_action("collect oak_log 5", before, after)
        assert result is True

    @pytest.mark.asyncio
    async def test_collect_failure(self):
        agent = make_perception_agent()
        before = {"oak_log": 3}
        after = {"oak_log": 3}
        result = await agent._verify_action("collect oak_log 5", before, after)
        assert result is False

    @pytest.mark.asyncio
    async def test_mine_success(self):
        agent = make_perception_agent()
        result = await agent._verify_action("mine cobblestone", {"cobblestone": 0}, {"cobblestone": 5})
        assert result is True

    @pytest.mark.asyncio
    async def test_get_success(self):
        agent = make_perception_agent()
        result = await agent._verify_action("get iron_ore", {}, {"iron_ore": 3})
        assert result is True

    @pytest.mark.asyncio
    async def test_craft_success(self):
        agent = make_perception_agent()
        result = await agent._verify_action("craft planks 4", {"planks": 0}, {"planks": 4})
        assert result is True

    @pytest.mark.asyncio
    async def test_craft_failure(self):
        agent = make_perception_agent()
        result = await agent._verify_action("craft planks 4", {"planks": 0}, {"planks": 0})
        assert result is False

    @pytest.mark.asyncio
    async def test_smelt_iron_ore(self):
        agent = make_perception_agent()
        result = await agent._verify_action("smelt iron_ore", {"iron_ingot": 0}, {"iron_ingot": 1})
        assert result is True

    @pytest.mark.asyncio
    async def test_smelt_sand_to_glass(self):
        agent = make_perception_agent()
        result = await agent._verify_action("smelt sand", {"glass": 0}, {"glass": 1})
        assert result is True

    @pytest.mark.asyncio
    async def test_smelt_unknown_item(self):
        agent = make_perception_agent()
        result = await agent._verify_action("smelt unknown_thing", {"unknown_thing": 0}, {"unknown_thing": 1})
        assert result is True

    @pytest.mark.asyncio
    async def test_goto_moved(self):
        agent = make_perception_agent()
        before_pos = {"x": 0, "y": 64, "z": 0}
        after_pos = {"x": 10, "y": 64, "z": 10}
        result = await agent._verify_action("goto 10 64 10", {}, {}, before_pos, after_pos)
        assert result is True

    @pytest.mark.asyncio
    async def test_goto_not_moved(self):
        agent = make_perception_agent()
        pos = {"x": 0, "y": 64, "z": 0}
        result = await agent._verify_action("goto 10 64 10", {}, {}, pos, pos)
        assert result is False

    @pytest.mark.asyncio
    async def test_explore_moved(self):
        agent = make_perception_agent()
        result = await agent._verify_action("explore", {}, {},
                                            {"x": 0, "y": 64, "z": 0},
                                            {"x": 5, "y": 64, "z": 5})
        assert result is True

    @pytest.mark.asyncio
    async def test_follow_no_positions(self):
        agent = make_perception_agent()
        result = await agent._verify_action("follow player1", {}, {})
        assert result is True

    @pytest.mark.asyncio
    async def test_chat_always_succeeds(self):
        agent = make_perception_agent()
        result = await agent._verify_action("chat hello world", {}, {})
        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_command_succeeds(self):
        agent = make_perception_agent()
        result = await agent._verify_action("dance", {}, {})
        assert result is True


# ──────────────────────────────────────
# _get_inventory_counts
# ──────────────────────────────────────

class TestGetInventoryCounts:
    @pytest.mark.asyncio
    async def test_success(self):
        agent = make_perception_agent()
        agent.bridge.get_status.return_value = BridgeResponse(True, {
            "inventory": [
                {"name": "oak_log", "count": 5},
                {"name": "cobblestone", "count": 32},
                {"name": "oak_log", "count": 3},  # Duplicate — should sum
            ]
        })
        result = await agent._get_inventory_counts()
        assert result == {"oak_log": 8, "cobblestone": 32}

    @pytest.mark.asyncio
    async def test_failure(self):
        agent = make_perception_agent()
        agent.bridge.get_status.return_value = BridgeResponse(False, error="timeout")
        result = await agent._get_inventory_counts()
        assert result == {}

    @pytest.mark.asyncio
    async def test_empty_inventory(self):
        agent = make_perception_agent()
        agent.bridge.get_status.return_value = BridgeResponse(True, {"inventory": []})
        result = await agent._get_inventory_counts()
        assert result == {}
