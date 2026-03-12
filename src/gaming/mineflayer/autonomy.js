/**
 * Autonomy Layer — event-driven survival that runs without Python involvement.
 *
 * Handles:
 * - Auto-eat: when food drops below threshold, eat best food from inventory
 * - Death recovery: sprint away from death location on respawn
 *
 * Combat (auto-defend, flee, creeper evasion) is already handled by combat.js.
 * Stuck recovery during pathfinding is already handled by movement.js auto-dig.
 */

const { getBot, mcLog, sendEvent } = require('./shared');

// === Autonomy state ===
let autoEatInterval = null;
let deathPosition = null;

// === Food quality ranking (highest saturation first) ===
const FOOD_QUALITY = [
    'golden_apple', 'enchanted_golden_apple',
    'cooked_beef', 'steak', 'cooked_porkchop',
    'cooked_mutton', 'cooked_salmon',
    'baked_potato', 'cooked_chicken', 'cooked_rabbit',
    'cooked_cod', 'bread', 'pumpkin_pie',
    'apple', 'melon_slice', 'cookie',
    'carrot', 'potato', 'beetroot',
    'beef', 'porkchop', 'chicken', 'mutton', 'rabbit', 'cod', 'salmon'
];

/**
 * Find the best food item in inventory.
 * Returns the inventory item or null.
 */
function findBestFood(bot) {
    const items = bot.inventory.items();
    for (const foodName of FOOD_QUALITY) {
        const item = items.find(i => i.name === foodName);
        if (item) return item;
    }
    // Fallback: any item with 'cooked', 'bread', 'apple', 'stew' in name
    return items.find(i =>
        i.name.includes('cooked') || i.name.includes('bread') ||
        i.name.includes('apple') || i.name.includes('stew')
    ) || null;
}

/**
 * Auto-eat: runs on health event, eats when food drops below threshold.
 * Doesn't interfere with combat — only eats when safe.
 */
let isEating = false;
async function tryAutoEat() {
    const bot = getBot();
    if (!bot || !bot.entity || bot.health <= 0) return;
    if (isEating) return;
    if (bot.food >= 14) return;  // Only eat when food is getting low

    const food = findBestFood(bot);
    if (!food) return;

    isEating = true;
    try {
        await bot.equip(food, 'hand');
        await bot.consume();
        mcLog('INFO', 'AUTO_EAT', { food: food.name, food_level: bot.food });
        sendEvent('auto_ate', { food: food.name });
    } catch (e) {
        mcLog('DEBUG', 'AUTO_EAT_FAILED', { food: food.name, error: e.message });
    } finally {
        isEating = false;
    }
}

/**
 * Setup autonomy event handlers on the bot.
 * Call this once after bot spawns.
 */
function setupAutonomy(bot) {
    // === Auto-eat on health/food change ===
    bot.on('health', () => {
        // Don't eat during active combat (let combat.js manage priority)
        if (bot.food < 14 && bot.health > 4) {
            tryAutoEat().catch(() => { });
        }
    });

    // === Also check periodically (in case health event doesn't fire) ===
    autoEatInterval = setInterval(() => {
        if (!bot.entity || bot.health <= 0) return;
        if (bot.food < 14) {
            tryAutoEat().catch(() => { });
        }
    }, 10000);  // Every 10s

    // === Death recovery: remember death position ===
    bot.on('death', () => {
        deathPosition = bot.entity ? bot.entity.position.clone() : null;
        mcLog('INFO', 'AUTONOMY_DEATH_RECORDED', {
            x: deathPosition?.x, y: deathPosition?.y, z: deathPosition?.z
        });
    });

    // === On respawn: flee death zone with water awareness ===
    bot.on('respawn', () => {
        if (!deathPosition) return;

        // Set a cooldown flag that the Python agent can check
        bot._respawnCooldownUntil = Date.now() + 10000;  // 10s safety window

        // Wait for world to load, then flee death zone
        setTimeout(async () => {
            try {
                const bot = getBot();
                if (!bot || !bot.entity) return;

                const pos = bot.entity.position;
                const dist = pos.distanceTo(deathPosition);

                // If we respawned near death location, run away
                if (dist < 50) {
                    let dx = pos.x - deathPosition.x;
                    let dz = pos.z - deathPosition.z;
                    const mag = Math.sqrt(dx * dx + dz * dz) || 1;

                    // Normalize and extend to 30 blocks
                    let escapeX = pos.x + (dx / mag) * 30;
                    let escapeZ = pos.z + (dz / mag) * 30;

                    // Check if escape direction is water — try perpendicular if so
                    const escapeBlock = bot.blockAt(bot.entity.position.offset(
                        (dx / mag) * 5, 0, (dz / mag) * 5
                    ));
                    if (escapeBlock && escapeBlock.name === 'water') {
                        // Rotate 90 degrees
                        const tmpDx = -dz;
                        dz = dx;
                        dx = tmpDx;
                        escapeX = pos.x + (dx / mag) * 30;
                        escapeZ = pos.z + (dz / mag) * 30;
                        mcLog('INFO', 'AUTONOMY_ESCAPE_WATER_AVOID', {
                            msg: 'Escape direction was water, trying perpendicular'
                        });
                    }

                    bot.setControlState('sprint', true);
                    bot.setControlState('forward', true);

                    mcLog('INFO', 'AUTONOMY_DEATH_ESCAPE', {
                        from: { x: Math.round(pos.x), z: Math.round(pos.z) },
                        toward: { x: Math.round(escapeX), z: Math.round(escapeZ) },
                        death_dist: Math.round(dist)
                    });

                    // Sprint for 5 seconds then stop (longer than before)
                    setTimeout(() => {
                        bot.clearControlStates();
                        mcLog('INFO', 'AUTONOMY_DEATH_ESCAPE_DONE');
                    }, 5000);
                }

                deathPosition = null;
            } catch (e) {
                mcLog('DEBUG', 'AUTONOMY_DEATH_ESCAPE_FAILED', { error: e.message });
            }
        }, 3000);  // 3s delay for world loading
    });

    mcLog('INFO', 'AUTONOMY_SETUP_COMPLETE');
}

/**
 * Cleanup autonomy intervals.
 */
function stopAutonomy() {
    if (autoEatInterval) {
        clearInterval(autoEatInterval);
        autoEatInterval = null;
    }
    isEating = false;
    deathPosition = null;
}

module.exports = { setupAutonomy, stopAutonomy, findBestFood };
