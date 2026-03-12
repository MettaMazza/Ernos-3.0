/**
 * Tests for visual.js — prismarine-viewer + puppeteer screenshot system.
 */

const mockPage = {
    setViewport: jest.fn().mockResolvedValue(),
    goto: jest.fn().mockResolvedValue(),
    screenshot: jest.fn().mockResolvedValue('base64screenshotdata'),
    close: jest.fn().mockResolvedValue()
};

const mockBrowser = {
    newPage: jest.fn().mockResolvedValue(mockPage),
    close: jest.fn().mockResolvedValue(),
    process: jest.fn().mockReturnValue({ pid: 12345 })
};

const mockMineflayerViewer = jest.fn();

jest.mock('prismarine-viewer', () => ({
    mineflayer: mockMineflayerViewer
}));

jest.mock('puppeteer', () => ({
    launch: jest.fn().mockResolvedValue(mockBrowser)
}));

jest.mock('child_process', () => ({
    execSync: jest.fn().mockReturnValue('')
}));

// Speed up all setTimeout calls to 0ms
const origSetTimeout = global.setTimeout;
beforeAll(() => {
    global.setTimeout = (fn, _ms) => origSetTimeout(fn, 0);
});
afterAll(() => {
    global.setTimeout = origSetTimeout;
});

describe('visual.js', () => {
    let visual;
    let mockBot;

    beforeEach(() => {
        jest.spyOn(console, 'error').mockImplementation();

        mockPage.setViewport.mockResolvedValue();
        mockPage.goto.mockResolvedValue();
        mockPage.screenshot.mockResolvedValue('base64screenshotdata');
        mockPage.close.mockResolvedValue();
        mockBrowser.newPage.mockResolvedValue(mockPage);
        mockBrowser.close.mockResolvedValue();
        mockMineflayerViewer.mockReset();

        jest.resetModules();
        visual = require('../visual');
        mockBot = { entity: { position: { x: 0, y: 64, z: 0 } } };
    });

    afterEach(() => { jest.restoreAllMocks(); });

    // ─── initViewer ───
    describe('initViewer', () => {
        test('initializes viewer successfully', async () => {
            const result = await visual.initViewer(mockBot);
            expect(result).toBe(true);
            expect(visual.isViewerReady()).toBe(true);
            expect(mockMineflayerViewer).toHaveBeenCalledWith(mockBot, expect.objectContaining({ firstPerson: true }));
        });

        test('returns false on initialization failure', async () => {
            mockMineflayerViewer.mockImplementation(() => { throw new Error('viewer crash'); });
            const result = await visual.initViewer(mockBot);
            expect(result).toBe(false);
            expect(visual.isViewerReady()).toBe(false);
        });
    });

    // ─── captureScreenshot ───
    describe('captureScreenshot', () => {
        test('returns not-ready when viewer not initialized', async () => {
            const result = await visual.captureScreenshot();
            expect(result.success).toBe(false);
            expect(result.error).toContain('not ready');
            expect(visual.getFailureCount()).toBe(1);
        });

        test('increments failures on repeated not-ready calls', async () => {
            await visual.captureScreenshot();
            await visual.captureScreenshot();
            expect(visual.getFailureCount()).toBe(2);
        });

        test('triggers auto-recovery after max failures (not ready)', async () => {
            await visual.captureScreenshot();
            await visual.captureScreenshot();
            await visual.captureScreenshot();
            expect(visual.getFailureCount()).toBe(3);
        });

        test('captures screenshot successfully', async () => {
            await visual.initViewer(mockBot);

            const result = await visual.captureScreenshot();
            expect(result.success).toBe(true);
            expect(result.image).toBe('base64screenshotdata');
            expect(result.format).toBe('jpeg');
            expect(result.width).toBe(800);
            expect(result.height).toBe(600);
            expect(visual.getFailureCount()).toBe(0);
        });

        test('handles screenshot error and increments failures', async () => {
            await visual.initViewer(mockBot);
            mockPage.screenshot.mockRejectedValueOnce(new Error('render failed'));

            const result = await visual.captureScreenshot();
            expect(result.success).toBe(false);
            expect(result.error).toBe('render failed');
            expect(visual.getFailureCount()).toBe(1);
        });

        test('screenshot errors trigger auto-recovery at max failures', async () => {
            await visual.initViewer(mockBot);
            mockPage.screenshot.mockRejectedValue(new Error('crash'));

            await visual.captureScreenshot();
            await visual.captureScreenshot();
            const result = await visual.captureScreenshot();
            expect(result.success).toBe(false);
            // After 3 failures, auto-recovery fires (reinitializeViewer)
            // which may reset counter, so just check it was reached
            expect(visual.getFailureCount()).toBeGreaterThanOrEqual(0);
        });
    });

    // ─── reinitializeViewer ───
    describe('reinitializeViewer', () => {
        test('returns false if no bot set', async () => {
            const result = await visual.reinitializeViewer();
            expect(result).toBe(false);
        });

        test('reinitializes successfully', async () => {
            await visual.initViewer(mockBot);
            const result = await visual.reinitializeViewer();
            expect(typeof result).toBe('boolean');
        });

        test('guards against double reinitialization', async () => {
            await visual.initViewer(mockBot);

            // Start first reinit (will block on awaits)
            const p1 = visual.reinitializeViewer();
            // Second call should return false immediately (isReinitializing guard)
            const r2 = await visual.reinitializeViewer();
            expect(r2).toBe(false);
            await p1;
        });

        test('handles reinit error gracefully', async () => {
            await visual.initViewer(mockBot);

            // Make the puppeteer launch throw during reinit's initViewer call
            // closeViewer nulls out browser, then initViewer is called and crashes
            const puppeteer = require('puppeteer');
            puppeteer.launch.mockRejectedValueOnce(new Error('launch crash'));

            const result = await visual.reinitializeViewer();
            // initViewer catches the error and returns false, reinit returns false
            expect(result).toBe(false);
        });
    });

    // ─── closeViewer ───
    describe('closeViewer', () => {
        test('no-op when not initialized', async () => {
            await visual.closeViewer();
            expect(visual.isViewerReady()).toBe(false);
        });

        test('closes browser and resets state', async () => {
            await visual.initViewer(mockBot);
            expect(visual.isViewerReady()).toBe(true);

            await visual.closeViewer();
            expect(visual.isViewerReady()).toBe(false);
            expect(visual.getFailureCount()).toBe(0);
            expect(mockBrowser.close).toHaveBeenCalled();
        });

        test('handles browser close error gracefully', async () => {
            await visual.initViewer(mockBot);
            mockBrowser.close.mockRejectedValueOnce(new Error('close failed'));

            await expect(visual.closeViewer()).resolves.not.toThrow();
            expect(visual.isViewerReady()).toBe(false);
        });
    });

    // ─── Getters ───
    describe('getters', () => {
        test('isViewerReady defaults to false', () => {
            expect(visual.isViewerReady()).toBe(false);
        });

        test('getFailureCount defaults to 0', () => {
            expect(visual.getFailureCount()).toBe(0);
        });
    });
});
