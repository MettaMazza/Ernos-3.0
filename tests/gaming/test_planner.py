"""
Tests for Hierarchical Planning System

Test-driven development for tech tree and planner.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestTechTree:
    """Tests for tech_tree.py"""
    
    def test_recipes_exist(self):
        """Core recipes should be defined."""
        from src.gaming.tech_tree import RECIPES
        
        assert "wooden_pickaxe" in RECIPES
        assert "stone_pickaxe" in RECIPES
        assert "iron_pickaxe" in RECIPES
        assert "diamond_pickaxe" in RECIPES
        assert "furnace" in RECIPES
    
    def test_smelting_recipes(self):
        """Smelting should map output -> input."""
        from src.gaming.tech_tree import SMELTING
        
        assert SMELTING["iron_ingot"] == "iron_ore"
        assert SMELTING["gold_ingot"] == "gold_ore"
        assert SMELTING["cooked_beef"] == "beef"
    
    def test_raw_materials(self):
        """Raw materials should include gatherable items."""
        from src.gaming.tech_tree import RAW_MATERIALS
        
        assert "oak_log" in RAW_MATERIALS
        assert "cobblestone" in RAW_MATERIALS
        assert "iron_ore" in RAW_MATERIALS
        assert "diamond_ore" in RAW_MATERIALS
    
    def test_ore_requirements(self):
        """Ores should require correct pickaxe tier."""
        from src.gaming.tech_tree import ORE_REQUIREMENTS
        
        assert ORE_REQUIREMENTS["coal_ore"] == "wooden_pickaxe"
        assert ORE_REQUIREMENTS["iron_ore"] == "stone_pickaxe"
        assert ORE_REQUIREMENTS["diamond_ore"] == "iron_pickaxe"
    
    def test_can_craft_with_ingredients(self):
        """can_craft should return True with all ingredients."""
        from src.gaming.tech_tree import can_craft
        
        inventory = {"oak_planks": 10, "stick": 5}
        assert can_craft("wooden_pickaxe", inventory) is True
    
    def test_cannot_craft_without_ingredients(self):
        """can_craft should return False without ingredients."""
        from src.gaming.tech_tree import can_craft
        
        inventory = {"oak_planks": 1}  # Not enough
        assert can_craft("wooden_pickaxe", inventory) is False
    
    def test_missing_ingredients(self):
        """missing_ingredients should list what's needed."""
        from src.gaming.tech_tree import missing_ingredients
        
        inventory = {"oak_planks": 1, "stick": 0}
        missing = missing_ingredients("wooden_pickaxe", inventory)
        
        # Should need 2 more oak_planks and 2 sticks
        assert ("oak_planks", 2) in missing
        assert ("stick", 2) in missing


class TestHierarchicalPlanner:
    """Tests for planner.py"""
    
    def test_decompose_raw_material(self):
        """Collecting raw materials should be single step."""
        from src.gaming.planner import HierarchicalPlanner
        
        planner = HierarchicalPlanner()
        plan = planner.decompose("oak_log", {}, 5)
        
        assert len(plan) == 1
        assert plan[0].action == "collect"
        assert plan[0].target == "oak_log"
        assert plan[0].count == 5
    
    def test_decompose_craftable_item(self):
        """Crafting should include gathering ingredients."""
        from src.gaming.planner import HierarchicalPlanner
        
        planner = HierarchicalPlanner()
        plan = planner.decompose("wooden_pickaxe", {})
        
        # Should include: collect oak_log, craft oak_planks, craft stick, craft pickaxe
        actions = [s.action for s in plan]
        targets = [s.target for s in plan]
        
        assert "collect" in actions
        assert "craft" in actions
        assert "oak_planks" in targets or "oak_log" in targets
    
    def test_decompose_smeltable(self):
        """Smelting should include getting ore and furnace."""
        from src.gaming.planner import HierarchicalPlanner
        
        planner = HierarchicalPlanner()
        plan = planner.decompose("iron_ingot", {})
        
        actions = [s.action for s in plan]
        targets = [s.target for s in plan]
        
        # Should include smelting
        assert "smelt" in actions
        assert "iron_ingot" in targets
    
    def test_decompose_already_have_item(self):
        """Should return empty plan if already have item."""
        from src.gaming.planner import HierarchicalPlanner
        
        planner = HierarchicalPlanner()
        inventory = {"diamond": 10}
        plan = planner.decompose("diamond", inventory, 5)
        
        assert plan == []
    
    def test_ore_requires_tool(self):
        """Mining ore should require appropriate pickaxe."""
        from src.gaming.planner import HierarchicalPlanner
        
        planner = HierarchicalPlanner()
        plan = planner.decompose("diamond_ore", {})
        
        targets = [s.target for s in plan]
        
        # Should require iron pickaxe before mining diamond
        assert "iron_pickaxe" in targets or "iron_ingot" in targets
    
    def test_plan_goal_convenience(self):
        """plan_goal should return action strings."""
        from src.gaming.planner import plan_goal
        
        actions = plan_goal("torch", {"coal": 1})
        
        # Should need stick (from planks from log)
        assert any("log" in a or "stick" in a or "planks" in a for a in actions)
    
    def test_simplify_combines_duplicates(self):
        """simplify_plan should combine duplicate steps."""
        from src.gaming.planner import HierarchicalPlanner, SubGoal
        
        planner = HierarchicalPlanner()
        plan = [
            SubGoal("collect", "log", 3),
            SubGoal("collect", "log", 2),
            SubGoal("craft", "planks", 1),
        ]
        
        simplified = planner.simplify_plan(plan)
        
        # Should have 2 steps (combined logs + craft)
        assert len(simplified) == 2
        # Log count should be combined
        log_step = next(s for s in simplified if s.target == "log")
        assert log_step.count == 5
    
    def test_to_actions_format(self):
        """to_actions should return properly formatted strings."""
        from src.gaming.planner import HierarchicalPlanner, SubGoal
        
        planner = HierarchicalPlanner()
        plan = [
            SubGoal("collect", "cobblestone", 8),
            SubGoal("craft", "furnace", 1),
        ]
        
        actions = planner.to_actions(plan)
        
        assert actions[0] == "collect cobblestone 8"
        assert actions[1] == "craft furnace"


class TestComplexPlans:
    """Tests for complex multi-step planning."""
    
    def test_diamond_pickaxe_plan(self):
        """Diamond pickaxe should require full tech tree."""
        from src.gaming.planner import plan_goal
        
        actions = plan_goal("diamond_pickaxe")
        
        # Should be a substantial plan
        assert len(actions) >= 5
        
        # Should include diamond at some point
        assert any("diamond" in a for a in actions)
    
    def test_iron_armor_plan(self):
        """Iron chestplate should require iron ingots."""
        from src.gaming.planner import plan_goal
        
        actions = plan_goal("iron_chestplate")
        
        # Should include smelting iron
        assert any("smelt" in a and "iron" in a for a in actions)
    
    def test_incremental_planning(self):
        """Planning with partial inventory should skip steps."""
        from src.gaming.planner import plan_goal
        
        # Already have iron pickaxe - mining diamond_ore is easier
        actions_with = plan_goal("diamond_ore", {"iron_pickaxe": 1})
        actions_without = plan_goal("diamond_ore", {})
        
        # Should have fewer steps when starting with iron pickaxe
        assert len(actions_with) < len(actions_without)
