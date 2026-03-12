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
        // Check dependencies before attempting init
        let mineflayerViewer, puppeteer;
        try {
            mineflayerViewer = require('prismarine-viewer').mineflayer;
        } catch (depErr) {
            console.error(`[Visual] FATAL: prismarine-viewer not installed: ${depErr.message}`);
            console.error('[Visual] Run: npm install prismarine-viewer');
            viewerReady = false;
            return false;
        }

        try {
            puppeteer = require('puppeteer');
        } catch (depErr) {
            console.error(`[Visual] FATAL: puppeteer not installed: ${depErr.message}`);
            console.error('[Visual] Run: npm install puppeteer && npx puppeteer browsers install chrome');
            viewerReady = false;
            return false;
        }

        // Kill any stale process hogging our viewer port (orphans from previous sessions)
        try {
            const { execSync } = require('child_process');
            const lsofOut = execSync(`lsof -ti :${viewerPort}`, { encoding: 'utf8', timeout: 3000 }).trim();
            if (lsofOut) {
                const pids = lsofOut.split('\n').filter(p => p && p !== String(process.pid));
                if (pids.length > 0) {
                    console.error(`[Visual] Killing stale processes on port ${viewerPort}: ${pids.join(', ')}`);
                    execSync(`kill -9 ${pids.join(' ')}`, { timeout: 3000 });
                    // Brief wait for port release
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            }
        } catch (cleanupErr) {
            // lsof returns exit code 1 if nothing found — that's fine
            if (cleanupErr.status !== 1) {
                console.error(`[Visual] Port cleanup note: ${cleanupErr.message || cleanupErr}`);
            }
        }

        // Start viewer on port
        console.error(`[Visual] Starting prismarine-viewer on port ${viewerPort}...`);
        mineflayerViewer(bot, {
            port: viewerPort,
            firstPerson: true
        });

        // Wait for viewer HTTP server to be ready
        await new Promise(resolve => setTimeout(resolve, 2000));
        console.error('[Visual] Prismarine-viewer started, launching headless browser...');

        // Launch headless browser with explicit error handling
        try {
            browser = await puppeteer.launch({
                headless: 'new',
                args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
            });
            console.error(`[Visual] Puppeteer launched (pid: ${browser.process()?.pid || 'unknown'})`);
        } catch (browserErr) {
            console.error(`[Visual] FATAL: Puppeteer failed to launch: ${browserErr.message}`);
            console.error('[Visual] This usually means Chromium is not installed.');
            console.error('[Visual] Fix: cd src/gaming/mineflayer && npx puppeteer browsers install chrome');
            viewerReady = false;
            return false;
        }

        page = await browser.newPage();
        await page.setViewport({ width: 800, height: 600 });

        console.error(`[Visual] Navigating to http://localhost:${viewerPort}...`);
        await page.goto(`http://localhost:${viewerPort}`, { waitUntil: 'networkidle2', timeout: 30000 });

        // Wait for canvas to render
        await new Promise(resolve => setTimeout(resolve, 3000));

        viewerReady = true;
        console.error('[Visual] ✅ Viewer initialized successfully — screenshots enabled');
        return true;

    } catch (err) {
        console.error(`[Visual] INIT FAILED: ${err.message}`);
        console.error(`[Visual] Stack: ${err.stack}`);
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

        // Auto-recovery: trigger immediately on first failure instead of waiting
        if (currentBot && !isReinitializing) {
            console.error('[Visual] Viewer not ready, triggering immediate auto-recovery');
            const recovered = await reinitializeViewer();
            if (recovered && viewerReady && page) {
                // Retry once after recovery
                try {
                    const screenshot = await page.screenshot({ encoding: 'base64', type: 'jpeg', quality: 70 });
                    consecutiveFailures = 0;
                    return { success: true, image: screenshot, format: 'jpeg', width: 800, height: 600 };
                } catch (retryErr) {
                    console.error(`[Visual] Post-recovery screenshot failed: ${retryErr.message}`);
                }
            }
        }

        return { success: false, error: 'Viewer not ready' };
    }

    try {
        // Reload page if canvas may be stale (after 3+ seconds idle)
        try { await page.reload({ waitUntil: 'networkidle2', timeout: 5000 }); } catch (_) { /* best effort */ }
        await new Promise(resolve => setTimeout(resolve, 500)); // Let canvas render

        // Capture screenshot as base64
        const screenshot = await page.screenshot({
            encoding: 'base64',
            type: 'jpeg',
            quality: 70
        });

        if (!screenshot || screenshot.length === 0) {
            consecutiveFailures++;
            console.error('[Visual] Screenshot returned empty data');
            return { success: false, error: 'Empty screenshot data' };
        }

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
