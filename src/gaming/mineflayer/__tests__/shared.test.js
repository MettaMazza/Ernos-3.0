/**
 * Tests for shared.js — bot ref, mcData, IPC, logging, constants.
 */

// Mock mineflayer-pathfinder before requiring shared
jest.mock('mineflayer-pathfinder', () => {
    const GoalNear = jest.fn();
    const GoalFollow = jest.fn();
    const GoalBlock = jest.fn();
    const GoalXZ = jest.fn();
    return {
        pathfinder: { name: 'pathfinder' },
        Movements: jest.fn(),
        goals: { GoalNear, GoalFollow, GoalBlock, GoalXZ }
    };
});

const shared = require('../shared');

describe('shared.js', () => {
    beforeEach(() => {
        // Reset bot/mcData state
        shared.setBot(null);
        shared.setMcData(null);
    });

    // ─── Bot ref ───
    describe('bot ref', () => {
        test('getBot returns null initially', () => {
            expect(shared.getBot()).toBeNull();
        });

        test('setBot/getBot roundtrip', () => {
            const fakeBot = { entity: { position: { x: 0 } } };
            shared.setBot(fakeBot);
            expect(shared.getBot()).toBe(fakeBot);
        });
    });

    // ─── mcData ref ───
    describe('mcData ref', () => {
        test('getMcData returns null initially', () => {
            expect(shared.getMcData()).toBeNull();
        });

        test('setMcData/getMcData roundtrip', () => {
            const fakeData = { blocksByName: {} };
            shared.setMcData(fakeData);
            expect(shared.getMcData()).toBe(fakeData);
        });
    });

    // ─── IPC: send ───
    describe('send()', () => {
        test('sends JSON to stdout', () => {
            const spy = jest.spyOn(console, 'log').mockImplementation();
            shared.send('abc', true, { hp: 20 });
            expect(spy).toHaveBeenCalledWith(
                JSON.stringify({ id: 'abc', success: true, data: { hp: 20 }, error: null })
            );
            spy.mockRestore();
        });

        test('sends error response', () => {
            const spy = jest.spyOn(console, 'log').mockImplementation();
            shared.send('xyz', false, null, 'timeout');
            expect(spy).toHaveBeenCalledWith(
                JSON.stringify({ id: 'xyz', success: false, data: null, error: 'timeout' })
            );
            spy.mockRestore();
        });
    });

    // ─── mcLog ───
    describe('mcLog()', () => {
        test('logs structured message to stderr', () => {
            const spy = jest.spyOn(console, 'error').mockImplementation();
            shared.mcLog('INFO', 'TEST_MSG', { key: 'val' });
            const call = spy.mock.calls[0][0];
            expect(call).toContain('[INFO]');
            expect(call).toContain('TEST_MSG');
            expect(call).toContain('key=val');
            spy.mockRestore();
        });

        test('handles empty data', () => {
            const spy = jest.spyOn(console, 'error').mockImplementation();
            shared.mcLog('DEBUG', 'NO_DATA');
            const call = spy.mock.calls[0][0];
            expect(call).toContain('[DEBUG]');
            expect(call).toContain('NO_DATA');
            expect(call).not.toContain(' | ');
            spy.mockRestore();
        });
    });

    // ─── sendEvent ───
    describe('sendEvent()', () => {
        test('sends event JSON to stdout', () => {
            const spy = jest.spyOn(console, 'log').mockImplementation();
            shared.sendEvent('spawn', { x: 10 });
            expect(spy).toHaveBeenCalledWith(
                JSON.stringify({ event: 'spawn', data: { x: 10 } })
            );
            spy.mockRestore();
        });
    });

    // ─── Constants ───
    describe('HOSTILE_NAMES', () => {
        test('contains key hostiles', () => {
            expect(shared.HOSTILE_NAMES).toContain('zombie');
            expect(shared.HOSTILE_NAMES).toContain('skeleton');
            expect(shared.HOSTILE_NAMES).toContain('creeper');
            expect(shared.HOSTILE_NAMES).toContain('enderman');
            expect(shared.HOSTILE_NAMES).toContain('warden');
        });

        test('is an array with 23 entries', () => {
            expect(Array.isArray(shared.HOSTILE_NAMES)).toBe(true);
            expect(shared.HOSTILE_NAMES.length).toBe(23);
        });
    });

    // ─── Exports ───
    describe('exports', () => {
        test('exports pathfinder-related', () => {
            expect(shared.pathfinder).toBeDefined();
            expect(shared.Movements).toBeDefined();
            expect(shared.goals).toBeDefined();
            expect(shared.GoalNear).toBeDefined();
            expect(shared.GoalFollow).toBeDefined();
            expect(shared.GoalBlock).toBeDefined();
            expect(shared.GoalXZ).toBeDefined();
        });
    });
});
