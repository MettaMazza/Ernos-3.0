/**
 * Tests for autonomy.js — auto-eat and death recovery.
 */

jest.mock('../shared', () => {
    const mockBot = {
        entity: { position: { x: 10, y: 64, z: 20, distanceTo: jest.fn().mockReturnValue(5), clone: jest.fn(), offset: jest.fn().mockReturnThis() }, isInWater: false },
        health: 20, food: 20,
        inventory: { items: jest.fn().mockReturnValue([]) },
        equip: jest.fn().mockResolvedValue(),
        consume: jest.fn().mockResolvedValue(),
        setControlState: jest.fn(),
        clearControlStates: jest.fn(),
        blockAt: jest.fn().mockReturnValue({ name: 'grass_block' }),  // Non-water for escape check
        on: jest.fn(),
    };
    return {
        getBot: jest.fn().mockReturnValue(mockBot),
        mcLog: jest.fn(),
        sendEvent: jest.fn(),
        _mockBot: mockBot,
    };
});

const shared = require('../shared');
const { setupAutonomy, stopAutonomy, findBestFood } = require('../autonomy');

describe('autonomy.js', () => {
    let mockBot;

    beforeEach(() => {
        jest.useFakeTimers();
        mockBot = shared._mockBot;
        mockBot.health = 20;
        mockBot.food = 20;
        mockBot.inventory.items.mockReturnValue([]);
        mockBot.equip.mockClear();
        mockBot.equip.mockResolvedValue();
        mockBot.consume.mockClear();
        mockBot.consume.mockResolvedValue();
        mockBot.setControlState.mockClear();
        mockBot.clearControlStates.mockClear();
        mockBot.entity.position.clone.mockReturnValue({ x: 10, y: 64, z: 20 });
        mockBot.entity.position.distanceTo.mockReturnValue(5);
        mockBot.on.mockClear();
        shared.mcLog.mockClear();
        shared.sendEvent.mockClear();
    });

    afterEach(() => {
        stopAutonomy();
        jest.useRealTimers();
    });

    // ─── findBestFood ───
    describe('findBestFood', () => {
        test('returns highest quality food', () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'cobblestone', count: 64 },
                { name: 'bread', count: 5 },
                { name: 'cooked_beef', count: 3 },
            ]);
            const food = findBestFood(mockBot);
            expect(food.name).toBe('cooked_beef');
        });

        test('returns bread when no cooked meat', () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'dirt', count: 64 },
                { name: 'bread', count: 2 },
            ]);
            const food = findBestFood(mockBot);
            expect(food.name).toBe('bread');
        });

        test('returns null when no food', () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'cobblestone', count: 64 },
                { name: 'dirt', count: 32 },
            ]);
            const food = findBestFood(mockBot);
            expect(food).toBeNull();
        });

        test('falls back to unnamed cooked item', () => {
            mockBot.inventory.items.mockReturnValue([
                { name: 'cooked_mystery', count: 1 },
            ]);
            const food = findBestFood(mockBot);
            expect(food.name).toBe('cooked_mystery');
        });
    });

    // ─── setupAutonomy ───
    describe('setupAutonomy', () => {
        test('registers health, death, and respawn handlers', () => {
            setupAutonomy(mockBot);
            const events = mockBot.on.mock.calls.map(c => c[0]);
            expect(events).toContain('health');
            expect(events).toContain('death');
            expect(events).toContain('respawn');
        });

        test('logs setup complete', () => {
            setupAutonomy(mockBot);
            expect(shared.mcLog).toHaveBeenCalledWith('INFO', 'AUTONOMY_SETUP_COMPLETE');
        });
    });

    // ─── Auto-eat ───
    describe('auto-eat', () => {
        test('health handler triggers eat when food < 14', async () => {
            mockBot.food = 10;
            mockBot.health = 10;
            mockBot.inventory.items.mockReturnValue([
                { name: 'bread', count: 3 },
            ]);

            setupAutonomy(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            healthHandler();
            // Let promises resolve
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(mockBot.equip).toHaveBeenCalled();
        });

        test('does not eat when food >= 14', async () => {
            mockBot.food = 18;
            mockBot.health = 20;
            mockBot.inventory.items.mockReturnValue([]);
            setupAutonomy(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];
            healthHandler();
            await Promise.resolve();
            expect(mockBot.equip).not.toHaveBeenCalled();
        });

        test('periodic check triggers eat', async () => {
            mockBot.food = 8;
            mockBot.health = 15;
            mockBot.inventory.items.mockReturnValue([
                { name: 'cooked_beef', count: 2 },
            ]);

            setupAutonomy(mockBot);

            jest.advanceTimersByTime(10000);
            await Promise.resolve();
            await Promise.resolve();
            await Promise.resolve();

            expect(mockBot.equip).toHaveBeenCalled();
        });
    });

    // ─── Death recovery ───
    describe('death recovery', () => {
        test('records death position', () => {
            setupAutonomy(mockBot);
            const deathHandler = mockBot.on.mock.calls.find(c => c[0] === 'death')[1];
            deathHandler();
            expect(mockBot.entity.position.clone).toHaveBeenCalled();
            expect(shared.mcLog).toHaveBeenCalledWith('INFO', 'AUTONOMY_DEATH_RECORDED', expect.any(Object));
        });

        test('respawn sprints away from death location', () => {
            mockBot.entity.position.clone.mockReturnValue({ x: 10, y: 64, z: 20 });
            mockBot.entity.position.distanceTo.mockReturnValue(5);

            setupAutonomy(mockBot);

            // Trigger death
            const deathHandler = mockBot.on.mock.calls.find(c => c[0] === 'death')[1];
            deathHandler();

            // Trigger respawn
            const respawnHandler = mockBot.on.mock.calls.find(c => c[0] === 'respawn')[1];
            respawnHandler();

            // Advance past the 3s delay
            jest.advanceTimersByTime(3500);

            expect(mockBot.setControlState).toHaveBeenCalledWith('sprint', true);
            expect(mockBot.setControlState).toHaveBeenCalledWith('forward', true);
        });

        test('respawn does nothing when no death position', () => {
            // Fresh setup — no death event fired
            setupAutonomy(mockBot);
            const respawnHandler = mockBot.on.mock.calls.find(c => c[0] === 'respawn')[1];
            mockBot.setControlState.mockClear();
            respawnHandler();
            jest.advanceTimersByTime(4000);
            expect(mockBot.setControlState).not.toHaveBeenCalledWith('sprint', true);
        });
    });

    // ─── stopAutonomy ───
    describe('stopAutonomy', () => {
        test('clears intervals', async () => {
            setupAutonomy(mockBot);
            stopAutonomy();
            mockBot.equip.mockClear();
            // Advance past periodic check — should not trigger
            mockBot.food = 5;
            mockBot.inventory.items.mockReturnValue([{ name: 'bread', count: 1 }]);
            jest.advanceTimersByTime(15000);
            await Promise.resolve();
            expect(mockBot.equip).not.toHaveBeenCalled();
        });
    });
});
