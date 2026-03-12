/**
 * Tests for commands/farming.js — farm, harvest, plant, fish.
 */

jest.mock('mineflayer-pathfinder', () => ({
    pathfinder: { name: 'pathfinder' },
    Movements: jest.fn(),
    goals: { GoalNear: jest.fn(), GoalFollow: jest.fn(), GoalBlock: jest.fn(), GoalXZ: jest.fn() }
}));

const shared = require('../shared');

function createMockBot() {
    return {
        entity: { position: { x: 0, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 0, y: 63, z: 0 }), distanceTo: jest.fn() } },
        inventory: { items: jest.fn().mockReturnValue([]) },
        equip: jest.fn().mockResolvedValue(),
        activateBlock: jest.fn().mockResolvedValue(),
        activateItem: jest.fn(),
        placeBlock: jest.fn().mockResolvedValue(),
        dig: jest.fn().mockResolvedValue(),
        lookAt: jest.fn().mockResolvedValue(),
        blockAt: jest.fn(),
        findBlock: jest.fn(),
        findBlocks: jest.fn().mockReturnValue([]),
        pathfinder: { setGoal: jest.fn() },
        on: jest.fn(), once: jest.fn()
    };
}

describe('farming.js', () => {
    let farming;
    let mockBot;
    const Vec3 = jest.fn();

    beforeEach(() => {
        jest.spyOn(console, 'error').mockImplementation();
        jest.spyOn(console, 'log').mockImplementation();
        mockBot = createMockBot();
        shared.setBot(mockBot);
        shared.setMcData({ Vec3 });
        farming = require('../commands/farming');
    });

    afterEach(() => { jest.restoreAllMocks(); });

    // ─── cmdFarm ───
    describe('cmdFarm', () => {
        test('returns error when no hoe', async () => {
            const result = await farming.cmdFarm({ crop: 'wheat' });
            expect(result.success).toBe(false);
            expect(result.error).toContain('hoe');
        });

        test('returns error when no seeds', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'stone_hoe', count: 1 }]);
            const result = await farming.cmdFarm({ crop: 'wheat' });
            expect(result.success).toBe(false);
            expect(result.error).toContain('wheat_seeds');
        });

        test('tills and plants successfully', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'stone_hoe', count: 1 },
                { name: 'wheat_seeds', count: 10 }
            ]);
            const abovePos = { x: 0, y: 64, z: 0 };
            const blockPos = { x: 0, y: 63, z: 0, offset: jest.fn().mockReturnValue(abovePos) };
            mockBot.entity.position = { x: 0, y: 64, z: 0, offset: jest.fn().mockReturnValue(blockPos) };
            mockBot.blockAt
                .mockReturnValueOnce({ name: 'dirt' })       // block at (0, 63, 0)
                .mockReturnValueOnce({ name: 'farmland' })    // after tilling, re-check same pos
                .mockReturnValueOnce({ name: 'air' })         // above block at (0, 64, 0)
                .mockReturnValue(null);

            const result = await farming.cmdFarm({ crop: 'wheat', radius: 0 });
            expect(result.success).toBe(true);
            expect(result.tilled).toBeGreaterThanOrEqual(1);
        });

        test('handles farm error', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'iron_hoe', count: 1 },
                { name: 'wheat_seeds', count: 5 }
            ]);
            mockBot.entity.position = { x: 0, y: 64, z: 0, offset: jest.fn().mockImplementation(() => { throw new Error('no block'); }) };

            const result = await farming.cmdFarm({ crop: 'wheat', radius: 0 });
            expect(result.success).toBe(false);
        });

        test('uses correct seed for carrots', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'stone_hoe', count: 1 },
                { name: 'carrot', count: 5 }
            ]);
            mockBot.blockAt.mockReturnValue(null);

            const result = await farming.cmdFarm({ crop: 'carrots', radius: 0 });
            expect(result.success).toBe(true);
        });
    });

    // ─── cmdHarvest ───
    describe('cmdHarvest', () => {
        test('harvests mature crops', async () => {
            mockBot.entity.position = { x: 0, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 0, y: 64, z: 0 }) };
            mockBot.blockAt
                .mockReturnValueOnce({ name: 'wheat', getProperties: () => ({ age: 7 }) })
                .mockReturnValue(null);

            const result = await farming.cmdHarvest({ radius: 0 });
            expect(result.success).toBe(true);
        });

        test('skips immature crops', async () => {
            mockBot.entity.position = { x: 0, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 0, y: 64, z: 0 }) };
            mockBot.blockAt.mockReturnValue({ name: 'wheat', getProperties: () => ({ age: 3 }) });

            const result = await farming.cmdHarvest({ radius: 0 });
            expect(result.success).toBe(true);
        });

        test('handles harvest error', async () => {
            mockBot.entity.position = { x: 0, y: 64, z: 0, offset: jest.fn().mockImplementation(() => { throw new Error('oops'); }) };
            const result = await farming.cmdHarvest({ radius: 0 });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdPlant ───
    describe('cmdPlant', () => {
        test('returns error when no seeds', async () => {
            const result = await farming.cmdPlant({ seed: 'wheat_seeds' });
            expect(result.success).toBe(false);
        });

        test('returns error when no farmland', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'wheat_seeds', count: 5 }]);
            mockBot.findBlocks.mockReturnValue([]);

            const result = await farming.cmdPlant({ seed: 'wheat_seeds' });
            expect(result.success).toBe(false);
            expect(result.error).toContain('farmland');
        });

        test('plants on farmland', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'wheat_seeds', count: 5 }]);
            const fPos = { x: 1, y: 63, z: 1, offset: jest.fn().mockReturnValue({ x: 1, y: 64, z: 1 }) };
            mockBot.findBlocks.mockReturnValue([fPos]);
            mockBot.blockAt
                .mockReturnValueOnce({ name: 'farmland' })  // farmBlock
                .mockReturnValueOnce({ name: 'air' });       // above

            const result = await farming.cmdPlant({ seed: 'wheat_seeds', count: 1 });
            expect(result.success).toBe(true);
        });
    });

    // ─── cmdFish ───
    describe('cmdFish', () => {
        test('returns error when no rod', async () => {
            const result = await farming.cmdFish({ duration: 1 });
            expect(result.success).toBe(false);
            expect(result.error).toContain('fishing rod');
        });

        test('returns error when no water', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'fishing_rod', count: 1 }]);
            mockBot.findBlock.mockReturnValue(null);

            const result = await farming.cmdFish({ duration: 1 });
            expect(result.success).toBe(false);
            expect(result.error).toContain('water');
        });

        test('fishes successfully', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'fishing_rod', count: 1 }]);
            mockBot.findBlock.mockReturnValue({ position: { x: 3, y: 63, z: 3 } });

            // Use very short duration
            const result = await farming.cmdFish({ duration: 0 });
            expect(result.success).toBe(true);
            expect(result.action).toBe('fished');
        }, 15000);

        test('handles fish outer error', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'fishing_rod', count: 1 }]);
            mockBot.findBlock.mockReturnValue({ position: { x: 3, y: 63, z: 3 } });
            mockBot.equip.mockRejectedValue(new Error('rod broken'));

            const result = await farming.cmdFish({ duration: 0 });
            expect(result.success).toBe(false);
            expect(result.error).toBe('rod broken');
        });
    });

    // ─── cmdPlant error catch ───
    describe('cmdPlant - error branch', () => {
        test('catches error during planting', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'wheat_seeds', count: 5 }]);
            const fPos = { x: 1, y: 63, z: 1, offset: jest.fn().mockReturnValue({ x: 1, y: 64, z: 1 }) };
            mockBot.findBlocks.mockReturnValue([fPos]);
            mockBot.blockAt.mockImplementation(() => { throw new Error('chunk unloaded'); });

            const result = await farming.cmdPlant({ seed: 'wheat_seeds', count: 1 });
            expect(result.success).toBe(false);
            expect(result.error).toBe('chunk unloaded');
        });
    });
});
