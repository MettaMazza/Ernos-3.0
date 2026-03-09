"""
Visualization Tool — v3.3 Mycelium Network.

Registered tool that lets Ernos start/stop the KG Visualizer,
capture high-quality screenshots, and share with users.
"""
import logging
import asyncio
import os
from pathlib import Path
from src.tools.registry import ToolRegistry

logger = logging.getLogger("Tools.Visualization")

# Track singleton server instance
_server_instance = None

# Screenshot output directory
SCREENSHOT_DIR = Path("memory/system/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def _capture_screenshot(url: str = "http://127.0.0.1:8742?view=full&zoom=3000", wait_ms: int = 10000) -> str:
    """
    Capture a high-quality screenshot of the KG visualizer using Playwright.
    
    Args:
        url: URL to screenshot
        wait_ms: Time to wait for 3D graph to render before capturing
    
    Returns:
        Absolute path to the saved PNG file
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")
    
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = SCREENSHOT_DIR / f"kg_visualizer_{timestamp}.png"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        
        await page.goto(url, wait_until="networkidle")
        
        # Wait for the 3D force graph to render and settle
        await page.wait_for_timeout(wait_ms)
        
        await page.screenshot(
            path=str(screenshot_path),
            full_page=False,
            type="png"
        )
        
        await browser.close()
    
    logger.info(f"KG screenshot captured: {screenshot_path}")
    return str(screenshot_path.resolve())


@ToolRegistry.register(
    name="manage_kg_visualizer",
    description="Start or stop the 3D Knowledge Graph Visualizer, or capture a screenshot. "
                "Actions: start, stop, status, screenshot."
)
async def manage_kg_visualizer(
    action: str = "status",
    **kwargs
) -> str:
    """
    Manage the 3D Knowledge Graph Visualizer.

    Actions:
    - start: Launch the visualization server (localhost:8742)
    - stop: Shut down the visualization server
    - status: Check if the visualizer is running
    - screenshot: Capture a high-quality screenshot of the visualizer and return the file path.
                   If the visualizer is not running, starts it first, captures, then stops.

    The visualizer shows all KG nodes and relationships in an
    interactive 3D force-directed graph, color-coded by cognitive layer.
    """
    global _server_instance
    bot = kwargs.get("bot")

    def _port_in_use(port=8742):
        """Check if port is already bound (standalone visualizer running)."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    if action == "start":
        if _server_instance is not None or _port_in_use():
            return "✅ KG Visualizer is already running at http://127.0.0.1:8742"

        if not bot:
            return "❌ Error: No bot context available."

        try:
            from src.visualization.server import KGVisualizationServer
            _server_instance = KGVisualizationServer(bot)
            await _server_instance.start()
            return (
                "✅ KG Visualizer started!\n"
                "🔗 Open http://127.0.0.1:8742 in your browser.\n"
                "Features:\n"
                "• 3D force-directed graph of all KG nodes\n"
                "• Color-coded by cognitive layer\n"
                "• Filter by scope (Public/Private/Core)\n"
                "• Click nodes to focus, hover for details\n"
                "• Quarantined entries shown in red"
            )
        except ImportError:
            return "❌ aiohttp not installed. Run: pip install aiohttp"
        except Exception as e:
            _server_instance = None
            logger.error(f"Failed to start visualizer: {e}")
            return f"❌ Failed to start: {e}"

    elif action == "stop":
        if _server_instance is None:
            return "ℹ️ KG Visualizer is not running."

        try:
            await _server_instance.stop()
            _server_instance = None
            return "✅ KG Visualizer stopped."
        except Exception as e:
            logger.error(f"Failed to stop visualizer: {e}")
            return f"❌ Failed to stop: {e}"

    elif action == "status":
        if _server_instance is not None or _port_in_use():
            return "✅ KG Visualizer is running at http://127.0.0.1:8742"
        return "⏹️ KG Visualizer is not running. Use action='start' to launch it."

    elif action == "screenshot":
        # Auto-start if not running (and standalone isn't either)
        auto_started = False
        if _server_instance is None and not _port_in_use():
            if not bot:
                return "❌ Error: No bot context available."
            try:
                from src.visualization.server import KGVisualizationServer
                _server_instance = KGVisualizationServer(bot)
                await _server_instance.start()
                auto_started = True
                # Give server a moment to fully start
                await asyncio.sleep(1)
            except Exception as e:
                _server_instance = None
                return f"❌ Failed to start visualizer for screenshot: {e}"

        try:
            screenshot_path = await _capture_screenshot()
            result = f"📸 SCREENSHOT_FILE:{screenshot_path}\n🔗 Visualizer URL: http://127.0.0.1:8742"
            if auto_started:
                result += "\n(Visualizer was auto-started for this capture)"
            return result
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return f"❌ Screenshot failed: {e}"

    else:
        return f"❌ Unknown action: '{action}'. Valid: start, stop, status, screenshot"
