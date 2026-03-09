/**
 * Mineflayer Bot - Clean MVP for Ernos Gaming
 * 
 * JSON IPC via stdin/stdout with Python bridge.
 * Commands: goto, follow, collect, attack, craft, status, chat
 */

const mineflayer = require('mineflayer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');
const { GoalNear, GoalFollow, GoalBlock } = goals;
const readline = require('readline');
const visual = require('./visual');

// === GLOBAL CRASH HANDLERS - CATCH EVERYTHING ===
process.on('uncaughtException', (err) => {
    console.error(`[FATAL] UNCAUGHT_EXCEPTION: ${err.message}`);
    console.error(err.stack);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error(`[FATAL] UNHANDLED_REJECTION: ${reason}`);
    if (reason && reason.stack) console.error(reason.stack);
});

process.on('exit', (code) => {
    console.error(`[FATAL] PROCESS_EXIT | code=${code}`);
});

process.on('SIGTERM', () => {
    console.error('[FATAL] SIGTERM received');
});

process.on('SIGINT', () => {
    console.error('[FATAL] SIGINT received');
});

// Configuration from environment
const config = {
    host: process.env.MC_HOST || 'localhost',
    port: parseInt(process.env.MC_PORT) || 65535,
    username: process.env.MC_USERNAME || 'Ernos',
    version: process.env.MC_VERSION || null
};

let bot = null;
let mcData = null;

// AGGRO SYSTEM: Track players who attacked Ernos
// When a player attacks Ernos, they enter this set
// They can only be removed by saying "sorry" in chat
const aggroPlayers = new Set();

// PROTECTED ZONES: Permanent no-break zones (persisted to disk)
// Format: [{x, y, z, radius, owner, created}]
let protectedZones = [];
const ZONES_FILE = './memory/public/protected_zones.json';
const fs = require('fs');
const path = require('path');

// SAVED LOCATIONS: Named waypoints (persisted to disk)
// Format: {name: {x, y, z, dimension, savedBy, created}}
let savedLocations = {};
const LOCATIONS_FILE = './memory/public/saved_locations.json';

// BLUEPRINTS: Saved building structures (persisted to disk)
// Format: {name: {blocks: [{dx, dy, dz, blockName}], origin: {x, y, z}, savedBy, created}}
let blueprints = {};
const BLUEPRINTS_FILE = './memory/public/blueprints.json';

function loadSavedLocations() {
    try {
        if (fs.existsSync(LOCATIONS_FILE)) {
            const data = fs.readFileSync(LOCATIONS_FILE, 'utf8');
            savedLocations = JSON.parse(data);
            console.error(`[INFO] Loaded ${Object.keys(savedLocations).length} saved locations`);
        }
    } catch (e) {
        console.error(`[WARN] Could not load saved locations: ${e.message}`);
        savedLocations = {};
    }
}

function saveSavedLocations() {
    try {
        const dir = path.dirname(LOCATIONS_FILE);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(LOCATIONS_FILE, JSON.stringify(savedLocations, null, 2));
    } catch (e) {
        console.error(`[ERROR] Could not save locations: ${e.message}`);
    }
}

function loadBlueprints() {
    try {
        if (fs.existsSync(BLUEPRINTS_FILE)) {
            const data = fs.readFileSync(BLUEPRINTS_FILE, 'utf8');
            blueprints = JSON.parse(data);
            console.error(`[INFO] Loaded ${Object.keys(blueprints).length} blueprints`);
        }
    } catch (e) {
        console.error(`[WARN] Could not load blueprints: ${e.message}`);
        blueprints = {};
    }
}

function saveBlueprints() {
    try {
        const dir = path.dirname(BLUEPRINTS_FILE);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(BLUEPRINTS_FILE, JSON.stringify(blueprints, null, 2));
    } catch (e) {
        console.error(`[ERROR] Could not save blueprints: ${e.message}`);
    }
}

function loadProtectedZones() {
    try {
        if (fs.existsSync(ZONES_FILE)) {
            const data = fs.readFileSync(ZONES_FILE, 'utf8');
            protectedZones = JSON.parse(data);
            console.error(`[INFO] Loaded ${protectedZones.length} protected zones`);
        }
    } catch (e) {
        console.error(`[WARN] Could not load protected zones: ${e.message}`);
        protectedZones = [];
    }
}

function saveProtectedZones() {
    try {
        // Ensure directory exists
        const dir = path.dirname(ZONES_FILE);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(ZONES_FILE, JSON.stringify(protectedZones, null, 2));
        console.error(`[INFO] Saved ${protectedZones.length} protected zones`);
    } catch (e) {
        console.error(`[ERROR] Could not save protected zones: ${e.message}`);
    }
}

function isBlockProtected(blockPos) {
    for (const zone of protectedZones) {
        const dist = Math.sqrt(
            Math.pow(blockPos.x - zone.x, 2) +
            Math.pow(blockPos.y - zone.y, 2) +
            Math.pow(blockPos.z - zone.z, 2)
        );
        if (dist <= zone.radius) {
            return zone;
        }
    }
    return null;
}

// Load zones on startup
loadProtectedZones();
loadSavedLocations();
loadBlueprints();

// IPC: Send response to Python
function send(id, success, data = null, error = null) {
    const response = JSON.stringify({ id, success, data, error });
    console.log(response);
}

// Structured logging to stderr (captured by Python bridge)
function mcLog(level, message, data = {}) {
    const timestamp = new Date().toISOString();
    const extra = Object.entries(data).map(([k, v]) => `${k}=${v}`).join(' | ');
    console.error(`[${timestamp}] [${level}] ${message}${extra ? ' | ' + extra : ''}`);
}

// IPC: Send event to Python
function sendEvent(type, data) {
    console.log(JSON.stringify({ event: type, data }));
}

// Initialize bot
function initBot() {
    bot = mineflayer.createBot(config);

    bot.loadPlugin(pathfinder);

    bot.once('spawn', () => {
        mcData = require('minecraft-data')(bot.version);
        const movements = new Movements(bot, mcData);
        bot.pathfinder.setMovements(movements);
        mcLog('INFO', 'BOT_SPAWNED', { x: bot.entity.position.x, y: bot.entity.position.y, z: bot.entity.position.z });
        sendEvent('spawn', { position: bot.entity.position });

        // Auto-spectate: Make all players spectate Ernos
        // First set to spectator mode, then spectate the bot
        setTimeout(() => {
            // Set all players (except Ernos) to spectator mode
            bot.chat('/gamemode spectator @a[name=!' + bot.username + ']');
            mcLog('INFO', 'AUTO_SPECTATE_GAMEMODE_SENT');
        }, 2000);

        setTimeout(() => {
            // Now make them spectate Ernos
            bot.chat('/spectate ' + bot.username + ' @a[name=!' + bot.username + ']');
            mcLog('INFO', 'AUTO_SPECTATE_TARGET_SENT', { target: bot.username });
        }, 3000);

        // Initialize visual perception (async, don't block spawn)
        visual.initViewer(bot).then(success => {
            if (success) {
                sendEvent('visual_ready', {});
            }
        });
    });

    bot.on('health', () => {
        mcLog('DEBUG', 'HEALTH_UPDATE', { health: bot.health, food: bot.food });
        sendEvent('health', { health: bot.health, food: bot.food });
    });

    bot.on('death', () => {
        mcLog('WARNING', 'BOT_DIED');
        sendEvent('death', {});
    });

    // Re-spectate after respawn
    bot.on('respawn', () => {
        mcLog('INFO', 'BOT_RESPAWNED');
        sendEvent('respawn', {});

        // Re-trigger spectate for all players
        setTimeout(() => {
            bot.chat('/gamemode spectator @a[name=!' + bot.username + ']');
            mcLog('INFO', 'RESPAWN_SPECTATE_GAMEMODE_SENT');
        }, 1000);

        setTimeout(() => {
            bot.chat('/spectate ' + bot.username + ' @a[name=!' + bot.username + ']');
            mcLog('INFO', 'RESPAWN_SPECTATE_TARGET_SENT', { target: bot.username });
        }, 2000);
    });

    bot.on('chat', (username, message) => {
        mcLog('DEBUG', 'CHAT_RAW', { from: username, msg: message.substring(0, 50), bot_name: bot.username });
        if (username !== bot.username) {
            // AGGRO SYSTEM: Check if player apologized
            const lowerMsg = message.toLowerCase();
            if (aggroPlayers.has(username) && (lowerMsg.includes('sorry') || lowerMsg.includes('apolog'))) {
                aggroPlayers.delete(username);
                mcLog('INFO', 'AGGRO_CLEARED', { player: username, reason: 'apology' });
                sendEvent('aggro_cleared', { username, message });
                // No canned reply - LLM generates natural response via event
            }

            mcLog('INFO', 'CHAT_FORWARDED', { username, message: message.substring(0, 50) });
            sendEvent('chat', { username, message });
        } else {
            mcLog('DEBUG', 'CHAT_IGNORED_SELF', { username });
        }
    });

    // AGGRO SYSTEM: Track when players attack Ernos
    bot.on('entityHurt', (entity) => {
        // Check if Ernos was hurt
        if (entity === bot.entity) {
            // Find the nearest player - they're likely the attacker
            const attacker = bot.nearestEntity(e => e.type === 'player' && e.username !== bot.username);
            if (attacker && attacker.username) {
                aggroPlayers.add(attacker.username);
                mcLog('WARNING', 'AGGRO_TRIGGERED', { attacker: attacker.username });
                sendEvent('aggro_triggered', { attacker: attacker.username });
                // No canned reply - LLM generates natural response via event
            }
        }
    });

    bot.on('error', (err) => {
        mcLog('ERROR', 'BOT_ERROR', { message: err.message });
        sendEvent('error', { message: err.message });
    });

    bot.on('kicked', (reason) => {
        sendEvent('kicked', { reason });
    });
}

// === COMMANDS ===

async function cmdGoto(params) {
    const { x, y, z, range = 1 } = params;
    const goal = new GoalNear(x, y, z, range);

    return new Promise((resolve, reject) => {
        mcLog('DEBUG', 'GOTO_STARTED', { x, y, z });
        bot.pathfinder.setGoal(goal);

        const onGoalReached = () => {
            cleanup();
            resolve({ position: bot.entity.position });
        };

        const onPathStop = () => {
            cleanup();
            resolve({ position: bot.entity.position, stopped: true });
        };

        const cleanup = () => {
            bot.removeListener('goal_reached', onGoalReached);
            bot.removeListener('path_stop', onPathStop);
        };

        bot.once('goal_reached', onGoalReached);
        bot.once('path_stop', onPathStop);

        // Short timeout - respond quickly so Python doesn't timeout
        setTimeout(() => {
            cleanup();
            bot.pathfinder.setGoal(null);
            // Don't reject - resolve with current position
            resolve({ position: bot.entity.position, timeout: true });
        }, 8000);  // 8s < bridge's 10s default
    });
}

async function cmdFollow(params) {
    const { username, range = 3 } = params;
    const player = bot.players[username];

    if (!player || !player.entity) {
        throw new Error(`Player ${username} not found or not visible`);
    }

    const goal = new GoalFollow(player.entity, range);
    bot.pathfinder.setGoal(goal, true); // Dynamic goal

    return { following: username };
}

async function cmdStopFollow() {
    bot.pathfinder.setGoal(null);
    return { stopped: true };
}

async function cmdCollect(params) {
    const { block_type, count = 1 } = params;
    const blockId = mcData.blocksByName[block_type]?.id;

    if (!blockId) {
        throw new Error(`Unknown block: ${block_type}`);
    }

    // BLOCK PROTECTION: Only allow collecting natural/raw resources
    // This prevents Ernos from destroying player-built structures
    const NATURAL_BLOCKS = [
        // Trees & Wood (natural only)
        'oak_log', 'birch_log', 'spruce_log', 'jungle_log', 'acacia_log', 'dark_oak_log',
        'cherry_log', 'mangrove_log', 'bamboo_block',
        // Stone & Ores (underground natural)
        'stone', 'cobblestone', 'deepslate', 'granite', 'diorite', 'andesite',
        'coal_ore', 'iron_ore', 'gold_ore', 'diamond_ore', 'emerald_ore', 'lapis_ore',
        'redstone_ore', 'copper_ore', 'deepslate_coal_ore', 'deepslate_iron_ore',
        // Natural terrain
        'dirt', 'grass_block', 'sand', 'gravel', 'clay', 'terracotta',
        // Plants (natural)
        'sugar_cane', 'bamboo', 'cactus', 'pumpkin', 'melon',
        // Leaves
        'oak_leaves', 'birch_leaves', 'spruce_leaves', 'jungle_leaves', 'acacia_leaves', 'dark_oak_leaves'
    ];

    if (!NATURAL_BLOCKS.includes(block_type)) {
        logDebug(`BLOCK_PROTECTED | type=${block_type} | reason=Not a natural block`);
        return { collected: 0, requested: count, error: `Cannot collect ${block_type} - may be player-placed` };
    }

    let collected = 0;

    for (let i = 0; i < count; i++) {
        const block = bot.findBlock({
            matching: blockId,
            maxDistance: 32
        });

        if (!block) {
            break;
        }

        // PERMANENT PROTECTED ZONES: Never break blocks in protected zones
        const protectedZone = isBlockProtected(block.position);
        if (protectedZone) {
            mcLog('DEBUG', 'BLOCK_IN_PROTECTED_ZONE', {
                zone_owner: protectedZone.owner,
                zone_radius: protectedZone.radius,
                block_type
            });
            // Skip this block entirely - find another
            continue;
        }

        // DISTANCE PROTECTION: Don't break blocks near non-aggro players
        const PROTECTION_RADIUS = 20;  // blocks
        let tooCloseToPlayer = false;

        for (const player of Object.values(bot.players)) {
            if (!player.entity || player.username === bot.username) continue;

            // Skip distance check for aggro players - their blocks are fair game!
            if (aggroPlayers.has(player.username)) {
                mcLog('DEBUG', 'AGGRO_BYPASS', { player: player.username, reason: 'Player in aggro list' });
                continue;
            }

            const dist = block.position.distanceTo(player.entity.position);
            if (dist < PROTECTION_RADIUS) {
                mcLog('DEBUG', 'BLOCK_NEAR_PLAYER', {
                    player: player.username,
                    distance: dist.toFixed(1),
                    block_type
                });
                tooCloseToPlayer = true;
                break;
            }
        }

        if (tooCloseToPlayer) {
            // Try to find a different block further away
            continue;
        }

        // Navigate to block with proper cleanup
        const goal = new GoalBlock(block.position.x, block.position.y, block.position.z);
        bot.pathfinder.setGoal(goal);

        await new Promise(resolve => {
            const onGoalReached = () => { cleanup(); resolve(); };
            const onPathStop = () => { cleanup(); resolve(); };
            const cleanup = () => {
                bot.removeListener('goal_reached', onGoalReached);
                bot.removeListener('path_stop', onPathStop);
            };
            bot.once('goal_reached', onGoalReached);
            bot.once('path_stop', onPathStop);
            setTimeout(() => { cleanup(); resolve(); }, 15000);  // 15s timeout for mining
        });

        // Dig block
        try {
            await bot.dig(block);
            collected++;
        } catch (e) {
            // Block may have been removed
        }
    }

    return { collected, requested: count };
}

async function cmdAttack(params) {
    const { entity_type = 'hostile' } = params;

    let target = null;

    if (entity_type === 'hostile') {
        // Find nearest hostile mob
        const hostiles = ['zombie', 'skeleton', 'spider', 'creeper'];
        target = bot.nearestEntity(e =>
            e.type === 'mob' && hostiles.includes(e.name)
        );
    } else {
        target = bot.nearestEntity(e => e.name === entity_type);
    }

    if (!target) {
        return { attacked: false, reason: 'No target found' };
    }

    // Navigate to target if not in attack range (about 3 blocks)
    const dist = bot.entity.position.distanceTo(target.position);
    if (dist > 3) {
        mcLog('DEBUG', 'ATTACK_NAVIGATING', { target: target.name, distance: dist.toFixed(1) });

        // Use GoalFollow to get close to the entity
        const goal = new GoalFollow(target, 2); // 2 blocks range
        bot.pathfinder.setGoal(goal);

        // Wait for navigation (max 5 seconds)
        await new Promise(resolve => {
            const checkInterval = setInterval(() => {
                const currentDist = bot.entity.position.distanceTo(target.position);
                if (currentDist <= 3 || !target.isValid) {
                    clearInterval(checkInterval);
                    bot.pathfinder.setGoal(null);
                    resolve();
                }
            }, 200);

            setTimeout(() => {
                clearInterval(checkInterval);
                bot.pathfinder.setGoal(null);
                resolve();
            }, 5000);
        });
    }

    // Now attack (should be in range)
    const finalDist = bot.entity.position.distanceTo(target.position);
    if (finalDist > 4) {
        mcLog('DEBUG', 'ATTACK_TOO_FAR', { target: target.name, distance: finalDist.toFixed(1) });
        return { attacked: false, reason: 'Could not reach target', distance: finalDist };
    }

    await bot.attack(target);
    mcLog('DEBUG', 'ATTACK_EXECUTED', { target: target.name, distance: finalDist.toFixed(1) });
    return { attacked: true, target: target.name };
}

async function cmdCraft(params) {
    const { item, count = 1 } = params;
    const itemData = mcData.itemsByName[item];

    if (!itemData) {
        throw new Error(`Unknown item: ${item}`);
    }

    const recipe = bot.recipesFor(itemData.id, null, 1, null)[0];

    if (!recipe) {
        throw new Error(`No recipe for ${item}`);
    }

    await bot.craft(recipe, count, null);
    return { crafted: item, count };
}

async function cmdStatus() {
    const inventory = bot.inventory.items().map(i => ({
        name: i.name,
        count: i.count
    }));

    return {
        health: bot.health,
        food: bot.food,
        position: {
            x: Math.round(bot.entity.position.x),
            y: Math.round(bot.entity.position.y),
            z: Math.round(bot.entity.position.z)
        },
        inventory: inventory.slice(0, 20) // Limit for IPC
    };
}

async function cmdChat(params) {
    const { message } = params;
    bot.chat(message);
    return { sent: message };
}

async function cmdDisconnect() {
    await visual.closeViewer();
    bot.quit();
    return { disconnected: true };
}

// Visual perception command
async function cmdGetScreenshot() {
    if (!visual.isViewerReady()) {
        return { success: false, error: 'Visual perception not ready' };
    }
    return await visual.captureScreenshot();
}

// === PREDICTIVE CHAIN SYSTEM ===
// State for predictive chain execution
const chainState = {
    isRunning: false,
    reflexLog: []
};

// Reflex: Look around randomly
async function cmdLookAround() {
    const yaw = bot.entity.yaw + (Math.random() - 0.5) * Math.PI;
    const pitch = (Math.random() - 0.5) * 0.5;
    await bot.look(yaw, pitch, false);
    return { looked: true };
}

// Reflex: Maintain status (eat if hungry)
async function cmdMaintainStatus() {
    if (bot.food >= 18) {
        return { action: 'none', reason: 'Not hungry' };
    }

    // Find food in inventory
    const food = bot.inventory.items().find(item =>
        item.name.includes('bread') || item.name.includes('apple') ||
        item.name.includes('cooked') || item.name.includes('steak') ||
        item.name.includes('carrot') || item.name.includes('potato')
    );

    if (!food) {
        return { action: 'none', reason: 'No food' };
    }

    try {
        await bot.equip(food, 'hand');
        await bot.consume();
        return { action: 'ate', item: food.name };
    } catch (e) {
        return { action: 'failed', error: e.message };
    }
}

// Reflex: Defend (look at nearby hostiles)
async function cmdDefend() {
    const hostiles = ['zombie', 'skeleton', 'spider', 'creeper', 'enderman'];
    const hostile = bot.nearestEntity(e =>
        e.type === 'mob' && hostiles.includes(e.name) &&
        bot.entity.position.distanceTo(e.position) < 8
    );

    if (!hostile) {
        return { threat: false };
    }

    await bot.lookAt(hostile.position.offset(0, hostile.height, 0));
    return { threat: true, entity: hostile.name, distance: bot.entity.position.distanceTo(hostile.position) };
}

// Reflex: Collect nearby dropped items
async function cmdCollectDrops() {
    const drop = bot.nearestEntity(e =>
        e.name === 'item' && bot.entity.position.distanceTo(e.position) < 4
    );

    if (!drop) {
        return { collected: false };
    }

    // Walk toward drop
    await bot.lookAt(drop.position);
    bot.setControlState('forward', true);
    await new Promise(r => setTimeout(r, 300));
    bot.setControlState('forward', false);

    return { collected: true };
}

// Reflex: Get nearby entities for observation
async function cmdGetNearby() {
    const entities = [];
    const hostiles = ['zombie', 'skeleton', 'spider', 'creeper'];

    for (const entity of Object.values(bot.entities)) {
        if (!entity || entity === bot.entity) continue;
        const dist = bot.entity.position.distanceTo(entity.position);
        if (dist > 32) continue;

        entities.push({
            name: entity.name || entity.username || 'unknown',
            type: entity.type,
            distance: Math.round(dist),
            hostile: hostiles.includes(entity.name)
        });
    }

    return {
        entities: entities.slice(0, 10),
        hostiles_nearby: entities.some(e => e.hostile && e.distance < 16)
    };
}

// Reflex: Get time of day
async function cmdGetTime() {
    return {
        time: bot.time.day,
        isDay: bot.time.day < 12000 || bot.time.day > 23000
    };
}

// Execute predictive chain (runs in background during LLM inference)
async function cmdExecutePredictiveChain(params) {
    const { chain = [] } = params;

    // Stop any existing chain
    chainState.isRunning = false;
    await new Promise(r => setTimeout(r, 100));

    chainState.isRunning = true;
    chainState.reflexLog = [];

    console.log(`[Predictive] Starting chain with ${chain.length} actions`);

    // Execute chain in background
    (async () => {
        for (const action of chain) {
            if (!chainState.isRunning) {
                chainState.reflexLog.push({ action: action.command, status: 'interrupted' });
                break;
            }

            try {
                const cmd = reflexCommands[action.command];
                if (cmd) {
                    await cmd(action.params || {});
                    chainState.reflexLog.push({ action: action.command, status: 'completed' });
                } else {
                    chainState.reflexLog.push({ action: action.command, status: 'unknown' });
                }
            } catch (e) {
                chainState.reflexLog.push({ action: action.command, status: 'failed', error: e.message });
            }

            await new Promise(r => setTimeout(r, 200));
        }
        chainState.isRunning = false;
    })();

    return { success: true, message: 'Chain started' };
}

// Stop predictive chain
async function cmdStopPredictiveChain() {
    chainState.isRunning = false;
    return { stopped: true, log: chainState.reflexLog };
}

// Get reflex log (what happened during inference)
async function cmdGetReflexLog() {
    const log = chainState.reflexLog;
    chainState.reflexLog = [];
    return { log };
}

// Create a protected zone (permanent, saved to disk)
async function cmdProtect({ username, x, y, z, radius = 50 }) {
    // Get position from bot if not specified
    if (x === undefined || y === undefined || z === undefined) {
        x = Math.floor(bot.entity.position.x);
        y = Math.floor(bot.entity.position.y);
        z = Math.floor(bot.entity.position.z);
    }

    const zone = {
        x: x,
        y: y,
        z: z,
        radius: radius,
        owner: username || 'unknown',
        created: new Date().toISOString()
    };

    protectedZones.push(zone);
    saveProtectedZones();

    mcLog('INFO', 'PROTECTED_ZONE_CREATED', zone);
    // No canned reply - LLM generates natural response via embodiment log

    return {
        success: true,
        zone: zone,
        total_zones: protectedZones.length
    };
}

// List all protected zones
async function cmdListProtectedZones() {
    return {
        zones: protectedZones,
        total: protectedZones.length
    };
}

// === PHASE 1: COMBAT SURVIVAL COMMANDS ===

// Equip armor, weapons, or tools
async function cmdEquip({ item, slot = 'hand' }) {
    if (!item) {
        return { success: false, error: 'No item specified' };
    }

    // Find the item in inventory
    const itemToEquip = bot.inventory.items().find(i =>
        i.name.toLowerCase().includes(item.toLowerCase())
    );

    if (!itemToEquip) {
        return { success: false, error: `Item '${item}' not found in inventory` };
    }

    // Map slot names to Mineflayer destinations
    const slotMap = {
        'hand': 'hand',
        'off-hand': 'off-hand',
        'head': 'head',
        'torso': 'torso',
        'legs': 'legs',
        'feet': 'feet'
    };

    const destination = slotMap[slot.toLowerCase()] || 'hand';

    try {
        await bot.equip(itemToEquip, destination);
        mcLog('INFO', 'ITEM_EQUIPPED', { item: itemToEquip.name, slot: destination });
        return {
            success: true,
            equipped: itemToEquip.name,
            slot: destination
        };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Use shield to block attacks
async function cmdShield({ activate = true }) {
    try {
        if (activate) {
            // Check if we have a shield
            const shield = bot.inventory.items().find(i => i.name === 'shield');
            if (!shield) {
                return { success: false, error: 'No shield in inventory' };
            }

            // Equip to off-hand if not already
            const offHand = bot.inventory.slots[45]; // Off-hand slot
            if (!offHand || offHand.name !== 'shield') {
                await bot.equip(shield, 'off-hand');
            }

            // Activate (right-click hold)
            bot.activateItem(true); // Use off-hand
            mcLog('INFO', 'SHIELD_ACTIVATED');
            return { success: true, action: 'shield_up' };
        } else {
            bot.deactivateItem();
            mcLog('INFO', 'SHIELD_DEACTIVATED');
            return { success: true, action: 'shield_down' };
        }
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Sleep in a bed (skip night, set spawn)
async function cmdSleep() {
    try {
        // Check if it's night
        const time = bot.time.timeOfDay;
        const isNight = time >= 12542 && time <= 23460;

        if (!isNight) {
            return { success: false, error: 'Can only sleep at night' };
        }

        // Find nearby bed
        const bedBlock = bot.findBlock({
            matching: block => block.name.includes('bed'),
            maxDistance: 6
        });

        if (!bedBlock) {
            return { success: false, error: 'No bed found nearby (within 6 blocks)' };
        }

        // Try to sleep
        await bot.sleep(bedBlock);
        mcLog('INFO', 'SLEEPING', { bed_pos: bedBlock.position });
        return {
            success: true,
            action: 'sleeping',
            bed_position: {
                x: bedBlock.position.x,
                y: bedBlock.position.y,
                z: bedBlock.position.z
            }
        };
    } catch (err) {
        // Common errors: "already sleeping", "too far", "monsters nearby"
        return { success: false, error: err.message };
    }
}

// Wake up from bed
async function cmdWake() {
    try {
        await bot.wake();
        mcLog('INFO', 'WOKE_UP');
        return { success: true, action: 'woke_up' };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// === PHASE 2: RESOURCE MANAGEMENT COMMANDS ===

// Smelt item in furnace
async function cmdSmelt({ input, fuel = 'coal', count = 1 }) {
    if (!input) {
        return { success: false, error: 'No input item specified' };
    }

    try {
        // Find nearby furnace
        const furnaceBlock = bot.findBlock({
            matching: block => block.name === 'furnace' || block.name === 'lit_furnace',
            maxDistance: 4
        });

        if (!furnaceBlock) {
            return { success: false, error: 'No furnace found nearby (within 4 blocks)' };
        }

        // Open furnace
        const furnace = await bot.openFurnace(furnaceBlock);

        // Find input item in inventory
        const inputItem = bot.inventory.items().find(i =>
            i.name.toLowerCase().includes(input.toLowerCase())
        );
        if (!inputItem) {
            await furnace.close();
            return { success: false, error: `No ${input} in inventory` };
        }

        // Find fuel in inventory
        const fuelItem = bot.inventory.items().find(i =>
            i.name.toLowerCase().includes(fuel.toLowerCase())
        );
        if (!fuelItem) {
            await furnace.close();
            return { success: false, error: `No ${fuel} fuel in inventory` };
        }

        // Put items in furnace
        await furnace.putInput(inputItem.type, null, Math.min(count, inputItem.count));
        await furnace.putFuel(fuelItem.type, null, 1);

        mcLog('INFO', 'SMELTING', { input: inputItem.name, fuel: fuelItem.name });

        // Wait for smelting (10 seconds per item, simplified)
        await new Promise(resolve => setTimeout(resolve, 10000 * count));

        // Take output
        const output = furnace.outputItem();
        if (output) {
            await furnace.takeOutput();
        }

        await furnace.close();

        return {
            success: true,
            action: 'smelted',
            input: inputItem.name,
            output: output ? output.name : 'unknown'
        };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Store items in chest
async function cmdStore({ item, count = null }) {
    try {
        // Find nearby chest
        const chestBlock = bot.findBlock({
            matching: block => block.name === 'chest' || block.name === 'trapped_chest',
            maxDistance: 4
        });

        if (!chestBlock) {
            return { success: false, error: 'No chest found nearby (within 4 blocks)' };
        }

        // Open chest
        const chest = await bot.openContainer(chestBlock);

        // Find item(s) to store
        const itemsToStore = bot.inventory.items().filter(i =>
            !item || i.name.toLowerCase().includes(item.toLowerCase())
        );

        if (itemsToStore.length === 0) {
            await chest.close();
            return { success: false, error: item ? `No ${item} in inventory` : 'Inventory empty' };
        }

        let stored = [];
        for (const invItem of itemsToStore) {
            const storeCount = count ? Math.min(count, invItem.count) : invItem.count;
            try {
                await chest.deposit(invItem.type, null, storeCount);
                stored.push({ name: invItem.name, count: storeCount });
            } catch (e) {
                // Chest might be full
                break;
            }
        }

        await chest.close();

        mcLog('INFO', 'STORED_ITEMS', { items: stored });
        return { success: true, action: 'stored', items: stored };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Take items from chest
async function cmdTake({ item, count = null }) {
    try {
        // Find nearby chest
        const chestBlock = bot.findBlock({
            matching: block => block.name === 'chest' || block.name === 'trapped_chest',
            maxDistance: 4
        });

        if (!chestBlock) {
            return { success: false, error: 'No chest found nearby (within 4 blocks)' };
        }

        // Open chest
        const chest = await bot.openContainer(chestBlock);

        // Find item(s) to take
        const chestItems = chest.containerItems().filter(i =>
            !item || i.name.toLowerCase().includes(item.toLowerCase())
        );

        if (chestItems.length === 0) {
            await chest.close();
            return { success: false, error: item ? `No ${item} in chest` : 'Chest empty' };
        }

        let taken = [];
        for (const chestItem of chestItems) {
            const takeCount = count ? Math.min(count, chestItem.count) : chestItem.count;
            try {
                await chest.withdraw(chestItem.type, null, takeCount);
                taken.push({ name: chestItem.name, count: takeCount });
            } catch (e) {
                // Inventory might be full
                break;
            }
        }

        await chest.close();

        mcLog('INFO', 'TOOK_ITEMS', { items: taken });
        return { success: true, action: 'took', items: taken };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Place a block
async function cmdPlace({ block, x, y, z }) {
    try {
        // Find the block in inventory
        const blockItem = bot.inventory.items().find(i =>
            i.name.toLowerCase().includes(block.toLowerCase())
        );

        if (!blockItem) {
            return { success: false, error: `No ${block} in inventory` };
        }

        // Equip the block
        await bot.equip(blockItem, 'hand');

        // If coordinates given, navigate there first
        if (x !== undefined && y !== undefined && z !== undefined) {
            const targetPos = { x: parseInt(x), y: parseInt(y), z: parseInt(z) };

            // Find reference block to place against
            const referenceBlock = bot.blockAt(new mcData.Vec3(targetPos.x, targetPos.y - 1, targetPos.z));
            if (!referenceBlock || referenceBlock.name === 'air') {
                return { success: false, error: 'No solid block to place against' };
            }

            await bot.placeBlock(referenceBlock, new mcData.Vec3(0, 1, 0));
        } else {
            // Place in front of bot
            const direction = bot.entity.yaw;
            const dx = -Math.sin(direction);
            const dz = Math.cos(direction);
            const targetX = Math.floor(bot.entity.position.x + dx);
            const targetZ = Math.floor(bot.entity.position.z + dz);
            const targetY = Math.floor(bot.entity.position.y);

            const referenceBlock = bot.blockAt(new mcData.Vec3(targetX, targetY - 1, targetZ));
            if (referenceBlock && referenceBlock.name !== 'air') {
                await bot.placeBlock(referenceBlock, new mcData.Vec3(0, 1, 0));
            } else {
                return { success: false, error: 'No suitable place to put block' };
            }
        }

        mcLog('INFO', 'PLACED_BLOCK', { block: blockItem.name });
        return { success: true, action: 'placed', block: blockItem.name };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// === PHASE 3: FARMING & SUSTAINABILITY COMMANDS ===

// Farm: Till soil and plant seeds in area
async function cmdFarm({ crop = 'wheat', radius = 3 }) {
    try {
        const pos = bot.entity.position;
        let tilled = 0;
        let planted = 0;

        // Get seeds based on crop type
        const seedMap = {
            'wheat': 'wheat_seeds',
            'carrots': 'carrot',
            'potatoes': 'potato',
            'beetroot': 'beetroot_seeds'
        };
        const seedName = seedMap[crop.toLowerCase()] || 'wheat_seeds';

        // Find hoe in inventory
        const hoe = bot.inventory.items().find(i => i.name.includes('hoe'));
        if (!hoe) {
            return { success: false, error: 'No hoe in inventory' };
        }

        // Find seeds
        const seeds = bot.inventory.items().find(i => i.name === seedName);
        if (!seeds) {
            return { success: false, error: `No ${seedName} in inventory` };
        }

        // Till and plant in radius
        for (let dx = -radius; dx <= radius; dx++) {
            for (let dz = -radius; dz <= radius; dz++) {
                const blockPos = pos.offset(dx, -1, dz);
                const block = bot.blockAt(blockPos);

                if (block && (block.name === 'dirt' || block.name === 'grass_block')) {
                    // Till the soil
                    await bot.equip(hoe, 'hand');
                    await bot.activateBlock(block);
                    tilled++;

                    // Plant seeds on farmland
                    await bot.equip(seeds, 'hand');
                    const farmland = bot.blockAt(blockPos);
                    if (farmland && farmland.name === 'farmland') {
                        const aboveBlock = bot.blockAt(blockPos.offset(0, 1, 0));
                        if (aboveBlock && aboveBlock.name === 'air') {
                            try {
                                await bot.placeBlock(farmland, new mcData.Vec3(0, 1, 0));
                                planted++;
                            } catch (e) { /* Skip if can't plant */ }
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

// Harvest mature crops
async function cmdHarvest({ radius = 5 }) {
    try {
        const pos = bot.entity.position;
        const matureCrops = ['wheat', 'carrots', 'potatoes', 'beetroots'];
        let harvested = 0;

        // Find mature crops nearby
        for (let dx = -radius; dx <= radius; dx++) {
            for (let dy = -1; dy <= 2; dy++) {
                for (let dz = -radius; dz <= radius; dz++) {
                    const blockPos = pos.offset(dx, dy, dz);
                    const block = bot.blockAt(blockPos);

                    if (block && matureCrops.some(c => block.name.includes(c))) {
                        // Check if crop is mature (age 7 for most crops)
                        const age = block.getProperties ? block.getProperties().age : null;
                        if (age === 7 || age === 3 || !age) { // Different crops have different max ages
                            try {
                                await bot.dig(block);
                                harvested++;
                            } catch (e) { /* Skip if can't harvest */ }
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

// Plant seeds on farmland
async function cmdPlant({ seed = 'wheat_seeds', count = 1 }) {
    try {
        // Find seeds in inventory
        const seeds = bot.inventory.items().find(i =>
            i.name.toLowerCase().includes(seed.toLowerCase())
        );

        if (!seeds) {
            return { success: false, error: `No ${seed} in inventory` };
        }

        await bot.equip(seeds, 'hand');

        // Find nearby farmland
        const farmland = bot.findBlocks({
            matching: block => block.name === 'farmland',
            maxDistance: 4,
            count: count
        });

        if (farmland.length === 0) {
            return { success: false, error: 'No farmland nearby' };
        }

        let planted = 0;
        for (const fPos of farmland) {
            const farmBlock = bot.blockAt(fPos);
            const aboveBlock = bot.blockAt(fPos.offset(0, 1, 0));

            if (farmBlock && aboveBlock && aboveBlock.name === 'air') {
                try {
                    await bot.placeBlock(farmBlock, new mcData.Vec3(0, 1, 0));
                    planted++;
                } catch (e) { /* Skip */ }
            }
        }

        mcLog('INFO', 'PLANTED', { seed: seeds.name, count: planted });
        return { success: true, action: 'planted', seed: seeds.name, count: planted };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Fish with fishing rod
async function cmdFish({ duration = 30 }) {
    try {
        // Find fishing rod
        const rod = bot.inventory.items().find(i => i.name === 'fishing_rod');
        if (!rod) {
            return { success: false, error: 'No fishing rod in inventory' };
        }

        await bot.equip(rod, 'hand');

        // Look at water
        const water = bot.findBlock({
            matching: block => block.name === 'water',
            maxDistance: 6
        });

        if (!water) {
            return { success: false, error: 'No water nearby' };
        }

        await bot.lookAt(water.position);

        // Cast line
        bot.activateItem();
        mcLog('INFO', 'FISHING_STARTED');

        // Wait for fish (simplified - in real Mineflayer would use events)
        let caught = 0;
        const endTime = Date.now() + (duration * 1000);

        while (Date.now() < endTime) {
            await new Promise(resolve => setTimeout(resolve, 5000));
            // Check for bobber movement (simplified)
            if (Math.random() < 0.3) { // 30% chance per check
                bot.activateItem(); // Reel in
                caught++;
                await new Promise(resolve => setTimeout(resolve, 1000));
                bot.activateItem(); // Cast again
            }
        }

        // Reel in at end
        bot.activateItem();

        mcLog('INFO', 'FISHING_COMPLETE', { caught });
        return { success: true, action: 'fished', caught, duration };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// === PHASE 4: LOCATION & BUILDING COMMANDS ===

// Save current location with a name
async function cmdSaveLocation({ name }) {
    if (!name) {
        return { success: false, error: 'Location name required' };
    }

    const pos = bot.entity.position;
    const location = {
        x: Math.floor(pos.x),
        y: Math.floor(pos.y),
        z: Math.floor(pos.z),
        dimension: bot.game.dimension || 'overworld',
        created: new Date().toISOString()
    };

    savedLocations[name.toLowerCase()] = location;
    saveSavedLocations();

    mcLog('INFO', 'LOCATION_SAVED', { name, ...location });
    return {
        success: true,
        action: 'location_saved',
        name: name.toLowerCase(),
        location
    };
}

// Go to a saved location
async function cmdGotoLocation({ name }) {
    if (!name) {
        // Return list of saved locations
        const names = Object.keys(savedLocations);
        return { success: true, action: 'list_locations', locations: names };
    }

    const location = savedLocations[name.toLowerCase()];
    if (!location) {
        return { success: false, error: `No location named "${name}" found. Saved: ${Object.keys(savedLocations).join(', ') || 'none'}` };
    }

    try {
        const { goals, Movements } = require('mineflayer-pathfinder');
        const movements = new Movements(bot, mcData);
        bot.pathfinder.setMovements(movements);

        const goal = new goals.GoalNear(location.x, location.y, location.z, 2);

        mcLog('INFO', 'NAVIGATING_TO_LOCATION', { name, ...location });
        await bot.pathfinder.goto(goal);

        mcLog('INFO', 'ARRIVED_AT_LOCATION', { name });
        return { success: true, action: 'arrived', name: name.toLowerCase(), location };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Copy/scan a build and save as blueprint
async function cmdCopyBuild({ name, radius = 5, height = 10 }) {
    if (!name) {
        return { success: false, error: 'Blueprint name required' };
    }

    try {
        const pos = bot.entity.position;
        const origin = {
            x: Math.floor(pos.x),
            y: Math.floor(pos.y),
            z: Math.floor(pos.z)
        };

        const blocks = [];
        const blockCounts = {};

        // Scan area around player
        for (let dx = -radius; dx <= radius; dx++) {
            for (let dy = 0; dy < height; dy++) {
                for (let dz = -radius; dz <= radius; dz++) {
                    const block = bot.blockAt(new mcData.Vec3(
                        origin.x + dx,
                        origin.y + dy,
                        origin.z + dz
                    ));

                    // Skip air and liquids
                    if (block && block.name !== 'air' &&
                        !block.name.includes('water') &&
                        !block.name.includes('lava')) {
                        blocks.push({
                            dx,
                            dy,
                            dz,
                            blockName: block.name
                        });
                        blockCounts[block.name] = (blockCounts[block.name] || 0) + 1;
                    }
                }
            }
        }

        if (blocks.length === 0) {
            return { success: false, error: 'No blocks found to copy in the area' };
        }

        blueprints[name.toLowerCase()] = {
            blocks,
            origin,
            blockCounts,
            radius,
            height,
            created: new Date().toISOString()
        };
        saveBlueprints();

        mcLog('INFO', 'BLUEPRINT_SAVED', { name, blockCount: blocks.length, blockCounts });
        return {
            success: true,
            action: 'blueprint_saved',
            name: name.toLowerCase(),
            blockCount: blocks.length,
            blockCounts
        };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Build a saved structure
async function cmdBuild({ name, gatherResources = true }) {
    if (!name) {
        // Return list of blueprints
        const names = Object.keys(blueprints);
        return { success: true, action: 'list_blueprints', blueprints: names };
    }

    const blueprint = blueprints[name.toLowerCase()];
    if (!blueprint) {
        return { success: false, error: `No blueprint named "${name}" found. Saved: ${Object.keys(blueprints).join(', ') || 'none'}` };
    }

    try {
        const pos = bot.entity.position;
        const buildOrigin = {
            x: Math.floor(pos.x),
            y: Math.floor(pos.y),
            z: Math.floor(pos.z)
        };

        // Check what resources we need vs have
        const needed = { ...blueprint.blockCounts };
        const have = {};
        const missing = {};

        for (const item of bot.inventory.items()) {
            if (needed[item.name]) {
                have[item.name] = (have[item.name] || 0) + item.count;
            }
        }

        for (const [block, count] of Object.entries(needed)) {
            const haveCount = have[block] || 0;
            if (haveCount < count) {
                missing[block] = count - haveCount;
            }
        }

        // If missing resources and gatherResources is true, collect them
        if (Object.keys(missing).length > 0 && gatherResources) {
            mcLog('INFO', 'BUILD_GATHERING_RESOURCES', { missing });

            for (const [blockName, count] of Object.entries(missing)) {
                // Try to collect missing blocks
                try {
                    const blocks = bot.findBlocks({
                        matching: block => block.name === blockName,
                        maxDistance: 32,
                        count: count
                    });

                    for (const blockPos of blocks) {
                        const block = bot.blockAt(blockPos);
                        if (block) {
                            await bot.dig(block);
                        }
                    }
                } catch (e) {
                    // Continue anyway
                }
            }
        }

        // Build the structure
        let placed = 0;
        let failed = 0;

        // Sort blocks by Y (bottom to top)
        const sortedBlocks = [...blueprint.blocks].sort((a, b) => a.dy - b.dy);

        for (const block of sortedBlocks) {
            const targetPos = new mcData.Vec3(
                buildOrigin.x + block.dx,
                buildOrigin.y + block.dy,
                buildOrigin.z + block.dz
            );

            // Find the block item in inventory
            const blockItem = bot.inventory.items().find(i =>
                i.name === block.blockName || i.name.includes(block.blockName)
            );

            if (!blockItem) {
                failed++;
                continue;
            }

            try {
                await bot.equip(blockItem, 'hand');

                // Find reference block to place against
                const belowPos = targetPos.offset(0, -1, 0);
                const referenceBlock = bot.blockAt(belowPos);

                if (referenceBlock && referenceBlock.name !== 'air') {
                    await bot.placeBlock(referenceBlock, new mcData.Vec3(0, 1, 0));
                    placed++;
                } else {
                    // Try other orientations
                    const directions = [
                        [0, 0, -1], [0, 0, 1], [-1, 0, 0], [1, 0, 0]
                    ];
                    let placedThisBlock = false;
                    for (const [dx, dy, dz] of directions) {
                        const adjPos = targetPos.offset(dx, dy, dz);
                        const adjBlock = bot.blockAt(adjPos);
                        if (adjBlock && adjBlock.name !== 'air') {
                            await bot.placeBlock(adjBlock, new mcData.Vec3(-dx, -dy, -dz));
                            placed++;
                            placedThisBlock = true;
                            break;
                        }
                    }
                    if (!placedThisBlock) failed++;
                }
            } catch (e) {
                failed++;
            }

            // Small delay between placements
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        mcLog('INFO', 'BUILD_COMPLETE', { name, placed, failed, total: blueprint.blocks.length });
        return {
            success: true,
            action: 'built',
            name: name.toLowerCase(),
            placed,
            failed,
            total: blueprint.blocks.length
        };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// List saved locations
async function cmdListLocations() {
    const locations = Object.entries(savedLocations).map(([name, loc]) => ({
        name,
        x: loc.x,
        y: loc.y,
        z: loc.z,
        dimension: loc.dimension
    }));
    return { success: true, locations };
}

// List saved blueprints
async function cmdListBlueprints() {
    const bps = Object.entries(blueprints).map(([name, bp]) => ({
        name,
        blockCount: bp.blocks.length,
        created: bp.created
    }));
    return { success: true, blueprints: bps };
}

// === PHASE 5: CO-OP MODE COMMANDS ===

// Drop items on ground
async function cmdDrop({ item, count = 1 }) {
    try {
        const items = bot.inventory.items();
        const targetItem = items.find(i =>
            i.name.toLowerCase().includes(item?.toLowerCase() || '')
        );

        if (!targetItem) {
            return { success: false, error: `No ${item || 'item'} in inventory` };
        }

        const dropCount = count === 'all' ? targetItem.count : Math.min(parseInt(count), targetItem.count);
        await bot.toss(targetItem.type, null, dropCount);

        mcLog('INFO', 'DROPPED_ITEM', { item: targetItem.name, count: dropCount });
        return { success: true, action: 'dropped', item: targetItem.name, count: dropCount };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Give item to a specific player (drop at their feet)
async function cmdGive({ player, item, count = 1 }) {
    if (!player) {
        return { success: false, error: 'Player name required' };
    }

    try {
        const targetPlayer = bot.players[player];
        if (!targetPlayer || !targetPlayer.entity) {
            return { success: false, error: `Player ${player} not found nearby` };
        }

        const items = bot.inventory.items();
        const targetItem = items.find(i =>
            i.name.toLowerCase().includes(item?.toLowerCase() || '')
        );

        if (!targetItem) {
            return { success: false, error: `No ${item || 'item'} in inventory` };
        }

        // Go near the player first
        const { goals, Movements } = require('mineflayer-pathfinder');
        const movements = new Movements(bot, mcData);
        bot.pathfinder.setMovements(movements);

        const goal = new goals.GoalNear(
            targetPlayer.entity.position.x,
            targetPlayer.entity.position.y,
            targetPlayer.entity.position.z,
            2
        );
        await bot.pathfinder.goto(goal);

        // Drop at their feet
        const dropCount = count === 'all' ? targetItem.count : Math.min(parseInt(count), targetItem.count);
        await bot.toss(targetItem.type, null, dropCount);

        mcLog('INFO', 'GAVE_ITEM', { player, item: targetItem.name, count: dropCount });
        return { success: true, action: 'gave', player, item: targetItem.name, count: dropCount };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Find/locate a block type and optionally go there
async function cmdFind({ block, go = false, radius = 64 }) {
    if (!block) {
        return { success: false, error: 'Block type required' };
    }

    try {
        // Find matching block types
        const blockTypes = [];
        for (const name in mcData.blocksByName) {
            if (name.toLowerCase().includes(block.toLowerCase())) {
                blockTypes.push(mcData.blocksByName[name].id);
            }
        }

        if (blockTypes.length === 0) {
            return { success: false, error: `Unknown block type: ${block}` };
        }

        const found = bot.findBlock({
            matching: blockTypes,
            maxDistance: radius,
            count: 1
        });

        if (!found) {
            return { success: false, error: `No ${block} found within ${radius} blocks` };
        }

        const distance = Math.floor(bot.entity.position.distanceTo(found.position));
        const direction = getDirection(bot.entity.position, found.position);

        mcLog('INFO', 'FOUND_BLOCK', { block: found.name, x: found.position.x, y: found.position.y, z: found.position.z, distance });

        if (go) {
            // Navigate to the block
            const { goals, Movements } = require('mineflayer-pathfinder');
            const movements = new Movements(bot, mcData);
            bot.pathfinder.setMovements(movements);

            const goal = new goals.GoalNear(found.position.x, found.position.y, found.position.z, 2);
            await bot.pathfinder.goto(goal);

            return {
                success: true,
                action: 'found_and_arrived',
                block: found.name,
                position: { x: Math.floor(found.position.x), y: Math.floor(found.position.y), z: Math.floor(found.position.z) }
            };
        }

        return {
            success: true,
            action: 'found',
            block: found.name,
            position: { x: Math.floor(found.position.x), y: Math.floor(found.position.y), z: Math.floor(found.position.z) },
            distance,
            direction
        };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Helper: Get cardinal direction
function getDirection(from, to) {
    const dx = to.x - from.x;
    const dz = to.z - from.z;

    if (Math.abs(dx) > Math.abs(dz)) {
        return dx > 0 ? 'east' : 'west';
    } else {
        return dz > 0 ? 'south' : 'north';
    }
}

// Eat food manually
async function cmdEat({ food = null }) {
    try {
        const items = bot.inventory.items();
        const foodItem = items.find(item => {
            if (food) {
                return item.name.toLowerCase().includes(food.toLowerCase());
            }
            // Default food options
            return item.name.includes('bread') || item.name.includes('apple') ||
                item.name.includes('cooked') || item.name.includes('steak') ||
                item.name.includes('carrot') || item.name.includes('potato') ||
                item.name.includes('porkchop') || item.name.includes('mutton');
        });

        if (!foodItem) {
            return { success: false, error: `No ${food || 'food'} in inventory` };
        }

        await bot.equip(foodItem, 'hand');
        await bot.consume();

        mcLog('INFO', 'ATE_FOOD', { food: foodItem.name });
        return { success: true, action: 'ate', food: foodItem.name };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Share resources - drop half of an item type for teammate
async function cmdShare({ item }) {
    try {
        const items = bot.inventory.items();
        const targetItem = items.find(i =>
            i.name.toLowerCase().includes(item?.toLowerCase() || '')
        );

        if (!targetItem) {
            return { success: false, error: `No ${item || 'item'} in inventory` };
        }

        const shareCount = Math.floor(targetItem.count / 2);
        if (shareCount < 1) {
            return { success: false, error: `Only have ${targetItem.count}, can't share` };
        }

        await bot.toss(targetItem.type, null, shareCount);

        mcLog('INFO', 'SHARED_ITEM', { item: targetItem.name, count: shareCount });
        return { success: true, action: 'shared', item: targetItem.name, count: shareCount, kept: targetItem.count - shareCount };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// Scan for nearby resources to help player
async function cmdScan({ radius = 32 }) {
    try {
        const valuableBlocks = ['diamond_ore', 'iron_ore', 'gold_ore', 'coal_ore', 'emerald_ore',
            'lapis_ore', 'redstone_ore', 'copper_ore', 'ancient_debris',
            'deepslate_diamond_ore', 'deepslate_iron_ore', 'deepslate_gold_ore'];

        const found = {};

        for (const blockName of valuableBlocks) {
            const blockType = mcData.blocksByName[blockName];
            if (!blockType) continue;

            const blocks = bot.findBlocks({
                matching: blockType.id,
                maxDistance: radius,
                count: 10
            });

            if (blocks.length > 0) {
                const closest = blocks[0];
                const block = bot.blockAt(closest);
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

// Co-op mode: Follow player loosely and help with tasks
async function cmdCoopMode({ player, mode = 'on' }) {
    if (mode === 'off') {
        bot.pathfinder.setGoal(null);
        return { success: true, action: 'coop_disabled' };
    }

    if (!player) {
        return { success: false, error: 'Player name required for coop mode' };
    }

    const targetPlayer = bot.players[player];
    if (!targetPlayer || !targetPlayer.entity) {
        return { success: false, error: `Player ${player} not found` };
    }

    // Follow at comfortable distance
    const { goals, Movements } = require('mineflayer-pathfinder');
    const movements = new Movements(bot, mcData);
    bot.pathfinder.setMovements(movements);

    // Dynamic follow goal that keeps 5 block distance
    const goal = new goals.GoalFollow(targetPlayer.entity, 5);
    bot.pathfinder.setGoal(goal, true); // dynamic = true

    mcLog('INFO', 'COOP_MODE_ENABLED', { player, followDistance: 5 });
    return { success: true, action: 'coop_enabled', player, mode: 'following at distance' };
}

// Reflex commands (safe to run during inference)
const reflexCommands = {
    look_around: cmdLookAround,
    maintain_status: cmdMaintainStatus,
    defend: cmdDefend,
    collect_drops: cmdCollectDrops,
    get_nearby: cmdGetNearby,
    get_time: cmdGetTime
};

// Command dispatch
const commands = {
    goto: cmdGoto,
    follow: cmdFollow,
    stop_follow: cmdStopFollow,
    collect: cmdCollect,
    attack: cmdAttack,
    craft: cmdCraft,
    status: cmdStatus,
    chat: cmdChat,
    disconnect: cmdDisconnect,
    // Visual perception
    get_screenshot: cmdGetScreenshot,
    // Predictive chain
    execute_predictive_chain: cmdExecutePredictiveChain,
    stop_predictive_chain: cmdStopPredictiveChain,
    get_reflex_log: cmdGetReflexLog,
    // Protected zones
    protect: cmdProtect,
    list_protected_zones: cmdListProtectedZones,
    // Phase 1: Combat Survival
    equip: cmdEquip,
    shield: cmdShield,
    sleep: cmdSleep,
    wake: cmdWake,
    // Phase 2: Resource Management
    smelt: cmdSmelt,
    store: cmdStore,
    take: cmdTake,
    place: cmdPlace,
    // Phase 3: Farming & Sustainability
    farm: cmdFarm,
    harvest: cmdHarvest,
    plant: cmdPlant,
    fish: cmdFish,
    // Phase 4: Location & Building
    save_location: cmdSaveLocation,
    goto_location: cmdGotoLocation,
    copy_build: cmdCopyBuild,
    build: cmdBuild,
    list_locations: cmdListLocations,
    list_blueprints: cmdListBlueprints,
    // Phase 5: Co-op Mode
    drop: cmdDrop,
    give: cmdGive,
    find: cmdFind,
    eat: cmdEat,
    share: cmdShare,
    scan: cmdScan,
    coop_mode: cmdCoopMode,
    // Reflex commands (can also be called directly)
    look_around: cmdLookAround,
    maintain_status: cmdMaintainStatus,
    defend: cmdDefend,
    collect_drops: cmdCollectDrops,
    get_nearby: cmdGetNearby,
    get_time: cmdGetTime
};

// IPC: Read commands from stdin
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

rl.on('line', async (line) => {
    try {
        const { id, command, params = {} } = JSON.parse(line);

        if (!commands[command]) {
            send(id, false, null, `Unknown command: ${command}`);
            return;
        }

        try {
            const result = await commands[command](params);
            send(id, true, result);
        } catch (err) {
            send(id, false, null, err.message);
        }
    } catch (err) {
        console.error('IPC parse error:', err.message);
    }
});

// Start bot
initBot();

