/**
 * Tests for commands/social.js — chat, status, drop, give, share, scan, coop, disconnect, screenshot.
 */

jest.mock('mineflayer-pathfinder', () => ({
    pathfinder: { name: 'pathfinder' },
    Movements: jest.fn().mockImplementation(() => ({})),
    goals: { GoalNear: jest.fn(), GoalFollow: jest.fn(), GoalBlock: jest.fn(), GoalXZ: jest.fn() }
}));

jest.mock('../visual', () => ({
    closeViewer: jest.fn().mockResolvedValue(),
    isViewerReady: jest.fn().mockReturnValue(false),
    captureScreenshot: jest.fn().mockResolvedValue({ success: true, image: 'base64data' })
}));

const shared = require('../shared');

function createMockBot() {
    return {
        entity: { position: { x: 10, y: 64, z: 20 } },
        health: 18, food: 16,
        chat: jest.fn(),
        quit: jest.fn(),
        toss: jest.fn().mockResolvedValue(),
        inventory: { items: jest.fn().mockReturnValue([]) },
        players: {},
        findBlock: jest.fn(),
        findBlocks: jest.fn().mockReturnValue([]),
        pathfinder: { setGoal: jest.fn(), setMovements: jest.fn(), goto: jest.fn().mockResolvedValue() },
        on: jest.fn(), once: jest.fn()
    };
}

describe('social.js', () => {
    let social;
    let mockBot;

    beforeEach(() => {
        jest.spyOn(console, 'error').mockImplementation();
        jest.spyOn(console, 'log').mockImplementation();
        mockBot = createMockBot();
        shared.setBot(mockBot);
        shared.setMcData({
            blocksByName: {
                diamond_ore: { id: 56 }, iron_ore: { id: 15 }, gold_ore: { id: 14 },
                coal_ore: { id: 16 }, emerald_ore: { id: 129 }, lapis_ore: { id: 21 },
                redstone_ore: { id: 73 }, copper_ore: { id: 100 }, ancient_debris: { id: 200 },
                deepslate_diamond_ore: { id: 201 }, deepslate_iron_ore: { id: 202 }, deepslate_gold_ore: { id: 203 }
            }
        });
        social = require('../commands/social');
    });

    afterEach(() => { jest.restoreAllMocks(); });

    // ─── cmdChat ───
    describe('cmdChat', () => {
        test('sends chat message', async () => {
            const result = await social.cmdChat({ message: 'Hello!' });
            expect(result.sent).toBe('Hello!');
            expect(mockBot.chat).toHaveBeenCalledWith('Hello!');
        });
    });

    // ─── cmdStatus ───
    describe('cmdStatus', () => {
        test('returns bot status', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'sword', count: 1 }]);
            const result = await social.cmdStatus();
            expect(result.health).toBe(18);
            expect(result.food).toBe(16);
            expect(result.position).toBeDefined();
            expect(result.inventory).toHaveLength(1);
        });

        test('caps inventory at 20 items', async () => {
            const items = Array.from({ length: 25 }, (_, i) => ({ name: `item${i}`, count: 1 }));
            mockBot.inventory.items.mockReturnValue(items);
            const result = await social.cmdStatus();
            expect(result.inventory.length).toBe(20);
        });
    });

    // ─── cmdDisconnect ───
    describe('cmdDisconnect', () => {
        test('disconnects bot', async () => {
            const result = await social.cmdDisconnect();
            expect(result.disconnected).toBe(true);
            expect(mockBot.quit).toHaveBeenCalled();
        });
    });

    // ─── cmdGetScreenshot ───
    describe('cmdGetScreenshot', () => {
        test('returns error when viewer not ready', async () => {
            await expect(social.cmdGetScreenshot()).rejects.toThrow('Visual perception not ready');
        });

        test('returns screenshot when ready', async () => {
            const visual = require('../visual');
            visual.isViewerReady.mockReturnValue(true);
            const result = await social.cmdGetScreenshot();
            expect(result.success).toBe(true);
        });
    });

    // ─── cmdDrop ───
    describe('cmdDrop', () => {
        test('returns error when no item', async () => {
            const result = await social.cmdDrop({ item: 'diamond' });
            expect(result.success).toBe(false);
        });

        test('drops items', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'diamond', count: 5, type: 264 }]);
            const result = await social.cmdDrop({ item: 'diamond', count: 3 });
            expect(result.success).toBe(true);
            expect(result.count).toBe(3);
        });

        test('drops all items', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'diamond', count: 10, type: 264 }]);
            const result = await social.cmdDrop({ item: 'diamond', count: 'all' });
            expect(result.success).toBe(true);
            expect(result.count).toBe(10);
        });

        test('handles drop error', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'diamond', count: 5, type: 264 }]);
            mockBot.toss.mockRejectedValue(new Error('toss failed'));
            const result = await social.cmdDrop({ item: 'diamond' });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdGive ───
    describe('cmdGive', () => {
        test('returns error when no player name', async () => {
            const result = await social.cmdGive({});
            expect(result.success).toBe(false);
        });

        test('returns error when player not found', async () => {
            const result = await social.cmdGive({ player: 'ghost', item: 'diamond' });
            expect(result.success).toBe(false);
        });

        test('gives items to player', async () => {
            mockBot.players = { steve: { entity: { position: { x: 5, y: 64, z: 5 } } } };
            mockBot.inventory.items.mockReturnValue([{ name: 'diamond', count: 5, type: 264 }]);

            const result = await social.cmdGive({ player: 'steve', item: 'diamond', count: 2 });
            expect(result.success).toBe(true);
            expect(result.player).toBe('steve');
        });

        test('returns error when item not in inventory', async () => {
            mockBot.players = { steve: { entity: { position: { x: 5, y: 64, z: 5 } } } };
            const result = await social.cmdGive({ player: 'steve', item: 'unobtanium' });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdShare ───
    describe('cmdShare', () => {
        test('returns error when no item', async () => {
            const result = await social.cmdShare({ item: 'diamond' });
            expect(result.success).toBe(false);
        });

        test('shares half of items', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'diamond', count: 10, type: 264 }]);
            const result = await social.cmdShare({ item: 'diamond' });
            expect(result.success).toBe(true);
            expect(result.count).toBe(5);
            expect(result.kept).toBe(5);
        });

        test('returns error when only 1 item', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'diamond', count: 1, type: 264 }]);
            const result = await social.cmdShare({ item: 'diamond' });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdScan ───
    describe('cmdScan', () => {
        test('scans and finds nothing', async () => {
            mockBot.findBlocks.mockReturnValue([]);
            mockBot.entity.position.distanceTo = jest.fn().mockReturnValue(10);

            const result = await social.cmdScan({ radius: 32 });
            expect(result.success).toBe(true);
            expect(Object.keys(result.resources).length).toBe(0);
        });

        test('scans and finds ores', async () => {
            mockBot.findBlocks.mockImplementation(({ matching }) => {
                if (matching === 56) return [{ x: 5, y: 12, z: 5 }];
                return [];
            });
            mockBot.entity.position.distanceTo = jest.fn().mockReturnValue(10);

            const result = await social.cmdScan({ radius: 32 });
            expect(result.success).toBe(true);
        });

        test('handles scan error', async () => {
            mockBot.findBlocks.mockImplementation(() => { throw new Error('scan error'); });
            const result = await social.cmdScan({ radius: 32 });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdCoopMode ───
    describe('cmdCoopMode', () => {
        test('disables coop mode', async () => {
            const result = await social.cmdCoopMode({ player: 'steve', mode: 'off' });
            expect(result.success).toBe(true);
            expect(result.action).toBe('coop_disabled');
        });

        test('returns error when no player', async () => {
            const result = await social.cmdCoopMode({ mode: 'on' });
            expect(result.success).toBe(false);
        });

        test('returns error when player not found', async () => {
            const result = await social.cmdCoopMode({ player: 'ghost', mode: 'on' });
            expect(result.success).toBe(false);
        });

        test('enables coop mode', async () => {
            mockBot.players = { steve: { entity: { position: { x: 5, y: 64, z: 5 } } } };
            const result = await social.cmdCoopMode({ player: 'steve', mode: 'on' });
            expect(result.success).toBe(true);
            expect(result.action).toBe('coop_enabled');
        });
    });

    // ─── cmdGive error branch ───
    describe('cmdGive - error branch', () => {
        test('catches navigation/toss error', async () => {
            mockBot.players = { steve: { entity: { position: { x: 5, y: 64, z: 5 } } } };
            mockBot.inventory.items.mockReturnValue([{ name: 'diamond', count: 5, type: 264 }]);
            mockBot.pathfinder.goto.mockRejectedValue(new Error('path blocked'));

            const result = await social.cmdGive({ player: 'steve', item: 'diamond' });
            expect(result.success).toBe(false);
            expect(result.error).toBe('path blocked');
        });
    });

    // ─── cmdShare error branch ───
    describe('cmdShare - error branch', () => {
        test('catches toss error', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'diamond', count: 10, type: 264 }]);
            mockBot.toss.mockRejectedValue(new Error('toss failed'));

            const result = await social.cmdShare({ item: 'diamond' });
            expect(result.success).toBe(false);
            expect(result.error).toBe('toss failed');
        });
    });

    // ─── cmdScan initial block ───
    describe('cmdScan - initial block', () => {
        test('scans with default radius', async () => {
            mockBot.findBlocks.mockReturnValue([]);
            const result = await social.cmdScan({});
            expect(result.success).toBe(true);
            expect(result.radius).toBeDefined();
        });
    });
});
