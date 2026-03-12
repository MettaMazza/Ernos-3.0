/**
 * World Queries — adapted from Mindcraft (MIT License)
 * https://github.com/mindcraft-bots/mindcraft
 *
 * Block finding, entity queries, inventory introspection, biome detection.
 */

const pf = require('mineflayer-pathfinder');
const mc = require('./mcdata');


function getNearestFreeSpace(bot, size = 1, distance = 8) {
    let empty_pos = bot.findBlocks({
        matching: (block) => block && block.name == 'air',
        maxDistance: distance,
        count: 1000
    });
    for (let i = 0; i < empty_pos.length; i++) {
        let empty = true;
        for (let x = 0; x < size; x++) {
            for (let z = 0; z < size; z++) {
                let top = bot.blockAt(empty_pos[i].offset(x, 0, z));
                let bottom = bot.blockAt(empty_pos[i].offset(x, -1, z));
                if (!top || top.name !== 'air' || !bottom || bottom.drops.length == 0 || !bottom.diggable) {
                    empty = false;
                    break;
                }
            }
            if (!empty) break;
        }
        if (empty) return empty_pos[i];
    }
    return null;
}

function getBlockAtPosition(bot, x = 0, y = 0, z = 0) {
    let block = bot.blockAt(bot.entity.position.offset(x, y, z));
    if (!block) block = { name: 'air' };
    return block;
}

function getSurroundingBlocks(bot) {
    let res = [];
    res.push(`Block Below: ${getBlockAtPosition(bot, 0, -1, 0).name}`);
    res.push(`Block at Legs: ${getBlockAtPosition(bot, 0, 0, 0).name}`);
    res.push(`Block at Head: ${getBlockAtPosition(bot, 0, 1, 0).name}`);
    return res;
}

function getFirstBlockAboveHead(bot, ignore_types = null, distance = 32) {
    let ignore_blocks = [];
    if (ignore_types === null) ignore_blocks = ['air', 'cave_air'];
    else {
        if (!Array.isArray(ignore_types)) ignore_types = [ignore_types];
        for (let ignore_type of ignore_types) {
            if (mc.getBlockId(ignore_type)) ignore_blocks.push(ignore_type);
        }
    }
    let block_above = { name: 'air' };
    let height = 0;
    for (let i = 0; i < distance; i++) {
        let block = bot.blockAt(bot.entity.position.offset(0, i + 2, 0));
        if (!block) block = { name: 'air' };
        if (ignore_blocks.includes(block.name)) continue;
        block_above = block;
        height = i;
        break;
    }
    if (ignore_blocks.includes(block_above.name)) return 'none';
    return `${block_above.name} (${height} blocks up)`;
}

function getNearestBlocks(bot, block_types = null, distance = 8, count = 10000) {
    let block_ids = [];
    if (block_types === null) {
        block_ids = mc.getAllBlockIds(['air']);
    } else {
        if (!Array.isArray(block_types)) block_types = [block_types];
        for (let block_type of block_types) {
            block_ids.push(mc.getBlockId(block_type));
        }
    }
    return getNearestBlocksWhere(bot, block_ids, distance, count);
}

function getNearestBlocksWhere(bot, predicate, distance = 8, count = 10000) {
    let positions = bot.findBlocks({ matching: predicate, maxDistance: distance, count: count });
    let blocks = positions.map(position => bot.blockAt(position));
    return blocks;
}

function getNearestBlock(bot, block_type, distance = 16) {
    let blocks = getNearestBlocks(bot, block_type, distance, 1);
    if (blocks.length > 0) return blocks[0];
    return null;
}

function getNearbyEntities(bot, maxDistance = 16) {
    let entities = [];
    for (const entity of Object.values(bot.entities)) {
        const distance = entity.position.distanceTo(bot.entity.position);
        if (distance > maxDistance) continue;
        entities.push({ entity: entity, distance: distance });
    }
    entities.sort((a, b) => a.distance - b.distance);
    return entities.map(e => e.entity);
}

function getNearestEntityWhere(bot, predicate, maxDistance = 16) {
    return bot.nearestEntity(entity => predicate(entity) && bot.entity.position.distanceTo(entity.position) < maxDistance);
}

function getNearbyPlayers(bot, maxDistance = 16) {
    let players = [];
    for (const entity of Object.values(bot.entities)) {
        const distance = entity.position.distanceTo(bot.entity.position);
        if (distance > maxDistance) continue;
        if (entity.type == 'player' && entity.username != bot.username) {
            players.push({ entity: entity, distance: distance });
        }
    }
    players.sort((a, b) => a.distance - b.distance);
    return players.map(p => p.entity);
}

function getInventoryStacks(bot) {
    let inventory = [];
    for (const item of bot.inventory.items()) {
        if (item != null) inventory.push(item);
    }
    return inventory;
}

function getInventoryCounts(bot) {
    let inventory = {};
    for (const item of bot.inventory.items()) {
        if (item != null) {
            if (inventory[item.name] == null) inventory[item.name] = 0;
            inventory[item.name] += item.count;
        }
    }
    return inventory;
}

function getCraftableItems(bot) {
    let table = getNearestBlock(bot, 'crafting_table');
    if (!table) {
        for (const item of bot.inventory.items()) {
            if (item != null && item.name === 'crafting_table') {
                table = item;
                break;
            }
        }
    }
    let res = [];
    for (const item of mc.getAllItems()) {
        let recipes = bot.recipesFor(item.id, null, 1, table);
        if (recipes.length > 0) res.push(item.name);
    }
    return res;
}

function getPosition(bot) {
    return bot.entity.position;
}

function getNearbyEntityTypes(bot) {
    let mobs = getNearbyEntities(bot, 16);
    let found = [];
    for (let i = 0; i < mobs.length; i++) {
        if (!found.includes(mobs[i].name)) found.push(mobs[i].name);
    }
    return found;
}

function isEntityType(name) {
    return mc.getEntityId(name) !== null;
}

function getNearbyPlayerNames(bot) {
    let players = getNearbyPlayers(bot, 64);
    let found = [];
    for (let i = 0; i < players.length; i++) {
        if (!found.includes(players[i].username) && players[i].username != bot.username) {
            found.push(players[i].username);
        }
    }
    return found;
}

function getNearbyBlockTypes(bot, distance = 16) {
    let blocks = getNearestBlocks(bot, null, distance);
    let found = [];
    for (let i = 0; i < blocks.length; i++) {
        if (!found.includes(blocks[i].name)) found.push(blocks[i].name);
    }
    return found;
}

async function isClearPath(bot, target) {
    let movements = new pf.Movements(bot);
    movements.canDig = false;
    movements.canPlaceOn = false;
    movements.canOpenDoors = false;
    let goal = new pf.goals.GoalNear(target.position.x, target.position.y, target.position.z, 1);
    let path = await bot.pathfinder.getPathTo(movements, goal, 100);
    return path.status === 'success';
}

function shouldPlaceTorch(bot) {
    const pos = getPosition(bot);
    let nearest_torch = getNearestBlock(bot, 'torch', 6);
    if (!nearest_torch) nearest_torch = getNearestBlock(bot, 'wall_torch', 6);
    if (!nearest_torch) {
        const block = bot.blockAt(pos);
        let has_torch = bot.inventory.items().find(item => item.name === 'torch');
        return has_torch && block?.name === 'air';
    }
    return false;
}

function getBiomeName(bot) {
    const biomeId = bot.world.getBiome(bot.entity.position);
    return mc.getAllBiomes()[biomeId].name;
}

module.exports = {
    getNearestFreeSpace, getBlockAtPosition, getSurroundingBlocks,
    getFirstBlockAboveHead, getNearestBlocks, getNearestBlocksWhere,
    getNearestBlock, getNearbyEntities, getNearestEntityWhere,
    getNearbyPlayers, getInventoryStacks, getInventoryCounts,
    getCraftableItems, getPosition, getNearbyEntityTypes, isEntityType,
    getNearbyPlayerNames, getNearbyBlockTypes, isClearPath,
    shouldPlaceTorch, getBiomeName
};
