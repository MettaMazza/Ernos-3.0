"""
Dynamic Minecraft Knowledge Base

Extends the static tech_tree.py with LLM-queried recipe knowledge.
When the planner encounters an unknown item, this module asks the LLM
for the recipe instead of falling back to blind collect.
"""

import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger("Gaming.KnowledgeBase")


class MinecraftKnowledge:
    """Dynamic Minecraft knowledge — extends static tech tree.
    
    Sources (checked in order):
    1. Local cache (persisted to disk)
    2. Static tech_tree.py
    3. LLM knowledge (ask the engine)
    """
    
    CACHE_FILE = "./memory/public/minecraft_knowledge.json"
    
    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached recipes from disk."""
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} cached recipes")
            except Exception as e:
                logger.warning(f"Failed to load knowledge cache: {e}")
    
    def _save_cache(self):
        """Persist cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save knowledge cache: {e}")
    
    def lookup_recipe(self, item: str) -> Optional[dict]:
        """Look up a recipe, checking cache first, then static tree, then LLM.
        
        Returns:
            dict with 'ingredients' (list of [item, count] pairs) and 'source',
            or None if unknown.
        """
        # 1. Check cache
        if item in self._cache:
            return self._cache[item]
        
        # 2. Check static tech tree
        from .tech_tree import RECIPES, SMELTING, RAW_MATERIALS
        if item in RECIPES:
            recipe = {
                "ingredients": {ing: count for ing, count in RECIPES[item]},
                "source": "tech_tree",
                "needs_table": len(RECIPES[item]) > 4,
            }
            self._cache[item] = recipe
            return recipe
        
        if item in SMELTING:
            recipe = {
                "ingredients": {SMELTING[item]: 1},
                "source": "tech_tree_smelting",
                "type": "smelting",
            }
            self._cache[item] = recipe
            return recipe
        
        if item in RAW_MATERIALS:
            recipe = {
                "ingredients": {},
                "source": "raw_material",
                "type": "collect",
            }
            return recipe
        
        # 3. Unknown — will be queried via LLM when called from async context
        return None
    
    async def lookup_recipe_async(self, item: str, engine=None) -> Optional[dict]:
        """Look up a recipe with LLM fallback for unknown items.
        
        Args:
            item: Minecraft item name
            engine: CognitionEngine or bot.cognition for LLM queries
        """
        # Check sync sources first
        result = self.lookup_recipe(item)
        if result is not None:
            return result
        
        # 4. Ask LLM for the recipe
        if engine:
            recipe = await self._ask_llm_recipe(item, engine)
            if recipe:
                self._cache[item] = recipe
                self._save_cache()
                return recipe
        
        return None
    
    async def _ask_llm_recipe(self, item: str, engine) -> Optional[dict]:
        """Query LLM for a Minecraft crafting recipe.
        
        Returns dict with 'ingredients' or None.
        """
        prompt = (
            f"What is the Minecraft Java Edition crafting recipe for '{item}'?\n\n"
            f"Reply as JSON ONLY: {{\"ingredients\": {{\"item_name\": count, ...}}, \"needs_table\": true/false}}\n"
            f"Use exact Minecraft item IDs (e.g., 'oak_planks' not 'planks', 'iron_ingot' not 'iron').\n"
            f"If this item cannot be crafted, reply: {{\"error\": \"not craftable\"}}"
        )
        
        try:
            result = await engine.process(
                input_text=prompt,
                context="",
                system_context="You are a Minecraft recipe database. Reply ONLY with valid JSON.",
                complexity="LOW",
                skip_defenses=True
            )
            
            response = str(result[0]) if isinstance(result, tuple) else str(result)
            
            if response and "{" in response:
                json_str = response[response.index("{"):response.rindex("}")+1]
                data = json.loads(json_str)
                
                if "error" in data:
                    logger.info(f"LLM says '{item}' is not craftable: {data['error']}")
                    return None
                
                if "ingredients" in data and isinstance(data["ingredients"], dict):
                    recipe = {
                        "ingredients": data["ingredients"],
                        "source": "llm",
                        "needs_table": data.get("needs_table", True),
                    }
                    logger.info(f"LLM recipe for '{item}': {recipe['ingredients']}")
                    return recipe
                    
        except Exception as e:
            logger.warning(f"LLM recipe query failed for '{item}': {e}")
        
        return None


# Singleton
_knowledge_base = None

def get_knowledge_base() -> MinecraftKnowledge:
    """Get the global knowledge base instance."""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = MinecraftKnowledge()
    return _knowledge_base
