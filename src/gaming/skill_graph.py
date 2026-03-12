"""
Skill Dependency Graph — extends beyond recipe-only tech tree.

Maps complex goals (building, farming, exploring, combat) to their
prerequisite skill chains using LLM-generated dependency relationships.
Complements the recipe-based HierarchicalPlanner with non-crafting goals.
"""

import json
import logging
import os
from collections import deque
from typing import Dict, List, Optional, Set

logger = logging.getLogger("Gaming.SkillGraph")


class SkillGraph:
    """LLM-built dependency graph for complex Minecraft goals.
    
    Beyond recipes: covers building, farming, exploring, combat.
    Example: "build shelter" → ["find flat area", "collect oak_log 20",
             "craft oak_planks 80", "place blocks in pattern"]
    """
    
    GRAPH_FILE = "./memory/public/skill_graph.json"
    
    # Seed graph with common non-crafting goals
    DEFAULT_GRAPH = {
        "build shelter": ["collect oak_log 20", "craft oak_planks 80", "craft door"],
        "build house": ["build shelter", "craft glass_pane 8", "craft bed"],
        "start farm": ["craft wooden_hoe", "collect wheat_seeds", "find water"],
        "go mining": ["get wooden_pickaxe", "craft torch 10", "find cave"],
        "explore cave": ["get stone_pickaxe", "craft torch 20", "get wooden_sword"],
        "prepare for night": ["craft bed", "build shelter", "craft torch 4"],
        "go fishing": ["craft fishing_rod", "find water"],
        "breed animals": ["start farm", "collect wheat 10", "find cow"],
        "enchant items": ["get diamond_pickaxe", "craft enchanting_table", "collect book 3"],
        "make portal": ["get diamond_pickaxe", "collect obsidian 10", "craft flint_and_steel"],
    }
    
    def __init__(self):
        self.graph: Dict[str, List[str]] = {}
        self._load()
    
    def _load(self):
        """Load skill graph from disk, merge with defaults."""
        self.graph = dict(self.DEFAULT_GRAPH)
        if os.path.exists(self.GRAPH_FILE):
            try:
                with open(self.GRAPH_FILE, 'r') as f:
                    saved = json.load(f)
                self.graph.update(saved)
                logger.info(f"Loaded skill graph: {len(self.graph)} goals")
            except Exception as e:
                logger.warning(f"Failed to load skill graph: {e}")
    
    def _save(self):
        """Persist graph to disk."""
        try:
            os.makedirs(os.path.dirname(self.GRAPH_FILE), exist_ok=True)
            with open(self.GRAPH_FILE, 'w') as f:
                json.dump(self.graph, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save skill graph: {e}")
    
    def get_plan(self, goal: str, completed: Set[str] = None) -> List[str]:
        """Get ordered action list for a goal, skipping completed steps.
        
        Performs BFS expansion of dependencies, handling nested goals.
        """
        if completed is None:
            completed = set()
        
        if goal not in self.graph:
            return [goal]  # Leaf action — execute directly
        
        # Expand all dependencies into flat list
        result = []
        expanded = set()  # Goals already expanded (prevents infinite recursion)
        
        def _expand(g: str):
            if g in expanded or g in completed:
                return
            if g in self.graph:
                expanded.add(g)
                for dep in self.graph[g]:
                    _expand(dep)
            else:
                # Leaf action — add to result
                if g not in completed and g not in result:
                    result.append(g)
        
        _expand(goal)
        return result
    
    def add_goal(self, goal: str, prerequisites: List[str]):
        """Add or update a goal's prerequisites."""
        self.graph[goal] = prerequisites
        self._save()
        logger.info(f"Added skill graph goal: '{goal}' → {prerequisites}")
    
    async def add_goal_via_llm(self, goal: str, engine) -> List[str]:
        """Ask LLM to define prerequisites for an unknown goal.
        
        Returns the generated prerequisite list.
        """
        prompt = (
            f"Break down this Minecraft goal into specific prerequisite steps:\n"
            f"Goal: {goal}\n\n"
            f"Reply as JSON: {{\"prerequisites\": [\"step1\", \"step2\", ...]}}\n"
            f"Each step should be a concrete action starting with: collect, craft, get, find, build, place.\n"
            f"List them in order of execution (earliest first).\n"
            f"Keep it to 3-8 steps maximum."
        )
        
        try:
            result = await engine.process(
                input_text=prompt,
                context="",
                system_context="You are a Minecraft planning expert. Reply ONLY with valid JSON.",
                complexity="LOW",
                skip_defenses=True
            )
            
            response = str(result[0]) if isinstance(result, tuple) else str(result)
            
            if response and "{" in response:
                json_str = response[response.index("{"):response.rindex("}")+1]
                data = json.loads(json_str)
                prereqs = data.get("prerequisites", [])
                if prereqs and isinstance(prereqs, list):
                    self.add_goal(goal, prereqs)
                    return prereqs
        except Exception as e:
            logger.warning(f"LLM skill graph query failed for '{goal}': {e}")
        
        return []
    
    def has_goal(self, goal: str) -> bool:
        """Check if a goal exists in the graph."""
        return goal in self.graph


# Singleton
_skill_graph = None

def get_skill_graph() -> SkillGraph:
    """Get the global skill graph instance."""
    global _skill_graph
    if _skill_graph is None:
        _skill_graph = SkillGraph()
    return _skill_graph
