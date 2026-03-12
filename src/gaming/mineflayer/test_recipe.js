const mineflayer = require('mineflayer');
const mcdata = require('./lib/mcdata');

const bot = mineflayer.createBot({
    host: 'localhost',
    port: 25565,
    username: 'TestBot2'
});

bot.once('spawn', () => {
    mcdata.initMcData(bot);
    console.log("birch_planks id:", mcdata.getItemId('birch_planks'));
    const recipes = mcdata.getItemCraftingRecipes('birch_planks');
    console.log("recipes:", JSON.stringify(recipes, null, 2));
    bot.quit();
});
