/**
 * Tests for persistence.js — load/save zones, locations, blueprints.
 */

jest.mock('fs');

beforeAll(() => { jest.spyOn(console, 'error').mockImplementation(); });
afterAll(() => { jest.restoreAllMocks(); });

describe('persistence.js', () => {
    let persistence;
    let fs;

    beforeEach(() => {
        jest.resetModules();
        jest.mock('fs');
        fs = require('fs');
        fs.existsSync = jest.fn().mockReturnValue(false);
        fs.readFileSync = jest.fn().mockReturnValue('{}');
        fs.writeFileSync = jest.fn();
        fs.mkdirSync = jest.fn();
        console.error = jest.fn();
        persistence = require('../persistence');
    });

    // ─── loadProtectedZones (tested via load-on-import) ───
    describe('loadProtectedZones', () => {
        test('loads empty array when file missing', () => {
            const zones = persistence.getProtectedZones();
            expect(Array.isArray(zones)).toBe(true);
            expect(zones).toHaveLength(0);
        });

        test('loads zones from file', () => {
            jest.resetModules();
            jest.mock('fs');
            const fs2 = require('fs');
            fs2.existsSync = jest.fn().mockReturnValue(true);
            fs2.readFileSync = jest.fn().mockReturnValue(JSON.stringify([{ x: 1, y: 2, z: 3, radius: 50, owner: 'test' }]));
            fs2.writeFileSync = jest.fn();
            fs2.mkdirSync = jest.fn();

            const p2 = require('../persistence');
            expect(p2.getProtectedZones()).toHaveLength(1);
            expect(p2.getProtectedZones()[0].owner).toBe('test');
        });

        test('handles corrupt JSON gracefully', () => {
            jest.resetModules();
            jest.mock('fs');
            const fs3 = require('fs');
            fs3.existsSync = jest.fn().mockReturnValue(true);
            fs3.readFileSync = jest.fn().mockReturnValue('not json!!!');
            fs3.writeFileSync = jest.fn();
            fs3.mkdirSync = jest.fn();

            const p3 = require('../persistence');
            expect(p3.getProtectedZones()).toEqual([]);
        });
    });

    describe('saveProtectedZones', () => {
        test('writes JSON file', () => {
            persistence.getProtectedZones().push({ x: 10, y: 20, z: 30, radius: 50, owner: 'admin' });
            persistence.saveProtectedZones();
            expect(fs.writeFileSync).toHaveBeenCalled();
        });

        test('creates directory if needed', () => {
            fs.existsSync.mockReturnValue(false);
            persistence.saveProtectedZones();
            expect(fs.mkdirSync).toHaveBeenCalled();
        });
    });

    describe('isBlockProtected', () => {
        test('returns null for unprotected block', () => {
            expect(persistence.isBlockProtected({ x: 1000, y: 64, z: 1000 })).toBeNull();
        });

        test('returns zone for protected block', () => {
            persistence.getProtectedZones().push({ x: 0, y: 64, z: 0, radius: 10, owner: 'test' });
            const result = persistence.isBlockProtected({ x: 5, y: 64, z: 5 });
            expect(result).not.toBeNull();
            expect(result.owner).toBe('test');
        });

        test('returns null for block outside radius', () => {
            persistence.getProtectedZones().push({ x: 0, y: 64, z: 0, radius: 5, owner: 'test' });
            expect(persistence.isBlockProtected({ x: 100, y: 64, z: 100 })).toBeNull();
        });
    });

    describe('setProtectedZones', () => {
        test('replaces zones array', () => {
            persistence.setProtectedZones([{ x: 1, y: 2, z: 3 }]);
            expect(persistence.getProtectedZones()).toHaveLength(1);
        });
    });

    // ─── Saved Locations ───
    describe('savedLocations', () => {
        test('loads empty object when file missing', () => {
            expect(typeof persistence.getSavedLocations()).toBe('object');
        });

        test('setSavedLocations replaces', () => {
            persistence.setSavedLocations({ home: { x: 1 } });
            expect(persistence.getSavedLocations().home.x).toBe(1);
        });

        test('saveSavedLocations writes file', () => {
            persistence.saveSavedLocations();
            expect(fs.writeFileSync).toHaveBeenCalled();
        });
    });

    describe('loadSavedLocations from file', () => {
        test('loads locations from JSON file', () => {
            jest.resetModules();
            jest.mock('fs');
            const fs4 = require('fs');
            fs4.existsSync = jest.fn().mockReturnValue(true);
            fs4.readFileSync = jest.fn().mockReturnValue(JSON.stringify({ base: { x: 10, y: 64, z: 20 } }));
            fs4.writeFileSync = jest.fn();
            fs4.mkdirSync = jest.fn();

            const p4 = require('../persistence');
            expect(p4.getSavedLocations().base.x).toBe(10);
        });
    });

    // ─── Blueprints ───
    describe('blueprints', () => {
        test('loads empty object when file missing', () => {
            expect(typeof persistence.getBlueprints()).toBe('object');
        });

        test('setBlueprints replaces', () => {
            persistence.setBlueprints({ house: { blocks: [] } });
            expect(persistence.getBlueprints().house).toBeDefined();
        });

        test('saveBlueprints writes file', () => {
            persistence.saveBlueprints();
            expect(fs.writeFileSync).toHaveBeenCalled();
        });
    });

    describe('loadBlueprints from file', () => {
        test('loads blueprints from JSON file', () => {
            jest.resetModules();
            jest.mock('fs');
            const fs5 = require('fs');
            fs5.existsSync = jest.fn().mockReturnValue(true);
            fs5.readFileSync = jest.fn().mockReturnValue(JSON.stringify({ tower: { blocks: [1, 2, 3] } }));
            fs5.writeFileSync = jest.fn();
            fs5.mkdirSync = jest.fn();

            const p5 = require('../persistence');
            expect(p5.getBlueprints().tower.blocks).toHaveLength(3);
        });
    });

    describe('writeJson error handling', () => {
        test('handles write error gracefully', () => {
            fs.writeFileSync.mockImplementation(() => { throw new Error('disk full'); });
            fs.existsSync.mockReturnValue(true);
            expect(() => persistence.saveProtectedZones()).not.toThrow();
        });
    });
});
