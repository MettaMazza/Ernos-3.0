/**
 * Shared state, IPC, and utilities for Mineflayer bot modules.
 * Single source of truth for the bot reference and communication.
 */

const { pathfinder, Movements: BaseMovements, goals } = require('mineflayer-pathfinder');
const { GoalNear, GoalFollow, GoalBlock, GoalXZ } = goals;

class Movements extends BaseMovements {
    constructor(bot, mcData) {
        super(bot, mcData);

        // Ernos Heuristics: Penalize and strictly avoid water where possible
        this.liquidCost = 100;

        if (mcData && mcData.blocksByName) {
            if (mcData.blocksByName.water) this.blocksToAvoid.add(mcData.blocksByName.water.id);
            if (mcData.blocksByName.flowing_water) this.blocksToAvoid.add(mcData.blocksByName.flowing_water.id);
        }

        // Strongly discourage digging through blocks (e.g. solid stone)
        this.digCost = 15;
        // Encourage placing blocks (bridges, stairs)
        this.placeCost = 2;

        // Ensure pathfinder actually knows what inventory items are allowed for stairs
        if (mcData && mcData.itemsByName) {
            const addScaffold = (name) => {
                if (mcData.itemsByName[name] && !this.scafoldingBlocks.includes(mcData.itemsByName[name].id)) {
                    this.scafoldingBlocks.push(mcData.itemsByName[name].id);
                }
            };
            ['dirt', 'cobblestone', 'oak_planks', 'spruce_planks', 'birch_planks', 'netherrack'].forEach(addScaffold);

            // Fetch valid light sources for the darkness avoidance heuristic
            const lightSources = ['torch', 'lantern', 'glowstone', 'shroomlight', 'sea_lantern', 'jack_o_lantern']
                .map(name => mcData.itemsByName[name] ? mcData.itemsByName[name].id : null)
                .filter(id => id !== null);

            // Darkness Avoidance: Plunging into dark caves without torches is deadly.
            this.exclusionAreasStep = this.exclusionAreasStep || [];
            this.exclusionAreasStep.push((block) => {
                // If light level is 5 or below, it's pitch black / mob spawning territory
                if (block.light <= 5) {
                    // Check if we have any light sources to theoretically use
                    const hasLightSource = bot.inventory.items().some(item => lightSources.includes(item.type));
                    if (!hasLightSource) {
                        return 100; // Impassable cost penalty
                    }
                }
                return 0; // Safe to pass
            });
        }
    }
}

// === Shared mutable state ===
let bot = null;
let mcData = null;
let _commandRegistry = {};

function getBot() { return bot; }
function setBot(b) { bot = b; }
function getMcData() { return mcData; }
function setMcData(d) { mcData = d; }

// === IPC: Send JSON response to Python bridge via stdout ===
function send(id, success, data = null, error = null) {
    const response = JSON.stringify({ id, success, data, error });
    console.log(response);
}

// === Structured logging to stderr (captured by Python bridge) ===
function mcLog(level, message, data = {}) {
    const timestamp = new Date().toISOString();
    const extra = Object.entries(data).map(([k, v]) => `${k}=${v}`).join(' | ');
    console.error(`[${timestamp}] [${level}] ${message}${extra ? ' | ' + extra : ''}`);
}

// === IPC: Send event to Python bridge via stdout ===
function sendEvent(type, data) {
    console.log(JSON.stringify({ event: type, data }));
}

// === Constants ===
const HOSTILE_NAMES = [
    'zombie', 'skeleton', 'spider', 'creeper', 'enderman', 'witch',
    'pillager', 'vindicator', 'phantom', 'drowned', 'husk', 'stray',
    'warden', 'blaze', 'ghast', 'piglin_brute', 'hoglin', 'zoglin',
    'evoker', 'ravager', 'vex', 'wither_skeleton', 'cave_spider'
];

module.exports = {
    getBot, setBot,
    getMcData, setMcData,
    send, mcLog, sendEvent,
    pathfinder, Movements, goals,
    GoalNear, GoalFollow, GoalBlock, GoalXZ,
    HOSTILE_NAMES,
    registerCommands: (cmds) => { _commandRegistry = cmds; },
    getCommand: (name) => _commandRegistry[name] || null
};
