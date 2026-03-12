/**
 * Auto-equip utilities — shared helpers for equipping the best tool, weapon, or armor.
 * Used by combat_cmds, resources, movement, and reflexes.
 */

const { getBot, mcLog } = require('../shared');

// Tier ordering — higher index = better
const TIER_ORDER = ['wooden', 'stone', 'golden', 'iron', 'diamond', 'netherite'];

function getTier(itemName) {
    for (let i = TIER_ORDER.length - 1; i >= 0; i--) {
        if (itemName.includes(TIER_ORDER[i])) return i;
    }
    return -1;
}

/**
 * Find the best item of a given type from inventory.
 * @param {string[]} suffixes — e.g. ['_sword', '_axe'] for weapons, ['_pickaxe'] for picks
 * @returns {object|null} — the inventory item, or null
 */
function findBest(suffixes) {
    const bot = getBot();
    if (!bot) return null;
    const items = bot.inventory.items();
    let best = null;
    let bestTier = -1;
    for (const item of items) {
        for (const suffix of suffixes) {
            if (item.name.endsWith(suffix)) {
                const tier = getTier(item.name);
                if (tier > bestTier) {
                    bestTier = tier;
                    best = item;
                }
            }
        }
    }
    return best;
}

/**
 * Equip the best weapon (sword > axe) to hand. Returns true if equipped.
 */
async function equipBestWeapon() {
    const bot = getBot();
    if (!bot) return false;
    const weapon = findBest(['_sword']) || findBest(['_axe']);
    if (!weapon) return false;

    const held = bot.heldItem;
    if (held && held.name === weapon.name) return true; // Already holding it

    try {
        await bot.equip(weapon, 'hand');
        mcLog('DEBUG', 'AUTO_EQUIP_WEAPON', { item: weapon.name });
        return true;
    } catch (e) {
        mcLog('DEBUG', 'AUTO_EQUIP_WEAPON_FAILED', { error: e.message });
        return false;
    }
}

/**
 * Equip the best tool for a given block type.
 * @param {string} blockName — e.g. 'stone', 'oak_log', 'dirt'
 */
async function equipBestTool(blockName) {
    const bot = getBot();
    if (!bot) return false;

    // 1. Try to use the physics-perfect mineflayer-tool plugin
    if (bot.tool && bot.tool.equipForBlock) {
        const mcData = bot.registry || require('minecraft-data')(bot.version);
        const blockData = mcData.blocksByName[blockName] || mcData.blocksByName[blockName.replace('minecraft:', '')];
        if (blockData) {
            try {
                const Block = require('prismarine-block')(bot.registry || bot.version);
                const fakeBlock = new Block(blockData.id, 0, 0);
                await bot.tool.equipForBlock(fakeBlock, {});
                mcLog('DEBUG', 'AUTO_EQUIP_TOOL_PHYSICS', { for_block: blockName });
                return true;
            } catch (e) {
                // If it fails (e.g. no tool logic), we just fall back
            }
        }
    }

    // 2. Fallback to naive string matching
    let toolSuffixes;
    if (/ore|stone|cobble|obsidian|brick|netherrack|basalt|andesite|diorite|granite|deepslate|sandstone|terracotta|concrete/.test(blockName)) {
        toolSuffixes = ['_pickaxe'];
    } else if (/log|wood|plank|fence|sign|door|chest|crafting|bookshelf|barrel/.test(blockName)) {
        toolSuffixes = ['_axe'];
    } else if (/dirt|grass|sand|gravel|clay|soul|mycelium|podzol|farmland|snow/.test(blockName)) {
        toolSuffixes = ['_shovel'];
    } else {
        // Default to pickaxe for unknown
        toolSuffixes = ['_pickaxe'];
    }

    const tool = findBest(toolSuffixes);
    if (!tool) return false;

    const held = bot.heldItem;
    if (held && held.name === tool.name) return true;

    try {
        await bot.equip(tool, 'hand');
        mcLog('DEBUG', 'AUTO_EQUIP_TOOL', { item: tool.name, for_block: blockName });
        return true;
    } catch (e) {
        mcLog('DEBUG', 'AUTO_EQUIP_TOOL_FAILED', { error: e.message });
        return false;
    }
}

/**
 * Auto-equip the best armor to all slots. Returns count of pieces equipped.
 */
async function equipBestArmor() {
    const bot = getBot();
    if (!bot) return 0;

    const ARMOR_SLOTS = [
        { suffix: '_helmet', slot: 'head' },
        { suffix: '_chestplate', slot: 'torso' },
        { suffix: '_leggings', slot: 'legs' },
        { suffix: '_boots', slot: 'feet' }
    ];

    let equipped = 0;

    for (const { suffix, slot } of ARMOR_SLOTS) {
        const best = findBest([suffix]);
        if (!best) continue;

        // Check if we already have something as good or better in that slot
        const slotIndex = { head: 5, torso: 6, legs: 7, feet: 8 }[slot];
        const current = bot.inventory.slots[slotIndex];
        if (current && getTier(current.name) >= getTier(best.name)) continue;

        try {
            await bot.equip(best, slot);
            mcLog('DEBUG', 'AUTO_EQUIP_ARMOR', { item: best.name, slot });
            equipped++;
        } catch (e) {
            mcLog('DEBUG', 'AUTO_EQUIP_ARMOR_FAILED', { item: best.name, error: e.message });
        }
    }

    // Shield to off-hand if available
    const shield = bot.inventory.items().find(i => i.name === 'shield');
    if (shield) {
        const offHand = bot.inventory.slots[45];
        if (!offHand || offHand.name !== 'shield') {
            try {
                await bot.equip(shield, 'off-hand');
                mcLog('DEBUG', 'AUTO_EQUIP_SHIELD');
                equipped++;
            } catch (e) { /* already equipped or slot busy */ }
        }
    }

    return equipped;
}

module.exports = { findBest, getTier, equipBestWeapon, equipBestTool, equipBestArmor };
