"""
Coverage tests for gaming/tech_tree.py — targets uncovered lines 114-162.

Tests: get_prerequisites, get_tool_for_ore, can_craft, missing_ingredients.
"""
import pytest
from src.gaming.tech_tree import (
    get_prerequisites, get_tool_for_ore, can_craft, missing_ingredients,
    RECIPES, SMELTING, RAW_MATERIALS, ORE_REQUIREMENTS, TOOL_TIERS
)


class TestGetPrerequisites:
    def test_raw_material(self):
        """Raw materials should just need collecting."""
        result = get_prerequisites("oak_log")
        assert result == [("oak_log", 1)]

    def test_raw_ore(self):
        result = get_prerequisites("iron_ore")
        assert result == [("iron_ore", 1)]

    def test_simple_craft(self):
        """Planks need log."""
        result = get_prerequisites("oak_planks")
        assert ("craft", "oak_planks") in result
        # Should include oak_log as prerequisite
        log_entries = [(item, count) for item, count in result if item == "oak_log"]
        assert len(log_entries) > 0

    def test_smelted_item(self):
        """Iron ingot needs iron_ore + smelting."""
        result = get_prerequisites("iron_ingot")
        assert ("smelt", "iron_ingot") in result

    def test_multi_step_craft(self):
        """Stick needs planks which need log."""
        result = get_prerequisites("stick")
        assert ("craft", "stick") in result

    def test_complex_item(self):
        """Diamond pickaxe needs diamond + sticks + planks + log."""
        result = get_prerequisites("diamond_pickaxe")
        assert ("craft", "diamond_pickaxe") in result
        items = [item for item, count in result]
        assert "diamond" in items

    def test_unknown_item(self):
        """Unknown item should just return it as (item, 1)."""
        result = get_prerequisites("netherite_thing")
        assert result == [("netherite_thing", 1)]

    def test_torch_requires_stick_and_coal(self):
        result = get_prerequisites("torch")
        assert ("craft", "torch") in result

    def test_furnace_requires_cobblestone(self):
        result = get_prerequisites("furnace")
        assert ("craft", "furnace") in result
        cobble = [(item, count) for item, count in result if item == "cobblestone"]
        assert len(cobble) > 0

    def test_ore_as_smelting_input(self):
        """Items that ARE the input to smelting (ores) should be handled."""
        # iron_ore is in SMELTING.values() → triggers the 'this is an ore' branch
        result = get_prerequisites("iron_ore")
        assert result == [("iron_ore", 1)]  # raw material

    def test_cooked_beef(self):
        """Cooked beef needs beef + smelting."""
        result = get_prerequisites("cooked_beef")
        assert ("smelt", "cooked_beef") in result

    def test_stone_via_smelting(self):
        """Stone is a raw material; smelting stone yields smooth_stone."""
        result = get_prerequisites("stone")
        # Stone is a raw material, so first entry is ('stone', 1)
        # Then it smelts to smooth_stone
        assert ("stone", 1) in result

    def test_glass_from_sand(self):
        result = get_prerequisites("glass")
        assert ("smelt", "glass") in result

    def test_armor_iron(self):
        result = get_prerequisites("iron_chestplate")
        assert ("craft", "iron_chestplate") in result


class TestGetToolForOre:
    def test_coal_ore(self):
        assert get_tool_for_ore("coal_ore") == "wooden_pickaxe"

    def test_iron_ore(self):
        assert get_tool_for_ore("iron_ore") == "stone_pickaxe"

    def test_diamond_ore(self):
        assert get_tool_for_ore("diamond_ore") == "iron_pickaxe"

    def test_obsidian(self):
        assert get_tool_for_ore("obsidian") == "diamond_pickaxe"

    def test_unknown_ore(self):
        assert get_tool_for_ore("unknown_ore") == "wooden_pickaxe"


class TestCanCraft:
    def test_can_craft_planks(self):
        inv = {"oak_log": 1}
        assert can_craft("oak_planks", inv) is True

    def test_cannot_craft_planks_no_log(self):
        inv = {}
        assert can_craft("oak_planks", inv) is False

    def test_can_craft_torch(self):
        inv = {"stick": 1, "coal": 1}
        assert can_craft("torch", inv) is True

    def test_cannot_craft_diamond_pickaxe(self):
        inv = {"diamond": 2, "stick": 2}  # Need 3 diamonds
        assert can_craft("diamond_pickaxe", inv) is False

    def test_can_craft_diamond_pickaxe(self):
        inv = {"diamond": 3, "stick": 2}
        assert can_craft("diamond_pickaxe", inv) is True

    def test_unknown_recipe(self):
        assert can_craft("unknown_item", {}) is False


class TestMissingIngredients:
    def test_all_missing(self):
        result = missing_ingredients("oak_planks", {})
        assert ("oak_log", 1) in result

    def test_partial_missing(self):
        result = missing_ingredients("diamond_pickaxe", {"diamond": 1, "stick": 2})
        assert ("diamond", 2) in result
        # stick has enough
        stick_missing = [x for x in result if x[0] == "stick"]
        assert len(stick_missing) == 0

    def test_nothing_missing(self):
        result = missing_ingredients("oak_planks", {"oak_log": 5})
        assert result == []

    def test_unknown_recipe(self):
        result = missing_ingredients("unknown_item", {})
        assert result == []

    def test_torch_missing_coal(self):
        result = missing_ingredients("torch", {"stick": 1})
        assert ("coal", 1) in result


class TestModuleConstants:
    """Verify module-level constants are populated."""

    def test_tool_tiers_exist(self):
        assert "wood" in TOOL_TIERS
        assert "diamond" in TOOL_TIERS

    def test_recipes_populated(self):
        assert len(RECIPES) > 10

    def test_smelting_populated(self):
        assert "iron_ingot" in SMELTING

    def test_raw_materials_populated(self):
        assert "oak_log" in RAW_MATERIALS
        assert "diamond_ore" in RAW_MATERIALS

    def test_ore_requirements_populated(self):
        assert "diamond_ore" in ORE_REQUIREMENTS
