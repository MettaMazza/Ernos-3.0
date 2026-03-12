# Audit Report: `src/gaming/mineflayer/` (JavaScript Bridge)

## Overview
The `src/gaming/mineflayer/` directory contains the Node.js Minecraft bridge implementation. It acts as the physical embodiment of the Ernos agent within the Minecraft world, leveraging the `mineflayer` and `mineflayer-pathfinder` libraries. It communicates with the Python `MineflayerBridge` via a robust JSON-over-stdin/stdout IPC protocol.

This layer handles low-level execution, safety guarantees (avoiding lava, water, players), combat reflexes, and autonomous survival tasks (like eating and running away from spawn deaths), freeing the Python LLM to focus on high-level reasoning.

---

## File-by-File Analysis

### 1. `bot.js` (Entry Point)
**Functionality:** Initializes the Mineflayer bot connection, wires up essential plugins (`pathfinder`, `pvp`, `auto-eat`), sets up global crash handlers, and maps incoming JSON IPC messages to command functions.
**Key Mechanisms:**
- Routes `stdout` logging via `mcLog()` back to Python.
- Triggers background modules like `setupCombat(bot)` and `setupAutonomy(bot)`.
**Quote:**
```javascript
rl.on('line', async (line) => {
    try {
        const { id, command, params = {} } = JSON.parse(line);
        if (!commands[command]) {
            shared.send(id, false, null, `Unknown command: ${command}`);
            return;
        }
// ...
        const result = await commands[command](params);
        shared.send(id, true, result);
```

### 2. `autonomy.js` (Background Survival)
**Functionality:** Handles survival behaviors that must happen instantaneously, independent of LLM inference latency.
**Key Mechanisms:**
- **Auto-Eat:** Background interval checks if food drops below 14. Equips the highest saturation food using a prioritized `FOOD_QUALITY` list.
- **Death Recovery (Spawn Camp Evasion):** Records death location, and upon respawn, sprints 30 blocks away from it to avoid getting trapped in a death loop.
**Quote:**
```javascript
// If we respawned near death location, run away
if (dist < 50) {
    let dx = pos.x - deathPosition.x;
    let dz = pos.z - deathPosition.z;
    // ... Calculate vector ...
    bot.setControlState('sprint', true);
    bot.setControlState('forward', true);
```

### 3. `combat.js` (Reflexive Fighting)
**Functionality:** A highly proactive 500ms-tick loop managing engagement priorities.
**Key Mechanisms:**
- **Strict Priority Ladder:** 1) Creeper Evasion (<5 blocks) -> 2) Low-Health Flee (Health < 6) -> 3) Persistent Player Aggro -> 4) Proactive Mob Attack.
- **Dynamic Fleeing:** Calculates escape vectors and runs for up to 5 seconds.
- **Ranged Awareness:** Automatically raises shield when facing skeletons/strays.
**Quote:**
```javascript
// PRIORITY 1: CREEPER EVASION — within 5 blocks → RUN
const nearbyCreeper = nearbyHostiles.find(h => h.name === 'creeper' && h.dist < 5);
if (nearbyCreeper) {
    mcLog('WARNING', 'CREEPER_EVASION_PROACTIVE', { distance: nearbyCreeper.dist.toFixed(1) });
    fleeFrom(nearbyCreeper.entity.position, 12);
    return;
}
```

### 4. `reflexes.js` (Precognition & Background Behaviors)
**Functionality:** Contains basic reflex routines (look around, auto-sleep, place torches) but crucially implements the "Predictive Chain" execution layer.
**Key Mechanisms:**
- **`cmdPrecogAction`:** Executes arbitrary game actions (like `explore`, `collect`, `scan`) parsing string arguments while the Python LLM is still typing its thought process.
- **`cmdExecutePredictiveChain`:** Sequentially runs actions, aborting cleanly if interrupted by the final authoritative action.
**Quote:**
```javascript
// Check if chain still running (abort early if LLM finished thinking)
if (!chainState.isRunning) return { precog: false, reason: 'chain_stopped' };
// ...
// Fallback: route to ANY registered command handler (same as inference)
const cmdHandler = getCommand(cmd);
```

### 5. `shared.js` & `visual.js` & `persistence.js`
- **`shared.js`:** State singleton. Extends `mineflayer-pathfinder`'s `Movements` class to apply heavy costs to water traversal (`liquidCost = 100`) and digging solid blocks (`digCost = 15`), ensuring realistic human-like pathing.
- **`visual.js`:** Uses `prismarine-viewer` backed by a headless Puppeteer Chrome instance to capture screenshots. Contains a robust 3-strike auto-restart recovery mechanism if rendering fails.
- **`persistence.js`:** Disk storage for protected zones, saved locations, and blueprints.

### 6. Command Modules (`commands/` directory)
**Functionality:** Discrete groupings of exposed actions.
- **`movement.js`:** Houses `smartGoto`, wrapped with 5-second interval stuck detection (triggers auto-digging of facing blocks) and a retry loop that executes perpendicular detours. Absolutely prohibits water swimming.
- **`resources.js`:** `cmdCollect`, `cmdCraft`, `cmdStore`. Utilizes `lib/skills.js` but adds crucial safety checks: `NEVER_COLLECT` (prevents destroying beds/logic gates), protected zones, and radius exclusion if other players are nearby.
- **`social.js`:** Exposes `cmdFullState` which bundles health, inventory, position, and nearby entities into one ultra-fast payload, eliminating IPC chatter.
- **`building.js`:** Includes logic for `copy_build` (saving solid blocks in a bounding box to a blueprint) and `build` (sequentially laying out blocks grouped by Y-level).

### 7. Core Libraries (`lib/` directory)
- **`mcdata.js` / `world.js`:** Utilities for resolving aliases to literal internal IDs and querying geometry via bounding boxes.
- **`skills.js`:** A massive 2,100+ line repository of complex, chained action promises (adapted heavily from the Voyager/Mindcraft framework) capable of intricate sequential logic (e.g., `tillAndSow`, `clearNearestFurnace`).

---

## Technical Debt & Observations
1.  **Water Phobia:** The `liquidCost=100` and `canSwim=false` prevent drowning deaths successfully but render the bot entirely incapable of oceanic exploration or swimming across rivers.
2.  **Visual.js Dependency Footprint:** Running Puppeteer inside the bot adds massive overhead and fragility (requires Chrome installation and X11/headless libs), though the auto-recovery attempts to mitigate crashes.
3.  **Third-Party Code:** The `mindcraft_ref/` folder exists as a standalone open-source clone. `lib/skills.js` has been directly ingested from it.
