"""
Hierarchical Planner for Minecraft

Decomposes high-level goals into ordered sub-goals using tech tree knowledge.
Inspired by GITM (Ghost in the Minecraft) hierarchical planning.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

from .tech_tree import (
    RECIPES, SMELTING, RAW_MATERIALS, ORE_REQUIREMENTS,
    get_prerequisites, can_craft, missing_ingredients, get_tool_for_ore,
    resolve_item
)

logger = logging.getLogger(__name__)


@dataclass
class SubGoal:
    """A single step in a hierarchical plan."""
    action: str          # collect, craft, smelt, mine, find, equip
    target: str          # item or block name
    count: int = 1       # quantity needed
    reason: str = ""     # why this step is needed
    completed: bool = False
    
    def __str__(self):
        return f"{self.action} {self.target} x{self.count}"


class HierarchicalPlanner:
    """
    Decomposes high-level goals into executable action sequences.
    
    Example:
        goal = "get diamond"
        plan = planner.decompose(goal, inventory)
        # Returns: [
        #   SubGoal(collect, log, 3),
        #   SubGoal(craft, planks, 12),
        #   SubGoal(craft, stick, 4),
        #   SubGoal(craft, wooden_pickaxe, 1),
        #   SubGoal(collect, cobblestone, 11),
        #   SubGoal(craft, stone_pickaxe, 1),
        #   SubGoal(craft, furnace, 1),
        #   SubGoal(collect, iron_ore, 3),
        #   SubGoal(smelt, iron_ingot, 3),
        #   SubGoal(craft, iron_pickaxe, 1),
        #   SubGoal(find, diamond_ore, 1),
        #   SubGoal(mine, diamond_ore, 1),
        # ]
    """
    
    def __init__(self):
        self.current_plan: List[SubGoal] = []
        self.goal_stack: List[str] = []
    
    def decompose(
        self, 
        goal: str, 
        inventory: Dict[str, int],
        count: int = 1
    ) -> List[SubGoal]:
        """
        Decompose a high-level goal into ordered sub-goals.
        
        Args:
            goal: Target item to obtain (e.g., "diamond", "iron_pickaxe")
            inventory: Current inventory {item_name: count}
            count: How many of the goal item we need
            
        Returns:
            List of SubGoal objects in execution order
        """
        plan = []
        
        # Resolve fuzzy names (e.g. "planks" -> "oak_planks")
        goal = resolve_item(goal)
        
        # Already have it?
        if inventory.get(goal, 0) >= count:
            return []
        
        needed = count - inventory.get(goal, 0)
        
        # Is it a raw material we can just collect?
        if goal in RAW_MATERIALS:
            # Check if we need a specific tool
            if goal.endswith("_ore"):
                tool = get_tool_for_ore(goal)
                if not self._has_tool(tool, inventory):
                    # Need to get the tool first
                    plan.extend(self.decompose(tool, inventory, 1))
                    # Update virtual inventory
                    inventory = dict(inventory)
                    inventory[tool] = 1
                plan.append(SubGoal("find", goal, 1, f"Locate {goal}"))
                plan.append(SubGoal("mine", goal, needed, f"Mine {needed} {goal}"))
            else:
                plan.append(SubGoal("collect", goal, needed, f"Gather {needed} {goal}"))
            return plan
        
        # Can we smelt something to get it?
        if goal in SMELTING:
            ore = SMELTING[goal]
            # Get the ore first
            plan.extend(self.decompose(ore, inventory, needed))
            # Update virtual inventory
            inventory = dict(inventory)
            inventory[ore] = inventory.get(ore, 0) + needed
            
            # Need furnace?
            if not self._has_item("furnace", inventory):
                plan.extend(self.decompose("furnace", inventory, 1))
                inventory["furnace"] = 1
            
            plan.append(SubGoal("smelt", goal, needed, f"Smelt {ore} into {goal}"))
            return plan
        
        # Can we craft it?
        if goal in RECIPES:
            # Get all missing ingredients
            missing = missing_ingredients(goal, inventory)
            
            for ingredient, ing_needed in missing:
                # Recursively decompose each ingredient
                sub_plan = self.decompose(ingredient, inventory, ing_needed)
                plan.extend(sub_plan)
                
                # Update virtual inventory
                inventory = dict(inventory)
                recipe = RECIPES.get(ingredient)
                recipe_yield = recipe[1] if isinstance(recipe, tuple) else 1
                import math
                actual_gain = math.ceil(ing_needed / recipe_yield) * recipe_yield
                inventory[ingredient] = inventory.get(ingredient, 0) + actual_gain
            
            # Need crafting table for multi-slot recipes?
            if len(RECIPES[goal]) > 4 and not self._has_item("crafting_table", inventory):
                plan.extend(self.decompose("crafting_table", inventory, 1))
                inventory["crafting_table"] = 1
            
            plan.append(SubGoal("craft", goal, needed, f"Craft {goal}"))
            return plan
        
        # Try dynamic knowledge base for unknown items
        from .knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        recipe = kb.lookup_recipe(goal)
        if recipe and recipe.get("ingredients"):
            for ingredient, qty in recipe["ingredients"].items():
                plan.extend(self.decompose(ingredient, inventory, int(qty)))
                inventory = dict(inventory)
                inventory[ingredient] = inventory.get(ingredient, 0) + int(qty)
            
            if recipe.get("needs_table") and not self._has_item("crafting_table", inventory):
                plan.extend(self.decompose("crafting_table", inventory, 1))
                inventory["crafting_table"] = 1
            
            plan.append(SubGoal("craft", goal, needed, f"Craft {goal} (dynamic recipe)"))
            return plan
        
        # Unknown item - just try to collect it
        plan.append(SubGoal("collect", goal, needed, f"Find {goal}"))
        return plan
    
    def _has_tool(self, tool: str, inventory: Dict[str, int]) -> bool:
        """Check if we have a specific tool or better."""
        tool_hierarchy = {
            "wooden_pickaxe": 0,
            "stone_pickaxe": 1,
            "iron_pickaxe": 2,
            "diamond_pickaxe": 3,
        }
        
        if tool not in tool_hierarchy:
            return inventory.get(tool, 0) > 0
        
        min_tier = tool_hierarchy[tool]
        for t, tier in tool_hierarchy.items():
            if tier >= min_tier and inventory.get(t, 0) > 0:
                return True
        return False
    
    def _has_item(self, item: str, inventory: Dict[str, int]) -> bool:
        """Check if we have an item."""
        return inventory.get(item, 0) > 0
    
    def simplify_plan(self, plan: List[SubGoal]) -> List[SubGoal]:
        """
        Combine duplicate steps and optimize the plan.
        """
        # Combine same action+target
        combined = {}
        for step in plan:
            key = (step.action, step.target)
            if key in combined:
                combined[key].count += step.count
            else:
                combined[key] = SubGoal(
                    step.action, step.target, step.count, step.reason
                )
        
        return list(combined.values())
    
    def to_actions(self, plan: List[SubGoal]) -> List[str]:
        """Convert plan to executable action strings."""
        actions = []
        for step in plan:
            if step.action == "collect":
                actions.append(f"collect {step.target} {step.count}")
            elif step.action == "craft":
                actions.append(f"craft {step.target}")
            elif step.action == "smelt":
                actions.append(f"smelt {step.target}")
            elif step.action == "find":
                actions.append(f"find {step.target}")
            elif step.action == "mine":
                actions.append(f"collect {step.target} {step.count}")
            else:
                actions.append(f"{step.action} {step.target}")
        return actions


def plan_goal(goal: str, inventory: Dict[str, int] = None) -> List[str]:
    """
    Simple interface to get executable actions for a goal.
    
    Args:
        goal: What to obtain (e.g., "diamond_pickaxe")
        inventory: Current inventory, defaults to empty
        
    Returns:
        List of action strings ready for execution
    """
    planner = HierarchicalPlanner()
    inventory = inventory or {}
    plan = planner.decompose(goal, inventory)
    simplified = planner.simplify_plan(plan)
    return planner.to_actions(simplified)
