/**
 * Tests for commands/movement.js — goto, follow, stop_follow, find, getDirection.
 */

jest.mock('mineflayer-pathfinder', () => ({
    pathfinder: { name: 'pathfinder' },
    Movements: jest.fn().mockImplementation(() => ({})),
    goals: { GoalNear: jest.fn(), GoalFollow: jest.fn(), GoalBlock: jest.fn(), GoalXZ: jest.fn() }
}));

const shared = require('../shared');

function createMockBot() {
    const pos = { x: 0, y: 64, z: 0, distanceTo: jest.fn().mockReturnValue(5), clone: jest.fn().mockReturnThis(), offset: jest.fn().mockReturnThis() };
    return {
        entity: { position: pos, yaw: 0 },
        pathfinder: { setGoal: jest.fn(), setMovements: jest.fn(), goto: jest.fn().mockResolvedValue() },
        players: {},
        findBlock: jest.fn(),
        blockAt: jest.fn().mockReturnValue(null),
        dig: jest.fn().mockResolvedValue(),
        equip: jest.fn().mockResolvedValue(),
        heldItem: null,
        inventory: { items: jest.fn().mockReturnValue([]), slots: {} },
        on: jest.fn(), once: jest.fn(), removeListener: jest.fn(),
        clearControlStates: jest.fn()
    };
}

describe('movement.js', () => {
    let movement;
    let mockBot;

    beforeEach(() => {
        jest.useFakeTimers();
        jest.spyOn(console, 'error').mockImplementation();
        jest.spyOn(console, 'log').mockImplementation();
        mockBot = createMockBot();
        shared.setBot(mockBot);
        shared.setMcData({
            blocksByName: { diamond_ore: { id: 56 }, stone: { id: 1 } }
        });
        movement = require('../commands/movement');
    });

    afterEach(() => { jest.useRealTimers(); jest.restoreAllMocks(); });

    // ─── getDirection ───
    describe('getDirection', () => {
        test('returns east', () => {
            expect(movement.getDirection({ x: 0, z: 0 }, { x: 10, z: 1 })).toBe('east');
        });
        test('returns west', () => {
            expect(movement.getDirection({ x: 0, z: 0 }, { x: -10, z: 1 })).toBe('west');
        });
        test('returns south', () => {
            expect(movement.getDirection({ x: 0, z: 0 }, { x: 1, z: 10 })).toBe('south');
        });
        test('returns north', () => {
            expect(movement.getDirection({ x: 0, z: 0 }, { x: 1, z: -10 })).toBe('north');
        });
    });

    // ─── cmdGoto ───
    describe('cmdGoto', () => {
        test('starts pathfinding and resolves on goal_reached', async () => {
            mockBot.once.mockImplementation((event, cb) => {
                if (event === 'goal_reached') setTimeout(() => cb(), 10);
            });
            const promise = movement.cmdGoto({ x: 10, y: 64, z: 20 });
            jest.advanceTimersByTime(100);
            const result = await promise;
            expect(result.position).toBeDefined();
        });

        test('resolves on path_stop', async () => {
            mockBot.once.mockImplementation((event, cb) => {
                if (event === 'path_stop') setTimeout(() => cb(), 10);
            });
            const promise = movement.cmdGoto({ x: 10, y: 64, z: 20 });
            jest.advanceTimersByTime(100);
            const result = await promise;
            expect(result.stopped || result.position).toBeDefined();
        });

        test('resolves on timeout', async () => {
            const promise = movement.cmdGoto({ x: 10, y: 64, z: 20 });
            jest.advanceTimersByTime(16000);
            const result = await promise;
            expect(result.timeout).toBe(true);
        });
    });

    // ─── cmdFollow ───
    describe('cmdFollow', () => {
        test('follows a visible player', async () => {
            mockBot.players = { steve: { entity: { position: { x: 5, y: 64, z: 5 } } } };
            const result = await movement.cmdFollow({ username: 'steve' });
            expect(result.following).toBe('steve');
            expect(mockBot.pathfinder.setGoal).toHaveBeenCalled();
        });

        test('throws when player not found', async () => {
            await expect(movement.cmdFollow({ username: 'ghost' }))
                .rejects.toThrow('Player ghost not found or not visible');
        });

        test('throws when player has no entity', async () => {
            mockBot.players = { afk: { entity: null } };
            await expect(movement.cmdFollow({ username: 'afk' }))
                .rejects.toThrow();
        });
    });

    // ─── cmdStopFollow ───
    describe('cmdStopFollow', () => {
        test('clears goal', async () => {
            const result = await movement.cmdStopFollow();
            expect(result.stopped).toBe(true);
            expect(mockBot.pathfinder.setGoal).toHaveBeenCalledWith(null);
        });
    });

    // ─── cmdFind ───
    describe('cmdFind', () => {
        test('returns error when no block specified', async () => {
            const result = await movement.cmdFind({ block: null });
            expect(result.success).toBe(false);
        });

        test('returns error for unknown block', async () => {
            const result = await movement.cmdFind({ block: 'unobtanium' });
            expect(result.success).toBe(false);
            expect(result.error).toContain('Unknown block');
        });

        test('returns found block info', async () => {
            mockBot.findBlock.mockReturnValue({
                name: 'diamond_ore',
                position: { x: 10, y: 12, z: 20, distanceTo: jest.fn().mockReturnValue(15) }
            });
            mockBot.entity.position.distanceTo.mockReturnValue(15);

            const result = await movement.cmdFind({ block: 'diamond' });
            expect(result.success).toBe(true);
            expect(result.action).toBe('found');
        });

        test('navigates when go=true', async () => {
            mockBot.findBlock.mockReturnValue({
                name: 'diamond_ore',
                position: { x: 10, y: 12, z: 20, distanceTo: jest.fn().mockReturnValue(15) }
            });
            mockBot.entity.position.distanceTo.mockReturnValue(15);
            // smartGoto: trigger goal_reached to resolve navigation
            mockBot.once.mockImplementation((event, cb) => {
                if (event === 'goal_reached') setTimeout(() => cb(), 10);
            });

            const promise = movement.cmdFind({ block: 'diamond', go: true });
            jest.advanceTimersByTime(100);
            const result = await promise;
            expect(result.success).toBe(true);
            expect(result.action).toBe('found_and_arrived');
        });

        test('returns not found', async () => {
            mockBot.findBlock.mockReturnValue(null);
            const result = await movement.cmdFind({ block: 'diamond' });
            expect(result.success).toBe(false);
            expect(result.error).toContain('No diamond');
        });

        test('handles findBlock error', async () => {
            mockBot.findBlock.mockImplementation(() => { throw new Error('world unloaded'); });
            const result = await movement.cmdFind({ block: 'diamond' });
            expect(result.success).toBe(false);
            expect(result.error).toBe('world unloaded');
        });
    });

    // ─── cmdExplore ───
    describe('cmdExplore', () => {
        test('explores random direction and returns result', async () => {
            // cmdExplore uses smartGoto with 15s timeout
            const promise = movement.cmdExplore({ distance: 20 });
            jest.advanceTimersByTime(16000);
            const result = await promise;
            expect(result).toHaveProperty('success');
            expect(result).toHaveProperty('distance_moved');
            expect(result).toHaveProperty('position');
        });

        test('uses default distance', async () => {
            const promise = movement.cmdExplore();
            jest.advanceTimersByTime(16000);
            const result = await promise;
            expect(result.position).toBeDefined();
        });
    });

    // ─── cmdWander ───
    describe('cmdWander', () => {
        test('wanders with capped distance', async () => {
            const promise = movement.cmdWander({ distance: 50 });
            jest.advanceTimersByTime(16000);
            const result = await promise;
            expect(result).toHaveProperty('success');
            expect(result).toHaveProperty('position');
        });

        test('uses default distance', async () => {
            const promise = movement.cmdWander();
            jest.advanceTimersByTime(16000);
            const result = await promise;
            expect(result.position).toBeDefined();
        });
    });

    // ─── Stuck detection via smartGoto ───
    // These tests use real timers with short thresholds to avoid fake-timer/async issues
    describe('smartGoto stuck detection', () => {
        beforeEach(() => {
            jest.useRealTimers(); // Override fake timers for these tests
        });

        afterEach(() => {
            jest.useFakeTimers(); // Restore for other tests
        });

        test('auto-digs blocks when stuck', async () => {
            mockBot.entity.position.distanceTo.mockReturnValue(0.1);
            mockBot.entity.yaw = 0;
            mockBot.blockAt.mockReturnValue({ name: 'stone', diggable: true, position: { x: 0, y: 64, z: 1 } });
            mockBot.dig.mockResolvedValue();

            // Use very short thresholds so test runs fast
            const { GoalNear } = require('mineflayer-pathfinder').goals;
            const goal = new GoalNear(100, 64, 100, 1);
            const result = await movement.smartGoto(goal, {
                timeout: 4000,
                stuckThresholdMs: 500,
                maxRetries: 1
            });

            // After being stuck for >500ms, it should have tried auto-dig
            expect(mockBot.dig).toHaveBeenCalled();
        }, 10000);

        test('returns stuck after exceeding retries', async () => {
            mockBot.entity.position.distanceTo.mockReturnValue(0.05);

            const { GoalNear } = require('mineflayer-pathfinder').goals;
            const goal = new GoalNear(100, 64, 100, 1);
            const result = await movement.smartGoto(goal, {
                timeout: 3000,
                stuckThresholdMs: 300,
                maxRetries: 1
            });

            expect(result.stuck || result.timeout || result.attempts_exhausted).toBeTruthy();
        }, 10000);

        test('succeeds when goal_reached fires', async () => {
            mockBot.entity.position.distanceTo.mockReturnValue(5.0); // Moving
            mockBot.once.mockImplementation((event, cb) => {
                if (event === 'goal_reached') setTimeout(() => cb(), 50);
            });

            const { GoalNear } = require('mineflayer-pathfinder').goals;
            const goal = new GoalNear(10, 64, 20, 1);
            const result = await movement.smartGoto(goal, {
                timeout: 5000,
                stuckThresholdMs: 2000,
                maxRetries: 1
            });

            expect(result.success).toBe(true);
        }, 10000);
    });
});
