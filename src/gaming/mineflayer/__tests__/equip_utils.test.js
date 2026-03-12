/**
 * Tests for equip_utils.js — auto-equip helpers
 */

// Mock shared.js before requiring anything
const mockBot = {
    inventory: {
        items: jest.fn().mockReturnValue([]),
        slots: {}
    },
    heldItem: null,
    equip: jest.fn().mockResolvedValue(undefined)
};
jest.mock('../shared', () => ({
    getBot: () => mockBot,
    getMcData: () => ({}),
    mcLog: jest.fn()
}));

const { findBest, getTier, equipBestWeapon, equipBestTool, equipBestArmor } = require('../commands/equip_utils');

describe('equip_utils', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        mockBot.heldItem = null;
        mockBot.inventory.items.mockReturnValue([]);
        mockBot.inventory.slots = {};
        mockBot.equip.mockResolvedValue(undefined);
    });

    describe('getTier', () => {
        test('returns correct tier for known materials', () => {
            expect(getTier('wooden_sword')).toBe(0);
            expect(getTier('stone_pickaxe')).toBe(1);
            expect(getTier('golden_axe')).toBe(2);
            expect(getTier('iron_sword')).toBe(3);
            expect(getTier('diamond_pickaxe')).toBe(4);
            expect(getTier('netherite_sword')).toBe(5);
        });
        test('returns -1 for unknown items', () => {
            expect(getTier('stick')).toBe(-1);
            expect(getTier('shield')).toBe(-1);
        });
    });

    describe('findBest', () => {
        test('returns null when no matching items', () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'stick', count: 1 }
            ]);
            expect(findBest(['_sword'])).toBeNull();
        });

        test('finds best sword by tier', () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'wooden_sword', count: 1 },
                { name: 'iron_sword', count: 1 },
                { name: 'stone_sword', count: 1 }
            ]);
            const best = findBest(['_sword']);
            expect(best.name).toBe('iron_sword');
        });

        test('finds best across multiple suffixes', () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'wooden_axe', count: 1 },
                { name: 'stone_sword', count: 1 }
            ]);
            const best = findBest(['_sword', '_axe']);
            expect(best.name).toBe('stone_sword');
        });
    });

    describe('equipBestWeapon', () => {
        test('returns false when no weapons', async () => {
            mockBot.inventory.items.mockReturnValue([]);
            expect(await equipBestWeapon()).toBe(false);
        });

        test('equips best sword', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'iron_sword', count: 1 }
            ]);
            expect(await equipBestWeapon()).toBe(true);
            expect(mockBot.equip).toHaveBeenCalledWith(
                expect.objectContaining({ name: 'iron_sword' }),
                'hand'
            );
        });

        test('returns true without equipping if already holding weapon', async () => {
            const weapon = { name: 'iron_sword', count: 1 };
            mockBot.heldItem = weapon;
            mockBot.inventory.items.mockReturnValue([weapon]);
            expect(await equipBestWeapon()).toBe(true);
            expect(mockBot.equip).not.toHaveBeenCalled();
        });

        test('falls back to axe when no sword', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'diamond_axe', count: 1 }
            ]);
            expect(await equipBestWeapon()).toBe(true);
            expect(mockBot.equip).toHaveBeenCalledWith(
                expect.objectContaining({ name: 'diamond_axe' }),
                'hand'
            );
        });

        test('returns false on equip failure', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'iron_sword', count: 1 }]);
            mockBot.equip.mockRejectedValueOnce(new Error('slot busy'));
            expect(await equipBestWeapon()).toBe(false);
        });
    });

    describe('equipBestTool', () => {
        test('returns false when no tools', async () => {
            expect(await equipBestTool('stone')).toBe(false);
        });

        test('selects pickaxe for stone', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'iron_pickaxe', count: 1 }
            ]);
            expect(await equipBestTool('stone')).toBe(true);
            expect(mockBot.equip).toHaveBeenCalledWith(
                expect.objectContaining({ name: 'iron_pickaxe' }), 'hand'
            );
        });

        test('selects axe for logs', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'stone_axe', count: 1 }
            ]);
            expect(await equipBestTool('oak_log')).toBe(true);
            expect(mockBot.equip).toHaveBeenCalledWith(
                expect.objectContaining({ name: 'stone_axe' }), 'hand'
            );
        });

        test('selects shovel for dirt', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'iron_shovel', count: 1 }
            ]);
            expect(await equipBestTool('dirt')).toBe(true);
            expect(mockBot.equip).toHaveBeenCalledWith(
                expect.objectContaining({ name: 'iron_shovel' }), 'hand'
            );
        });

        test('defaults to pickaxe for unknown blocks', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'stone_pickaxe', count: 1 }
            ]);
            expect(await equipBestTool('weird_block')).toBe(true);
        });

        test('skips equip if already holding correct tool', async () => {
            const tool = { name: 'iron_pickaxe', count: 1 };
            mockBot.heldItem = tool;
            mockBot.inventory.items.mockReturnValue([tool]);
            expect(await equipBestTool('stone')).toBe(true);
            expect(mockBot.equip).not.toHaveBeenCalled();
        });

        test('returns false on equip failure', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'iron_pickaxe', count: 1 }]);
            mockBot.equip.mockRejectedValueOnce(new Error('fail'));
            expect(await equipBestTool('stone')).toBe(false);
        });
    });

    describe('equipBestArmor', () => {
        test('returns 0 when no armor', async () => {
            expect(await equipBestArmor()).toBe(0);
        });

        test('equips helmet', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'iron_helmet', count: 1 }
            ]);
            expect(await equipBestArmor()).toBe(1);
            expect(mockBot.equip).toHaveBeenCalledWith(
                expect.objectContaining({ name: 'iron_helmet' }), 'head'
            );
        });

        test('equips full set', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'iron_helmet', count: 1 },
                { name: 'iron_chestplate', count: 1 },
                { name: 'iron_leggings', count: 1 },
                { name: 'iron_boots', count: 1 }
            ]);
            expect(await equipBestArmor()).toBe(4);
        });

        test('skips slot if better armor already equipped', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'iron_helmet', count: 1 }
            ]);
            mockBot.inventory.slots[5] = { name: 'diamond_helmet' }; // Better
            expect(await equipBestArmor()).toBe(0);
        });

        test('upgrades slot if worse armor equipped', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'diamond_helmet', count: 1 }
            ]);
            mockBot.inventory.slots[5] = { name: 'iron_helmet' }; // Worse
            expect(await equipBestArmor()).toBe(1);
        });

        test('equips shield to off-hand', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'shield', count: 1 }
            ]);
            expect(await equipBestArmor()).toBe(1);
            expect(mockBot.equip).toHaveBeenCalledWith(
                expect.objectContaining({ name: 'shield' }), 'off-hand'
            );
        });

        test('does not re-equip shield already in off-hand', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'shield', count: 1 }
            ]);
            mockBot.inventory.slots[45] = { name: 'shield' };
            expect(await equipBestArmor()).toBe(0);
        });

        test('handles equip failure gracefully', async () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'iron_helmet', count: 1 }
            ]);
            mockBot.equip.mockRejectedValueOnce(new Error('fail'));
            expect(await equipBestArmor()).toBe(0);
        });
    });
});
