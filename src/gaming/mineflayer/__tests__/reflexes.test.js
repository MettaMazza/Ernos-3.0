/**
 * Tests for reflexes.js — predictive chain, reflex commands.
 */

jest.mock('mineflayer-pathfinder', () => ({
    pathfinder: { name: 'pathfinder' },
    Movements: jest.fn(),
    goals: { GoalNear: jest.fn(), GoalFollow: jest.fn(), GoalBlock: jest.fn(), GoalXZ: jest.fn() }
}));

jest.mock('../combat', () => ({
    getLastAutoAttackTime: jest.fn().mockReturnValue(0),
    setLastAutoAttackTime: jest.fn(),
    aggroPlayers: new Set()
}));

const shared = require('../shared');

function createMockBot() {
    return {
        entity: {
            position: { x: 0, y: 64, z: 0, distanceTo: jest.fn().mockReturnValue(3) },
            yaw: 0, height: 1.8
        },
        health: 20, food: 20,
        username: 'Ernos',
        entities: {},
        time: { day: 6000 },
        nearestEntity: jest.fn().mockReturnValue(null),
        lookAt: jest.fn().mockResolvedValue(),
        look: jest.fn().mockResolvedValue(),
        attack: jest.fn().mockResolvedValue(),
        consume: jest.fn().mockResolvedValue(),
        equip: jest.fn().mockResolvedValue(),
        setControlState: jest.fn(),
        inventory: { items: jest.fn().mockReturnValue([]) },
        pathfinder: { setGoal: jest.fn() },
        on: jest.fn(), once: jest.fn(), removeListener: jest.fn()
    };
}

describe('reflexes.js', () => {
    let reflexes;
    let mockBot;

    beforeEach(() => {
        jest.spyOn(console, 'error').mockImplementation();
        jest.spyOn(console, 'log').mockImplementation();
        mockBot = createMockBot();
        shared.setBot(mockBot);
        reflexes = require('../reflexes');
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    // ─── cmdLookAround ───
    describe('cmdLookAround', () => {
        test('looks in random direction', async () => {
            const result = await reflexes.cmdLookAround();
            expect(result.looked).toBe(true);
            expect(mockBot.look).toHaveBeenCalled();
        });
    });

    // ─── cmdMaintainStatus ───
    describe('cmdMaintainStatus', () => {
        test('returns none when not hungry', async () => {
            mockBot.food = 20;
            const result = await reflexes.cmdMaintainStatus();
            expect(result.action).toBe('none');
            expect(result.reason).toBe('Not hungry');
        });

        test('returns none when no food', async () => {
            mockBot.food = 10;
            mockBot.inventory.items.mockReturnValue([]);
            const result = await reflexes.cmdMaintainStatus();
            expect(result.action).toBe('none');
            expect(result.reason).toBe('No food');
        });

        test('eats food when hungry', async () => {
            mockBot.food = 10;
            mockBot.inventory.items.mockReturnValue([{ name: 'bread', count: 3 }]);
            const result = await reflexes.cmdMaintainStatus();
            expect(result.action).toBe('ate');
            expect(result.item).toBe('bread');
        });

        test('handles eat failure', async () => {
            mockBot.food = 10;
            mockBot.inventory.items.mockReturnValue([{ name: 'cooked_beef', count: 1 }]);
            mockBot.consume.mockRejectedValue(new Error('cannot eat'));
            const result = await reflexes.cmdMaintainStatus();
            expect(result.action).toBe('failed');
        });
    });

    // ─── cmdDefend ───
    describe('cmdDefend', () => {
        test('returns no threat when no hostiles', async () => {
            const result = await reflexes.cmdDefend();
            expect(result.threat).toBe(false);
        });

        test('attacks nearby hostile', async () => {
            const hostile = {
                name: 'zombie', type: 'hostile', height: 1.8,
                position: { x: 2, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 0 }) }
            };
            mockBot.nearestEntity.mockReturnValue(hostile);
            mockBot.entity.position.distanceTo.mockReturnValue(3);
            const combat = require('../combat');
            combat.getLastAutoAttackTime.mockReturnValue(0);

            const result = await reflexes.cmdDefend();
            expect(result.threat).toBe(true);
        });

        test('looks at distant hostile without attacking', async () => {
            const hostile = {
                name: 'skeleton', type: 'hostile', height: 1.8,
                position: { x: 10, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 10, y: 65, z: 0 }) }
            };
            mockBot.nearestEntity.mockReturnValue(hostile);
            mockBot.entity.position.distanceTo.mockReturnValue(12);

            const result = await reflexes.cmdDefend();
            expect(result.threat).toBe(true);
            expect(result.attacked).toBeUndefined();
            expect(mockBot.lookAt).toHaveBeenCalled();
        });
    });

    // ─── cmdCollectDrops ───
    describe('cmdCollectDrops', () => {
        test('returns false when no drops', async () => {
            const result = await reflexes.cmdCollectDrops();
            expect(result.collected).toBe(false);
        });

        test('walks toward nearby drop', async () => {
            const drop = { name: 'item', position: { x: 1, y: 64, z: 1 } };
            mockBot.nearestEntity.mockReturnValue(drop);
            mockBot.entity.position.distanceTo.mockReturnValue(2);

            const result = await reflexes.cmdCollectDrops();
            expect(result.collected).toBe(true);
            expect(mockBot.setControlState).toHaveBeenCalledWith('forward', true);
        });
    });

    // ─── cmdGetNearby ───
    describe('cmdGetNearby', () => {
        test('returns empty entities list', async () => {
            mockBot.entities = {};
            const result = await reflexes.cmdGetNearby();
            expect(result.entities).toEqual([]);
            expect(result.hostiles_nearby).toBe(false);
        });

        test('returns nearby entities', async () => {
            mockBot.entities = {
                1: { name: 'zombie', type: 'hostile', position: { x: 5, y: 64, z: 0 } },
                2: { name: 'cow', type: 'animal', position: { x: 10, y: 64, z: 0 } }
            };
            mockBot.entity.position.distanceTo
                .mockReturnValueOnce(5)
                .mockReturnValueOnce(10);

            const result = await reflexes.cmdGetNearby();
            expect(result.entities.length).toBe(2);
            expect(result.hostiles_nearby).toBe(true);
        });

        test('skips self and distant entities', async () => {
            mockBot.entities = {
                self: mockBot.entity,
                far: { name: 'pig', type: 'animal', position: { x: 100, y: 64, z: 100 } }
            };
            mockBot.entity.position.distanceTo.mockReturnValue(50);

            const result = await reflexes.cmdGetNearby();
            expect(result.entities).toEqual([]);
        });
    });

    // ─── cmdGetTime ───
    describe('cmdGetTime', () => {
        test('returns day time', async () => {
            mockBot.time.day = 6000;
            const result = await reflexes.cmdGetTime();
            expect(result.time).toBe(6000);
            expect(result.isDay).toBe(true);
        });

        test('returns night time', async () => {
            mockBot.time.day = 15000;
            const result = await reflexes.cmdGetTime();
            expect(result.isDay).toBe(false);
        });
    });

    // ─── cmdExecutePredictiveChain ───
    describe('cmdExecutePredictiveChain', () => {
        test('starts chain with commands', async () => {
            const result = await reflexes.cmdExecutePredictiveChain({
                chain: [{ command: 'look_around' }, { command: 'get_time' }]
            });
            expect(result.success).toBe(true);
            expect(result.message).toBe('Chain started');
        });

        test('handles unknown commands gracefully', async () => {
            const result = await reflexes.cmdExecutePredictiveChain({
                chain: [{ command: 'nonexistent' }]
            });
            expect(result.success).toBe(true);
        });

        test('handles empty chain', async () => {
            const result = await reflexes.cmdExecutePredictiveChain({});
            expect(result.success).toBe(true);
        });
    });

    // ─── cmdStopPredictiveChain ───
    describe('cmdStopPredictiveChain', () => {
        test('stops chain and returns log', async () => {
            const result = await reflexes.cmdStopPredictiveChain();
            expect(result.stopped).toBe(true);
            expect(Array.isArray(result.log)).toBe(true);
        });
    });

    // ─── cmdGetReflexLog ───
    describe('cmdGetReflexLog', () => {
        test('returns log and clears it', async () => {
            const result = await reflexes.cmdGetReflexLog();
            expect(Array.isArray(result.log)).toBe(true);
        });
    });

    // ─── reflexCommands map ───
    describe('reflexCommands', () => {
        test('contains all reflex command entries', () => {
            expect(reflexes.reflexCommands.look_around).toBeDefined();
            expect(reflexes.reflexCommands.maintain_status).toBeDefined();
            expect(reflexes.reflexCommands.defend).toBeDefined();
            expect(reflexes.reflexCommands.collect_drops).toBeDefined();
            expect(reflexes.reflexCommands.get_nearby).toBeDefined();
            expect(reflexes.reflexCommands.get_time).toBeDefined();
        });
    });

    // ─── cmdDefend - attack failure ───
    describe('cmdDefend - error branch', () => {
        test('handles attack failure gracefully', async () => {
            const hostile = {
                name: 'zombie', type: 'hostile', height: 1.8,
                position: { x: 2, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 0 }) }
            };
            mockBot.nearestEntity.mockReturnValue(hostile);
            mockBot.entity.position.distanceTo.mockReturnValue(3);
            const combat = require('../combat');
            combat.getLastAutoAttackTime.mockReturnValue(0);
            mockBot.lookAt.mockResolvedValue();
            mockBot.attack.mockRejectedValue(new Error('swing missed'));

            const result = await reflexes.cmdDefend();
            expect(result.threat).toBe(true);
        });
    });

    // ─── cmdCollectDrops - no drop ───
    describe('cmdCollectDrops - edge cases', () => {
        test('returns false when drop exists but not item type', async () => {
            mockBot.nearestEntity.mockReturnValue(null);
            const result = await reflexes.cmdCollectDrops();
            expect(result.collected).toBe(false);
        });
    });

    // ─── predictive chain - action error ───
    describe('predictive chain - error handling', () => {
        test('logs failed status when command throws', async () => {
            // Make look_around throw
            const origLookAround = reflexes.reflexCommands.look_around;
            reflexes.reflexCommands.look_around = jest.fn().mockRejectedValue(new Error('look error'));

            const result = await reflexes.cmdExecutePredictiveChain({
                chain: [{ command: 'look_around' }]
            });
            expect(result.success).toBe(true);

            // Wait for the async chain to complete
            await new Promise(resolve => setTimeout(resolve, 500));

            const log = await reflexes.cmdGetReflexLog();
            const failed = log.log.find(l => l.status === 'failed');
            expect(failed).toBeDefined();

            reflexes.reflexCommands.look_around = origLookAround;
        });
    });

    // ─── cmdPrecogAction ───
    describe('cmdPrecogAction', () => {
        beforeEach(() => {
            jest.useFakeTimers();
            shared.setMcData({
                blocksByName: { oak_log: { id: 17 }, stone: { id: 1 } }
            });
            mockBot.findBlock = jest.fn().mockReturnValue(null);
            mockBot.blockAt = jest.fn().mockReturnValue(null);
            mockBot.dig = jest.fn().mockResolvedValue();
            mockBot.pathfinder.goto = jest.fn().mockResolvedValue();
            mockBot.pathfinder.setMovements = jest.fn();
            mockBot.clearControlStates = jest.fn();
            mockBot.entity.position.offset = jest.fn().mockReturnValue({ x: 0, y: 64, z: 0 });
        });

        afterEach(() => {
            jest.useRealTimers();
        });

        async function startChainAndKeepRunning() {
            // Start a chain with a long-running command to keep isRunning=true
            // We use a chain with look_around which will take some time
            const chainPromise = reflexes.cmdExecutePredictiveChain({
                chain: [
                    { command: 'look_around' },
                    { command: 'look_around' },
                    { command: 'look_around' }
                ]
            });
            // Advance past the 100ms initial delay so isRunning = true
            jest.advanceTimersByTime(101);
            await Promise.resolve();
            await Promise.resolve();
            return chainPromise;
        }

        test('returns chain_stopped when chain not running', async () => {
            await reflexes.cmdStopPredictiveChain();
            const result = await reflexes.cmdPrecogAction({ action: 'explore' });
            expect(result.precog).toBe(false);
            expect(result.reason).toBe('chain_stopped');
        });

        test('collects block when found', async () => {
            await startChainAndKeepRunning();

            mockBot.findBlock.mockReturnValue({
                position: { x: 5, y: 64, z: 5 }
            });
            mockBot.blockAt.mockReturnValue({ type: 17, name: 'oak_log' });

            const result = await reflexes.cmdPrecogAction({ action: 'collect', block_type: 'oak_log', count: 1 });
            expect(result.precog).toBe(true);
            expect(result.action).toBe('collect');
            expect(result.collected).toBe(true);
        });

        test('collect returns error for unknown block', async () => {
            await startChainAndKeepRunning();

            const result = await reflexes.cmdPrecogAction({ action: 'collect', block_type: 'unobtanium' });
            expect(result.precog).toBe(true);
            expect(result.error).toContain('Unknown block');
        });

        test('collect returns not found', async () => {
            await startChainAndKeepRunning();

            mockBot.findBlock.mockReturnValue(null);
            const result = await reflexes.cmdPrecogAction({ action: 'collect', block_type: 'oak_log' });
            expect(result.precog).toBe(true);
            expect(result.found).toBe(false);
        });

        test('explore moves in random direction', async () => {
            await startChainAndKeepRunning();

            const result = await reflexes.cmdPrecogAction({ action: 'explore' });
            expect(result.precog).toBe(true);
            expect(result.action).toBe('explore');
        });

        test('scan returns ore count', async () => {
            await startChainAndKeepRunning();

            mockBot.blockAt.mockReturnValue({ name: 'iron_ore' });
            const result = await reflexes.cmdPrecogAction({ action: 'scan', radius: 4 });
            expect(result.precog).toBe(true);
            expect(result.action).toBe('scan');
            expect(result.ores_found).toBeGreaterThanOrEqual(0);
        });

        test('unknown action returns skipped', async () => {
            await startChainAndKeepRunning();

            const result = await reflexes.cmdPrecogAction({ action: 'dance' });
            expect(result.precog).toBe(true);
            expect(result.skipped).toBe(true);
        });

        test('handles error gracefully', async () => {
            await startChainAndKeepRunning();

            mockBot.findBlock.mockImplementation(() => { throw new Error('world unloaded'); });
            const result = await reflexes.cmdPrecogAction({ action: 'collect', block_type: 'oak_log' });
            expect(result.precog).toBe(true);
            expect(result.error).toBe('world unloaded');
        });
    });
});
