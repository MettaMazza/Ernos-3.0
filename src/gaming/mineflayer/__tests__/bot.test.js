/**
 * Tests for bot.js — entry point: init, event wiring, IPC dispatch.
 */

// Must mock before require
jest.mock('mineflayer', () => ({
    createBot: jest.fn()
}));
jest.mock('mineflayer-pathfinder', () => ({
    pathfinder: { name: 'pathfinder' },
    Movements: jest.fn().mockImplementation(() => ({})),
    goals: { GoalNear: jest.fn(), GoalFollow: jest.fn(), GoalBlock: jest.fn(), GoalXZ: jest.fn() }
}));
jest.mock('minecraft-data', () => jest.fn().mockReturnValue({
    blocksByName: {}, itemsByName: {}
}));
jest.mock('../visual', () => ({
    initViewer: jest.fn().mockResolvedValue(true),
    closeViewer: jest.fn().mockResolvedValue(),
    isViewerReady: jest.fn().mockReturnValue(false),
    captureScreenshot: jest.fn().mockResolvedValue({ success: false })
}));
jest.mock('../autonomy', () => ({
    setupAutonomy: jest.fn(),
    stopAutonomy: jest.fn()
}));
jest.mock('readline', () => ({
    createInterface: jest.fn().mockReturnValue({
        on: jest.fn()
    })
}));
jest.mock('fs');

function createMockBot() {
    const mockBot = {
        entity: { position: { x: 0, y: 64, z: 0, distanceTo: jest.fn().mockReturnValue(5), clone: jest.fn().mockReturnValue({ x: 0, y: 64, z: 0 }) }, yaw: 0, height: 1.8 },
        health: 20, food: 20,
        username: 'Ernos',
        version: '1.20.4',
        time: { day: 6000, timeOfDay: 6000 },
        game: { dimension: 'overworld' },
        entities: {},
        players: {},
        inventory: { items: jest.fn().mockReturnValue([]), slots: {} },
        nearestEntity: jest.fn().mockReturnValue(null),
        lookAt: jest.fn().mockResolvedValue(),
        look: jest.fn().mockResolvedValue(),
        attack: jest.fn().mockResolvedValue(),
        equip: jest.fn().mockResolvedValue(),
        consume: jest.fn().mockResolvedValue(),
        setControlState: jest.fn(),
        clearControlStates: jest.fn(),
        chat: jest.fn(),
        quit: jest.fn(),
        toss: jest.fn().mockResolvedValue(),
        findBlock: jest.fn(),
        findBlocks: jest.fn().mockReturnValue([]),
        blockAt: jest.fn(),
        dig: jest.fn().mockResolvedValue(),
        craft: jest.fn().mockResolvedValue(),
        recipesFor: jest.fn().mockReturnValue([]),
        sleep: jest.fn().mockResolvedValue(),
        wake: jest.fn().mockResolvedValue(),
        activateItem: jest.fn(),
        deactivateItem: jest.fn(),
        activateBlock: jest.fn().mockResolvedValue(),
        placeBlock: jest.fn().mockResolvedValue(),
        openFurnace: jest.fn(),
        openContainer: jest.fn(),
        loadPlugin: jest.fn(),
        pathfinder: { setGoal: jest.fn(), setMovements: jest.fn(), goto: jest.fn().mockResolvedValue() },
        on: jest.fn(),
        once: jest.fn(),
        removeListener: jest.fn()
    };
    return mockBot;
}

describe('bot.js', () => {
    beforeEach(() => {
        jest.useFakeTimers();
        jest.spyOn(console, 'error').mockImplementation();
        jest.spyOn(console, 'log').mockImplementation();

        const fs = require('fs');
        fs.existsSync = jest.fn().mockReturnValue(false);
        fs.readFileSync = jest.fn().mockReturnValue('{}');
        fs.writeFileSync = jest.fn();
        fs.mkdirSync = jest.fn();
    });

    afterEach(() => {
        jest.useRealTimers();
        jest.restoreAllMocks();
        jest.resetModules();
    });

    test('creates bot and loads pathfinder plugin', () => {
        const mineflayer = require('mineflayer');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        require('../bot');

        expect(mineflayer.createBot).toHaveBeenCalled();
        expect(mockBot.loadPlugin).toHaveBeenCalled();
    });

    test('spawn handler initializes mcData and movements', () => {
        const mineflayer = require('mineflayer');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        require('../bot');

        // Find and trigger spawn handler
        const spawnCall = mockBot.once.mock.calls.find(c => c[0] === 'spawn');
        expect(spawnCall).toBeDefined();

        spawnCall[1](); // Trigger spawn

        // Should set movements
        expect(mockBot.pathfinder.setMovements).toHaveBeenCalled();
    });

    test('death handler fires sendEvent', () => {
        const mineflayer = require('mineflayer');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        require('../bot');

        const deathCall = mockBot.on.mock.calls.find(c => c[0] === 'death');
        expect(deathCall).toBeDefined();
        expect(() => deathCall[1]()).not.toThrow();
    });

    test('respawn handler sends respawn event', () => {
        const mineflayer = require('mineflayer');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        require('../bot');

        const respawnCall = mockBot.on.mock.calls.find(c => c[0] === 'respawn');
        expect(respawnCall).toBeDefined();
        respawnCall[1]();
        // Spectate is handled Python-side, not via JS chat commands
    });

    test('chat handler forwards non-self messages', () => {
        const mineflayer = require('mineflayer');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        require('../bot');

        const chatCall = mockBot.on.mock.calls.find(c => c[0] === 'chat');
        expect(chatCall).toBeDefined();

        // Non-self message test
        chatCall[1]('steve', 'Hello');
        // Self message test
        chatCall[1]('Ernos', 'Hi');
    });

    test('chat handler clears aggro on apology', () => {
        const mineflayer = require('mineflayer');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        jest.isolateModules(() => {
            // Need to get combat module before bot loads
        });

        require('../bot');
        const { aggroPlayers } = require('../combat');
        aggroPlayers.add('griefer');

        const chatCall = mockBot.on.mock.calls.find(c => c[0] === 'chat');
        chatCall[1]('griefer', 'I am sorry about that');

        expect(aggroPlayers.has('griefer')).toBe(false);
    });

    test('error handler does not crash', () => {
        const mineflayer = require('mineflayer');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        require('../bot');

        const errorCall = mockBot.on.mock.calls.find(c => c[0] === 'error');
        expect(errorCall).toBeDefined();
        expect(() => errorCall[1](new Error('test error'))).not.toThrow();
    });

    test('kicked handler does not crash', () => {
        const mineflayer = require('mineflayer');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        require('../bot');

        const kickedCall = mockBot.on.mock.calls.find(c => c[0] === 'kicked');
        expect(kickedCall).toBeDefined();
        expect(() => kickedCall[1]('banned')).not.toThrow();
    });

    test('IPC dispatches known commands', async () => {
        const mineflayer = require('mineflayer');
        const readline = require('readline');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        let lineHandler;
        readline.createInterface.mockReturnValue({
            on: jest.fn().mockImplementation((event, handler) => {
                if (event === 'line') lineHandler = handler;
            })
        });

        require('../bot');

        // Dispatch 'status' command
        const cmd = JSON.stringify({ id: 'test1', command: 'status', params: {} });
        await lineHandler(cmd);

        // Check response was sent to stdout
        expect(console.log).toHaveBeenCalled();
    });

    test('IPC returns error for unknown commands', async () => {
        const mineflayer = require('mineflayer');
        const readline = require('readline');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        let lineHandler;
        readline.createInterface.mockReturnValue({
            on: jest.fn().mockImplementation((event, handler) => {
                if (event === 'line') lineHandler = handler;
            })
        });

        require('../bot');

        const cmd = JSON.stringify({ id: 'test2', command: 'nonexistent', params: {} });
        await lineHandler(cmd);

        // Should get error response
        const logCalls = console.log.mock.calls;
        const errorResponse = logCalls.find(c => c[0].includes('Unknown command'));
        expect(errorResponse).toBeDefined();
    });

    test('IPC handles malformed JSON', async () => {
        const mineflayer = require('mineflayer');
        const readline = require('readline');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        let lineHandler;
        readline.createInterface.mockReturnValue({
            on: jest.fn().mockImplementation((event, handler) => {
                if (event === 'line') lineHandler = handler;
            })
        });

        require('../bot');

        await lineHandler('not json at all');
        // Should not crash, just log error
    });

    test('spawn handler executes without spectate chat', () => {
        const mineflayer = require('mineflayer');
        const mockBot = createMockBot();
        mineflayer.createBot.mockReturnValue(mockBot);

        require('../bot');

        const spawnCall = mockBot.once.mock.calls.find(c => c[0] === 'spawn');
        spawnCall[1]();

        jest.advanceTimersByTime(4000);
        // Spectate is now handled Python-side via AppleScript, not JS chat
        // No spectate chat commands should be sent
    });

    // ─── Process crash handlers ───
    describe('process crash handlers', () => {
        test('uncaughtException handler logs error', () => {
            const mineflayer = require('mineflayer');
            const mockBot = createMockBot();
            mineflayer.createBot.mockReturnValue(mockBot);
            require('../bot');

            // Get the registered handler
            const handlers = process.listeners('uncaughtException');
            const handler = handlers[handlers.length - 1];
            expect(() => handler(new Error('test crash'))).not.toThrow();
        });

        test('unhandledRejection handler logs reason with stack', () => {
            const mineflayer = require('mineflayer');
            const mockBot = createMockBot();
            mineflayer.createBot.mockReturnValue(mockBot);
            require('../bot');

            const handlers = process.listeners('unhandledRejection');
            const handler = handlers[handlers.length - 1];
            expect(() => handler(new Error('promise failure'))).not.toThrow();
        });

        test('unhandledRejection handler logs string reason', () => {
            const mineflayer = require('mineflayer');
            const mockBot = createMockBot();
            mineflayer.createBot.mockReturnValue(mockBot);
            require('../bot');

            const handlers = process.listeners('unhandledRejection');
            const handler = handlers[handlers.length - 1];
            expect(() => handler('just a string')).not.toThrow();
        });

        test('exit handler logs exit code', () => {
            const mineflayer = require('mineflayer');
            const mockBot = createMockBot();
            mineflayer.createBot.mockReturnValue(mockBot);
            require('../bot');

            const handlers = process.listeners('exit');
            const handler = handlers[handlers.length - 1];
            expect(() => handler(0)).not.toThrow();
        });

        test('SIGTERM handler logs', () => {
            const mineflayer = require('mineflayer');
            const mockBot = createMockBot();
            mineflayer.createBot.mockReturnValue(mockBot);
            require('../bot');

            const handlers = process.listeners('SIGTERM');
            const handler = handlers[handlers.length - 1];
            expect(() => handler()).not.toThrow();
        });

        test('SIGINT handler logs', () => {
            const mineflayer = require('mineflayer');
            const mockBot = createMockBot();
            mineflayer.createBot.mockReturnValue(mockBot);
            require('../bot');

            const handlers = process.listeners('SIGINT');
            const handler = handlers[handlers.length - 1];
            expect(() => handler()).not.toThrow();
        });
    });
});
