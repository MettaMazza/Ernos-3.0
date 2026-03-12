/**
 * Minecraft Data Utilities — adapted from Mindcraft (MIT License)
 * https://github.com/mindcraft-bots/mindcraft
 *
 * Provides block/item/entity ID lookups, recipe helpers, ore detection.
 * Requires initialization via initMcData(bot) after bot login.
 */

const minecraftData = require('minecraft-data');
const prismarineItem = require('prismarine-item');

let mcdata = null;
let Item = null;

const WOOD_TYPES = ['oak', 'spruce', 'birch', 'jungle', 'acacia', 'dark_oak', 'mangrove', 'cherry'];
const MATCHING_WOOD_BLOCKS = [
    'log', 'planks', 'sign', 'boat', 'fence_gate', 'door',
    'fence', 'slab', 'stairs', 'button', 'pressure_plate', 'trapdoor'
];
const WOOL_COLORS = [
    'white', 'orange', 'magenta', 'light_blue', 'yellow', 'lime',
    'pink', 'gray', 'light_gray', 'cyan', 'purple', 'blue',
    'brown', 'green', 'red', 'black'
];

function initMcData(bot) {
    mcdata = minecraftData(bot.version);
    Item = prismarineItem(bot.version);
}

function isHuntable(mob) {
    if (!mob || !mob.name) return false;
    const animals = ['chicken', 'cow', 'llama', 'mooshroom', 'pig', 'rabbit', 'sheep'];
    return animals.includes(mob.name.toLowerCase()) && !mob.metadata[16];
}

function isHostile(mob) {
    if (!mob || !mob.name) return false;
    return (mob.type === 'mob' || mob.type === 'hostile') && mob.name !== 'iron_golem' && mob.name !== 'snow_golem';
}

function mustCollectManually(blockName) {
    const full_names = ['wheat', 'carrots', 'potatoes', 'beetroots', 'nether_wart', 'cocoa', 'sugar_cane', 'kelp', 'short_grass', 'fern', 'tall_grass', 'bamboo',
        'poppy', 'dandelion', 'blue_orchid', 'allium', 'azure_bluet', 'oxeye_daisy', 'cornflower', 'lilac', 'wither_rose', 'lily_of_the_valley',
        'lever', 'redstone_wire', 'lantern'];
    const partial_names = ['sapling', 'torch', 'button', 'carpet', 'pressure_plate', 'mushroom', 'tulip', 'bush', 'vines', 'fern'];
    return full_names.includes(blockName.toLowerCase()) || partial_names.some(partial => blockName.toLowerCase().includes(partial));
}

function getItemId(itemName) {
    if (!mcdata) return null;
    let item = mcdata.itemsByName[itemName];
    return item ? item.id : null;
}

function getItemName(itemId) {
    if (!mcdata) return null;
    let item = mcdata.items[itemId];
    return item ? item.name : null;
}

function getBlockId(blockName) {
    if (!mcdata) return null;
    let block = mcdata.blocksByName[blockName];
    return block ? block.id : null;
}

function getBlockName(blockId) {
    if (!mcdata) return null;
    let block = mcdata.blocks[blockId];
    return block ? block.name : null;
}

function getEntityId(entityName) {
    if (!mcdata) return null;
    let entity = mcdata.entitiesByName[entityName];
    return entity ? entity.id : null;
}

function getAllItems(ignore) {
    if (!mcdata) return [];
    if (!ignore) ignore = [];
    let items = [];
    for (const itemId in mcdata.items) {
        const item = mcdata.items[itemId];
        if (!ignore.includes(item.name)) items.push(item);
    }
    return items;
}

function getAllItemIds(ignore) {
    return getAllItems(ignore).map(item => item.id);
}

function getAllBlocks(ignore) {
    if (!mcdata) return [];
    if (!ignore) ignore = [];
    let blocks = [];
    for (const blockId in mcdata.blocks) {
        const block = mcdata.blocks[blockId];
        if (!ignore.includes(block.name)) blocks.push(block);
    }
    return blocks;
}

function getAllBlockIds(ignore) {
    return getAllBlocks(ignore).map(block => block.id);
}

function getAllBiomes() {
    if (!mcdata) return {};
    return mcdata.biomes;
}

function getItemCraftingRecipes(itemName) {
    let itemId = getItemId(itemName);
    if (!mcdata || !mcdata.recipes[itemId]) return null;

    let recipes = [];
    for (let r of mcdata.recipes[itemId]) {
        let recipe = {};
        let ingredients = [];
        if (r.ingredients) {
            ingredients = r.ingredients;
        } else if (r.inShape) {
            ingredients = r.inShape.flat();
        }
        for (let ingredient of ingredients) {
            let ingredientName = getItemName(ingredient);
            if (ingredientName === null) continue;
            if (!recipe[ingredientName]) recipe[ingredientName] = 0;
            recipe[ingredientName]++;
        }
        recipes.push([recipe, { craftedCount: r.result.count }]);
    }
    const commonItems = ['oak_planks', 'oak_log', 'coal', 'cobblestone'];
    recipes.sort((a, b) => {
        let commonCountA = Object.keys(a[0]).filter(key => commonItems.includes(key)).reduce((acc, key) => acc + a[0][key], 0);
        let commonCountB = Object.keys(b[0]).filter(key => commonItems.includes(key)).reduce((acc, key) => acc + b[0][key], 0);
        return commonCountB - commonCountA;
    });
    return recipes;
}

function isSmeltable(itemName) {
    const misc_smeltables = ['beef', 'chicken', 'cod', 'mutton', 'porkchop', 'rabbit', 'salmon', 'tropical_fish', 'potato', 'kelp', 'sand', 'cobblestone', 'clay_ball'];
    return itemName.includes('raw') || itemName.includes('log') || misc_smeltables.includes(itemName);
}

function getSmeltingFuel(bot) {
    let fuel = bot.inventory.items().find(i => i.name === 'coal' || i.name === 'charcoal' || i.name === 'blaze_rod');
    if (fuel) return fuel;
    fuel = bot.inventory.items().find(i => i.name.includes('log') || i.name.includes('planks'));
    if (fuel) return fuel;
    return bot.inventory.items().find(i => i.name === 'coal_block' || i.name === 'lava_bucket');
}

function getFuelSmeltOutput(fuelName) {
    if (fuelName === 'coal' || fuelName === 'charcoal') return 8;
    if (fuelName === 'blaze_rod') return 12;
    if (fuelName.includes('log') || fuelName.includes('planks')) return 1.5;
    if (fuelName === 'coal_block') return 80;
    if (fuelName === 'lava_bucket') return 100;
    return 0;
}

function getItemSmeltingIngredient(itemName) {
    return {
        baked_potato: 'potato', steak: 'raw_beef', cooked_chicken: 'raw_chicken',
        cooked_cod: 'raw_cod', cooked_mutton: 'raw_mutton', cooked_porkchop: 'raw_porkchop',
        cooked_rabbit: 'raw_rabbit', cooked_salmon: 'raw_salmon', dried_kelp: 'kelp',
        iron_ingot: 'raw_iron', gold_ingot: 'raw_gold', copper_ingot: 'raw_copper', glass: 'sand'
    }[itemName];
}

function getItemBlockSources(itemName) {
    let itemId = getItemId(itemName);
    let sources = [];
    for (let block of getAllBlocks()) {
        if (block.drops.includes(itemId)) sources.push(block.name);
    }
    return sources;
}

function getItemAnimalSource(itemName) {
    return {
        raw_beef: 'cow', raw_chicken: 'chicken', raw_cod: 'cod',
        raw_mutton: 'sheep', raw_porkchop: 'pig', raw_rabbit: 'rabbit',
        raw_salmon: 'salmon', leather: 'cow', wool: 'sheep'
    }[itemName];
}

function getBlockTool(blockName) {
    if (!mcdata) return null;
    let block = mcdata.blocksByName[blockName];
    if (!block || !block.harvestTools) return null;
    return getItemName(Object.keys(block.harvestTools)[0]);
}

function makeItem(name, amount = 1) {
    return new Item(getItemId(name), amount);
}

function ingredientsFromPrismarineRecipe(recipe) {
    let requiredIngredients = {};
    if (recipe.inShape)
        for (const ingredient of recipe.inShape.flat()) {
            if (ingredient.id < 0) continue;
            const ingredientName = getItemName(ingredient.id);
            requiredIngredients[ingredientName] ??= 0;
            requiredIngredients[ingredientName] += ingredient.count;
        }
    if (recipe.ingredients)
        for (const ingredient of recipe.ingredients) {
            if (ingredient.id < 0) continue;
            const ingredientName = getItemName(ingredient.id);
            requiredIngredients[ingredientName] ??= 0;
            requiredIngredients[ingredientName] -= ingredient.count;
        }
    return requiredIngredients;
}

function calculateLimitingResource(availableItems, requiredItems, discrete = true) {
    let limitingResource = null;
    let num = Infinity;
    for (const itemType in requiredItems) {
        if (availableItems[itemType] < requiredItems[itemType] * num) {
            limitingResource = itemType;
            num = availableItems[itemType] / requiredItems[itemType];
        }
    }
    if (discrete) num = Math.floor(num);
    return { num, limitingResource };
}

module.exports = {
    initMcData,
    WOOD_TYPES, MATCHING_WOOD_BLOCKS, WOOL_COLORS,
    isHuntable, isHostile, mustCollectManually,
    getItemId, getItemName, getBlockId, getBlockName, getEntityId,
    getAllItems, getAllItemIds, getAllBlocks, getAllBlockIds, getAllBiomes,
    getItemCraftingRecipes, isSmeltable, getSmeltingFuel, getFuelSmeltOutput,
    getItemSmeltingIngredient, getItemBlockSources, getItemAnimalSource,
    getBlockTool, makeItem, ingredientsFromPrismarineRecipe, calculateLimitingResource
};
