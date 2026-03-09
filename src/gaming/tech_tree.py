"""
Minecraft Tech Tree - Prerequisites and Recipes

Knows what's needed to craft/obtain items for hierarchical planning.
"""

# Tool tiers (what can mine what)
TOOL_TIERS = {
    "wood": ["dirt", "sand", "gravel", "log", "planks"],
    "stone": ["stone", "coal_ore", "iron_ore"],
    "iron": ["gold_ore", "lapis_ore", "redstone_ore", "diamond_ore"],
    "diamond": ["obsidian", "ancient_debris"],
}

# Crafting recipes: item -> [ingredients]
RECIPES = {
    # Basic
    "planks": [("log", 1)],
    "stick": [("planks", 2)],
    "crafting_table": [("planks", 4)],
    "furnace": [("cobblestone", 8)],
    "chest": [("planks", 8)],
    "torch": [("stick", 1), ("coal", 1)],
    "bed": [("planks", 3), ("wool", 3)],
    
    # Wood tools
    "wooden_pickaxe": [("planks", 3), ("stick", 2)],
    "wooden_axe": [("planks", 3), ("stick", 2)],
    "wooden_sword": [("planks", 2), ("stick", 1)],
    "wooden_shovel": [("planks", 1), ("stick", 2)],
    "wooden_hoe": [("planks", 2), ("stick", 2)],
    
    # Stone tools
    "stone_pickaxe": [("cobblestone", 3), ("stick", 2)],
    "stone_axe": [("cobblestone", 3), ("stick", 2)],
    "stone_sword": [("cobblestone", 2), ("stick", 1)],
    "stone_shovel": [("cobblestone", 1), ("stick", 2)],
    "stone_hoe": [("cobblestone", 2), ("stick", 2)],
    
    # Iron tools
    "iron_pickaxe": [("iron_ingot", 3), ("stick", 2)],
    "iron_axe": [("iron_ingot", 3), ("stick", 2)],
    "iron_sword": [("iron_ingot", 2), ("stick", 1)],
    "iron_shovel": [("iron_ingot", 1), ("stick", 2)],
    "iron_hoe": [("iron_ingot", 2), ("stick", 2)],
    "shield": [("iron_ingot", 1), ("planks", 6)],
    "bucket": [("iron_ingot", 3)],
    
    # Diamond tools
    "diamond_pickaxe": [("diamond", 3), ("stick", 2)],
    "diamond_axe": [("diamond", 3), ("stick", 2)],
    "diamond_sword": [("diamond", 2), ("stick", 1)],
    "diamond_shovel": [("diamond", 1), ("stick", 2)],
    "diamond_hoe": [("diamond", 2), ("stick", 2)],
    
    # Armor - Iron
    "iron_helmet": [("iron_ingot", 5)],
    "iron_chestplate": [("iron_ingot", 8)],
    "iron_leggings": [("iron_ingot", 7)],
    "iron_boots": [("iron_ingot", 4)],
    
    # Armor - Diamond
    "diamond_helmet": [("diamond", 5)],
    "diamond_chestplate": [("diamond", 8)],
    "diamond_leggings": [("diamond", 7)],
    "diamond_boots": [("diamond", 4)],
}

# Smelting recipes: output -> input
SMELTING = {
    "iron_ingot": "iron_ore",
    "gold_ingot": "gold_ore",
    "copper_ingot": "copper_ore",
    "glass": "sand",
    "stone": "cobblestone",
    "smooth_stone": "stone",
    "charcoal": "log",
    "cooked_beef": "beef",
    "cooked_porkchop": "porkchop",
    "cooked_chicken": "chicken",
    "cooked_mutton": "mutton",
    "brick": "clay_ball",
}

# Gatherable raw materials (from world)
RAW_MATERIALS = {
    "log", "cobblestone", "dirt", "sand", "gravel", "clay",
    "coal_ore", "iron_ore", "gold_ore", "diamond_ore", "copper_ore",
    "lapis_ore", "redstone_ore", "emerald_ore",
    "wool", "leather", "beef", "porkchop", "chicken", "mutton",
    "wheat", "carrot", "potato", "beetroot",
    "coal",  # Can be mined directly
}

# What pickaxe tier is needed to mine each ore
ORE_REQUIREMENTS = {
    "coal_ore": "wooden_pickaxe",
    "copper_ore": "stone_pickaxe", 
    "iron_ore": "stone_pickaxe",
    "lapis_ore": "stone_pickaxe",
    "gold_ore": "iron_pickaxe",
    "redstone_ore": "iron_pickaxe",
    "diamond_ore": "iron_pickaxe",
    "emerald_ore": "iron_pickaxe",
    "obsidian": "diamond_pickaxe",
}


def get_prerequisites(item: str) -> list:
    """
    Get all items needed to obtain the target item.
    Returns list of (item, count) tuples in order of acquisition.
    """
    if item in RAW_MATERIALS:
        return [(item, 1)]  # Just go collect it
    
    if item in SMELTING.values():
        # This is an ore that needs smelting
        for output, input_ore in SMELTING.items():
            if input_ore == item:
                return [(item, 1), ("smelt", output)]
    
    if item in SMELTING:
        # Need to smelt something
        ore = SMELTING[item]
        ore_prereqs = get_prerequisites(ore)
        return ore_prereqs + [("smelt", item)]
    
    if item in RECIPES:
        # Need to craft
        prereqs = []
        for ingredient, count in RECIPES[item]:
            ing_prereqs = get_prerequisites(ingredient)
            for prereq_item, prereq_count in ing_prereqs:
                prereqs.append((prereq_item, count * prereq_count))
        prereqs.append(("craft", item))
        return prereqs
    
    # Unknown item
    return [(item, 1)]


def get_tool_for_ore(ore: str) -> str:
    """Get the minimum pickaxe tier needed to mine an ore."""
    return ORE_REQUIREMENTS.get(ore, "wooden_pickaxe")


def can_craft(item: str, inventory: dict) -> bool:
    """Check if we have ingredients to craft the item."""
    if item not in RECIPES:
        return False
    
    for ingredient, count in RECIPES[item]:
        if inventory.get(ingredient, 0) < count:
            return False
    return True


def missing_ingredients(item: str, inventory: dict) -> list:
    """Get list of missing ingredients to craft item."""
    if item not in RECIPES:
        return []
    
    missing = []
    for ingredient, count in RECIPES[item]:
        have = inventory.get(ingredient, 0)
        if have < count:
            missing.append((ingredient, count - have))
    return missing
