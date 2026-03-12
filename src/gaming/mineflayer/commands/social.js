/**
 * Social/co-op commands — chat, status, drop, give, share, scan, coop_mode, disconnect, screenshot.
 */

const { getBot, getMcData, mcLog, GoalNear, GoalFollow, Movements, goals } = require('../shared');
const visual = require('../visual');

async function cmdChat(params) {
    getBot().chat(params.message);
    return { sent: params.message };
}

async function cmdStatus() {
    const bot = getBot();
    const inventory = bot.inventory.items().map(i => ({ name: i.name, count: i.count }));
    return {
        health: bot.health,
        food: bot.food,
        position: {
            x: Math.round(bot.entity.position.x),
            y: Math.round(bot.entity.position.y),
            z: Math.round(bot.entity.position.z)
        },
        inventory: inventory.slice(0, 20)
    };
}

// Full state in ONE call — replaces 3 separate bridge calls (status + nearby + time)
async function cmdFullState() {
    const bot = getBot();
    const HOSTILE_NAMES = ['zombie', 'skeleton', 'spider', 'creeper', 'enderman',
        'witch', 'phantom', 'drowned', 'husk', 'stray', 'pillager', 'vindicator',
        'ravager', 'blaze', 'ghast', 'piglin_brute', 'warden', 'wither_skeleton'];

    // Inventory
    const inventory = bot.inventory.items().map(i => ({ name: i.name, count: i.count }));

    // Nearby entities
    const entities = [];
    let hostilesNearby = false;
    for (const entity of Object.values(bot.entities)) {
        if (!entity || entity === bot.entity) continue;
        const dist = bot.entity.position.distanceTo(entity.position);
        if (dist > 32) continue;
        const isHostile = HOSTILE_NAMES.includes(entity.name);
        if (isHostile && dist < 16) hostilesNearby = true;
        entities.push({
            name: entity.name || entity.username || 'unknown',
            type: entity.type,
            distance: Math.round(dist),
            hostile: isHostile
        });
    }

    return {
        health: bot.health,
        food: bot.food,
        position: {
            x: Math.round(bot.entity.position.x),
            y: Math.round(bot.entity.position.y),
            z: Math.round(bot.entity.position.z)
        },
        inventory: inventory.slice(0, 20),
        nearby_entities: entities.slice(0, 10),
        hostiles_nearby: hostilesNearby,
        is_day: bot.time.day < 12000 || bot.time.day > 23000,
        time: bot.time.day
    };
}

async function cmdDisconnect() {
    await visual.closeViewer();
    getBot().quit();
    return { disconnected: true };
}

async function cmdGetScreenshot() {
    if (!visual.isViewerReady()) {
        // Throw so bot.js IPC dispatcher sends success:false to Python bridge.
        // Returning { success: false } here was silently masked as success by the dispatcher.
        throw new Error('Visual perception not ready (viewer failed to initialize)');
    }
    const result = await visual.captureScreenshot();
    if (!result || !result.success) {
        throw new Error(result?.error || 'Screenshot capture failed');
    }
    return result;
}

async function cmdDrop({ item, count = 1 }) {
    const bot = getBot();
    try {
        const targetItem = bot.inventory.items().find(i =>
            i.name.toLowerCase().includes(item?.toLowerCase() || '')
        );
        if (!targetItem) return { success: false, error: `No ${item || 'item'} in inventory` };

        const dropCount = count === 'all' ? targetItem.count : Math.min(parseInt(count), targetItem.count);
        await bot.toss(targetItem.type, null, dropCount);

        mcLog('INFO', 'DROPPED_ITEM', { item: targetItem.name, count: dropCount });
        return { success: true, action: 'dropped', item: targetItem.name, count: dropCount };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdGive({ player, item, count = 1 }) {
    const bot = getBot();
    const mcData = getMcData();
    if (!player) return { success: false, error: 'Player name required' };

    try {
        const targetPlayer = bot.players[player];
        if (!targetPlayer || !targetPlayer.entity) return { success: false, error: `Player ${player} not found nearby` };

        const targetItem = bot.inventory.items().find(i =>
            i.name.toLowerCase().includes(item?.toLowerCase() || '')
        );
        if (!targetItem) return { success: false, error: `No ${item || 'item'} in inventory` };

        const movements = new Movements(bot, mcData);
        bot.pathfinder.setMovements(movements);
        await bot.pathfinder.goto(new GoalNear(
            targetPlayer.entity.position.x, targetPlayer.entity.position.y, targetPlayer.entity.position.z, 2
        ));

        const dropCount = count === 'all' ? targetItem.count : Math.min(parseInt(count), targetItem.count);
        await bot.toss(targetItem.type, null, dropCount);

        mcLog('INFO', 'GAVE_ITEM', { player, item: targetItem.name, count: dropCount });
        return { success: true, action: 'gave', player, item: targetItem.name, count: dropCount };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdShare({ item }) {
    const bot = getBot();
    try {
        const targetItem = bot.inventory.items().find(i =>
            i.name.toLowerCase().includes(item?.toLowerCase() || '')
        );
        if (!targetItem) return { success: false, error: `No ${item || 'item'} in inventory` };

        const shareCount = Math.floor(targetItem.count / 2);
        if (shareCount < 1) return { success: false, error: `Only have ${targetItem.count}, can't share` };

        await bot.toss(targetItem.type, null, shareCount);
        mcLog('INFO', 'SHARED_ITEM', { item: targetItem.name, count: shareCount });
        return { success: true, action: 'shared', item: targetItem.name, count: shareCount, kept: targetItem.count - shareCount };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdScan({ radius = 128 }) {
    const bot = getBot();
    const mcData = getMcData();
    try {
        const valuableBlocks = [
            'diamond_ore', 'iron_ore', 'gold_ore', 'coal_ore', 'emerald_ore',
            'lapis_ore', 'redstone_ore', 'copper_ore', 'ancient_debris',
            'deepslate_diamond_ore', 'deepslate_iron_ore', 'deepslate_gold_ore'
        ];

        const found = {};
        for (const blockName of valuableBlocks) {
            const blockType = mcData.blocksByName[blockName];
            if (!blockType) continue;

            const blocks = bot.findBlocks({ matching: blockType.id, maxDistance: radius, count: 10 });
            if (blocks.length > 0) {
                const closest = blocks[0];
                found[blockName] = {
                    count: blocks.length,
                    closest: { x: closest.x, y: closest.y, z: closest.z },
                    distance: Math.floor(bot.entity.position.distanceTo(closest))
                };
            }
        }

        mcLog('INFO', 'SCAN_COMPLETE', { found: Object.keys(found).length, resources: Object.keys(found) });
        return { success: true, action: 'scanned', radius, resources: found };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdCoopMode({ player, mode = 'on' }) {
    const bot = getBot();
    const mcData = getMcData();

    if (mode === 'off') { bot.pathfinder.setGoal(null); return { success: true, action: 'coop_disabled' }; }
    if (!player) return { success: false, error: 'Player name required for coop mode' };

    const targetPlayer = bot.players[player];
    if (!targetPlayer || !targetPlayer.entity) return { success: false, error: `Player ${player} not found` };

    const movements = new Movements(bot, mcData);
    bot.pathfinder.setMovements(movements);
    bot.pathfinder.setGoal(new GoalFollow(targetPlayer.entity, 5), true);

    mcLog('INFO', 'COOP_MODE_ENABLED', { player, followDistance: 5 });
    return { success: true, action: 'coop_enabled', player, mode: 'following at distance' };
}

module.exports = {
    cmdChat, cmdStatus, cmdFullState, cmdDisconnect, cmdGetScreenshot,
    cmdDrop, cmdGive, cmdShare, cmdScan, cmdCoopMode
};
