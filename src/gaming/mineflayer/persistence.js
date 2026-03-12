/**
 * Persistence module — load/save protected zones, locations, blueprints.
 */

const fs = require('fs');
const path = require('path');

const ZONES_FILE = './memory/public/protected_zones.json';
const LOCATIONS_FILE = './memory/public/saved_locations.json';
const BLUEPRINTS_FILE = './memory/public/blueprints.json';

// === Mutable state ===
let protectedZones = [];
let savedLocations = {};
let blueprints = {};

// === Helper: ensure dir and write JSON ===
function writeJson(filePath, data) {
    try {
        const dir = path.dirname(filePath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
    } catch (e) {
        console.error(`[ERROR] Could not save ${filePath}: ${e.message}`);
    }
}

function readJson(filePath, fallback) {
    try {
        if (fs.existsSync(filePath)) {
            return JSON.parse(fs.readFileSync(filePath, 'utf8'));
        }
    } catch (e) {
        console.error(`[WARN] Could not load ${filePath}: ${e.message}`);
    }
    return fallback;
}

// === Protected Zones ===
function loadProtectedZones() {
    protectedZones = readJson(ZONES_FILE, []);
    console.error(`[INFO] Loaded ${protectedZones.length} protected zones`);
}

function saveProtectedZones() {
    writeJson(ZONES_FILE, protectedZones);
    console.error(`[INFO] Saved ${protectedZones.length} protected zones`);
}

function getProtectedZones() { return protectedZones; }
function setProtectedZones(zones) { protectedZones = zones; }

function isBlockProtected(blockPos) {
    for (const zone of protectedZones) {
        const dist = Math.sqrt(
            Math.pow(blockPos.x - zone.x, 2) +
            Math.pow(blockPos.y - zone.y, 2) +
            Math.pow(blockPos.z - zone.z, 2)
        );
        if (dist <= zone.radius) return zone;
    }
    return null;
}

// === Saved Locations ===
function loadSavedLocations() {
    savedLocations = readJson(LOCATIONS_FILE, {});
    console.error(`[INFO] Loaded ${Object.keys(savedLocations).length} saved locations`);
}

function saveSavedLocations() {
    writeJson(LOCATIONS_FILE, savedLocations);
}

function getSavedLocations() { return savedLocations; }
function setSavedLocations(locs) { savedLocations = locs; }

// === Blueprints ===
function loadBlueprints() {
    blueprints = readJson(BLUEPRINTS_FILE, {});
    console.error(`[INFO] Loaded ${Object.keys(blueprints).length} blueprints`);
}

function saveBlueprints() {
    writeJson(BLUEPRINTS_FILE, blueprints);
}

function getBlueprints() { return blueprints; }
function setBlueprints(bp) { blueprints = bp; }

// Load on import
loadProtectedZones();
loadSavedLocations();
loadBlueprints();

module.exports = {
    loadProtectedZones, saveProtectedZones, getProtectedZones, setProtectedZones,
    isBlockProtected,
    loadSavedLocations, saveSavedLocations, getSavedLocations, setSavedLocations,
    loadBlueprints, saveBlueprints, getBlueprints, setBlueprints
};
