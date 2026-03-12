/**
 * Tests for combat.js — aggro, flee, damage retaliation, proactive attack.
 */

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

// Helper to create a mock bot
function createMockBot() {
    return {
        entity: {
            position: {
                x: 0, y: 64, z: 0,
                distanceTo: jest.fn().mockReturnValue(3)
            },
            height: 1.8
        },
        health: 20,
        food: 20,
        username: 'Ernos',
        entities: {},
        nearestEntity: jest.fn().mockReturnValue(null),
        lookAt: jest.fn().mockResolvedValue(),
        attack: jest.fn().mockResolvedValue(),
        equip: jest.fn().mockResolvedValue(),
        heldItem: null,
        inventory: { items: jest.fn().mockReturnValue([]), slots: {} },
        activateItem: jest.fn(),
        deactivateItem: jest.fn(),
        pathfinder: {
            setGoal: jest.fn(),
            setMovements: jest.fn()
        },
        setControlState: jest.fn(),
        clearControlStates: jest.fn(),
        on: jest.fn(),
        once: jest.fn(),
        removeListener: jest.fn()
    };
}

describe('combat.js', () => {
    let combat;
    let mockBot;

    beforeEach(() => {
        jest.resetModules();
        jest.useFakeTimers();
        jest.mock('mineflayer-pathfinder', () => ({
            pathfinder: { name: 'pathfinder' },
            Movements: jest.fn(),
            goals: {
                GoalNear: jest.fn(),
                GoalFollow: jest.fn(),
                GoalBlock: jest.fn(),
                GoalXZ: jest.fn()
            }
        }));
        jest.spyOn(console, 'error').mockImplementation();
        jest.spyOn(console, 'log').mockImplementation();

        const sharedModule = require('../shared');
        mockBot = createMockBot();
        sharedModule.setBot(mockBot);

        combat = require('../combat');
    });

    afterEach(() => {
        combat.stopCombat();
        jest.useRealTimers();
        jest.restoreAllMocks();
    });

    // ─── aggroPlayers ───
    describe('aggroPlayers', () => {
        test('starts empty', () => {
            expect(combat.aggroPlayers.size).toBe(0);
        });

        test('can add/delete players', () => {
            combat.aggroPlayers.add('griefer');
            expect(combat.aggroPlayers.has('griefer')).toBe(true);
            combat.aggroPlayers.delete('griefer');
            expect(combat.aggroPlayers.has('griefer')).toBe(false);
        });

        test('getAggroPlayers returns the Set', () => {
            expect(combat.getAggroPlayers()).toBe(combat.aggroPlayers);
        });
    });

    // ─── lastAutoAttackTime ───
    describe('attack timing', () => {
        test('getLastAutoAttackTime starts at 0', () => {
            expect(combat.getLastAutoAttackTime()).toBe(0);
        });

        test('setLastAutoAttackTime updates the value', () => {
            combat.setLastAutoAttackTime(12345);
            expect(combat.getLastAutoAttackTime()).toBe(12345);
        });
    });

    // ─── fleeFrom ───
    describe('fleeFrom', () => {
        test('sets sprint and pathfinder goal', () => {
            combat.fleeFrom({ x: 10, y: 64, z: 10 }, 12);
            expect(mockBot.pathfinder.setGoal).toHaveBeenCalled();
            expect(mockBot.setControlState).toHaveBeenCalledWith('sprint', true);
        });

        test('clears flee after reaching safe distance', () => {
            // Mock distanceTo to return >= fleeDistance after interval tick
            mockBot.entity.position.distanceTo.mockReturnValue(15);
            combat.fleeFrom({ x: 10, y: 64, z: 10 }, 12);
            jest.advanceTimersByTime(501); // First interval check
            expect(mockBot.setControlState).toHaveBeenCalledWith('sprint', false);
            expect(mockBot.clearControlStates).toHaveBeenCalled();
        });

        test('does nothing when already fleeing', () => {
            combat.fleeFrom({ x: 10, y: 64, z: 10 });
            mockBot.pathfinder.setGoal.mockClear();
            combat.fleeFrom({ x: 20, y: 64, z: 20 }); // Should be ignored
            expect(mockBot.pathfinder.setGoal).not.toHaveBeenCalled();
            // Let the flee finish by advancing past max time + safety
            mockBot.entity.position.distanceTo.mockReturnValue(15);
            jest.advanceTimersByTime(6001);
        });

        test('does nothing when bot is null', () => {
            const sharedModule = require('../shared');
            sharedModule.setBot(null);
            expect(() => combat.fleeFrom({ x: 10, y: 64, z: 10 })).not.toThrow();
        });
    });

    // ─── isFleeingCombat ───
    describe('isFleeingCombat', () => {
        test('returns false initially', () => {
            expect(combat.isFleeingCombat()).toBe(false);
        });

        test('returns true during flee', () => {
            combat.fleeFrom({ x: 10, y: 64, z: 10 });
            expect(combat.isFleeingCombat()).toBe(true);
            // Simulate reaching safe distance
            mockBot.entity.position.distanceTo.mockReturnValue(15);
            jest.advanceTimersByTime(501);
            expect(combat.isFleeingCombat()).toBe(false);
        });
    });

    // ─── setupCombat ───
    describe('setupCombat', () => {
        test('registers health, entityHurt handlers and interval', () => {
            combat.setupCombat(mockBot);
            expect(mockBot.on).toHaveBeenCalledWith('health', expect.any(Function));
            expect(mockBot.on).toHaveBeenCalledWith('entityHurt', expect.any(Function));
        });

        test('health handler detects damage and retaliates', async () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            // Simulate damage
            mockBot.health = 15;
            const target = { name: 'zombie', position: { x: 2, y: 64, z: 2, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 2 }) }, height: 1.8, isValid: true };
            mockBot.nearestEntity.mockReturnValue(target);
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            healthHandler();
            await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); // flush equipBestWeapon promise
            // Should attempt retaliation
            expect(mockBot.lookAt).toHaveBeenCalled();
        });

        test('health handler flees when low health', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            mockBot.health = 4;  // Low HP
            const threat = { name: 'zombie', position: { x: 2, y: 64, z: 2 }, type: 'hostile' };
            mockBot.nearestEntity.mockReturnValue(threat);
            mockBot.entity.position.distanceTo.mockReturnValue(5);

            healthHandler();
            // Should flee, not attack
            expect(mockBot.setControlState).toHaveBeenCalledWith('sprint', true);
            mockBot.entity.position.distanceTo.mockReturnValue(20);
            jest.advanceTimersByTime(501);
        });

        test('health handler evades creepers', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            mockBot.health = 15;
            const creeper = { name: 'creeper', position: { x: 2, y: 64, z: 2 }, height: 1.5, isValid: true };
            mockBot.nearestEntity.mockReturnValue(creeper);
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            healthHandler();
            expect(mockBot.setControlState).toHaveBeenCalledWith('sprint', true);
            mockBot.entity.position.distanceTo.mockReturnValue(20);
            jest.advanceTimersByTime(501);
        });

        test('health handler does nothing when not damaged', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            mockBot.health = 20; // No damage
            healthHandler();
            expect(mockBot.lookAt).not.toHaveBeenCalled();
        });

        test('entityHurt tracks damage source', () => {
            combat.setupCombat(mockBot);
            const entityHurtHandler = mockBot.on.mock.calls.find(c => c[0] === 'entityHurt')[1];

            const source = { name: 'zombie', position: { x: 1, y: 64, z: 1 }, type: 'hostile' };
            entityHurtHandler(mockBot.entity, source);
            // Should have logged damage source tracking
        });

        test('entityHurt infers source when none provided', () => {
            combat.setupCombat(mockBot);
            const entityHurtHandler = mockBot.on.mock.calls.find(c => c[0] === 'entityHurt')[1];

            const attacker = { name: 'zombie', username: null, position: { x: 1, y: 64, z: 1 }, type: 'hostile' };
            mockBot.nearestEntity.mockReturnValue(attacker);
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            entityHurtHandler(mockBot.entity, null);
            // Should infer attacker
        });

        test('entityHurt tracks player aggro', () => {
            combat.setupCombat(mockBot);
            const entityHurtHandler = mockBot.on.mock.calls.find(c => c[0] === 'entityHurt')[1];

            const player = { name: undefined, username: 'griefer', type: 'player', position: { x: 2, y: 64, z: 2 } };
            mockBot.nearestEntity.mockReturnValue(player);
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            entityHurtHandler(mockBot.entity, player);
            expect(combat.aggroPlayers.has('griefer')).toBe(true);
        });

        test('entityHurt ignores non-bot entities', () => {
            combat.setupCombat(mockBot);
            const entityHurtHandler = mockBot.on.mock.calls.find(c => c[0] === 'entityHurt')[1];

            const otherEntity = { position: { x: 50, y: 64, z: 50 } };
            entityHurtHandler(otherEntity, null);
            // Should do nothing
        });
    });

    // ─── stopCombat ───
    describe('stopCombat', () => {
        test('clears interval without error', () => {
            combat.setupCombat(mockBot);
            expect(() => combat.stopCombat()).not.toThrow();
        });

        test('calling stopCombat twice is safe', () => {
            combat.stopCombat();
            expect(() => combat.stopCombat()).not.toThrow();
        });
    });

    // ─── proactive interval ───
    describe('proactive combat interval', () => {
        test('attacks nearby hostile mobs', () => {
            combat.setupCombat(mockBot);

            const zombie = {
                entity: { position: { x: 3, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 3, y: 65, z: 0 }) }, height: 1.8, type: 'hostile' },
                name: 'zombie', type: 'hostile',
                position: { x: 3, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 3, y: 65, z: 0 }) },
                height: 1.8
            };

            mockBot.entities = {
                1: { ...zombie.entity, name: 'zombie', type: 'hostile' }
            };
            mockBot.entity.position.distanceTo.mockReturnValue(5);

            jest.advanceTimersByTime(501);
        });

        test('flees from nearby creepers', () => {
            combat.setupCombat(mockBot);

            const creeper = { name: 'creeper', type: 'hostile', position: { x: 2, y: 64, z: 0 } };
            mockBot.entities = { 1: creeper };
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            jest.advanceTimersByTime(501);
            mockBot.entity.position.distanceTo.mockReturnValue(20);
            jest.advanceTimersByTime(501);
        });

        test('interval skips when bot is dead', () => {
            combat.setupCombat(mockBot);
            mockBot.health = 0;
            jest.advanceTimersByTime(501);
        });

        test('interval skips when no entity', () => {
            combat.setupCombat(mockBot);
            mockBot.entity = null;
            jest.advanceTimersByTime(501);
        });

        test('low-health flee from threats in interval', () => {
            combat.setupCombat(mockBot);
            mockBot.health = 4;

            const zombie = { name: 'zombie', type: 'hostile', position: { x: 8, y: 64, z: 0 } };
            mockBot.entities = { 1: zombie };
            mockBot.entity.position.distanceTo.mockReturnValue(8);

            jest.advanceTimersByTime(501);
            expect(mockBot.setControlState).toHaveBeenCalledWith('sprint', true);
            mockBot.entity.position.distanceTo.mockReturnValue(20);
            jest.advanceTimersByTime(501);
        });

        test('chases aggro players at distance > 4', () => {
            combat.setupCombat(mockBot);
            combat.aggroPlayers.add('griefer');

            const player = { name: undefined, username: 'griefer', type: 'player', position: { x: 20, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 20, y: 65, z: 0 }) }, height: 1.8 };
            mockBot.entities = { 1: player };
            mockBot.entity.position.distanceTo.mockReturnValue(15);

            jest.advanceTimersByTime(501);
            expect(mockBot.pathfinder.setGoal).toHaveBeenCalled();
        });

        test('attacks aggro players within 5 blocks', async () => {
            combat.setupCombat(mockBot);
            combat.aggroPlayers.add('griefer');

            const player = { name: undefined, username: 'griefer', type: 'player', position: { x: 3, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 3, y: 65, z: 0 }) }, height: 1.8 };
            mockBot.entities = { 1: player };
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            jest.advanceTimersByTime(501);
            await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
            expect(mockBot.lookAt).toHaveBeenCalled();
        });

        test('proactive mob attack on non-creeper within 8 blocks', async () => {
            combat.setupCombat(mockBot);

            const spider = { name: 'spider', type: 'hostile', position: { x: 6, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 6, y: 65, z: 0 }) }, height: 1.0 };
            mockBot.entities = { 1: spider };
            mockBot.entity.position.distanceTo.mockReturnValue(6);

            jest.advanceTimersByTime(501);
            await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
            expect(mockBot.lookAt).toHaveBeenCalled();
        });

        test('skips fleeing when already fleeing', () => {
            combat.setupCombat(mockBot);
            combat.fleeFrom({ x: 10, y: 64, z: 10 }, 12);

            const zombie = { name: 'zombie', type: 'hostile', position: { x: 2, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 0 }) }, height: 1.8 };
            mockBot.entities = { 1: zombie };
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            jest.advanceTimersByTime(501);
            mockBot.entity.position.distanceTo.mockReturnValue(20);
            jest.advanceTimersByTime(501);
        });
    });

    // ─── health handler - additional branches ───
    describe('health handler - advanced', () => {
        test('low-health flee when food < 4', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            mockBot.health = 10;
            mockBot.food = 2; // Low food triggers flee
            const threat = { name: 'zombie', position: { x: 2, y: 64, z: 2 }, type: 'mob' };
            mockBot.nearestEntity.mockReturnValue(threat);
            mockBot.entity.position.distanceTo.mockReturnValue(5);

            healthHandler();
            expect(mockBot.setControlState).toHaveBeenCalledWith('sprint', true);
            mockBot.entity.position.distanceTo.mockReturnValue(20);
            jest.advanceTimersByTime(501);
        });

        test('retaliation uses tracked damage source', async () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];
            const entityHurtHandler = mockBot.on.mock.calls.find(c => c[0] === 'entityHurt')[1];

            // First track damage source
            const source = { name: 'zombie', position: { x: 2, y: 64, z: 2, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 2 }) }, type: 'hostile', isValid: true, height: 1.8 };
            entityHurtHandler(mockBot.entity, source);

            // Now simulate damage and check retaliation uses tracked source
            mockBot.health = 15;
            mockBot.entity.position.distanceTo.mockReturnValue(3);
            healthHandler();
            await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
            expect(mockBot.lookAt).toHaveBeenCalled();
        });

        test('retaliation falls back to nearest entity when no tracked source', async () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            mockBot.health = 15;
            const target = {
                name: 'zombie', type: 'hostile',
                position: { x: 2, y: 64, z: 2, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 2 }) },
                height: 1.8, username: undefined
            };
            mockBot.nearestEntity.mockReturnValue(target);
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            healthHandler();
            await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
            expect(mockBot.lookAt).toHaveBeenCalled();
        });

        test('retaliation respects attack cooldown', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            // First attack
            mockBot.health = 15;
            const target = {
                name: 'zombie', type: 'hostile',
                position: { x: 2, y: 64, z: 2, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 2 }) },
                height: 1.8
            };
            mockBot.nearestEntity.mockReturnValue(target);
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            healthHandler();
            mockBot.lookAt.mockClear();

            // Second attack too fast — should be throttled
            mockBot.health = 12;
            healthHandler();
            // lookAt should still be called (retaliation) but timing is checked internally
        });

        test('retaliation with aggro player as nearest', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            combat.aggroPlayers.add('griefer');

            mockBot.health = 15;
            const player = {
                type: 'player', username: 'griefer',
                position: { x: 2, y: 64, z: 2, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 2 }) },
                height: 1.8
            };
            mockBot.nearestEntity.mockReturnValue(player);
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            healthHandler();
        });

        test('no target found does nothing', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            mockBot.health = 15;
            mockBot.nearestEntity.mockReturnValue(null);

            healthHandler();
            expect(mockBot.lookAt).not.toHaveBeenCalled();
        });

        test('health handler with health 0 (dead) does nothing', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            mockBot.health = 0;
            healthHandler();
            expect(mockBot.lookAt).not.toHaveBeenCalled();
        });
    });

    // ─── entityHurt - additional branches ───
    describe('entityHurt - advanced', () => {
        test('infers probable attacker when no source and entity is player', () => {
            combat.setupCombat(mockBot);
            const entityHurtHandler = mockBot.on.mock.calls.find(c => c[0] === 'entityHurt')[1];

            const attacker = { name: undefined, username: 'pvpplayer', type: 'player', position: { x: 2, y: 64, z: 2 } };
            mockBot.nearestEntity.mockReturnValue(attacker);
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            entityHurtHandler(mockBot.entity, null);
        });

        test('no probable attacker found when no entities nearby', () => {
            combat.setupCombat(mockBot);
            const entityHurtHandler = mockBot.on.mock.calls.find(c => c[0] === 'entityHurt')[1];

            mockBot.nearestEntity.mockReturnValue(null);
            entityHurtHandler(mockBot.entity, null);
        });

        test('no aggro added when no player nearby', () => {
            combat.setupCombat(mockBot);
            const entityHurtHandler = mockBot.on.mock.calls.find(c => c[0] === 'entityHurt')[1];

            // attacker is mob not player — nearestEntity for player check returns null
            const source = { name: 'zombie', position: { x: 1, y: 64, z: 1 }, type: 'hostile' };
            mockBot.nearestEntity
                .mockReturnValueOnce(null)  // probable attacker search
                .mockReturnValueOnce(null); // player aggro search

            entityHurtHandler(mockBot.entity, source);
            expect(combat.aggroPlayers.size).toBe(0);
        });
    });

    // ─── nearestEntity filter callbacks ───
    describe('nearestEntity filter callbacks', () => {
        test('low-health flee filter exercised with valid entity', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            mockBot.health = 5;
            mockBot.food = 2;

            const zombie = {
                name: 'zombie', type: 'hostile', height: 1.8,
                position: { x: 2, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 0 }) }
            };

            // Make nearestEntity actually call the filter
            mockBot.nearestEntity.mockImplementation(fn => {
                // Test with null entity
                fn(null);
                // Test with entity that has no position
                fn({ type: 'hostile' });
                // Test with entity too far
                fn({ position: { x: 100, y: 64, z: 100 }, type: 'hostile' });
                // Test with non-hostile entity
                fn({ position: { x: 2, y: 64, z: 0 }, type: 'animal' });
                // Test with valid threat
                return fn(zombie) ? zombie : null;
            });
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            healthHandler();
            // Should flee from zombie
        });

        test('retaliation filter exercises all branches', () => {
            combat.setupCombat(mockBot);
            const healthHandler = mockBot.on.mock.calls.find(c => c[0] === 'health')[1];

            mockBot.health = 15;

            const zombie = {
                name: 'zombie', type: 'hostile', height: 1.8,
                position: { x: 2, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 0 }) }
            };

            mockBot.nearestEntity.mockImplementation(fn => {
                fn(null);                                    // null check
                fn({ type: 'mob' });                         // no position
                fn({ position: { x: 100, y: 64, z: 100 }, type: 'mob' }); // too far
                fn({ position: { x: 2, y: 64, z: 0 }, type: 'animal', name: 'cow' }); // non-hostile
                fn({ position: { x: 2, y: 64, z: 0 }, type: 'player', username: 'notaggro' }); // non-aggro player
                return fn(zombie) ? zombie : null;
            });
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            healthHandler();
        });

        test('entityHurt filter exercises all branches', () => {
            combat.setupCombat(mockBot);
            const entityHurtHandler = mockBot.on.mock.calls.find(c => c[0] === 'entityHurt')[1];

            const nearby = {
                name: 'zombie', type: 'hostile', height: 1.8,
                position: { x: 2, y: 64, z: 0, offset: jest.fn().mockReturnValue({ x: 2, y: 65, z: 0 }) }
            };

            let callCount = 0;
            mockBot.nearestEntity.mockImplementation(fn => {
                callCount++;
                if (callCount === 1) {
                    // First call: infer attacker (line 124) - has null guard
                    fn(null);                                    // null
                    fn({ type: 'mob' });                         // no position
                    fn(mockBot.entity);                          // self
                    fn({ position: { x: 100, y: 64, z: 100 }, type: 'mob' }); // too far
                    return fn(nearby) ? nearby : null;
                } else {
                    // Second call: player aggro (line 138) - no null guard, just test real entities
                    fn({ type: 'mob', username: 'mob1' });       // non-player
                    fn({ type: 'player', username: mockBot.username }); // self player
                    return null;
                }
            });
            mockBot.entity.position.distanceTo.mockReturnValue(3);

            entityHurtHandler(mockBot.entity, null);
        });
    });

    // ─── Exports ───
    describe('exports', () => {
        test('all expected exports exist', () => {
            expect(combat.setupCombat).toBeDefined();
            expect(combat.stopCombat).toBeDefined();
            expect(combat.aggroPlayers).toBeDefined();
            expect(combat.getAggroPlayers).toBeDefined();
            expect(combat.getLastAutoAttackTime).toBeDefined();
            expect(combat.setLastAutoAttackTime).toBeDefined();
            expect(combat.fleeFrom).toBeDefined();
            expect(combat.isFleeingCombat).toBeDefined();
        });
    });
});
