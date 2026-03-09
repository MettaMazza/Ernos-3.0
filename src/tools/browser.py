import logging
import asyncio
from .registry import ToolRegistry
from .web import _is_safe_url
from playwright.async_api import async_playwright
import random

logger = logging.getLogger("Tools.Browser")

@ToolRegistry.register(name="browse_interactive", description="Browse a website using a real browser (supports JS).")
async def browse_interactive(url: str, **kwargs) -> str:
    """
    Visits a URL using a headless browser (Playwright), waits for content to load,
    and returns the text content. Useful for JavaScript-heavy sites.
    """
    if not _is_safe_url(url):
        return "Error: URL blocked — cannot access private/internal network addresses."
    try:
        async with async_playwright() as p:
            # Launch browser with anti-bot measures (random user agent, etc.)
            browser = await p.chromium.launch(headless=True)
            
            # Use a realistic user agent
            user_agents = [
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
            context = await browser.new_context(
                user_agent=random.choice(user_agents),
                viewport={"width": 1280, "height": 720}
            )
            
            page = await context.new_page()
            
            logger.info(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait a bit for dynamic content if networkidle isn't enough
            await page.wait_for_timeout(2000)
            
            title = await page.title()
            
            # Extract text using evaluation to get visible text
            text = await page.evaluate("() => document.body.innerText")
            
            # Cleanup
            await browser.close()
            
            # Format output
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = "\n".join(lines)
            
            return f"Title: {title}\nURL: {url}\n\n[CONTENT START]\n{clean_text}\n[CONTENT END]"
            
    except Exception as e:
        logger.error(f"Browser Error: {e}")
        return f"Browser Error: {str(e)}"
