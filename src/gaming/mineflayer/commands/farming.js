/**
 * Farming commands — farm, harvest, plant, fish.
 */

const { getBot, getMcData, mcLog } = require('../shared');

async function cmdFarm({ crop = 'wheat', radius = 8 }) {
    const bot = getBot();
    const mcData = getMcData();
    try {
        const pos = bot.entity.position;
        let tilled = 0, planted = 0;

        const seedMap = { 'wheat': 'wheat_seeds', 'carrots': 'carrot', 'potatoes': 'potato', 'beetroot': 'beetroot_seeds' };
        const seedName = seedMap[crop.toLowerCase()] || 'wheat_seeds';

        const hoe = bot.inventory.items().find(i => i.name.includes('hoe'));
        if (!hoe) return { success: false, error: 'No hoe in inventory' };

        const seeds = bot.inventory.items().find(i => i.name === seedName);
        if (!seeds) return { success: false, error: `No ${seedName} in inventory` };

        for (let dx = -radius; dx <= radius; dx++) {
            for (let dz = -radius; dz <= radius; dz++) {
                const blockPos = pos.offset(dx, -1, dz);
                const block = bot.blockAt(blockPos);

                if (block && (block.name === 'dirt' || block.name === 'grass_block')) {
                    await bot.equip(hoe, 'hand');
                    await bot.activateBlock(block);
                    tilled++;

                    await bot.equip(seeds, 'hand');
                    const farmland = bot.blockAt(blockPos);
                    if (farmland && farmland.name === 'farmland') {
                        const aboveBlock = bot.blockAt(blockPos.offset(0, 1, 0));
                        if (aboveBlock && aboveBlock.name === 'air') {
                            try {
                                await bot.placeBlock(farmland, new mcData.Vec3(0, 1, 0));
                                planted++;
                            } catch (e) { /* Skip */ }
                        }
                    }
                }
            }
        }

        mcLog('INFO', 'FARMED', { tilled, planted, crop });
        return { success: true, action: 'farmed', tilled, planted, crop };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdHarvest({ radius = 10 }) {
    const bot = getBot();
    try {
        const pos = bot.entity.position;
        const matureCrops = ['wheat', 'carrots', 'potatoes', 'beetroots'];
        let harvested = 0;

        for (let dx = -radius; dx <= radius; dx++) {
            for (let dy = -1; dy <= 2; dy++) {
                for (let dz = -radius; dz <= radius; dz++) {
                    const blockPos = pos.offset(dx, dy, dz);
                    const block = bot.blockAt(blockPos);

                    if (block && matureCrops.some(c => block.name.includes(c))) {
                        const age = block.getProperties ? block.getProperties().age : null;
                        if (age === 7 || age === 3 || !age) {
                            try { await bot.dig(block); harvested++; }
                            catch (e) { /* Skip */ }
                        }
                    }
                }
            }
        }

        mcLog('INFO', 'HARVESTED', { count: harvested });
        return { success: true, action: 'harvested', count: harvested };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdPlant({ seed = 'wheat_seeds', count = 1 }) {
    const bot = getBot();
    const mcData = getMcData();
    try {
        const seeds = bot.inventory.items().find(i =>
            i.name.toLowerCase().includes(seed.toLowerCase())
        );
        if (!seeds) return { success: false, error: `No ${seed} in inventory` };

        await bot.equip(seeds, 'hand');

        const farmland = bot.findBlocks({ matching: block => block.name === 'farmland', maxDistance: 32, count });
        if (farmland.length === 0) return { success: false, error: 'No farmland nearby' };

        let planted = 0;
        for (const fPos of farmland) {
            const farmBlock = bot.blockAt(fPos);
            const aboveBlock = bot.blockAt(fPos.offset(0, 1, 0));
            if (farmBlock && aboveBlock && aboveBlock.name === 'air') {
                try { await bot.placeBlock(farmBlock, new mcData.Vec3(0, 1, 0)); planted++; }
                catch (e) { /* Skip */ }
            }
        }

        mcLog('INFO', 'PLANTED', { seed: seeds.name, count: planted });
        return { success: true, action: 'planted', seed: seeds.name, count: planted };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdFish({ duration = 30 }) {
    const bot = getBot();
    try {
        const rod = bot.inventory.items().find(i => i.name === 'fishing_rod');
        if (!rod) return { success: false, error: 'No fishing rod in inventory' };

        await bot.equip(rod, 'hand');

        const water = bot.findBlock({ matching: block => block.name === 'water', maxDistance: 32 });
        if (!water) return { success: false, error: 'No water nearby' };

        await bot.lookAt(water.position);
        bot.activateItem();
        mcLog('INFO', 'FISHING_STARTED');

        let caught = 0;
        const endTime = Date.now() + (duration * 1000);

        while (Date.now() < endTime) {
            await new Promise(resolve => setTimeout(resolve, 5000));
            if (Math.random() < 0.3) {
                bot.activateItem();
                caught++;
                await new Promise(resolve => setTimeout(resolve, 1000));
                bot.activateItem();
            }
        }

        bot.activateItem();
        mcLog('INFO', 'FISHING_COMPLETE', { caught });
        return { success: true, action: 'fished', caught, duration };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

module.exports = { cmdFarm, cmdHarvest, cmdPlant, cmdFish };
