/**
 * Tests for commands/resources.js — collect, craft, smelt, store, take.
 * Tests the delegation to Mindcraft skills + Ernos-specific pre-checks.
 */

jest.mock('mineflayer-pathfinder', () => ({
    pathfinder: { name: 'pathfinder' },
    Movements: jest.fn().mockImplementation(() => ({})),
    goals: { GoalNear: jest.fn(), GoalFollow: jest.fn(), GoalBlock: jest.fn(), GoalXZ: jest.fn() }
}));

jest.mock('fs');
jest.mock('../lib/skills');

const shared = require('../shared');
const skills = require('../lib/skills');

function createMockBot() {
    return {
        entity: { position: { x: 0, y: 64, z: 0, distanceTo: jest.fn().mockReturnValue(5), offset: jest.fn().mockReturnThis() } },
        username: 'Ernos',
        players: {},
        findBlock: jest.fn().mockReturnValue(null),
        findBlocks: jest.fn().mockReturnValue([]),
        blockAt: jest.fn(),
        dig: jest.fn().mockResolvedValue(),
        craft: jest.fn().mockResolvedValue(),
        equip: jest.fn().mockResolvedValue(),
        lookAt: jest.fn().mockResolvedValue(),
        openFurnace: jest.fn(),
        openContainer: jest.fn(),
        recipesFor: jest.fn().mockReturnValue([]),
        inventory: { items: jest.fn().mockReturnValue([]) },
        pathfinder: { setGoal: jest.fn(), setMovements: jest.fn(), goto: jest.fn().mockResolvedValue() },
        on: jest.fn(), once: jest.fn(), removeListener: jest.fn(),
        output: '',
        modes: { pause: jest.fn(), unpause: jest.fn(), isOn: jest.fn().mockReturnValue(false) },
        interrupt_code: false
    };
}

describe('resources.js', () => {
    let resources;
    let mockBot;

    beforeEach(() => {
        jest.spyOn(console, 'error').mockImplementation();
        jest.spyOn(console, 'log').mockImplementation();
        mockBot = createMockBot();
        shared.setBot(mockBot);
        shared.setMcData({
            blocksByName: { oak_log: { id: 17 }, diamond_ore: { id: 56 }, crafting_table: { id: 58 } },
            itemsByName: { planks: { id: 5 }, stick: { id: 280 } }
        });

        // Default skill mocks
        skills.ensureModes.mockImplementation((bot) => {
            if (!bot.modes) bot.modes = { pause: jest.fn(), unpause: jest.fn(), isOn: jest.fn().mockReturnValue(false) };
            if (!bot.output) bot.output = '';
        });
        skills.collectBlock.mockResolvedValue(false);
        skills.craftRecipe.mockResolvedValue(false);
        skills.smeltItem.mockResolvedValue(false);
        skills.putInChest.mockResolvedValue(false);
        skills.takeFromChest.mockResolvedValue(false);
        skills.goToNearestBlock.mockResolvedValue(true);

        resources = require('../commands/resources');
    });

    afterEach(() => { jest.restoreAllMocks(); });

    // ─── cmdCollect ───
    describe('cmdCollect', () => {
        test('returns 0 when collectBlock returns false', async () => {
            // findBlock returns a block at safe pos so protection checks pass
            mockBot.findBlock.mockReturnValue({ position: { x: 100, y: 64, z: 100, distanceTo: jest.fn().mockReturnValue(50) } });
            skills.collectBlock.mockResolvedValue(false);
            const result = await resources.cmdCollect({ block_type: 'oak_log' });
            expect(result.collected).toBe(0);
            expect(result.requested).toBe(1);
        });

        test('returns collected count from Mindcraft output', async () => {
            mockBot.findBlock.mockReturnValue({ position: { x: 100, y: 64, z: 100, distanceTo: jest.fn().mockReturnValue(50) } });
            skills.collectBlock.mockImplementation(async (bot) => {
                bot.output += 'Collected 3 oak_log.\n';
                return true;
            });
            const result = await resources.cmdCollect({ block_type: 'oak_log', count: 5 });
            expect(result.collected).toBe(3);
            expect(result.requested).toBe(5);
        });

        test('resolves item aliases', async () => {
            mockBot.findBlock.mockReturnValue({ position: { x: 100, y: 64, z: 100, distanceTo: jest.fn().mockReturnValue(50) } });
            skills.collectBlock.mockResolvedValue(false);
            await resources.cmdCollect({ block_type: 'wood' });
            // 'wood' should be resolved to 'oak_log' via ITEM_ALIASES
            expect(skills.collectBlock).toHaveBeenCalledWith(
                expect.anything(), 'oak_log', 1
            );
        });

        test('calls ensureModes on bot', async () => {
            await resources.cmdCollect({ block_type: 'oak_log' });
            expect(skills.ensureModes).toHaveBeenCalled();
        });
    });

    // ─── cmdCraft ───
    describe('cmdCraft', () => {
        test('throws when craftRecipe returns false', async () => {
            skills.craftRecipe.mockImplementation(async (bot) => {
                bot.output += 'planks is either not an item, or it does not have a crafting recipe!\n';
                return false;
            });
            await expect(resources.cmdCraft({ item: 'planks' })).rejects.toThrow('Failed to craft');
        });

        test('crafts successfully', async () => {
            skills.craftRecipe.mockImplementation(async (bot) => {
                bot.output += 'Successfully crafted planks\n';
                return true;
            });
            const result = await resources.cmdCraft({ item: 'planks', count: 4 });
            expect(result.crafted).toBe('planks');
            expect(result.count).toBe(4);
        });

        test('resolves item aliases', async () => {
            skills.craftRecipe.mockResolvedValue(true);
            await resources.cmdCraft({ item: 'wood' });
            // 'wood' should be resolved to 'oak_log' via ITEM_ALIASES
            expect(skills.craftRecipe).toHaveBeenCalledWith(
                expect.anything(), 'oak_log', 1
            );
        });
    });

    // ─── cmdSmelt ───
    describe('cmdSmelt', () => {
        test('returns error when no input', async () => {
            const result = await resources.cmdSmelt({ input: null });
            expect(result.success).toBe(false);
        });

        test('smelts successfully', async () => {
            skills.smeltItem.mockImplementation(async (bot) => {
                bot.output += 'Successfully smelted iron_ore\n';
                return true;
            });
            const result = await resources.cmdSmelt({ input: 'iron_ore', fuel: 'coal', count: 1 });
            expect(result.success).toBe(true);
            expect(result.action).toBe('smelted');
        });

        test('returns failure when smeltItem fails', async () => {
            skills.smeltItem.mockImplementation(async (bot) => {
                bot.output += 'Cannot smelt iron_ore.\n';
                return false;
            });
            const result = await resources.cmdSmelt({ input: 'iron_ore', count: 1 });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdStore ───
    describe('cmdStore', () => {
        test('returns error when no item specified', async () => {
            const result = await resources.cmdStore({});
            expect(result.success).toBe(false);
            expect(result.error).toBe('No item specified');
        });

        test('stores items successfully', async () => {
            skills.putInChest.mockImplementation(async (bot) => {
                bot.output += 'Successfully put 10 iron_ingot in the chest.\n';
                return true;
            });
            const result = await resources.cmdStore({ item: 'iron_ingot' });
            expect(result.success).toBe(true);
            expect(result.action).toBe('stored');
        });

        test('handles store failure', async () => {
            skills.putInChest.mockResolvedValue(false);
            const result = await resources.cmdStore({ item: 'iron_ingot' });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdTake ───
    describe('cmdTake', () => {
        test('returns error when no item specified', async () => {
            const result = await resources.cmdTake({});
            expect(result.success).toBe(false);
            expect(result.error).toBe('No item specified');
        });

        test('takes items successfully', async () => {
            skills.takeFromChest.mockImplementation(async (bot) => {
                bot.output += 'Successfully took 5 diamond from the chest.\n';
                return true;
            });
            const result = await resources.cmdTake({ item: 'diamond' });
            expect(result.success).toBe(true);
            expect(result.action).toBe('took');
        });

        test('handles take failure', async () => {
            skills.takeFromChest.mockResolvedValue(false);
            const result = await resources.cmdTake({ item: 'diamond' });
            expect(result.success).toBe(false);
        });

        test('takes items with count', async () => {
            skills.takeFromChest.mockResolvedValue(true);
            const result = await resources.cmdTake({ item: 'diamond', count: 5 });
            expect(result.success).toBe(true);
            expect(result.items[0].count).toBe(5);
        });
    });
});
