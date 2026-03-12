/**
 * Building commands — place, copy_build, build, protect, locations, blueprints.
 */

const { getBot, getMcData, mcLog, GoalNear, Movements } = require('../shared');
const {
    getProtectedZones, saveProtectedZones,
    getSavedLocations, saveSavedLocations,
    getBlueprints, saveBlueprints
} = require('../persistence');

async function cmdPlace({ block, x, y, z }) {
    const bot = getBot();
    const mcData = getMcData();
    try {
        const blockItem = bot.inventory.items().find(i => i.name.toLowerCase().includes(block.toLowerCase()));
        if (!blockItem) return { success: false, error: `No ${block} in inventory` };

        await bot.equip(blockItem, 'hand');

        if (x !== undefined && y !== undefined && z !== undefined) {
            const targetPos = { x: parseInt(x), y: parseInt(y), z: parseInt(z) };
            const referenceBlock = bot.blockAt(new mcData.Vec3(targetPos.x, targetPos.y - 1, targetPos.z));
            if (!referenceBlock || referenceBlock.name === 'air') return { success: false, error: 'No solid block to place against' };
            await bot.placeBlock(referenceBlock, new mcData.Vec3(0, 1, 0));
        } else {
            // Place 1 block in front of the bot (not at feet — hitbox blocks that)
            const direction = bot.entity.yaw;
            const dx = -Math.sin(direction);
            const dz = Math.cos(direction);
            const targetX = Math.floor(bot.entity.position.x + dx);
            const targetZ = Math.floor(bot.entity.position.z + dz);
            const targetY = Math.floor(bot.entity.position.y);

            mcLog('DEBUG', 'PLACE_TRYING_OFFSETS', {
                botPos: { x: Math.floor(bot.entity.position.x), y: targetY, z: Math.floor(bot.entity.position.z) },
                frontPos: { x: targetX, y: targetY, z: targetZ }
            });

            // Try the block in front first, then adjacent positions
            const offsets = [
                { x: targetX, z: targetZ },
                { x: targetX + 1, z: targetZ },
                { x: targetX - 1, z: targetZ },
                { x: targetX, z: targetZ + 1 },
                { x: targetX, z: targetZ - 1 },
            ];

            let placed = false;
            for (const offset of offsets) {
                const referenceBlock = bot.blockAt(new mcData.Vec3(offset.x, targetY - 1, offset.z));
                const aboveBlock = bot.blockAt(new mcData.Vec3(offset.x, targetY, offset.z));
                if (referenceBlock && referenceBlock.name !== 'air' && aboveBlock && aboveBlock.name === 'air') {
                    await bot.placeBlock(referenceBlock, new mcData.Vec3(0, 1, 0));
                    placed = true;
                    break;
                }
            }
            if (!placed) {
                return { success: false, error: 'No suitable place to put block — no solid ground with air above nearby' };
            }
        }

        // Verify the block was actually placed
        const verifyBlock = bot.findBlock({
            matching: b => b.name.toLowerCase().includes(block.toLowerCase()),
            maxDistance: 5
        });
        if (!verifyBlock) {
            mcLog('WARNING', 'PLACE_VERIFY_FAILED', { block: blockItem.name });
            return { success: false, error: `Placed ${blockItem.name} but cannot find it nearby — placement may have failed` };
        }

        mcLog('INFO', 'PLACED_BLOCK', { block: blockItem.name, pos: verifyBlock.position });
        return { success: true, action: 'placed', block: blockItem.name, position: { x: verifyBlock.position.x, y: verifyBlock.position.y, z: verifyBlock.position.z } };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdProtect({ username, x, y, z, radius = 50 }) {
    const bot = getBot();
    const protectedZones = getProtectedZones();

    if (x === undefined || y === undefined || z === undefined) {
        x = Math.floor(bot.entity.position.x);
        y = Math.floor(bot.entity.position.y);
        z = Math.floor(bot.entity.position.z);
    }

    const zone = { x, y, z, radius, owner: username || 'unknown', created: new Date().toISOString() };
    protectedZones.push(zone);
    saveProtectedZones();

    mcLog('INFO', 'PROTECTED_ZONE_CREATED', zone);
    return { success: true, zone, total_zones: protectedZones.length };
}

async function cmdListProtectedZones() {
    const zones = getProtectedZones();
    return { zones, total: zones.length };
}

async function cmdSaveLocation({ name }) {
    const bot = getBot();
    if (!name) return { success: false, error: 'Location name required' };

    const pos = bot.entity.position;
    const location = {
        x: Math.floor(pos.x), y: Math.floor(pos.y), z: Math.floor(pos.z),
        dimension: bot.game.dimension || 'overworld',
        created: new Date().toISOString()
    };

    const savedLocations = getSavedLocations();
    savedLocations[name.toLowerCase()] = location;
    saveSavedLocations();

    mcLog('INFO', 'LOCATION_SAVED', { name, ...location });
    return { success: true, action: 'location_saved', name: name.toLowerCase(), location };
}

async function cmdGotoLocation({ name }) {
    const bot = getBot();
    const mcData = getMcData();
    const savedLocations = getSavedLocations();

    if (!name) return { success: true, action: 'list_locations', locations: Object.keys(savedLocations) };

    const location = savedLocations[name.toLowerCase()];
    if (!location) return { success: false, error: `No location named "${name}" found. Saved: ${Object.keys(savedLocations).join(', ') || 'none'}` };

    try {
        const movements = new Movements(bot, mcData);
        bot.pathfinder.setMovements(movements);
        await bot.pathfinder.goto(new GoalNear(location.x, location.y, location.z, 2));

        mcLog('INFO', 'ARRIVED_AT_LOCATION', { name });
        return { success: true, action: 'arrived', name: name.toLowerCase(), location };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdCopyBuild({ name, radius = 5, height = 10 }) {
    const bot = getBot();
    const mcData = getMcData();
    const blueprints = getBlueprints();

    if (!name) return { success: false, error: 'Blueprint name required' };

    try {
        const pos = bot.entity.position;
        const origin = { x: Math.floor(pos.x), y: Math.floor(pos.y), z: Math.floor(pos.z) };
        const blocks = [];
        const blockCounts = {};

        for (let dx = -radius; dx <= radius; dx++) {
            for (let dy = 0; dy < height; dy++) {
                for (let dz = -radius; dz <= radius; dz++) {
                    const block = bot.blockAt(new mcData.Vec3(origin.x + dx, origin.y + dy, origin.z + dz));
                    if (block && block.name !== 'air' && !block.name.includes('water') && !block.name.includes('lava')) {
                        blocks.push({ dx, dy, dz, blockName: block.name });
                        blockCounts[block.name] = (blockCounts[block.name] || 0) + 1;
                    }
                }
            }
        }

        if (blocks.length === 0) return { success: false, error: 'No blocks found to copy in the area' };

        blueprints[name.toLowerCase()] = { blocks, origin, blockCounts, radius, height, created: new Date().toISOString() };
        saveBlueprints();

        mcLog('INFO', 'BLUEPRINT_SAVED', { name, blockCount: blocks.length, blockCounts });
        return { success: true, action: 'blueprint_saved', name: name.toLowerCase(), blockCount: blocks.length, blockCounts };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdBuild({ name, gatherResources = true }) {
    const bot = getBot();
    const mcData = getMcData();
    const blueprints = getBlueprints();

    if (!name) return { success: true, action: 'list_blueprints', blueprints: Object.keys(blueprints) };

    const blueprint = blueprints[name.toLowerCase()];
    if (!blueprint) return { success: false, error: `No blueprint named "${name}" found. Saved: ${Object.keys(blueprints).join(', ') || 'none'}` };

    try {
        const pos = bot.entity.position;
        const buildOrigin = { x: Math.floor(pos.x), y: Math.floor(pos.y), z: Math.floor(pos.z) };

        const needed = { ...blueprint.blockCounts };
        const have = {};
        const missing = {};

        for (const item of bot.inventory.items()) {
            if (needed[item.name]) have[item.name] = (have[item.name] || 0) + item.count;
        }
        for (const [block, count] of Object.entries(needed)) {
            const haveCount = have[block] || 0;
            if (haveCount < count) missing[block] = count - haveCount;
        }

        if (Object.keys(missing).length > 0 && gatherResources) {
            mcLog('INFO', 'BUILD_GATHERING_RESOURCES', { missing });
            for (const [blockName, count] of Object.entries(missing)) {
                try {
                    const blocks = bot.findBlocks({ matching: block => block.name === blockName, maxDistance: 128, count });
                    for (const blockPos of blocks) {
                        const block = bot.blockAt(blockPos);
                        if (block) await bot.dig(block);
                    }
                } catch (e) { /* Continue */ }
            }
        }

        let placed = 0, failed = 0;
        const sortedBlocks = [...blueprint.blocks].sort((a, b) => a.dy - b.dy);

        for (const block of sortedBlocks) {
            const targetPos = new mcData.Vec3(buildOrigin.x + block.dx, buildOrigin.y + block.dy, buildOrigin.z + block.dz);
            const blockItem = bot.inventory.items().find(i => i.name === block.blockName || i.name.includes(block.blockName));
            if (!blockItem) { failed++; continue; }

            try {
                await bot.equip(blockItem, 'hand');
                const belowPos = targetPos.offset(0, -1, 0);
                const referenceBlock = bot.blockAt(belowPos);

                if (referenceBlock && referenceBlock.name !== 'air') {
                    await bot.placeBlock(referenceBlock, new mcData.Vec3(0, 1, 0));
                    placed++;
                } else {
                    const directions = [[0, 0, -1], [0, 0, 1], [-1, 0, 0], [1, 0, 0]];
                    let placedThisBlock = false;
                    for (const [ddx, ddy, ddz] of directions) {
                        const adjBlock = bot.blockAt(targetPos.offset(ddx, ddy, ddz));
                        if (adjBlock && adjBlock.name !== 'air') {
                            await bot.placeBlock(adjBlock, new mcData.Vec3(-ddx, -ddy, -ddz));
                            placed++;
                            placedThisBlock = true;
                            break;
                        }
                    }
                    if (!placedThisBlock) failed++;
                }
            } catch (e) { failed++; }

            await new Promise(resolve => setTimeout(resolve, 100));
        }

        mcLog('INFO', 'BUILD_COMPLETE', { name, placed, failed, total: blueprint.blocks.length });
        return { success: true, action: 'built', name: name.toLowerCase(), placed, failed, total: blueprint.blocks.length };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdListLocations() {
    const savedLocations = getSavedLocations();
    const locations = Object.entries(savedLocations).map(([name, loc]) => ({
        name, x: loc.x, y: loc.y, z: loc.z, dimension: loc.dimension
    }));
    return { success: true, locations };
}

async function cmdListBlueprints() {
    const blueprints = getBlueprints();
    const bps = Object.entries(blueprints).map(([name, bp]) => ({
        name, blockCount: bp.blocks.length, created: bp.created
    }));
    return { success: true, blueprints: bps };
}

module.exports = {
    cmdPlace, cmdProtect, cmdListProtectedZones,
    cmdSaveLocation, cmdGotoLocation, cmdListLocations,
    cmdCopyBuild, cmdBuild, cmdListBlueprints
};
