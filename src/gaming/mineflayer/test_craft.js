const mineflayer = require('mineflayer');
const { pathfinder, Movements } = require('mineflayer-pathfinder');
const mcdata = require('./lib/mcdata');
const skills = require('./lib/skills');
const armorManager = require('mineflayer-armor-manager');

const bot = mineflayer.createBot({
    host: 'localhost',
    port: 25565,
    username: 'TestBot2'
});

bot.loadPlugin(pathfinder);
bot.loadPlugin(armorManager);

bot.once('spawn', async () => {
    mcdata.initMcData(bot);
    const mcData = require('minecraft-data')(bot.version);
    bot.pathfinder.setMovements(new Movements(bot, mcData));

    // Give ourselves birch wood
    bot.chat('/give @s birch_log 10');
    await new Promise(r => setTimeout(r, 1000));

    console.log("Testing craftRecipe for birch_planks... Inventory size:", bot.inventory.items().length);
    bot.output = "";
    try {
        const result = await skills.craftRecipe(bot, 'birch_planks', 4);
        console.log("Result:", result, "\nLog:\n" + bot.output);
    } catch (e) {
        console.error("Exception:", e);
    }

    bot.quit();
});
