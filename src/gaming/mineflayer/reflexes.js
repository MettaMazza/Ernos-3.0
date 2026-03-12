/**
 * Reflexes & Predictive Chain — background behaviors during LLM inference.
 * Now supports LLM-directed precognition: arbitrary commands run during thinking.
 */

const { getBot, getMcData, mcLog, HOSTILE_NAMES, GoalNear, Movements, getCommand } = require('./shared');
const { getLastAutoAttackTime, setLastAutoAttackTime } = require('./combat');
const { equipBestWeapon, equipBestArmor } = require('./commands/equip_utils');
const { smartGoto } = require('./commands/movement');
const Vec3 = require('vec3').Vec3;

// === Predictive chain state ===
const chainState = { isRunning: false, reflexLog: [] };

// ─── Reflex: Look around randomly ───
async function cmdLookAround() {
    const bot = getBot();
    const yaw = bot.entity.yaw + (Math.random() - 0.5) * Math.PI;
    const pitch = (Math.random() - 0.5) * 0.5;
    await bot.look(yaw, pitch, false);
    return { looked: true };
}

// ─── Reflex: Eat if hungry ───
async function cmdMaintainStatus() {
    const bot = getBot();
    if (bot.food >= 18) return { action: 'none', reason: 'Not hungry' };

    const food = bot.inventory.items().find(item =>
        item.name.includes('bread') || item.name.includes('apple') ||
        item.name.includes('cooked') || item.name.includes('steak') ||
        item.name.includes('carrot') || item.name.includes('potato')
    );

    if (!food) return { action: 'none', reason: 'No food' };

    try {
        await bot.equip(food, 'hand');
        await bot.consume();
        return { action: 'ate', item: food.name };
    } catch (e) {
        return { action: 'failed', error: e.message };
    }
}

// ─── Reflex: Auto-attack nearby hostiles ───
async function cmdDefend() {
    const bot = getBot();
    const hostile = bot.nearestEntity(e =>
        ['mob', 'hostile'].includes(e.type) && HOSTILE_NAMES.includes(e.name) &&
        bot.entity.position.distanceTo(e.position) < 16
    );

    if (!hostile) return { threat: false };

    const dist = bot.entity.position.distanceTo(hostile.position);

    if (dist < 5) {
        const now = Date.now();
        if (now - getLastAutoAttackTime() >= 500) {
            setLastAutoAttackTime(now);
            try {
                await equipBestWeapon();
                await bot.lookAt(hostile.position.offset(0, hostile.height * 0.8, 0));
                await bot.attack(hostile);
                mcLog('INFO', 'AUTO_ATTACK_HIT', { target: hostile.name, distance: dist.toFixed(1) });
                return { threat: true, attacked: true, entity: hostile.name, distance: dist };
            } catch (e) {
                mcLog('DEBUG', 'AUTO_ATTACK_FAILED', { target: hostile.name, error: e.message });
            }
        }
    }

    await bot.lookAt(hostile.position.offset(0, hostile.height, 0));
    return { threat: true, entity: hostile.name, distance: dist };
}

// ─── Reflex: Collect nearby dropped items ───
async function cmdCollectDrops() {
    const bot = getBot();
    const drop = bot.nearestEntity(e =>
        e.name === 'item' && bot.entity.position.distanceTo(e.position) < 4
    );

    if (!drop) return { collected: false };

    await bot.lookAt(drop.position);
    bot.setControlState('forward', true);
    await new Promise(r => setTimeout(r, 300));
    bot.setControlState('forward', false);
    return { collected: true };
}

// ─── Reflex: Get nearby entities ───
async function cmdGetNearby() {
    const bot = getBot();
    const entities = [];
    const hostileNames = ['zombie', 'skeleton', 'spider', 'creeper'];

    for (const entity of Object.values(bot.entities)) {
        if (!entity || entity === bot.entity) continue;
        const dist = bot.entity.position.distanceTo(entity.position);
        if (dist > 32) continue;

        entities.push({
            name: entity.name || entity.username || 'unknown',
            type: entity.type,
            distance: Math.round(dist),
            hostile: hostileNames.includes(entity.name)
        });
    }

    return {
        entities: entities.slice(0, 10),
        hostiles_nearby: entities.some(e => e.hostile && e.distance < 16)
    };
}

// ─── Reflex: Get time of day ───
async function cmdGetTime() {
    const bot = getBot();
    return {
        time: bot.time.day,
        isDay: bot.time.day < 12000 || bot.time.day > 23000
    };
}

// ─── Reflex: Auto-equip best armor + shield ───
async function cmdAutoGear() {
    const equipped = await equipBestArmor();
    if (equipped > 0) {
        mcLog('INFO', 'AUTO_GEAR_EQUIPPED', { pieces: equipped });
    }
    return { equipped };
}

// ─── Reflex: Auto-sleep at night when safe ───
async function cmdAutoSleep() {
    const bot = getBot();
    const time = bot.time.timeOfDay;

    // Only at night
    if (time < 12542 || time > 23460) return { action: 'none', reason: 'daytime' };
    if (bot.isSleeping) return { action: 'none', reason: 'already_sleeping' };
    // Don't sleep if in danger
    if (bot.health < 10) return { action: 'none', reason: 'low_health' };

    // Find a bed
    const bed = bot.findBlock({ matching: block => block.name.includes('bed'), maxDistance: 64 });
    if (!bed) return { action: 'none', reason: 'no_bed' };

    try {
        // Navigate to the bed
        const navResult = await smartGoto(
            new GoalNear(bed.position.x, bed.position.y, bed.position.z, 2),
            { timeout: 15000, maxRetries: 1 }
        );
        if (navResult.stuck || navResult.timeout) {
            return { action: 'none', reason: 'could_not_reach_bed' };
        }

        await bot.sleep(bed);
        mcLog('INFO', 'AUTO_SLEEP', { bed: `${bed.position.x},${bed.position.y},${bed.position.z}` });
        return { action: 'slept', bed: { x: bed.position.x, y: bed.position.y, z: bed.position.z } };
    } catch (e) {
        mcLog('DEBUG', 'AUTO_SLEEP_FAILED', { error: e.message });
        return { action: 'none', reason: e.message };
    }
}

// ─── Reflex: Place torch in dark areas ───
async function cmdPlaceTorch() {
    const bot = getBot();

    // Check light level at bot's position
    const blockAtFeet = bot.blockAt(bot.entity.position);
    if (!blockAtFeet || blockAtFeet.light >= 7) return { action: 'none', reason: 'bright_enough' };

    // Find torch in inventory
    const torch = bot.inventory.items().find(i => i.name === 'torch');
    if (!torch) return { action: 'none', reason: 'no_torches' };

    // Need a solid surface below to place on
    const below = bot.blockAt(bot.entity.position.offset(0, -1, 0));
    if (!below || below.name === 'air' || below.name === 'water') return { action: 'none', reason: 'no_surface' };

    try {
        await bot.equip(torch, 'hand');
        await bot.placeBlock(below, new Vec3(0, 1, 0));
        mcLog('INFO', 'AUTO_TORCH_PLACED', { pos: `${below.position.x},${below.position.y + 1},${below.position.z}` });
        return { action: 'placed_torch' };
    } catch (e) {
        mcLog('DEBUG', 'AUTO_TORCH_FAILED', { error: e.message });
        return { action: 'none', reason: e.message };
    }
}

// ─── Precognition: Execute arbitrary game actions during inference ───
async function cmdPrecogAction(params) {
    const bot = getBot();
    const mcData = getMcData();
    const actionStr = params.action || '';

    // Check if chain still running (abort early if LLM finished thinking)
    if (!chainState.isRunning) return { precog: false, reason: 'chain_stopped' };

    mcLog('DEBUG', 'PRECOG_ACTION_EXEC', { action: actionStr });

    try {
        // Handle pre-parsed collect commands
        if (params.action === 'collect' && params.block_type) {
            const blockType = params.block_type;
            const count = params.count || 1;
            const blockId = mcData.blocksByName[blockType]?.id;
            if (!blockId) return { precog: true, action: 'collect', error: `Unknown block: ${blockType}` };

            const block = bot.findBlock({ matching: blockId, maxDistance: 32 });
            if (!block) return { precog: true, action: 'collect', found: false };

            const movements = new Movements(bot, mcData);
            bot.pathfinder.setMovements(movements);
            await bot.pathfinder.goto(new GoalNear(block.position.x, block.position.y, block.position.z, 2));

            if (!chainState.isRunning) return { precog: true, action: 'collect', interrupted: true };

            const currentBlock = bot.blockAt(block.position);
            if (currentBlock && currentBlock.type === blockId) {
                await bot.dig(currentBlock);
                mcLog('DEBUG', 'PRECOG_COLLECT_SUCCESS', { block_type: blockType });
                return { precog: true, action: 'collect', collected: true, block_type: blockType };
            }
            return { precog: true, action: 'collect', found: false };
        }

        // Handle explore
        if (actionStr === 'explore') {
            const x = bot.entity.position.x + (Math.random() - 0.5) * 40;
            const z = bot.entity.position.z + (Math.random() - 0.5) * 40;
            const y = bot.entity.position.y;
            const movements = new Movements(bot, mcData);
            bot.pathfinder.setMovements(movements);
            try {
                await bot.pathfinder.goto(new GoalNear(x, y, z, 3));
            } catch (e) { /* navigation failure is fine for precog */ }
            return { precog: true, action: 'explore' };
        }

        // Handle scan
        if (actionStr === 'scan' || (typeof actionStr === 'string' && actionStr.startsWith('scan'))) {
            const radius = params.radius || 16;
            const ores = [];
            const pos = bot.entity.position;
            for (let dx = -radius; dx <= radius; dx += 4) {
                for (let dz = -radius; dz <= radius; dz += 4) {
                    for (let dy = -4; dy <= 4; dy += 2) {
                        if (!chainState.isRunning) return { precog: true, action: 'scan', interrupted: true };
                        const block = bot.blockAt(pos.offset(dx, dy, dz));
                        if (block && block.name.includes('ore')) {
                            ores.push({ name: block.name, x: pos.x + dx, y: pos.y + dy, z: pos.z + dz });
                        }
                    }
                }
            }
            return { precog: true, action: 'scan', ores_found: ores.length };
        }

        // Fallback: route to ANY registered command handler (same as inference)
        const parts = (typeof actionStr === 'string') ? actionStr.split(/\s+/) : [actionStr];
        const cmd = parts[0];
        const cmdHandler = getCommand(cmd);
        if (cmdHandler) {
            // Build params from the action string parts
            const cmdParams = { ...params };
            if (parts.length > 1) cmdParams.args = parts.slice(1);
            // For common patterns, parse into expected param format
            if (cmd === 'collect' && parts[1]) { cmdParams.block_type = parts[1]; cmdParams.count = parseInt(parts[2]) || 1; }
            if (cmd === 'craft' && parts[1]) { cmdParams.item = parts[1]; cmdParams.count = parseInt(parts[2]) || 1; }
            if (cmd === 'goto' && parts.length >= 4) { cmdParams.x = parseFloat(parts[1]); cmdParams.y = parseFloat(parts[2]); cmdParams.z = parseFloat(parts[3]); }
            if (cmd === 'attack') { cmdParams.entity_type = parts[1] || 'hostile'; }
            if (cmd === 'find' && parts[1]) { cmdParams.block_type = parts[1]; if (parts[2]) cmdParams.action = parts[2]; }
            if (cmd === 'smelt' && parts[1]) { cmdParams.item = parts[1]; cmdParams.count = parseInt(parts[2]) || 1; }
            if (cmd === 'place' && parts[1]) { cmdParams.block_type = parts[1]; }

            mcLog('DEBUG', 'PRECOG_DISPATCH', { command: cmd, params: JSON.stringify(cmdParams) });
            const result = await cmdHandler(cmdParams);
            return { precog: true, action: cmd, result };
        }

        mcLog('DEBUG', 'PRECOG_ACTION_UNKNOWN', { action: actionStr });
        return { precog: true, action: actionStr, skipped: true };

    } catch (e) {
        mcLog('DEBUG', 'PRECOG_ACTION_ERROR', { action: actionStr, error: e.message });
        return { precog: true, action: actionStr, error: e.message };
    }
}

// ─── Predictive chain execution ───
const reflexCommands = {
    look_around: cmdLookAround,
    maintain_status: cmdMaintainStatus,
    defend: cmdDefend,
    collect_drops: cmdCollectDrops,
    get_nearby: cmdGetNearby,
    get_time: cmdGetTime,
    precog_action: cmdPrecogAction,
    auto_gear: cmdAutoGear,
    auto_sleep: cmdAutoSleep,
    place_torch: cmdPlaceTorch
};

async function cmdExecutePredictiveChain(params) {
    const { chain = [] } = params;

    chainState.isRunning = false;
    await new Promise(r => setTimeout(r, 100));

    chainState.isRunning = true;
    chainState.reflexLog = [];

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
                    mcLog('DEBUG', 'REFLEX_UNKNOWN_COMMAND', { command: action.command });
                    chainState.reflexLog.push({ action: action.command, status: 'unknown' });
                }
            } catch (e) {
                chainState.reflexLog.push({ action: action.command, status: 'failed', error: e.message });
            }
            await new Promise(r => setTimeout(r, 200));
        }
        chainState.isRunning = false;
    })();

    return { success: true, message: 'Chain started', commands: chain.length };
}

async function cmdStopPredictiveChain() {
    chainState.isRunning = false;
    return { stopped: true, log: chainState.reflexLog };
}

async function cmdGetReflexLog() {
    const log = chainState.reflexLog;
    chainState.reflexLog = [];
    return { log };
}

module.exports = {
    cmdLookAround, cmdMaintainStatus, cmdDefend,
    cmdCollectDrops, cmdGetNearby, cmdGetTime,
    cmdPrecogAction, cmdAutoGear, cmdAutoSleep, cmdPlaceTorch,
    cmdExecutePredictiveChain, cmdStopPredictiveChain, cmdGetReflexLog,
    reflexCommands
};
