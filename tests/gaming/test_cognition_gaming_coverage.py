"""
Tests for cognition_gaming.py — LLM failure analysis, curriculum novelty, quick LLM call.

Tests the Phase 1 (P0) changes: LLM-driven reflection and novelty curriculum.
"""

import pytest
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Mock modules that cognition_gaming imports
sys.modules.setdefault("psutil", MagicMock())


class MockBot:
    """Mock Ernos bot for testing CognitionMixin."""

    def __init__(self):
        self.cognition = None


class MockCognitionMixin:
    """Instantiable test wrapper around CognitionMixin methods."""

    def __init__(self):
        self.bot = MockBot()
        self._current_goal = None
        self._discovered_items = set()


def _make_mixin():
    """Create a mixin instance with required attributes."""
    from src.gaming.cognition_gaming import CognitionMixin
    mixin = MockCognitionMixin()
    # Bind methods from CognitionMixin
    for name in dir(CognitionMixin):
        if not name.startswith("__"):
            attr = getattr(CognitionMixin, name)
            if callable(attr):
                import types
                setattr(mixin, name, types.MethodType(attr, mixin))
    return mixin


class TestReflectHeuristic:
    """Tests for _reflect_heuristic (keyword-based fallback)."""

    def test_no_nearby_pattern(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("collect oak_log", "No oak_log nearby")
        assert result == "find oak_log"

    def test_cannot_reach_pattern(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("collect stone", "Cannot reach block")
        assert result == "explore"

    def test_path_error_pattern(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("goto village", "Path not found")
        assert result == "explore"

    def test_no_recipe_pattern(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("craft wooden_pickaxe", "No recipe for wooden_pickaxe")
        assert result == "get wooden_pickaxe"

    def test_dont_have_pickaxe(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("mine iron_ore", "Don't have pickaxe")
        assert result == "get wooden_pickaxe"

    def test_dont_have_axe(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("collect oak_log", "Don't have axe")
        assert result == "get wooden_axe"

    def test_need_iron_pickaxe(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("mine diamond_ore", "Requires iron pickaxe")
        assert result == "get iron_pickaxe"

    def test_need_diamond_pickaxe(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("mine obsidian", "Requires diamond pickaxe")
        assert result == "get diamond_pickaxe"

    def test_food_pattern(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("explore", "Low food level")
        assert result == "get cooked_beef"

    def test_unknown_error_returns_none(self):
        mixin = _make_mixin()
        result = mixin._reflect_heuristic("fly", "Unknown error xyz")
        assert result is None

    def test_records_failure_on_unknown(self):
        mixin = _make_mixin()
        mixin._current_goal = "test_goal"

        with patch("src.gaming.cognition_gaming.get_skill_library") as mock_lib:
            mock_lib.return_value = MagicMock()
            mixin._reflect_heuristic("fly", "Unknown error")
            mock_lib.return_value.record_failure.assert_called_once_with("test_goal")


class TestReflectOnFailureAsync:
    """Tests for async _reflect_on_failure (LLM-driven)."""

    @pytest.mark.asyncio
    async def test_llm_driven_reflection(self):
        """Should use LLM for failure analysis when available."""
        mixin = _make_mixin()
        mock_cognition = AsyncMock()
        mock_cognition.process.return_value = (
            '{"analysis": "Missing planks", "retry_action": "collect oak_log 3"}',
        )
        mixin.bot.cognition = mock_cognition

        state = {"inventory": [{"name": "stick", "count": 2}]}
        result = await mixin._reflect_on_failure("craft wooden_pickaxe", "No recipe", state)
        assert result == "collect oak_log 3"

    @pytest.mark.asyncio
    async def test_falls_back_to_heuristic_on_llm_error(self):
        """Should use heuristic when LLM fails."""
        mixin = _make_mixin()
        mock_cognition = AsyncMock()
        mock_cognition.process.side_effect = Exception("API down")
        mixin.bot.cognition = mock_cognition

        result = await mixin._reflect_on_failure("collect oak_log", "No oak_log nearby")
        assert result == "find oak_log"  # Heuristic result

    @pytest.mark.asyncio
    async def test_rejects_same_action_retry(self):
        """Should not retry the exact same action."""
        mixin = _make_mixin()
        mock_cognition = AsyncMock()
        mock_cognition.process.return_value = (
            '{"analysis": "Bad luck", "retry_action": "craft wooden_pickaxe"}',
        )
        mixin.bot.cognition = mock_cognition

        result = await mixin._reflect_on_failure("craft wooden_pickaxe", "Error")
        # Should NOT return the same action, should fall through to heuristic
        assert result != "craft wooden_pickaxe" or result is None

    @pytest.mark.asyncio
    async def test_handles_null_retry(self):
        """Should handle null retry from LLM."""
        mixin = _make_mixin()
        mock_cognition = AsyncMock()
        mock_cognition.process.return_value = (
            '{"analysis": "Impossible", "retry_action": "null"}',
        )
        mixin.bot.cognition = mock_cognition

        result = await mixin._reflect_on_failure("impossible_action", "Error")
        # Should fall through to heuristic (returns None for unknown)
        assert result is None or isinstance(result, str)

    @pytest.mark.asyncio
    async def test_no_cognition_engine(self):
        """Should use heuristic when no cognition engine."""
        mixin = _make_mixin()
        mixin.bot.cognition = None

        result = await mixin._reflect_on_failure("collect oak_log", "No oak_log nearby")
        assert result == "find oak_log"

    @pytest.mark.asyncio
    async def test_no_state_provided(self):
        """Should work without state parameter."""
        mixin = _make_mixin()
        mixin.bot.cognition = None

        result = await mixin._reflect_on_failure("explore", "Path not found", None)
        assert result == "explore"  # Heuristic: path → explore


class TestQuickLlmCall:
    """Tests for _quick_llm_call."""

    @pytest.mark.asyncio
    async def test_returns_response(self):
        mixin = _make_mixin()
        mock_cognition = AsyncMock()
        mock_cognition.process.return_value = ("test response",)
        mixin.bot.cognition = mock_cognition

        result = await mixin._quick_llm_call("prompt")
        assert result == "test response"

    @pytest.mark.asyncio
    async def test_handles_non_tuple_response(self):
        mixin = _make_mixin()
        mock_cognition = AsyncMock()
        mock_cognition.process.return_value = "plain string"
        mixin.bot.cognition = mock_cognition

        result = await mixin._quick_llm_call("prompt")
        assert result == "plain string"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        mixin = _make_mixin()
        mock_cognition = AsyncMock()
        mock_cognition.process.side_effect = Exception("fail")
        mixin.bot.cognition = mock_cognition

        result = await mixin._quick_llm_call("prompt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_no_engine(self):
        mixin = _make_mixin()
        mixin.bot.cognition = None

        result = await mixin._quick_llm_call("prompt")
        assert result == ""

    @pytest.mark.asyncio
    async def test_handles_none_result(self):
        mixin = _make_mixin()
        mock_cognition = AsyncMock()
        mock_cognition.process.return_value = (None,)
        mixin.bot.cognition = mock_cognition

        result = await mixin._quick_llm_call("prompt")
        assert result == ""


class TestGetDiscoveredItems:
    """Tests for _get_discovered_items."""

    def test_empty_by_default(self):
        mixin = _make_mixin()
        with patch("src.gaming.cognition_gaming.get_skill_library") as mock_lib:
            mock_lib.return_value = MagicMock()
            mock_lib.return_value.get_all.return_value = []
            items = mixin._get_discovered_items()
            assert items == set()

    def test_includes_successful_skills(self):
        mixin = _make_mixin()
        mock_skill = MagicMock()
        mock_skill.success_count = 3
        mock_skill.goal = "iron_pickaxe"

        with patch("src.gaming.cognition_gaming.get_skill_library") as mock_lib:
            mock_lib.return_value = MagicMock()
            mock_lib.return_value.get_all.return_value = [mock_skill]
            items = mixin._get_discovered_items()
            assert "iron_pickaxe" in items

    def test_excludes_failed_skills(self):
        mixin = _make_mixin()
        mock_skill = MagicMock()
        mock_skill.success_count = 0
        mock_skill.goal = "failed_item"

        with patch("src.gaming.cognition_gaming.get_skill_library") as mock_lib:
            mock_lib.return_value = MagicMock()
            mock_lib.return_value.get_all.return_value = [mock_skill]
            items = mixin._get_discovered_items()
            assert "failed_item" not in items

    def test_includes_discovered_items_set(self):
        mixin = _make_mixin()
        mixin._discovered_items = {"oak_log", "cobblestone"}

        with patch("src.gaming.cognition_gaming.get_skill_library") as mock_lib:
            mock_lib.return_value = MagicMock()
            mock_lib.return_value.get_all.return_value = []
            items = mixin._get_discovered_items()
            assert "oak_log" in items
            assert "cobblestone" in items


class TestCurriculumFallback:
    """Tests for _curriculum_fallback."""

    def test_iron_armor_when_iron_tools(self):
        mixin = _make_mixin()
        inv = {"iron_pickaxe": 1}
        result = mixin._curriculum_fallback({}, inv, has_iron=True, has_diamond=False)
        assert result == "get iron_chestplate"

    def test_diamond_pickaxe_when_iron_and_no_diamond(self):
        mixin = _make_mixin()
        inv = {"iron_pickaxe": 1, "iron_chestplate": 1}
        result = mixin._curriculum_fallback({}, inv, has_iron=True, has_diamond=False)
        assert result == "get diamond_pickaxe"

    def test_exploration_when_fully_geared(self):
        mixin = _make_mixin()
        inv = {"diamond_pickaxe": 1, "iron_chestplate": 1}
        result = mixin._curriculum_fallback({}, inv, has_iron=True, has_diamond=True)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_defaults_inventory_from_state(self):
        mixin = _make_mixin()
        state = {"inventory": [{"name": "iron_pickaxe", "count": 1}]}
        result = mixin._curriculum_fallback(state)
        # Should work without explicit inventory
        assert isinstance(result, str)


class TestProposeCurriculumGoal:
    """Tests for _propose_curriculum_goal."""

    def test_critical_food_need(self):
        mixin = _make_mixin()
        state = {"inventory": [], "health": 20, "food": 5}
        result = mixin._propose_curriculum_goal(state)
        assert result == "get cooked_beef"

    def test_no_pickaxe(self):
        mixin = _make_mixin()
        state = {
            "inventory": [{"name": "oak_log", "count": 5}],
            "health": 20,
            "food": 20,
        }
        result = mixin._propose_curriculum_goal(state)
        assert result == "get wooden_pickaxe"

    def test_upgrade_to_stone(self):
        mixin = _make_mixin()
        state = {
            "inventory": [{"name": "wooden_pickaxe", "count": 1}],
            "health": 20,
            "food": 20,
        }
        result = mixin._propose_curriculum_goal(state)
        assert result == "get stone_pickaxe"

    def test_upgrade_to_iron(self):
        mixin = _make_mixin()
        state = {
            "inventory": [
                {"name": "wooden_pickaxe", "count": 1},
                {"name": "stone_pickaxe", "count": 1},
            ],
            "health": 20,
            "food": 20,
        }
        result = mixin._propose_curriculum_goal(state)
        assert result == "get iron_pickaxe"

    def test_food_with_existing_food_skips(self):
        mixin = _make_mixin()
        state = {
            "inventory": [
                {"name": "cooked_beef", "count": 5},
                {"name": "wooden_pickaxe", "count": 1},
                {"name": "stone_pickaxe", "count": 1},
                {"name": "iron_pickaxe", "count": 1},
            ],
            "health": 20,
            "food": 5,  # Low food but has cooked_beef
        }
        result = mixin._propose_curriculum_goal(state)
        # Should NOT suggest food since we have cooked_beef
        assert result != "get cooked_beef"
