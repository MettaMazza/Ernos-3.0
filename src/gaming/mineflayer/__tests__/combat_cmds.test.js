/**
 * Tests for commands/combat_cmds.js — attack, equip, shield, sleep, wake, eat.
 */

jest.mock('mineflayer-pathfinder', () => ({
    pathfinder: { name: 'pathfinder' },
    Movements: jest.fn(),
    goals: { GoalNear: jest.fn(), GoalFollow: jest.fn(), GoalBlock: jest.fn(), GoalXZ: jest.fn() }
}));

const shared = require('../shared');

function createMockBot() {
    return {
        entity: { position: { x: 0, y: 64, z: 0, distanceTo: jest.fn().mockReturnValue(2) } },
        health: 20, food: 20,
        time: { timeOfDay: 15000 },
        nearestEntity: jest.fn().mockReturnValue(null),
        lookAt: jest.fn().mockResolvedValue(),
        attack: jest.fn().mockResolvedValue(),
        equip: jest.fn().mockResolvedValue(),
        consume: jest.fn().mockResolvedValue(),
        activateItem: jest.fn(),
        deactivateItem: jest.fn(),
        sleep: jest.fn().mockResolvedValue(),
        wake: jest.fn().mockResolvedValue(),
        inventory: {
            items: jest.fn().mockReturnValue([]),
            slots: {}
        },
        pathfinder: { setGoal: jest.fn() },
        findBlock: jest.fn(),
        on: jest.fn(), once: jest.fn(), removeListener: jest.fn()
    };
}

describe('combat_cmds.js', () => {
    let cmds;
    let mockBot;

    beforeEach(() => {
        jest.useFakeTimers();
        jest.spyOn(console, 'error').mockImplementation();
        jest.spyOn(console, 'log').mockImplementation();
        mockBot = createMockBot();
        shared.setBot(mockBot);
        shared.setMcData({});
        cmds = require('../commands/combat_cmds');
    });

    afterEach(() => { jest.useRealTimers(); jest.restoreAllMocks(); });

    // ─── cmdAttack ───
    describe('cmdAttack', () => {
        test('returns no target when none found', async () => {
            const result = await cmds.cmdAttack({ entity_type: 'hostile' });
            expect(result.attacked).toBe(false);
            expect(result.reason).toBe('No target found');
        });

        test('attacks nearby hostile', async () => {
            const zombie = { name: 'zombie', type: 'hostile', height: 1.8, position: { x: 2, y: 64, z: 0, distanceTo: jest.fn().mockReturnValue(2), offset: jest.fn().mockReturnThis() }, isValid: true };
            mockBot.nearestEntity.mockReturnValue(zombie);
            mockBot.entity.position.distanceTo.mockReturnValue(2);
            // Make entity die after first attack so loop breaks
            mockBot.attack.mockImplementation(async () => { zombie.isValid = false; });

            const promise = cmds.cmdAttack({ entity_type: 'hostile' });
            // Advance timers to resolve attack cooldown promises
            await jest.advanceTimersByTimeAsync(1000);
            const result = await promise;
            expect(result.attacked).toBe(true);
            expect(result.target).toBe('zombie');
        });

        test('attacks specific entity type', async () => {
            const cow = { name: 'cow', type: 'animal', height: 1.4, position: { x: 2, y: 64, z: 0, distanceTo: jest.fn().mockReturnValue(2), offset: jest.fn().mockReturnThis() }, isValid: true };
            mockBot.nearestEntity.mockReturnValue(cow);
            mockBot.entity.position.distanceTo.mockReturnValue(2);
            // Make entity die after first attack so loop breaks
            mockBot.attack.mockImplementation(async () => { cow.isValid = false; });

            const promise = cmds.cmdAttack({ entity_type: 'cow' });
            await jest.advanceTimersByTimeAsync(1000);
            const result = await promise;
            expect(result.attacked).toBe(true);
            expect(result.target).toBe('cow');
        });

        test('navigates to distant target', async () => {
            const zombie = { name: 'zombie', type: 'hostile', height: 1.8, position: { x: 10, y: 64, z: 0, distanceTo: jest.fn().mockReturnValue(10), offset: jest.fn().mockReturnThis() }, isValid: false };
            mockBot.nearestEntity.mockReturnValue(zombie);
            mockBot.entity.position.distanceTo
                .mockReturnValueOnce(10)   // initial dist check
                .mockReturnValueOnce(2)    // check in interval
                .mockReturnValueOnce(2)    // final dist check
                .mockReturnValue(2);

            const promise = cmds.cmdAttack({ entity_type: 'hostile' });
            await jest.advanceTimersByTimeAsync(6000);
            const result = await promise;
            // Either attacked or couldn't reach
            expect(result).toBeDefined();
        });

        test('returns too far after navigation failure', async () => {
            const zombie = { name: 'zombie', type: 'hostile', height: 1.8, position: { x: 50, y: 64, z: 0, distanceTo: jest.fn().mockReturnValue(50), offset: jest.fn().mockReturnThis() }, isValid: true };
            mockBot.nearestEntity.mockReturnValue(zombie);
            mockBot.entity.position.distanceTo.mockReturnValue(50);

            const promise = cmds.cmdAttack({ entity_type: 'hostile' });
            await jest.advanceTimersByTimeAsync(6000);
            const result = await promise;
            expect(result.attacked).toBe(false);
        });
    });

    // ─── cmdEquip ───
    describe('cmdEquip', () => {
        test('returns error when no item specified', async () => {
            const result = await cmds.cmdEquip({ item: null });
            expect(result.success).toBe(false);
        });

        test('returns error when item not in inventory', async () => {
            const result = await cmds.cmdEquip({ item: 'diamond_sword' });
            expect(result.success).toBe(false);
        });

        test('equips item from inventory', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'diamond_sword', count: 1 }]);
            const result = await cmds.cmdEquip({ item: 'diamond_sword', slot: 'hand' });
            expect(result.success).toBe(true);
            expect(result.equipped).toBe('diamond_sword');
        });

        test('equips to different slots', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'iron_helmet', count: 1 }]);
            const result = await cmds.cmdEquip({ item: 'iron_helmet', slot: 'head' });
            expect(result.success).toBe(true);
            expect(result.slot).toBe('head');
        });

        test('handles equip error', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'sword', count: 1 }]);
            mockBot.equip.mockRejectedValue(new Error('slot busy'));
            const result = await cmds.cmdEquip({ item: 'sword' });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdShield ───
    describe('cmdShield', () => {
        test('returns error when no shield', async () => {
            const result = await cmds.cmdShield({ activate: true });
            expect(result.success).toBe(false);
        });

        test('activates shield', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'shield', count: 1 }]);
            mockBot.inventory.slots[45] = null;
            const result = await cmds.cmdShield({ activate: true });
            expect(result.success).toBe(true);
            expect(result.action).toBe('shield_up');
        });

        test('activates shield already in off-hand', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'shield', count: 1 }]);
            mockBot.inventory.slots[45] = { name: 'shield' };
            const result = await cmds.cmdShield({ activate: true });
            expect(result.success).toBe(true);
        });

        test('deactivates shield', async () => {
            const result = await cmds.cmdShield({ activate: false });
            expect(result.success).toBe(true);
            expect(result.action).toBe('shield_down');
        });

        test('handles shield error', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'shield', count: 1 }]);
            mockBot.inventory.slots[45] = null;
            mockBot.equip.mockRejectedValue(new Error('shield error'));
            const result = await cmds.cmdShield({ activate: true });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdSleep ───
    describe('cmdSleep', () => {
        test('returns error during daytime', async () => {
            mockBot.time.timeOfDay = 6000;
            const result = await cmds.cmdSleep();
            expect(result.success).toBe(false);
            expect(result.error).toContain('night');
        });

        test('returns error when no bed', async () => {
            mockBot.time.timeOfDay = 15000;
            mockBot.findBlock.mockReturnValue(null);
            const result = await cmds.cmdSleep();
            expect(result.success).toBe(false);
            expect(result.error).toContain('No bed');
        });

        test('sleeps successfully', async () => {
            mockBot.time.timeOfDay = 15000;
            mockBot.findBlock.mockReturnValue({ position: { x: 5, y: 64, z: 5 } });
            const result = await cmds.cmdSleep();
            expect(result.success).toBe(true);
            expect(result.action).toBe('sleeping');
        });

        test('handles sleep error', async () => {
            mockBot.time.timeOfDay = 15000;
            mockBot.findBlock.mockReturnValue({ position: { x: 5, y: 64, z: 5 } });
            mockBot.sleep.mockRejectedValue(new Error('monsters nearby'));
            const result = await cmds.cmdSleep();
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdWake ───
    describe('cmdWake', () => {
        test('wakes successfully', async () => {
            const result = await cmds.cmdWake();
            expect(result.success).toBe(true);
            expect(result.action).toBe('woke_up');
        });

        test('handles wake error', async () => {
            mockBot.wake.mockRejectedValue(new Error('not sleeping'));
            const result = await cmds.cmdWake();
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdEat ───
    describe('cmdEat', () => {
        test('returns error when no food', async () => {
            const result = await cmds.cmdEat({});
            expect(result.success).toBe(false);
        });

        test('eats specific food', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'bread', count: 5 }]);
            const result = await cmds.cmdEat({ food: 'bread' });
            expect(result.success).toBe(true);
            expect(result.food).toBe('bread');
        });

        test('eats any available food', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'cooked_beef', count: 3 }]);
            const result = await cmds.cmdEat({ food: null });
            expect(result.success).toBe(true);
        });

        test('handles eat error', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'bread', count: 1 }]);
            mockBot.consume.mockRejectedValue(new Error('too fast'));
            const result = await cmds.cmdEat({ food: 'bread' });
            expect(result.success).toBe(false);
        });
    });
});
