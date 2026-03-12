/**
 * Resource commands — collect, craft, smelt, store, take.
 * Powered by Mindcraft skill library for robust action execution.
 */

const { getBot, getMcData, mcLog, GoalNear, Movements } = require('../shared');
const { isBlockProtected } = require('../persistence');
const { aggroPlayers } = require('../combat');
const { smartGoto } = require('./movement');
const { equipBestTool } = require('./equip_utils');
const skills = require('../lib/skills');

// Fuzzy name resolution: generic names -> correct Minecraft IDs
const ITEM_ALIASES = {
    'planks': 'oak_planks', 'plank': 'oak_planks', 'wooden_planks': 'oak_planks',
    'oak_planks': 'oak_planks', 'spruce_planks': 'spruce_planks', 'birch_planks': 'birch_planks',
    'jungle_planks': 'jungle_planks', 'acacia_planks': 'acacia_planks', 'dark_oak_planks': 'dark_oak_planks',
    'log': 'oak_log', 'logs': 'oak_log', 'wood': 'oak_log',
    'wool': 'white_wool',
    'cobble': 'cobblestone',
    // Tools — LLM commonly uses "wooden_" but Minecraft uses "wooden_" or version-specific names
    'wooden_pickaxe': 'wooden_pickaxe', 'wood_pickaxe': 'wooden_pickaxe',
    'wooden_axe': 'wooden_axe', 'wood_axe': 'wooden_axe',
    'wooden_sword': 'wooden_sword', 'wood_sword': 'wooden_sword',
    'wooden_shovel': 'wooden_shovel', 'wood_shovel': 'wooden_shovel',
    'wooden_hoe': 'wooden_hoe', 'wood_hoe': 'wooden_hoe',
    'stone_pickaxe': 'stone_pickaxe', 'stone_axe': 'stone_axe',
    'stone_sword': 'stone_sword', 'stone_shovel': 'stone_shovel',
    'iron_pickaxe': 'iron_pickaxe', 'iron_axe': 'iron_axe',
    'iron_sword': 'iron_sword', 'iron_shovel': 'iron_shovel',
    'diamond_pickaxe': 'diamond_pickaxe', 'diamond_axe': 'diamond_axe',
    'diamond_sword': 'diamond_sword', 'diamond_shovel': 'diamond_shovel',
    // Armor
    'iron_helmet': 'iron_helmet', 'iron_chestplate': 'iron_chestplate',
    'iron_leggings': 'iron_leggings', 'iron_boots': 'iron_boots',
    'diamond_helmet': 'diamond_helmet', 'diamond_chestplate': 'diamond_chestplate',
    // Common items
    'sticks': 'stick', 'crafting_bench': 'crafting_table',
    'furnace': 'furnace', 'chest': 'chest', 'torch': 'torch',
    'bed': 'red_bed', 'cooked_beef': 'cooked_beef', 'cooked_porkchop': 'cooked_porkchop',
};

function resolveItem(name, mcData) {
    // Direct match first
    if (mcData.itemsByName[name] || mcData.blocksByName[name]) return name;
    // Check aliases
    const alias = ITEM_ALIASES[name];
    if (alias && (mcData.itemsByName[alias] || mcData.blocksByName[alias])) return alias;
    // Fuzzy fallback: search all items for a partial match
    const lowerName = name.toLowerCase();
    for (const itemName of Object.keys(mcData.itemsByName)) {
        if (itemName === lowerName) return itemName;
    }
    // Try replacing underscores and matching loosely
    for (const itemName of Object.keys(mcData.itemsByName)) {
        if (itemName.includes(lowerName) || lowerName.includes(itemName)) return itemName;
    }
    return name;
}

async function cmdCollect(params) {
    const bot = getBot();
    const mcData = getMcData();
    const rawType = params.block_type;
    const { count = 1 } = params;
    const block_type = resolveItem(rawType, mcData);
    if (block_type !== rawType) mcLog('DEBUG', 'COLLECT_ALIAS_RESOLVED', { from: rawType, to: block_type });

    // === HARD BLOCK: Never collect clearly player-crafted/placed-only blocks ===
    const NEVER_COLLECT = [
        'furnace', 'blast_furnace', 'smoker', 'chest', 'trapped_chest', 'barrel',
        'bed', 'white_bed', 'red_bed', 'blue_bed', 'green_bed', 'yellow_bed',
        'anvil', 'enchanting_table', 'brewing_stand', 'beacon', 'hopper',
        'dispenser', 'dropper', 'observer', 'piston', 'sticky_piston',
        'oak_door', 'iron_door', 'spruce_door', 'birch_door', 'jungle_door', 'acacia_door', 'dark_oak_door',
        'oak_fence', 'spruce_fence', 'birch_fence', 'jungle_fence', 'acacia_fence', 'dark_oak_fence',
        'oak_fence_gate', 'spruce_fence_gate', 'birch_fence_gate',
        'oak_stairs', 'spruce_stairs', 'birch_stairs', 'stone_stairs', 'cobblestone_stairs',
        'oak_slab', 'spruce_slab', 'birch_slab', 'stone_slab', 'cobblestone_slab',
        'glass', 'glass_pane', 'bookshelf', 'ladder', 'torch', 'wall_torch',
        'sign', 'oak_sign', 'spruce_sign', 'birch_sign',
        'jukebox', 'note_block', 'campfire', 'lantern', 'lectern',
        'stonecutter', 'cartography_table', 'fletching_table', 'loom', 'smithing_table',
        'composter', 'beehive', 'bee_nest', 'respawn_anchor', 'lodestone',
        'tnt', 'spawner'
    ];

    if (NEVER_COLLECT.includes(block_type)) {
        mcLog('DEBUG', 'COLLECT_BLOCKED_PLAYER_ITEM', { block_type });
        return { collected: 0, requested: count, error: `Cannot collect ${block_type} - player-placed item` };
    }

    // === ERNOS SAFETY: Protected zones ===
    const blockId = mcData.blocksByName[block_type]?.id;
    if (blockId) {
        const targetBlock = bot.findBlock({ matching: blockId, maxDistance: 64 });
        if (targetBlock) {
            const protectedZone = isBlockProtected(targetBlock.position);
            if (protectedZone) {
                mcLog('DEBUG', 'COLLECT_BLOCKED_PROTECTED_ZONE', { zone_owner: protectedZone.owner, block_type });
                return { collected: 0, requested: count, error: `Block in protected zone (${protectedZone.owner})` };
            }

            // === PLAYER PROXIMITY: Don't mine blocks near other players (they may be structures) ===
            const PROTECTION_RADIUS = 20;
            for (const player of Object.values(bot.players)) {
                if (!player.entity || player.username === bot.username) continue;
                if (aggroPlayers.has(player.username)) continue;
                if (targetBlock.position.distanceTo(player.entity.position) < PROTECTION_RADIUS) {
                    mcLog('DEBUG', 'COLLECT_BLOCKED_NEAR_PLAYER', { player: player.username, block_type });
                    return { collected: 0, requested: count, error: `Block too close to ${player.username}` };
                }
            }
        }
    }

    // === AUTO-NAVIGATE: If no blocks nearby, travel to find them ===
    skills.ensureModes(bot);
    bot.output = '';

    if (blockId) {
        const nearbyCheck = bot.findBlock({ matching: blockId, maxDistance: 64 });
        if (!nearbyCheck) {
            mcLog('DEBUG', 'COLLECT_AUTO_NAVIGATE', { block_type, reason: 'none_within_64' });
            try {
                // Search wider area (256 blocks) and navigate there
                const navigated = await skills.goToNearestBlock(bot, block_type, 4, 256);
                if (!navigated) {
                    mcLog('INFO', 'COLLECT_NO_BLOCKS_ANYWHERE', { block_type, searched_radius: 256 });
                    return { collected: 0, requested: count, error: `No ${block_type} found within 256 blocks` };
                }
                mcLog('DEBUG', 'COLLECT_NAVIGATED_TO_BLOCK', { block_type });
            } catch (navErr) {
                mcLog('WARNING', 'COLLECT_NAV_FAILED', { block_type, error: String(navErr).substring(0, 100) });
                return { collected: 0, requested: count, error: `Could not navigate to ${block_type}` };
            }
        }
    }

    // === COLLECT via Mindcraft ===
    mcLog('DEBUG', 'COLLECT_MINDCRAFT_START', { block_type, count });
    try {
        const success = await skills.collectBlock(bot, block_type, count);
        mcLog('INFO', 'COLLECT_MINDCRAFT_DONE', { block_type, count, success, log: bot.output.substring(0, 200) });

        const match = bot.output.match(/Collected (\d+)/);
        const collected = match ? parseInt(match[1]) : (success ? count : 0);
        return { collected, requested: count };
    } catch (err) {
        mcLog('WARNING', 'COLLECT_MINDCRAFT_ERROR', { block_type, error: String(err).substring(0, 200) });
        return { collected: 0, requested: count, error: String(err).substring(0, 100) };
    }
}

async function cmdCraft(params) {
    const bot = getBot();
    const mcData = getMcData();
    const rawItem = params.item;
    const { count = 1 } = params;
    const item = resolveItem(rawItem, mcData);
    if (item !== rawItem) mcLog('DEBUG', 'CRAFT_ALIAS_RESOLVED', { from: rawItem, to: item });

    // Initialize Mindcraft's bot compatibility layer
    skills.ensureModes(bot);
    bot.output = '';

    mcLog('DEBUG', 'CRAFT_MINDCRAFT_START', { item, count });
    const success = await skills.craftRecipe(bot, item, count);

    mcLog('INFO', 'CRAFT_MINDCRAFT_DONE', { item, count, success, log: bot.output.substring(0, 200) });

    if (!success) {
        const out = bot.output.trim();
        throw new Error(`Failed to craft ${item}: ${out ? out : 'Recipe or materials missing / pathing to table failed.'}`);
    }
    return { crafted: item, count, used_table: bot.output.includes('crafting_table') };
}

async function cmdSmelt({ input, fuel = 'coal', count = 1 }) {
    const bot = getBot();
    if (!input) return { success: false, error: 'No input item specified' };

    // Initialize Mindcraft's bot compatibility layer
    skills.ensureModes(bot);
    bot.output = '';

    mcLog('DEBUG', 'SMELT_MINDCRAFT_START', { input, count });
    const success = await skills.smeltItem(bot, input, count);

    mcLog('INFO', 'SMELT_MINDCRAFT_DONE', { input, count, success, log: bot.output.substring(0, 200) });

    return { success, action: 'smelted', input, output: bot.output.trim() };
}

async function cmdStore({ item, count = null }) {
    const bot = getBot();
    if (!item) return { success: false, error: 'No item specified' };

    // Initialize Mindcraft's bot compatibility layer
    skills.ensureModes(bot);
    bot.output = '';

    const storeCount = count || -1;  // -1 means all in Mindcraft
    mcLog('DEBUG', 'STORE_MINDCRAFT_START', { item, count: storeCount });
    const success = await skills.putInChest(bot, item, storeCount);

    mcLog('INFO', 'STORE_MINDCRAFT_DONE', { item, success, log: bot.output.substring(0, 200) });

    return { success, action: 'stored', items: [{ name: item, count: storeCount }] };
}

async function cmdTake({ item, count = null }) {
    const bot = getBot();
    if (!item) return { success: false, error: 'No item specified' };

    // Initialize Mindcraft's bot compatibility layer
    skills.ensureModes(bot);
    bot.output = '';

    const takeCount = count || -1;  // -1 means all in Mindcraft
    mcLog('DEBUG', 'TAKE_MINDCRAFT_START', { item, count: takeCount });
    const success = await skills.takeFromChest(bot, item, takeCount);

    mcLog('INFO', 'TAKE_MINDCRAFT_DONE', { item, success, log: bot.output.substring(0, 200) });

    return { success, action: 'took', items: [{ name: item, count: takeCount }] };
}

module.exports = { cmdCollect, cmdCraft, cmdSmelt, cmdStore, cmdTake };
