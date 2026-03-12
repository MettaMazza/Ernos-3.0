/**
 * Tests for commands/building.js — place, protect, locations, blueprints.
 */

jest.mock('mineflayer-pathfinder', () => ({
    pathfinder: { name: 'pathfinder' },
    Movements: jest.fn().mockImplementation(() => ({})),
    goals: { GoalNear: jest.fn(), GoalFollow: jest.fn(), GoalBlock: jest.fn(), GoalXZ: jest.fn() }
}));

jest.mock('fs');

describe('building.js', () => {
    let building;
    let shared;
    let mockBot;
    let fs;

    const Vec3 = jest.fn().mockImplementation((x, y, z) => ({ x, y, z }));

    beforeEach(() => {
        jest.resetModules();
        jest.mock('fs');
        fs = require('fs');
        fs.existsSync = jest.fn().mockReturnValue(false);
        fs.readFileSync = jest.fn().mockReturnValue('{}');
        fs.writeFileSync = jest.fn();
        fs.mkdirSync = jest.fn();

        jest.spyOn(console, 'error').mockImplementation();
        jest.spyOn(console, 'log').mockImplementation();

        shared = require('../shared');
        mockBot = {
            entity: { position: { x: 0, y: 64, z: 0 }, yaw: 0 },
            game: { dimension: 'overworld' },
            inventory: { items: jest.fn().mockReturnValue([]) },
            equip: jest.fn().mockResolvedValue(),
            placeBlock: jest.fn().mockResolvedValue(),
            dig: jest.fn().mockResolvedValue(),
            blockAt: jest.fn(),
            findBlock: jest.fn(),
            findBlocks: jest.fn().mockReturnValue([]),
            players: {},
            pathfinder: { setGoal: jest.fn(), setMovements: jest.fn(), goto: jest.fn().mockResolvedValue() },
            on: jest.fn(), once: jest.fn()
        };
        shared.setBot(mockBot);
        shared.setMcData({ Vec3 });

        building = require('../commands/building');
    });

    afterEach(() => { jest.restoreAllMocks(); });

    // ─── cmdPlace ───
    describe('cmdPlace', () => {
        test('returns error when item not in inventory', async () => {
            const result = await building.cmdPlace({ block: 'cobblestone' });
            expect(result.success).toBe(false);
        });

        test('places at specific coords', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'cobblestone', count: 64 }]);
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            mockBot.findBlock.mockReturnValue({ name: 'cobblestone', position: { x: 1, y: 64, z: 1 } });

            const result = await building.cmdPlace({ block: 'cobblestone', x: 1, y: 64, z: 1 });
            expect(result.success).toBe(true);
        });

        test('places in front without coords', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'cobblestone', count: 64 }]);
            // blockAt returns solid for ground (y-1) and air for above (y) for the offset placement
            mockBot.blockAt.mockImplementation((pos) => {
                if (pos && pos.y < 64) return { name: 'stone' };  // below = solid
                return { name: 'air' };  // at placement level = air
            });
            mockBot.findBlock.mockReturnValue({ name: 'cobblestone', position: { x: 0, y: 64, z: -2 } });

            const result = await building.cmdPlace({ block: 'cobblestone' });
            expect(result.success).toBe(true);
        });

        test('returns error when no reference block (direction)', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'cobblestone', count: 64 }]);
            mockBot.blockAt.mockReturnValue({ name: 'air' });

            const result = await building.cmdPlace({ block: 'cobblestone' });
            expect(result.success).toBe(false);
        });

        test('returns error for coord placement without reference block', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'cobblestone', count: 64 }]);
            mockBot.blockAt.mockReturnValue(null);

            const result = await building.cmdPlace({ block: 'cobblestone', x: 1, y: 100, z: 1 });
            expect(result.success).toBe(false);
        });

        test('handles place error', async () => {
            mockBot.inventory.items.mockReturnValue([{ name: 'cobblestone', count: 64 }]);
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            mockBot.placeBlock.mockRejectedValue(new Error('cannot place'));

            const result = await building.cmdPlace({ block: 'cobblestone', x: 1, y: 64, z: 1 });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdProtect ───
    describe('cmdProtect', () => {
        test('creates zone at bot position', async () => {
            const result = await building.cmdProtect({ username: 'admin', radius: 50 });
            expect(result.success).toBe(true);
            expect(result.zone.owner).toBe('admin');
        });

        test('creates zone at specific coords', async () => {
            const result = await building.cmdProtect({ username: 'admin', x: 10, y: 64, z: 20, radius: 30 });
            expect(result.success).toBe(true);
            expect(result.zone.x).toBe(10);
        });
    });

    // ─── cmdListProtectedZones ───
    describe('cmdListProtectedZones', () => {
        test('returns zones list', async () => {
            const result = await building.cmdListProtectedZones();
            expect(Array.isArray(result.zones)).toBe(true);
            expect(typeof result.total).toBe('number');
        });
    });

    // ─── cmdSaveLocation ───
    describe('cmdSaveLocation', () => {
        test('returns error when no name', async () => {
            const result = await building.cmdSaveLocation({});
            expect(result.success).toBe(false);
        });

        test('saves current position', async () => {
            const result = await building.cmdSaveLocation({ name: 'Home' });
            expect(result.success).toBe(true);
            expect(result.name).toBe('home');
        });
    });

    // ─── cmdGotoLocation ───
    describe('cmdGotoLocation', () => {
        test('lists locations when no name', async () => {
            const result = await building.cmdGotoLocation({});
            expect(result.action).toBe('list_locations');
        });

        test('returns error for unknown location', async () => {
            const result = await building.cmdGotoLocation({ name: 'nowhere' });
            expect(result.success).toBe(false);
        });

        test('goes to saved location', async () => {
            await building.cmdSaveLocation({ name: 'base' });
            const result = await building.cmdGotoLocation({ name: 'base' });
            expect(result.success).toBe(true);
        });

        test('handles navigation error', async () => {
            await building.cmdSaveLocation({ name: 'far' });
            mockBot.pathfinder.goto.mockRejectedValue(new Error('path blocked'));
            const result = await building.cmdGotoLocation({ name: 'far' });
            expect(result.success).toBe(false);
        });
    });

    // ─── cmdCopyBuild ───
    describe('cmdCopyBuild', () => {
        test('returns error when no name', async () => {
            const result = await building.cmdCopyBuild({});
            expect(result.success).toBe(false);
        });

        test('returns error when no blocks found', async () => {
            mockBot.blockAt.mockReturnValue({ name: 'air' });
            const result = await building.cmdCopyBuild({ name: 'empty', radius: 0, height: 1 });
            expect(result.success).toBe(false);
        });

        test('saves blueprint', async () => {
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            const result = await building.cmdCopyBuild({ name: 'tower', radius: 0, height: 1 });
            expect(result.success).toBe(true);
        });
    });

    // ─── cmdBuild ───
    describe('cmdBuild', () => {
        test('lists blueprints when no name', async () => {
            const result = await building.cmdBuild({});
            expect(result.action).toBe('list_blueprints');
        });

        test('returns error for unknown blueprint', async () => {
            const result = await building.cmdBuild({ name: 'castle' });
            expect(result.success).toBe(false);
        });

        test('builds from blueprint with items in inventory', async () => {
            // First save a blueprint
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            await building.cmdCopyBuild({ name: 'tower', radius: 0, height: 1 });

            // Set up inventory with matching blocks
            mockBot.inventory.items.mockReturnValue([{ name: 'stone', count: 64, type: 1 }]);

            // Mock block placement — below block is solid
            mockBot.blockAt.mockReturnValue({ name: 'dirt' });

            const result = await building.cmdBuild({ name: 'tower' });
            expect(result.success).toBe(true);
            expect(result.action).toBe('built');
            expect(result.placed).toBeGreaterThanOrEqual(0);
        });

        test('gathers missing resources when gatherResources=true', async () => {
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            await building.cmdCopyBuild({ name: 'base', radius: 0, height: 1 });

            // No matching items in inventory
            mockBot.inventory.items.mockReturnValue([]);

            // findBlocks returns block positions for gathering
            const blockPos = { x: 5, y: 64, z: 5 };
            mockBot.findBlocks.mockReturnValue([blockPos]);
            mockBot.blockAt.mockReturnValue({ name: 'stone' });

            const result = await building.cmdBuild({ name: 'base', gatherResources: true });
            expect(result.success).toBe(true);
            expect(mockBot.dig).toHaveBeenCalled();
        });

        test('skips resource gathering when gatherResources=false', async () => {
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            await building.cmdCopyBuild({ name: 'wall', radius: 0, height: 1 });

            mockBot.inventory.items.mockReturnValue([]);
            mockBot.blockAt.mockReturnValue(null);

            const result = await building.cmdBuild({ name: 'wall', gatherResources: false });
            expect(result.success).toBe(true);
        });

        test('places block using adjacent reference when no below block', async () => {
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            await building.cmdCopyBuild({ name: 'bridge', radius: 0, height: 1 });

            mockBot.inventory.items.mockReturnValue([{ name: 'stone', count: 64, type: 1 }]);

            // First call (belowPos) returns air, second (adjacent) returns solid
            let callCount = 0;
            mockBot.blockAt.mockImplementation(() => {
                callCount++;
                if (callCount % 2 === 1) return { name: 'air' }; // below is air
                return { name: 'stone' }; // adjacent is solid
            });

            const result = await building.cmdBuild({ name: 'bridge', gatherResources: false });
            expect(result.success).toBe(true);
        });

        test('increments failed when no reference block found', async () => {
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            await building.cmdCopyBuild({ name: 'float', radius: 0, height: 1 });

            mockBot.inventory.items.mockReturnValue([{ name: 'stone', count: 64, type: 1 }]);
            mockBot.blockAt.mockReturnValue({ name: 'air' }); // All directions are air

            const result = await building.cmdBuild({ name: 'float', gatherResources: false });
            expect(result.success).toBe(true);
            expect(result.failed).toBeGreaterThan(0);
        });

        test('handles equip/place error', async () => {
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            await building.cmdCopyBuild({ name: 'err', radius: 0, height: 1 });

            mockBot.inventory.items.mockReturnValue([{ name: 'stone', count: 64, type: 1 }]);
            mockBot.blockAt.mockReturnValue({ name: 'dirt' });
            mockBot.equip.mockRejectedValue(new Error('hand busy'));

            const result = await building.cmdBuild({ name: 'err', gatherResources: false });
            expect(result.success).toBe(true);
            expect(result.failed).toBeGreaterThan(0);
        });

        test('handles build error', async () => {
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            await building.cmdCopyBuild({ name: 'crash', radius: 0, height: 1 });

            // Make bot.entity null to trigger outer catch
            mockBot.entity = null;
            const result = await building.cmdBuild({ name: 'crash' });
            expect(result.success).toBe(false);
        });

        test('fails when no block item in inventory during placement', async () => {
            mockBot.blockAt.mockReturnValue({ name: 'stone' });
            await building.cmdCopyBuild({ name: 'no_items', radius: 0, height: 1 });

            // Inventory has items but wrong name
            mockBot.inventory.items.mockReturnValue([{ name: 'dirt', count: 64, type: 3 }]);
            mockBot.blockAt.mockReturnValue({ name: 'dirt' });

            const result = await building.cmdBuild({ name: 'no_items', gatherResources: false });
            expect(result.success).toBe(true);
            expect(result.failed).toBeGreaterThan(0);
        });
    });

    // ─── cmdCopyBuild error ───
    describe('cmdCopyBuild - error branch', () => {
        test('returns error when blockAt throws', async () => {
            mockBot.blockAt.mockImplementation(() => { throw new Error('world not loaded'); });
            const result = await building.cmdCopyBuild({ name: 'broken', radius: 0, height: 1 });
            expect(result.success).toBe(false);
            expect(result.error).toBe('world not loaded');
        });
    });

    // ─── cmdListLocations ───
    describe('cmdListLocations', () => {
        test('returns locations', async () => {
            const result = await building.cmdListLocations();
            expect(result.success).toBe(true);
            expect(Array.isArray(result.locations)).toBe(true);
        });
    });

    // ─── cmdListBlueprints ───
    describe('cmdListBlueprints', () => {
        test('returns blueprints', async () => {
            const result = await building.cmdListBlueprints();
            expect(result.success).toBe(true);
            expect(Array.isArray(result.blueprints)).toBe(true);
        });
    });
});
