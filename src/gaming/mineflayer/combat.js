/**
 * Combat AI System — proactive attack, source-targeted retaliation,
 * persistent aggro, creeper evasion, low-health flee.
 * 
 * Priority chain: Creeper Evasion > Low-Health Flee > Aggro Player > Retaliate Source > Proactive Attack
 */

const { getBot, mcLog, sendEvent, GoalXZ, GoalFollow, HOSTILE_NAMES } = require('./shared');
const { equipBestWeapon } = require('./commands/equip_utils');

// === Combat state ===
const aggroPlayers = new Set();   // Players who attacked Ernos (cleared on "sorry")
let lastAutoAttackTime = 0;
let lastDamageSource = null;      // Entity that last hit us
let isFleeingCombat = false;
let combatInterval = null;

const RANGED_MOBS = ['skeleton', 'stray', 'pillager', 'blaze', 'ghast', 'wither_skeleton'];

// === Public accessors ===
function getAggroPlayers() { return aggroPlayers; }
function getLastAutoAttackTime() { return lastAutoAttackTime; }
function setLastAutoAttackTime(t) { lastAutoAttackTime = t; }

// === Helper: Sprint away from a position (dynamic flee) ===
function fleeFrom(dangerPos, distance = 10) {
    const bot = getBot();
    if (!bot || isFleeingCombat) return;
    isFleeingCombat = true;

    const botPos = bot.entity.position;
    const dx = botPos.x - dangerPos.x;
    const dz = botPos.z - dangerPos.z;
    const mag = Math.sqrt(dx * dx + dz * dz) || 1;

    const fleeX = botPos.x + (dx / mag) * distance;
    const fleeZ = botPos.z + (dz / mag) * distance;

    bot.pathfinder.setGoal(new GoalXZ(fleeX, fleeZ));
    bot.setControlState('sprint', true);

    // Dynamic flee: recheck every 500ms, up to 5s max
    let elapsed = 0;
    const MAX_FLEE_MS = 5000;
    const CHECK_INTERVAL = 500;

    const fleeCheck = setInterval(() => {
        elapsed += CHECK_INTERVAL;

        // Stop fleeing if: safe distance reached, max time, or dead
        const currentDist = bot.entity.position.distanceTo(dangerPos);
        const isSafe = currentDist >= distance;
        const isMaxTime = elapsed >= MAX_FLEE_MS;
        const isDead = bot.health <= 0;

        if (isSafe || isMaxTime || isDead) {
            clearInterval(fleeCheck);
            bot.pathfinder.setGoal(null);
            bot.setControlState('sprint', false);
            bot.clearControlStates();
            isFleeingCombat = false;
            mcLog('DEBUG', 'FLEE_ENDED', {
                reason: isDead ? 'dead' : isSafe ? 'safe_distance' : 'max_time',
                elapsed, distance: currentDist.toFixed(1)
            });
        }
    }, CHECK_INTERVAL);

    // Hard safety fallback
    setTimeout(() => {
        clearInterval(fleeCheck);
        if (isFleeingCombat) {
            bot.pathfinder.setGoal(null);
            bot.setControlState('sprint', false);
            bot.clearControlStates();
            isFleeingCombat = false;
        }
    }, MAX_FLEE_MS + 500);
}

// === Setup: wire all combat event handlers and intervals ===
function setupCombat(bot) {
    let previousHealth = 20;

    // ─── DAMAGE DETECTION + SOURCE-TARGETED RETALIATION ───
    bot.on('health', () => {
        mcLog('DEBUG', 'HEALTH_UPDATE', { health: bot.health, food: bot.food });
        sendEvent('health', { health: bot.health, food: bot.food });

        if (bot.health < previousHealth && bot.health > 0) {
            const damageTaken = previousHealth - bot.health;
            mcLog('WARNING', 'DAMAGE_DETECTED', { damage: damageTaken.toFixed(1), health: bot.health.toFixed(1) });

            // LOW HEALTH — flee instead of fight
            if (bot.health < 6 || bot.food < 4) {
                const threat = bot.nearestEntity(e => {
                    if (!e || !e.position) return false;
                    return bot.entity.position.distanceTo(e.position) < 10 &&
                        ['mob', 'hostile'].includes(e.type);
                });
                if (threat) {
                    mcLog('WARNING', 'LOW_HEALTH_FLEE', { health: bot.health.toFixed(1), food: bot.food, threat: threat.name });
                    fleeFrom(threat.position, 15);
                    previousHealth = bot.health;
                    return;
                }
            }

            // TARGET THE SOURCE — prefer tracked source, fallback to nearest
            let target = null;
            if (lastDamageSource && lastDamageSource.isValid !== false && lastDamageSource.position) {
                const srcDist = bot.entity.position.distanceTo(lastDamageSource.position);
                if (srcDist < 6) target = lastDamageSource;
            }

            if (!target) {
                target = bot.nearestEntity(e => {
                    if (!e || !e.position) return false;
                    const d = bot.entity.position.distanceTo(e.position);
                    if (d > 6) return false;
                    if (['mob', 'hostile'].includes(e.type) && HOSTILE_NAMES.includes(e.name)) return true;
                    if (e.type === 'player' && e.username && aggroPlayers.has(e.username)) return true;
                    return false;
                });
            }

            if (target) {
                // CREEPER — don't attack, flee
                if (target.name === 'creeper') {
                    mcLog('WARNING', 'CREEPER_EVASION', { distance: bot.entity.position.distanceTo(target.position).toFixed(1) });
                    fleeFrom(target.position, 12);
                    previousHealth = bot.health;
                    return;
                }

                const now = Date.now();
                if (now - lastAutoAttackTime >= 400) {
                    lastAutoAttackTime = now;
                    mcLog('INFO', 'DAMAGE_RETALIATE_START', { target: target.name || target.username, source: lastDamageSource ? 'tracked' : 'nearest' });
                    equipBestWeapon().then(() =>
                        bot.lookAt(target.position.offset(0, (target.height || 1) * 0.8, 0))
                    )
                        .then(() => bot.attack(target))
                        .then(() => mcLog('INFO', 'DAMAGE_RETALIATE_HIT', { target: target.name || target.username }))
                        .catch(e => mcLog('DEBUG', 'DAMAGE_RETALIATE_FAILED', { error: e.message }));
                }
            }
        }
        previousHealth = bot.health;
    });

    // ─── DAMAGE SOURCE TRACKING via entityHurt ───
    bot.on('entityHurt', (entity, source) => {
        if (entity !== bot.entity) return;

        // Track source
        if (source && source.position) {
            lastDamageSource = source;
            mcLog('INFO', 'DAMAGE_SOURCE_TRACKED', { source: source.name || source.username || 'unknown', type: source.type });
        } else {
            const probableAttacker = bot.nearestEntity(e => {
                if (!e || !e.position || e === bot.entity) return false;
                const d = bot.entity.position.distanceTo(e.position);
                if (d > 6) return false;
                return ['mob', 'hostile'].includes(e.type) ||
                    (e.type === 'player' && e.username !== bot.username);
            });
            if (probableAttacker) {
                lastDamageSource = probableAttacker;
                mcLog('INFO', 'DAMAGE_SOURCE_INFERRED', { source: probableAttacker.name || probableAttacker.username || 'unknown' });
            }
        }

        // Track player aggro
        const attacker = bot.nearestEntity(e => e.type === 'player' && e.username !== bot.username);
        if (attacker && attacker.username && bot.entity.position.distanceTo(attacker.position) < 5) {
            aggroPlayers.add(attacker.username);
            mcLog('WARNING', 'AGGRO_TRIGGERED', { attacker: attacker.username });
            sendEvent('aggro_triggered', { attacker: attacker.username });
        }
    });

    // ─── PROACTIVE COMBAT INTERVAL ───
    // Runs every 500ms — creeper evasion, flee, aggro chase, proactive attack
    combatInterval = setInterval(() => {
        if (!bot.entity || bot.health <= 0 || isFleeingCombat) return;

        // Collect all nearby hostiles
        const nearbyHostiles = [];
        for (const entity of Object.values(bot.entities)) {
            if (!entity || !entity.position || entity === bot.entity) continue;
            if (!['mob', 'hostile'].includes(entity.type)) continue;
            if (!HOSTILE_NAMES.includes(entity.name)) continue;
            const dist = bot.entity.position.distanceTo(entity.position);
            if (dist < 16) nearbyHostiles.push({ entity, dist, name: entity.name });
        }

        // Collect nearby aggro players
        const nearbyAggroPlayers = [];
        if (aggroPlayers.size > 0) {
            for (const entity of Object.values(bot.entities)) {
                if (!entity || !entity.position || entity === bot.entity) continue;
                if (entity.type !== 'player' || !entity.username) continue;
                if (!aggroPlayers.has(entity.username)) continue;
                const dist = bot.entity.position.distanceTo(entity.position);
                if (dist < 32) nearbyAggroPlayers.push({ entity, dist, name: entity.username });
            }
        }

        // PRIORITY 1: CREEPER EVASION — within 5 blocks → RUN
        const nearbyCreeper = nearbyHostiles.find(h => h.name === 'creeper' && h.dist < 5);
        if (nearbyCreeper) {
            mcLog('WARNING', 'CREEPER_EVASION_PROACTIVE', { distance: nearbyCreeper.dist.toFixed(1) });
            fleeFrom(nearbyCreeper.entity.position, 12);
            return;
        }

        // PRIORITY 2: LOW HEALTH — flee from all threats
        if (bot.health < 6 || bot.food < 4) {
            const allThreats = [...nearbyHostiles, ...nearbyAggroPlayers].sort((a, b) => a.dist - b.dist);
            if (allThreats.length > 0 && allThreats[0].dist < 10) {
                mcLog('WARNING', 'LOW_HEALTH_FLEE_PROACTIVE', { health: bot.health.toFixed(1), food: bot.food, threat: allThreats[0].name });
                fleeFrom(allThreats[0].entity.position, 15);
                return;
            }
        }

        // PRIORITY 3: PERSISTENT AGGRO — chase and attack aggro players
        if (nearbyAggroPlayers.length > 0) {
            const target = nearbyAggroPlayers.sort((a, b) => a.dist - b.dist)[0];
            const now = Date.now();

            if (target.dist > 4) {
                // Chase: navigate toward the aggro player
                try {
                    bot.pathfinder.setGoal(new GoalFollow(target.entity, 2));
                    mcLog('INFO', 'AGGRO_CHASE', { target: target.name, distance: target.dist.toFixed(1) });
                } catch (e) { /* pathfinder busy */ }
            }

            if (target.dist < 5 && now - lastAutoAttackTime >= 500) {
                lastAutoAttackTime = now;
                equipBestWeapon().then(() =>
                    bot.lookAt(target.entity.position.offset(0, (target.entity.height || 1) * 0.8, 0))
                )
                    .then(() => bot.attack(target.entity))
                    .then(() => mcLog('INFO', 'AGGRO_ATTACK', { target: target.name, distance: target.dist.toFixed(1) }))
                    .catch(() => { });
            }
            return;  // Aggro takes priority over mob attacks
        }

        // PRIORITY 4: PROACTIVE MOB ATTACK — nearest non-creeper within 8 blocks
        const attackTargets = nearbyHostiles
            .filter(h => h.name !== 'creeper' && h.dist < 8)
            .sort((a, b) => a.dist - b.dist);

        // SHIELD VS RANGED — auto-equip shield and raise between swings
        const nearbyRanged = nearbyHostiles.find(h => RANGED_MOBS.includes(h.name) && h.dist < 16);
        if (nearbyRanged) {
            const shield = bot.inventory.items().find(i => i.name === 'shield');
            if (shield) {
                const offHand = bot.inventory.slots[45];
                if (!offHand || offHand.name !== 'shield') {
                    bot.equip(shield, 'off-hand').catch(() => { });
                }
                // Raise shield between attack swings
                const timeSinceAttack = Date.now() - lastAutoAttackTime;
                if (timeSinceAttack > 100 && timeSinceAttack < 400) {
                    bot.activateItem(true);
                } else {
                    bot.deactivateItem();
                }
            }
        }

        if (attackTargets.length > 0) {
            const target = attackTargets[0];
            const now = Date.now();
            if (now - lastAutoAttackTime >= 500) {
                lastAutoAttackTime = now;
                equipBestWeapon().then(() =>
                    bot.lookAt(target.entity.position.offset(0, (target.entity.height || 1) * 0.8, 0))
                )
                    .then(() => bot.attack(target.entity))
                    .then(() => mcLog('INFO', 'PROACTIVE_ATTACK', { target: target.name, distance: target.dist.toFixed(1) }))
                    .catch(() => { });
            }
        }
    }, 500);
}

// === Cleanup ===
function stopCombat() {
    if (combatInterval) {
        clearInterval(combatInterval);
        combatInterval = null;
    }
}

module.exports = {
    setupCombat, stopCombat,
    aggroPlayers, getAggroPlayers,
    getLastAutoAttackTime, setLastAutoAttackTime,
    fleeFrom, isFleeingCombat: () => isFleeingCombat,
    HOSTILE_NAMES
};
