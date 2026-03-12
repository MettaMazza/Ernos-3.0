/**
 * Combat commands — attack, equip, shield, sleep, wake, eat.
 */

const { getBot, getMcData, mcLog, GoalFollow, HOSTILE_NAMES } = require('../shared');
const { equipBestWeapon } = require('./equip_utils');

async function cmdAttack(params) {
    const bot = getBot();
    const { entity_type = 'hostile' } = params;
    let target = null;

    if (entity_type === 'hostile') {
        const hostiles = ['zombie', 'skeleton', 'spider', 'creeper'];
        target = bot.nearestEntity(e =>
            ['mob', 'hostile'].includes(e.type) && hostiles.includes(e.name)
        );
    } else {
        target = bot.nearestEntity(e => e.name === entity_type);
    }

    if (!target) return { attacked: false, reason: 'No target found' };

    const dist = bot.entity.position.distanceTo(target.position);
    if (dist > 3) {
        mcLog('DEBUG', 'ATTACK_NAVIGATING', { target: target.name, distance: dist.toFixed(1) });
        // Look at target while approaching
        await bot.lookAt(target.position.offset(0, (target.height || 1) * 0.8, 0));
        bot.pathfinder.setGoal(new GoalFollow(target, 2));

        await new Promise(resolve => {
            const checkInterval = setInterval(() => {
                const currentDist = bot.entity.position.distanceTo(target.position);
                // Keep looking at target while chasing
                bot.lookAt(target.position.offset(0, (target.height || 1) * 0.8, 0)).catch(() => { });
                if (currentDist <= 3 || !target.isValid) {
                    clearInterval(checkInterval);
                    bot.pathfinder.setGoal(null);
                    resolve();
                }
            }, 200);
            setTimeout(() => { clearInterval(checkInterval); bot.pathfinder.setGoal(null); resolve(); }, 5000);
        });
    }

    const finalDist = bot.entity.position.distanceTo(target.position);
    if (finalDist > 4) {
        mcLog('DEBUG', 'ATTACK_TOO_FAR', { target: target.name, distance: finalDist.toFixed(1) });
        return { attacked: false, reason: 'Could not reach target', distance: finalDist };
    }

    // Auto-equip best weapon before fighting
    await equipBestWeapon();

    // Attack continuously until mob is dead
    let hits = 0;
    const attackStart = Date.now();
    const ATTACK_TIMEOUT = 30000; // 30s safety cap
    const ATTACK_COOLDOWN = 600;  // Minecraft attack cooldown ~0.6s

    while (target.isValid && Date.now() - attackStart < ATTACK_TIMEOUT) {
        const d = bot.entity.position.distanceTo(target.position);
        if (d > 4) {
            // Chase the mob — keep looking at it
            await bot.lookAt(target.position.offset(0, (target.height || 1) * 0.8, 0));
            bot.pathfinder.setGoal(new GoalFollow(target, 2));
            await new Promise(r => setTimeout(r, 300));
            continue;
        }
        bot.pathfinder.setGoal(null);
        try {
            // Look at target before each swing — keeps camera locked on enemy
            await bot.lookAt(target.position.offset(0, (target.height || 1) * 0.8, 0));
            await bot.attack(target);
            hits++;
        } catch (e) {
            // Entity died or became invalid mid-swing
            break;
        }
        await new Promise(r => setTimeout(r, ATTACK_COOLDOWN));
    }
    bot.pathfinder.setGoal(null);

    mcLog('DEBUG', 'ATTACK_COMPLETE', { target: target.name, hits, alive: target.isValid, elapsed_ms: Date.now() - attackStart });
    return { attacked: true, target: target.name, hits, killed: !target.isValid };
}

async function cmdEquip({ item, slot = 'hand' }) {
    const bot = getBot();
    if (!item) return { success: false, error: 'No item specified' };

    const itemToEquip = bot.inventory.items().find(i =>
        i.name.toLowerCase().includes(item.toLowerCase())
    );
    if (!itemToEquip) return { success: false, error: `Item '${item}' not found in inventory` };

    const slotMap = { 'hand': 'hand', 'off-hand': 'off-hand', 'head': 'head', 'torso': 'torso', 'legs': 'legs', 'feet': 'feet' };
    const destination = slotMap[slot.toLowerCase()] || 'hand';

    try {
        await bot.equip(itemToEquip, destination);
        mcLog('INFO', 'ITEM_EQUIPPED', { item: itemToEquip.name, slot: destination });
        return { success: true, equipped: itemToEquip.name, slot: destination };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdShield({ activate = true }) {
    const bot = getBot();
    try {
        if (activate) {
            const shield = bot.inventory.items().find(i => i.name === 'shield');
            if (!shield) return { success: false, error: 'No shield in inventory' };

            const offHand = bot.inventory.slots[45];
            if (!offHand || offHand.name !== 'shield') await bot.equip(shield, 'off-hand');

            bot.activateItem(true);
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

async function cmdSleep() {
    const bot = getBot();
    try {
        const time = bot.time.timeOfDay;
        if (!(time >= 12542 && time <= 23460)) return { success: false, error: 'Can only sleep at night' };

        const bedBlock = bot.findBlock({ matching: block => block.name.includes('bed'), maxDistance: 64 });
        if (!bedBlock) return { success: false, error: 'No bed found nearby (within 64 blocks)' };

        await bot.sleep(bedBlock);
        mcLog('INFO', 'SLEEPING', { bed_pos: bedBlock.position });
        return { success: true, action: 'sleeping', bed_position: { x: bedBlock.position.x, y: bedBlock.position.y, z: bedBlock.position.z } };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdWake() {
    try {
        await getBot().wake();
        mcLog('INFO', 'WOKE_UP');
        return { success: true, action: 'woke_up' };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

async function cmdEat({ food = null }) {
    const bot = getBot();
    try {
        const foodItem = bot.inventory.items().find(item => {
            if (food) return item.name.toLowerCase().includes(food.toLowerCase());
            return item.name.includes('bread') || item.name.includes('apple') ||
                item.name.includes('cooked') || item.name.includes('steak') ||
                item.name.includes('carrot') || item.name.includes('potato') ||
                item.name.includes('porkchop') || item.name.includes('mutton');
        });

        if (!foodItem) return { success: false, error: `No ${food || 'food'} in inventory` };

        await bot.equip(foodItem, 'hand');
        await bot.consume();
        mcLog('INFO', 'ATE_FOOD', { food: foodItem.name });
        return { success: true, action: 'ate', food: foodItem.name };
    } catch (err) {
        return { success: false, error: err.message };
    }
}

module.exports = { cmdAttack, cmdEquip, cmdShield, cmdSleep, cmdWake, cmdEat };
