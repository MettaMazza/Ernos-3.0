/**
 * Visual Perception Module for Mineflayer
 * 
 * Uses prismarine-viewer for 3D rendering and puppeteer for screenshots.
 * Provides get_screenshot command that returns base64 PNG.
 * Includes auto-recovery: restarts viewer after 3 consecutive failures.
 */

let viewer = null;
let browser = null;
let page = null;
let viewerReady = false;
let viewerPort = 3007;
let currentBot = null;

// Auto-recovery tracking
let consecutiveFailures = 0;
const MAX_FAILURES_BEFORE_RESTART = 3;
let isReinitializing = false;

/**
 * Initialize the prismarine-viewer for visual perception.
 * @param {object} bot - Mineflayer bot instance
 * @returns {Promise<boolean>}
 */
async function initViewer(bot) {
    currentBot = bot;
    consecutiveFailures = 0;

    try {
        const mineflayerViewer = require('prismarine-viewer').mineflayer;
        const puppeteer = require('puppeteer');

        // Start viewer on port
        mineflayerViewer(bot, {
            port: viewerPort,
            firstPerson: true
        });

        // Wait for viewer to be ready
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Launch headless browser
        browser = await puppeteer.launch({
            headless: 'new',
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });

        page = await browser.newPage();
        await page.setViewport({ width: 800, height: 600 });
        await page.goto(`http://localhost:${viewerPort}`, { waitUntil: 'networkidle2', timeout: 30000 });

        // Wait for canvas to render
        await new Promise(resolve => setTimeout(resolve, 3000));

        viewerReady = true;
        console.error('[Visual] Viewer initialized successfully');
        return true;

    } catch (err) {
        console.error('[Visual] Failed to initialize viewer:', err.message);
        viewerReady = false;
        return false;
    }
}

/**
 * Reinitialize viewer after failures.
 */
async function reinitializeViewer() {
    if (isReinitializing || !currentBot) return false;

    isReinitializing = true;
    console.error('[Visual] Auto-recovery: Reinitializing viewer...');

    try {
        await closeViewer();
        await new Promise(resolve => setTimeout(resolve, 1000));
        const result = await initViewer(currentBot);
        console.error(`[Visual] Reinit result: ${result ? 'SUCCESS' : 'FAILED'}`);
        return result;
    } catch (err) {
        console.error('[Visual] Reinit error:', err.message);
        return false;
    } finally {
        isReinitializing = false;
    }
}

/**
 * Capture a screenshot of the current view.
 * Includes auto-recovery: restarts viewer after 3 consecutive failures.
 * @returns {Promise<{success: boolean, image?: string, error?: string}>}
 */
async function captureScreenshot() {
    if (!viewerReady || !page) {
        consecutiveFailures++;
        console.error(`[Visual] Not ready (failures: ${consecutiveFailures}/${MAX_FAILURES_BEFORE_RESTART})`);

        // Auto-recovery trigger
        if (consecutiveFailures >= MAX_FAILURES_BEFORE_RESTART) {
            console.error('[Visual] Max failures reached, triggering auto-recovery');
            reinitializeViewer(); // Fire and forget
        }

        return { success: false, error: 'Viewer not ready' };
    }

    try {
        // Capture screenshot as base64
        const screenshot = await page.screenshot({
            encoding: 'base64',
            type: 'jpeg',
            quality: 70
        });

        // Reset failure counter on success
        consecutiveFailures = 0;

        return {
            success: true,
            image: screenshot,
            format: 'jpeg',
            width: 800,
            height: 600
        };

    } catch (err) {
        consecutiveFailures++;
        console.error(`[Visual] Screenshot error (failures: ${consecutiveFailures}): ${err.message}`);

        // Auto-recovery trigger
        if (consecutiveFailures >= MAX_FAILURES_BEFORE_RESTART) {
            console.error('[Visual] Max failures reached, triggering auto-recovery');
            reinitializeViewer(); // Fire and forget
        }

        return { success: false, error: err.message };
    }
}

/**
 * Cleanup viewer resources.
 */
async function closeViewer() {
    if (browser) {
        try {
            await browser.close();
        } catch (e) {
            console.error('[Visual] Browser close error:', e.message);
        }
        browser = null;
        page = null;
    }
    viewerReady = false;
    consecutiveFailures = 0;
}

/**
 * Check if viewer is ready.
 */
function isViewerReady() {
    return viewerReady;
}

/**
 * Get failure count for monitoring.
 */
function getFailureCount() {
    return consecutiveFailures;
}

module.exports = {
    initViewer,
    reinitializeViewer,
    captureScreenshot,
    closeViewer,
    isViewerReady,
    getFailureCount
};
