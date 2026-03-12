/**
 * Movement commands — goto, follow, stop_follow, find, explore, wander.
 * 
 * All navigation uses smartGoto() which has:
 * - Time-based stuck detection (>5s at same coords)
 * - 3-block auto-dig (legs, torso, head) that waits until block is cleared
 * - Backtrack + perpendicular detour rerouting
 * - Up to 3 retry attempts
 */

const { getBot, getMcData, mcLog, GoalNear, GoalFollow, Movements } = require('../shared');
const { equipBestTool } = require('./equip_utils');

// Helper: Get cardinal direction
function getDirection(from, to) {
    const dx = to.x - from.x;
    const dz = to.z - from.z;
    return Math.abs(dx) > Math.abs(dz)
        ? (dx > 0 ? 'east' : 'west')
        : (dz > 0 ? 'south' : 'north');
}

// ─── Auto-dig: clear all 3 blocks in front (legs, torso, head) ───
async function tryAutoDig(bot) {
    const yaw = bot.entity.yaw;
    const dx = -Math.sin(yaw);
    const dz = Math.cos(yaw);

    // 3-block player area: legs (y+0), torso (y+1), head — we also check y-1 for ground obstacles
    const offsets = [
        { dy: 0, label: 'legs' },
        { dy: 1, label: 'torso' },
        { dy: -1, label: 'ground' },
    ];

    let dugAny = false;
    for (const { dy, label } of offsets) {
        const block = bot.blockAt(bot.entity.position.offset(dx, dy, dz));
        if (block && block.name !== 'air' && block.name !== 'water' && block.diggable) {
            mcLog('DEBUG', 'PATHFIND_AUTO_DIG', { block: block.name, level: label });
            try {
                // Keep digging until the block is actually gone (hard blocks need multiple ticks)
                let attempts = 0;
                while (attempts < 10) {
                    const current = bot.blockAt(block.position);
                    if (!current || current.name === 'air') break;
                    await equipBestTool(current.name);
                    await bot.dig(current, true);  // forceLook=true
                    attempts++;
                }
                dugAny = true;
            } catch (e) {
                mcLog('DEBUG', 'PATHFIND_DIG_FAIL', { block: block.name, level: label, error: e.message });
            }
        }
    }
    return dugAny;
}

// ─── smartGoto: Navigation with stuck detection + rerouting ───
async function smartGoto(goal, { timeout = 15000, stuckThresholdMs = 5000, maxRetries = 3 } = {}) {
    const bot = getBot();
    const mcData = getMcData();
    const startPos = bot.entity.position.clone();

    for (let attempt = 0; attempt < maxRetries; attempt++) {
        const movements = new Movements(bot, mcData);
        movements.canDig = true;
        movements.allow1by1towers = false;  // Prefer stairs/caves over towering
        movements.placeCost = 10;           // 10x penalty for scaffolding (digging = 1x)

        // ── WATER AVOIDANCE ──────────────────────────────────────────
        // Heavy penalty on water traversal — prevents drowning deaths.
        // The pathfinder will route AROUND water instead of through it.
        movements.canSwim = false;           // Don't allow swimming paths
        const waterBlock = mcData.blocksByName['water'];
        if (waterBlock) {
            movements.blocksCantBreak.add(waterBlock.id);  // Never try to dig water
        }
        bot.pathfinder.setMovements(movements);

        const result = await new Promise((resolve) => {
            let lastPos = bot.entity.position.clone();
            let lastMoveTime = Date.now();
            let resolved = false;

            const safeResolve = (val) => {
                if (resolved) return;
                resolved = true;
                cleanup();
                resolve(val);
            };

            // Time-based stuck check every 1s
            const stuckCheck = setInterval(async () => {
                if (resolved) return;
                const moved = bot.entity.position.distanceTo(lastPos);
                if (moved < 0.5) {
                    const stuckDuration = Date.now() - lastMoveTime;

                    if (stuckDuration > stuckThresholdMs && stuckDuration <= stuckThresholdMs + 1500) {
                        // First stuck threshold: try auto-dig all 3 blocks
                        mcLog('DEBUG', 'PATHFIND_STUCK_DIGGING', { seconds: Math.floor(stuckDuration / 1000), attempt });
                        await tryAutoDig(bot);
                    }

                    if (stuckDuration > stuckThresholdMs * 2) {
                        // 10s stuck — give up this attempt, will reroute
                        mcLog('WARNING', 'PATHFIND_STUCK_GIVING_UP', { seconds: Math.floor(stuckDuration / 1000), attempt });
                        safeResolve({ stuck: true, attempt });
                    }
                } else {
                    lastPos = bot.entity.position.clone();
                    lastMoveTime = Date.now();
                }
            }, 1000);

            const onGoalReached = () => safeResolve({ success: true });
            const onPathStop = () => safeResolve({ stopped: true, position: bot.entity.position });

            const cleanup = () => {
                clearInterval(stuckCheck);
                clearTimeout(failsafe);
                bot.removeListener('goal_reached', onGoalReached);
                bot.removeListener('path_stop', onPathStop);
                bot.pathfinder.setGoal(null);
                bot.clearControlStates();
            };

            bot.once('goal_reached', onGoalReached);
            bot.once('path_stop', onPathStop);
            bot.pathfinder.setGoal(goal);

            const failsafe = setTimeout(() => {
                safeResolve({ timeout: true });
            }, timeout);
        });

        if (result.success || result.stopped) {
            return { ...result, position: bot.entity.position, attempts: attempt + 1 };
        }

        if (result.stuck && attempt < maxRetries - 1) {
            // REROUTE: Take a perpendicular detour to get around the obstacle
            mcLog('WARNING', 'PATHFIND_STUCK_REROUTE', {
                attempt: attempt + 1,
                pos: `${Math.floor(bot.entity.position.x)},${Math.floor(bot.entity.position.y)},${Math.floor(bot.entity.position.z)}`
            });

            // Calculate perpendicular direction to the goal
            const goalX = goal.x !== undefined ? goal.x : bot.entity.position.x;
            const goalZ = goal.z !== undefined ? goal.z : bot.entity.position.z;
            const angle = Math.atan2(goalZ - bot.entity.position.z, goalX - bot.entity.position.x);
            const perpAngle = angle + (attempt % 2 === 0 ? Math.PI / 2 : -Math.PI / 2);
            const detourDist = 10 + attempt * 5;
            const detourX = Math.floor(bot.entity.position.x + Math.cos(perpAngle) * detourDist);
            const detourZ = Math.floor(bot.entity.position.z + Math.sin(perpAngle) * detourDist);
            const detourGoal = new GoalNear(detourX, bot.entity.position.y, detourZ, 3);

            const detourMovements = new Movements(bot, mcData);
            detourMovements.canDig = true;
            // Only allow towering as absolute last resort
            if (attempt >= maxRetries - 1) {
                detourMovements.allow1by1towers = true;
                detourMovements.placeCost = 3;  // Relaxed cost for last-resort reroute
            } else {
                detourMovements.allow1by1towers = false;
                detourMovements.placeCost = 10;
            }
            bot.pathfinder.setMovements(detourMovements);

            try {
                await Promise.race([
                    bot.pathfinder.goto(detourGoal),
                    new Promise((_, reject) => setTimeout(() => reject(new Error('detour_timeout')), 8000))
                ]);
            } catch (e) {
                mcLog('DEBUG', 'PATHFIND_DETOUR_RESULT', { result: e.message || 'ok' });
            }
            bot.pathfinder.setGoal(null);
            bot.clearControlStates();

            continue;  // Retry original goal from new position
        }

        // Timeout or final stuck
        return { ...result, position: bot.entity.position, attempts: attempt + 1 };
    }

    return { stuck: true, attempts_exhausted: true, position: bot.entity.position, attempts: maxRetries };
}

// ─── cmdGoto: Navigate to coordinates ───
async function cmdGoto(params) {
    const { x, y, z, range = 1 } = params;
    const goal = new GoalNear(x, y, z, range);
    mcLog('DEBUG', 'GOTO_STARTED', { x, y, z });
    return smartGoto(goal, { timeout: 15000 });
}

// ─── cmdFollow: Follow a player ───
async function cmdFollow(params) {
    const bot = getBot();
    const { username, range = 3 } = params;
    const player = bot.players[username];

    if (!player || !player.entity) {
        throw new Error(`Player ${username} not found or not visible`);
    }

    bot.pathfinder.setGoal(new GoalFollow(player.entity, range), true);
    return { following: username };
}

async function cmdStopFollow() {
    getBot().pathfinder.setGoal(null);
    return { stopped: true };
}

// ─── cmdFind: Locate a block, optionally navigate to it ───
async function cmdFind({ block, go = false, radius = 64 }) {
    const bot = getBot();
    const mcData = getMcData();

    if (!block) return { success: false, error: 'Block type required' };

    try {
        const blockTypes = [];
        for (const name in mcData.blocksByName) {
            if (name.toLowerCase().includes(block.toLowerCase())) {
                blockTypes.push(mcData.blocksByName[name].id);
            }
        }

        if (blockTypes.length === 0) return { success: false, error: `Unknown block type: ${block}` };

        const found = bot.findBlock({ matching: blockTypes, maxDistance: radius, count: 1 });
        if (!found) return { success: false, error: `No ${block} found within ${radius} blocks` };

        const distance = Math.floor(bot.entity.position.distanceTo(found.position));
        const direction = getDirection(bot.entity.position, found.position);

        mcLog('INFO', 'FOUND_BLOCK', { block: found.name, x: found.position.x, y: found.position.y, z: found.position.z, distance });

        if (go) {
            const goal = new GoalNear(found.position.x, found.position.y, found.position.z, 2);
            const result = await smartGoto(goal, { timeout: 30000 });
            return {
                success: !result.stuck && !result.timeout,
                action: 'found_and_arrived', block: found.name,
                position: { x: Math.floor(found.position.x), y: Math.floor(found.position.y), z: Math.floor(found.position.z) },
                ...(result.stuck ? { stuck: true } : {}),
                ...(result.timeout ? { nav_timeout: true } : {})
            };
        }

        return {
            success: true, action: 'found', block: found.name,
            position: { x: Math.floor(found.position.x), y: Math.floor(found.position.y), z: Math.floor(found.position.z) },
            distance, direction
        };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

// ─── Explore: walk in a random direction, AVOIDING WATER ───
async function cmdExplore({ distance = 30 } = {}) {
    const bot = getBot();
    const pos = bot.entity.position;

    // Try up to 5 random directions to find a land target
    let x, z, y;
    let foundLand = false;
    for (let i = 0; i < 5; i++) {
        const angle = Math.random() * Math.PI * 2;
        const dist = 10 + Math.random() * (distance - 10);
        x = Math.floor(pos.x + Math.cos(angle) * dist);
        z = Math.floor(pos.z + Math.sin(angle) * dist);
        y = Math.max(Math.floor(pos.y), 64);

        // Check if the target area is water/ocean — reject if so
        const targetBlock = bot.blockAt(bot.entity.position.offset(
            x - pos.x, 0, z - pos.z
        ));
        if (!targetBlock || targetBlock.name !== 'water') {
            foundLand = true;
            break;
        }
        mcLog('DEBUG', 'EXPLORE_WATER_REJECTED', { x, z, attempt: i + 1 });
    }

    // If currently in water, head toward highest nearby ground
    if (bot.entity.isInWater) {
        mcLog('WARNING', 'EXPLORE_IN_WATER', { msg: 'Bot is in water, seeking land' });
        // Find nearest non-water block at surface level
        const landBlock = bot.findBlock({
            matching: b => b.name !== 'water' && b.name !== 'air' && b.name !== 'lava',
            maxDistance: 32,
            useExtraInfo: (block) => block.position.y >= pos.y - 3
        });
        if (landBlock) {
            x = landBlock.position.x;
            y = landBlock.position.y + 1;
            z = landBlock.position.z;
            mcLog('INFO', 'EXPLORE_LAND_FOUND', { x, y, z });
        }
    }

    mcLog('DEBUG', 'EXPLORE_START', { x, y, z, distance: Math.floor(Math.sqrt((x-pos.x)**2 + (z-pos.z)**2)), land_check: foundLand });

    const result = await smartGoto(new GoalNear(x, y, z, 3), { timeout: 15000 });
    const distanceMoved = Math.floor(bot.entity.position.distanceTo(pos));

    return {
        success: !result.stuck && !result.timeout,
        distance_moved: distanceMoved,
        position: {
            x: Math.round(bot.entity.position.x),
            y: Math.round(bot.entity.position.y),
            z: Math.round(bot.entity.position.z)
        },
        stuck: result.stuck || false,
        timeout: result.timeout || false
    };
}

// ─── Wander: short-range explore ───
async function cmdWander({ distance = 15 } = {}) {
    return cmdExplore({ distance: Math.min(distance, 15) });
}

module.exports = { cmdGoto, cmdFollow, cmdStopFollow, cmdFind, cmdExplore, cmdWander, getDirection, smartGoto };
