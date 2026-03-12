"""
Minecraft Tech Tree & Crafting Definitions
"""

TOOL_TIERS = ["wood", "stone", "iron", "gold", "diamond", "netherite"]

RECIPES = {
    "oak_planks": [("oak_log", 1)],
    "stick": [("oak_planks", 2)],
    "crafting_table": [("oak_planks", 4)],
    "furnace": [("cobblestone", 8)],
    "torch": [("stick", 1), ("coal", 1)],
    "campfire": [("stick", 3), ("coal", 1), ("oak_log", 3)],
    "bed": [("oak_planks", 3), ("white_wool", 3)],
    
    # Wood tools
    "wooden_pickaxe": [("oak_planks", 3), ("stick", 2)],
    "wooden_axe": [("oak_planks", 3), ("stick", 2)],
    "wooden_sword": [("oak_planks", 2), ("stick", 1)],
    "wooden_shovel": [("oak_planks", 1), ("stick", 2)],
    "wooden_hoe": [("oak_planks", 2), ("stick", 2)],
    
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
    "shield": [("iron_ingot", 1), ("oak_planks", 6)],
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

RECIPE_YIELDS = {
    "oak_planks": 4,
    "stick": 4,
    "torch": 4,
}


# Smelting recipes: output -> input
SMELTING = {
    "iron_ingot": "iron_ore",
    "gold_ingot": "gold_ore",
    "copper_ingot": "copper_ore",
    "glass": "sand",
    "stone": "cobblestone",
    "smooth_stone": "stone",
    "charcoal": "oak_log",
    "cooked_beef": "beef",
    "cooked_porkchop": "porkchop",
    "cooked_chicken": "chicken",
    "cooked_mutton": "mutton",
    "brick": "clay_ball",
}

# Gatherable raw materials (from world)
RAW_MATERIALS = {
    "oak_log", "birch_log", "spruce_log", "jungle_log", "acacia_log", "dark_oak_log",
    "cobblestone", "dirt", "sand", "gravel", "clay",
    "coal_ore", "iron_ore", "gold_ore", "diamond_ore", "copper_ore",
    "lapis_ore", "redstone_ore", "emerald_ore",
    "white_wool", "leather", "beef", "porkchop", "chicken", "mutton",
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

# Fuzzy aliases: generic name -> correct Minecraft item ID
# Used by planner and bridge to resolve ambiguous names
ITEM_ALIASES = {
    "planks": "oak_planks",
    "log": "oak_log",
    "wood": "oak_log",
    "wool": "white_wool",
    "plank": "oak_planks",
    "logs": "oak_log",
    "wooden_plank": "oak_planks",
    "wooden_planks": "oak_planks",
}

def resolve_item(name: str) -> str:
    """Resolve a generic/fuzzy item name to the correct Minecraft ID."""
    return ITEM_ALIASES.get(name, name)


def get_prerequisites(item: str) -> list:
    """
    Get all items needed to obtain the target item.
    Returns list of (item, count) tuples in order of acquisition.
    """
    item = resolve_item(item)
    
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
        recipe = RECIPES[item]
        ingredients = recipe[0] if isinstance(recipe, tuple) else recipe
        
        prereqs = []
        for ingredient, count in ingredients:
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


def can_craft(item: str, inventory: dict, target_count: int = 1) -> bool:
    """Check if we have ingredients to craft the item."""
    item = resolve_item(name=item)
    if item not in RECIPES:
        return False
    
    recipe = RECIPES[item]
    ingredients = recipe[0] if isinstance(recipe, tuple) else recipe
    recipe_yield = recipe[1] if isinstance(recipe, tuple) else RECIPE_YIELDS.get(item, 1)
    
    import math
    runs = math.ceil(target_count / recipe_yield)
    
    for ingredient, count_per_run in ingredients:
        if inventory.get(ingredient, 0) < (count_per_run * runs):
            return False
    return True


def missing_ingredients(item: str, inventory: dict, target_count: int = 1) -> list:
    """Get list of missing ingredients to craft item, accounting for yield."""
    item = resolve_item(name=item)
    if item not in RECIPES:
        return []
    
    recipe = RECIPES[item]
    # Handle both old format [ingredients] and new (ingredients, yield)
    ingredients = recipe[0] if isinstance(recipe, tuple) else recipe
    recipe_yield = recipe[1] if isinstance(recipe, tuple) else RECIPE_YIELDS.get(item, 1)
    
    # How many times do we need to run the recipe?
    import math
    runs = math.ceil(target_count / recipe_yield)
    
    missing = []
    for ingredient, count_per_run in ingredients:
        total_needed = count_per_run * runs
        have = inventory.get(ingredient, 0)
        if have < total_needed:
            missing.append((ingredient, total_needed - have))
    return missing
