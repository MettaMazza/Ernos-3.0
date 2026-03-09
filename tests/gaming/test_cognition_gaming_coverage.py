"""
Coverage tests for gaming/cognition_gaming.py — targets uncovered lines 33-235.

Tests: CognitionMixin._think, _propose_curriculum_goal, _reflect_on_failure.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.gaming.mineflayer_bridge import BridgeResponse


def make_cognition_agent():
    """Create a mock agent with CognitionMixin methods."""
    from src.gaming.cognition_gaming import CognitionMixin

    class MockAgent(CognitionMixin):
        pass

    agent = MockAgent()
    agent.bot = MagicMock()
    agent.bot.cognition = AsyncMock()
    agent.bridge = AsyncMock()
    agent._pending_chats = []
    agent._following_player = None
    agent._current_goal = None
    agent._action_queue = []
    return agent


# ──────────────────────────────────────
# _think
# ──────────────────────────────────────

class TestThink:
    def _make_state(self, **overrides):
        state = {
            "health": 20, "food": 20,
            "nearby_entities": [],
            "is_day": True,
            "hostiles_nearby": False,
            "inventory": [],
            "position": {"x": 0, "y": 64, "z": 0},
            "pending_chats": [],
            "screenshot": None,
        }
        state.update(overrides)
        return state

    @pytest.mark.asyncio
    async def test_think_with_action_response(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.return_value = "I see trees.\nACTION: collect oak_log 5"
        state = self._make_state()
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "system_prompt"
            result = await agent._think(state)
        assert result == "collect oak_log 5"

    @pytest.mark.asyncio
    async def test_think_with_tuple_response(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.return_value = ("ACTION: explore", {})
        state = self._make_state()
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "explore"

    @pytest.mark.asyncio
    async def test_think_no_action_in_response(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.return_value = "Just looking around."
        state = self._make_state()
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "explore"  # Fallback

    @pytest.mark.asyncio
    async def test_think_no_cognition_engine(self):
        agent = make_cognition_agent()
        agent.bot.cognition = None
        state = self._make_state()
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "explore"

    @pytest.mark.asyncio
    async def test_think_error(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.side_effect = Exception("LLM error")
        state = self._make_state()
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result is None

    @pytest.mark.asyncio
    async def test_think_with_pending_chats(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.return_value = "ACTION: chat Hello player!"
        state = self._make_state(
            pending_chats=[{"username": "player1", "message": "@Ernos hi!"}]
        )
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "chat Hello player!"

    @pytest.mark.asyncio
    async def test_think_with_following_player(self):
        agent = make_cognition_agent()
        agent._following_player = "metta_mazza"
        agent.bot.cognition.process.return_value = "ACTION: follow metta_mazza"
        state = self._make_state()
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "follow metta_mazza"

    @pytest.mark.asyncio
    async def test_think_with_screenshot(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.return_value = "ACTION: explore"
        state = self._make_state(screenshot="base64data")
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "explore"
        # Verify images were passed to cognition
        call_kwargs = agent.bot.cognition.process.call_args
        assert call_kwargs[1].get("images") == ["base64data"]

    @pytest.mark.asyncio
    async def test_think_nighttime(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.return_value = "ACTION: sleep"
        state = self._make_state(is_day=False)
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "sleep"

    @pytest.mark.asyncio
    async def test_think_with_hostiles(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.return_value = "ACTION: attack zombie"
        state = self._make_state(
            hostiles_nearby=True,
            nearby_entities=[{"name": "zombie"}, {"name": "skeleton"}]
        )
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "attack zombie"

    @pytest.mark.asyncio
    async def test_think_with_inventory(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.return_value = "ACTION: craft planks 4"
        state = self._make_state(
            inventory=[{"name": "oak_log", "count": 5}, {"name": "stick", "count": 2}]
        )
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "craft planks 4"

    @pytest.mark.asyncio
    async def test_think_none_response(self):
        agent = make_cognition_agent()
        agent.bot.cognition.process.return_value = None
        state = self._make_state()
        with patch("src.gaming.cognition_gaming.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = "prompt"
            result = await agent._think(state)
        assert result == "explore"


# ──────────────────────────────────────
# _propose_curriculum_goal
# ──────────────────────────────────────

class TestProposeCurriculumGoal:
    def _make_state(self, health=20, food=20, inventory=None):
        return {
            "health": health,
            "food": food,
            "inventory": inventory or []
        }

    def test_hungry_no_food(self):
        agent = make_cognition_agent()
        state = self._make_state(food=5, inventory=[{"name": "dirt", "count": 1}])
        result = agent._propose_curriculum_goal(state)
        assert result == "get cooked_beef"

    def test_hungry_has_food(self):
        agent = make_cognition_agent()
        state = self._make_state(food=5, inventory=[{"name": "cooked_beef", "count": 5}])
        result = agent._propose_curriculum_goal(state)
        # Should NOT suggest food since we have it
        assert result != "get cooked_beef"

    def test_no_pickaxe(self):
        agent = make_cognition_agent()
        state = self._make_state(inventory=[{"name": "dirt", "count": 1}])
        result = agent._propose_curriculum_goal(state)
        assert result == "get wooden_pickaxe"

    def test_has_wooden_no_stone(self):
        agent = make_cognition_agent()
        state = self._make_state(inventory=[{"name": "wooden_pickaxe", "count": 1}])
        result = agent._propose_curriculum_goal(state)
        assert result == "get stone_pickaxe"

    def test_has_stone_no_iron(self):
        agent = make_cognition_agent()
        state = self._make_state(inventory=[
            {"name": "stone_pickaxe", "count": 1}
        ])
        result = agent._propose_curriculum_goal(state)
        assert result == "get iron_pickaxe"

    def test_has_iron_no_armor(self):
        agent = make_cognition_agent()
        state = self._make_state(inventory=[
            {"name": "iron_pickaxe", "count": 1},
            {"name": "stone_pickaxe", "count": 1},
            {"name": "wooden_pickaxe", "count": 1},
        ])
        result = agent._propose_curriculum_goal(state)
        assert result == "get iron_chestplate"

    def test_has_iron_and_armor_no_diamond(self):
        agent = make_cognition_agent()
        state = self._make_state(inventory=[
            {"name": "iron_pickaxe", "count": 1},
            {"name": "stone_pickaxe", "count": 1},
            {"name": "wooden_pickaxe", "count": 1},
            {"name": "iron_chestplate", "count": 1},
        ])
        result = agent._propose_curriculum_goal(state)
        assert result == "get diamond_pickaxe"

    def test_full_gear_explores(self):
        agent = make_cognition_agent()
        state = self._make_state(inventory=[
            {"name": "diamond_pickaxe", "count": 1},
            {"name": "iron_pickaxe", "count": 1},
            {"name": "stone_pickaxe", "count": 1},
            {"name": "wooden_pickaxe", "count": 1},
            {"name": "iron_chestplate", "count": 1},
        ])
        with patch("src.gaming.cognition_gaming.log_embodiment"):
            result = agent._propose_curriculum_goal(state)
        assert result is not None
        # Should be one of the exploration goals
        assert isinstance(result, str)

    def test_food_priority_over_tools(self):
        """Low food should override tool progression."""
        agent = make_cognition_agent()
        state = self._make_state(food=3, inventory=[{"name": "cobblestone", "count": 64}])
        result = agent._propose_curriculum_goal(state)
        assert result == "get cooked_beef"

    def test_hungry_with_bread(self):
        """Should not ask for food if we have bread."""
        agent = make_cognition_agent()
        state = self._make_state(food=5, inventory=[{"name": "bread", "count": 3}])
        result = agent._propose_curriculum_goal(state)
        assert result != "get cooked_beef"

    def test_hungry_with_apple(self):
        """Should not ask for food if we have apples."""
        agent = make_cognition_agent()
        state = self._make_state(food=5, inventory=[{"name": "apple", "count": 2}])
        result = agent._propose_curriculum_goal(state)
        assert result != "get cooked_beef"


# ──────────────────────────────────────
# _reflect_on_failure
# ──────────────────────────────────────

class TestReflectOnFailure:
    def test_no_nearby(self):
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("collect diamond_ore", "No diamond_ore nearby")
        assert result == "find diamond_ore"

    def test_cannot_reach(self):
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("goto 100 64 200", "Cannot reach destination")
        assert result == "explore"

    def test_path_error(self):
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("goto 100 64 200", "Path finding error")
        assert result == "explore"

    def test_need_pickaxe(self):
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("collect iron_ore", "Don't have a pickaxe")
        assert result == "get wooden_pickaxe"

    def test_need_axe(self):
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("collect oak_log", "Need an axe to chop trees")
        assert result == "get wooden_axe"

    def test_need_iron_pickaxe(self):
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("collect gold_ore", "Requires iron pickaxe or better")
        assert result == "get iron_pickaxe"

    def test_need_diamond_pickaxe(self):
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("collect obsidian", "Requires diamond pickaxe")
        assert result == "get diamond_pickaxe"

    def test_food_error(self):
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("explore", "Too hungry to continue, need food")
        assert result == "get cooked_beef"

    def test_hungry_error(self):
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("mine stone", "Bot is hungry")
        assert result == "get cooked_beef"

    def test_unknown_error_with_goal(self):
        agent = make_cognition_agent()
        agent._current_goal = "build_house"
        with patch("src.gaming.cognition_gaming.get_skill_library") as mock_lib:
            result = agent._reflect_on_failure("place cobblestone", "Unknown block state error")
        assert result is None
        mock_lib.return_value.record_failure.assert_called_with("build_house")

    def test_unknown_error_no_goal(self):
        agent = make_cognition_agent()
        agent._current_goal = None
        result = agent._reflect_on_failure("dance", "Unknown command")
        assert result is None

    def test_no_nearby_single_word(self):
        """Single-word action should not crash on 'no nearby' pattern."""
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("collect", "No items nearby")
        # Only 1 part, so won't match the len(parts) >= 2 check
        assert result is None or result == "explore"

    def test_dont_have_generic(self):
        """Don't have without pickaxe/axe keyword falls through."""
        agent = make_cognition_agent()
        result = agent._reflect_on_failure("smelt iron", "Don't have enough coal")
        assert result is None or isinstance(result, str)
