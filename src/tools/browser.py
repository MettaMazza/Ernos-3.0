"""
Browser Automation Toolkit — Full Playwright-based browser control for Ernos.

Provides 13 tools for complete browser automation:
  browser_open, browser_click, browser_type, browser_screenshot,
  browser_scroll, browser_get_text, browser_navigate, browser_fill_form,
  browser_select, browser_wait, browser_close, browser_evaluate, browser_get_links

Features:
  - Persistent per-user browser sessions (browser stays open across tool calls)
  - Auto-cleanup after 10 minutes of inactivity
  - Screenshots returned as file paths for Discord attachment
  - URL safety enforcement (no localhost/internal network access)
  - Headless by default (runs on server without GUI)
"""

import logging
import asyncio
import os
import time
import tempfile
from pathlib import Path
from typing import Dict, Optional
from .registry import ToolRegistry
from .web import _is_safe_url
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("Tools.Browser")

# ═══════════════════════════════════════════════════════════════════════
# Session Manager — Persistent per-user browser sessions
# ═══════════════════════════════════════════════════════════════════════

SESSION_TIMEOUT = 600  # 10 minutes inactivity timeout
SCREENSHOT_DIR = os.path.join(tempfile.gettempdir(), "ernos_browser_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


class BrowserSession:
    """Manages a single user's browser session."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.last_activity = time.time()
        self._lock = asyncio.Lock()
        self.action_lock = asyncio.Lock()

    async def ensure_open(self) -> Page:
        """Ensure browser is open and return the active page."""
        async with self._lock:
            self.last_activity = time.time()
            if self.page and not self.page.is_closed():
                return self.page

            # Close stale resources if any
            await self._cleanup_resources()

            # Launch fresh session
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )
            self.page = await self.context.new_page()
            logger.info(f"[{self.user_id}] New browser session created")
            return self.page

    async def close(self):
        """Close the session completely."""
        async with self._lock:
            await self._cleanup_resources()
            logger.info(f"[{self.user_id}] Browser session closed")

    async def _cleanup_resources(self):
        """Internal cleanup of browser resources."""
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.last_activity) > SESSION_TIMEOUT


class SessionManager:
    """Manages all active browser sessions with auto-cleanup."""

    def __init__(self):
        self._sessions: Dict[str, BrowserSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    def get_session(self, user_id: str) -> BrowserSession:
        """Get or create a session for a user."""
        if user_id not in self._sessions:
            self._sessions[user_id] = BrowserSession(user_id)
        session = self._sessions[user_id]
        session.last_activity = time.time()

        # Start cleanup loop if not running
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._cleanup_loop())
            except RuntimeError:
                pass

        return session

    async def close_session(self, user_id: str):
        """Close and remove a specific session."""
        if user_id in self._sessions:
            await self._sessions[user_id].close()
            del self._sessions[user_id]

    async def _cleanup_loop(self):
        """Periodically clean up expired sessions."""
        while self._sessions:
            await asyncio.sleep(60)
            expired = [
                uid for uid, s in self._sessions.items() if s.is_expired
            ]
            for uid in expired:
                logger.info(f"[{uid}] Session expired (idle timeout)")
                await self.close_session(uid)
        self._cleanup_task = None


# Global session manager
_manager = SessionManager()



import functools

def serialize_browser_action(func):
    """Decorator to serialize concurrent actions on the same browser session."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        user_id = _get_user_id(**kwargs)
        session = _manager.get_session(user_id)
        async with session.action_lock:
            return await func(*args, **kwargs)
    return wrapper

def _get_user_id(**kwargs) -> str:
    """Extract user_id from tool kwargs."""
    user_id = kwargs.get("user_id", "default")
    agent_id = kwargs.get("agent_id")
    if agent_id:
        return f"{user_id}_{agent_id}"
    return user_id


# ═══════════════════════════════════════════════════════════════════════
# Tool 1: browser_open — Open a URL
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_open",
    description=(
        "Open a URL in a persistent browser session. The browser stays open "
        "across multiple tool calls so you can interact with the page. "
        "Returns the page title and a text preview."
    ),
)
@serialize_browser_action
async def browser_open(url: str, **kwargs) -> str:
    """Open a URL in the browser. Creates a new session if needed."""
    if not _is_safe_url(url):
        return "Error: URL blocked — cannot access private/internal network addresses."

    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as nav_err:
            # Retry HTTP/2 failures with HTTP/1.1 fallback
            if "ERR_HTTP2_PROTOCOL_ERROR" in str(nav_err):
                logger.warning(f"HTTP/2 error for {url}, retrying with HTTP/1.1 fallback...")
                try:
                    cdp = await page.context.new_cdp_session(page)
                    await cdp.send("Network.enable")
                    await cdp.send("Network.setExtraHTTPHeaders", {"headers": {"Connection": "keep-alive"}})
                except Exception:
                    pass  # CDP best-effort
                await page.goto(url, wait_until="commit", timeout=30000)
            else:
                raise
        await page.wait_for_timeout(2000)

        title = await page.title()
        current_url = page.url

        # Get a text preview (first 500 chars)
        text = await page.evaluate("() => document.body.innerText")
        preview = text[:500].strip() if text else "(empty page)"

        return (
            f"✅ Page loaded\n"
            f"Title: {title}\n"
            f"URL: {current_url}\n\n"
            f"[PREVIEW]\n{preview}\n[/PREVIEW]"
        )
    except Exception as e:
        error_msg = str(e)
        if "ERR_HTTP2_PROTOCOL_ERROR" in error_msg:
            logger.error(f"browser_open HTTP/2 error (site may block bots): {url}")
            return f"Error: Site {url} rejected the connection (HTTP/2 protocol error). This site likely blocks automated browsers."
        if "Download is starting" in error_msg:
            logger.info(f"browser_open intercepted download for {url}. Deferring to read_url_content.")
            return f"Error: The URL '{url}' points to a raw file or PDF (Download is starting). Please use the `read_url_content` tool instead to parse this document."
        logger.error(f"browser_open error: {e}")
        return f"Error opening URL: {error_msg}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 2: browser_click — Click an element
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_click",
    description=(
        "Click an element on the current page. Use a CSS selector "
        "(e.g. '#submit-btn', '.nav-link', 'button') or text content "
        "(e.g. 'Sign In', 'Submit'). Returns what happened after the click."
    ),
)
@serialize_browser_action
async def browser_click(selector: str, **kwargs) -> str:
    """Click an element by CSS selector or text content."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        # Try CSS selector first
        try:
            element = page.locator(selector).first
            if await element.count() > 0:
                await element.click(timeout=5000)
                await page.wait_for_timeout(1000)
                title = await page.title()
                return f"✅ Clicked element matching '{selector}'\nPage is now: {title} ({page.url})"
        except Exception:
            pass

        # Try text-based click
        try:
            element = page.get_by_text(selector, exact=False).first
            if await element.count() > 0:
                await element.click(timeout=5000)
                await page.wait_for_timeout(1000)
                title = await page.title()
                return f"✅ Clicked element with text '{selector}'\nPage is now: {title} ({page.url})"
        except Exception:
            pass

        # Try role-based click
        try:
            for role in ["button", "link", "menuitem", "tab"]:
                element = page.get_by_role(role, name=selector).first
                if await element.count() > 0:
                    await element.click(timeout=5000)
                    await page.wait_for_timeout(1000)
                    title = await page.title()
                    return f"✅ Clicked {role} '{selector}'\nPage is now: {title} ({page.url})"
        except Exception:
            pass

        return f"Error: Could not find element matching '{selector}'. Try browser_get_text to see what's on the page."

    except Exception as e:
        logger.error(f"browser_click error: {e}")
        return f"Error clicking: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 3: browser_type — Type text into an input
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_type",
    description=(
        "Type text into an input field on the current page. Specify the "
        "field using a CSS selector (e.g. '#search', 'input[name=email]') "
        "or a label (e.g. 'Email', 'Search'). Optionally press Enter after."
    ),
)
@serialize_browser_action
async def browser_type(
    selector: str, text: str, press_enter: str = "false", **kwargs
) -> str:
    """Type text into an input field."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        should_enter = press_enter.lower() in ("true", "yes", "1")

        # Try CSS selector
        try:
            element = page.locator(selector).first
            if await element.count() > 0:
                await element.fill(text)
                if should_enter:
                    await element.press("Enter")
                    await page.wait_for_timeout(1500)
                return f"✅ Typed '{text}' into '{selector}'" + (
                    " and pressed Enter" if should_enter else ""
                )
        except Exception:
            pass

        # Try label-based
        try:
            element = page.get_by_label(selector).first
            if await element.count() > 0:
                await element.fill(text)
                if should_enter:
                    await element.press("Enter")
                    await page.wait_for_timeout(1500)
                return f"✅ Typed '{text}' into field labeled '{selector}'" + (
                    " and pressed Enter" if should_enter else ""
                )
        except Exception:
            pass

        # Try placeholder
        try:
            element = page.get_by_placeholder(selector).first
            if await element.count() > 0:
                await element.fill(text)
                if should_enter:
                    await element.press("Enter")
                    await page.wait_for_timeout(1500)
                return f"✅ Typed '{text}' into placeholder '{selector}'" + (
                    " and pressed Enter" if should_enter else ""
                )
        except Exception:
            pass

        return f"Error: Could not find input matching '{selector}'."

    except Exception as e:
        logger.error(f"browser_type error: {e}")
        return f"Error typing: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 4: browser_screenshot — Capture the current page
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_screenshot",
    description=(
        "Take a screenshot of the current browser page. Returns the file "
        "path to the screenshot image, which can be sent as a Discord "
        "attachment. Optionally capture just a specific element."
    ),
)
@serialize_browser_action
async def browser_screenshot(selector: str = "", **kwargs) -> str:
    """Take a screenshot and return the file path."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        timestamp = int(time.time())
        filename = f"browser_{user_id}_{timestamp}.png"
        filepath = os.path.join(SCREENSHOT_DIR, filename)

        if selector:
            # Screenshot specific element
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    await element.screenshot(path=filepath)
                    return f"✅ Screenshot of '{selector}' saved\n📎 {filepath}"
            except Exception:
                pass
            return f"Error: Element '{selector}' not found for screenshot."
        else:
            # Full page screenshot
            await page.screenshot(path=filepath, full_page=False)
            title = await page.title()
            return f"✅ Screenshot captured: {title}\n📎 {filepath}"

    except Exception as e:
        logger.error(f"browser_screenshot error: {e}")
        return f"Error taking screenshot: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 5: browser_scroll — Scroll the page
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_scroll",
    description=(
        "Scroll the current page. Direction can be 'down', 'up', 'top', "
        "or 'bottom'. Amount is in pixels (default 500)."
    ),
)
@serialize_browser_action
async def browser_scroll(
    direction: str = "down", amount: str = "500", **kwargs
) -> str:
    """Scroll the page in a direction."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        try:
            px = int(amount)
        except ValueError:
            px = 500

        direction = direction.lower().strip()

        if direction == "top":
            await page.evaluate("window.scrollTo(0, 0)")
        elif direction == "bottom":
            await page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
        elif direction == "up":
            await page.evaluate(f"window.scrollBy(0, -{px})")
        else:  # down
            await page.evaluate(f"window.scrollBy(0, {px})")

        await page.wait_for_timeout(500)

        # Report scroll position
        pos = await page.evaluate(
            "() => ({ y: window.scrollY, max: document.body.scrollHeight - window.innerHeight })"
        )
        return f"✅ Scrolled {direction} ({px}px)\nScroll position: {int(pos['y'])} / {int(pos['max'])}px"

    except Exception as e:
        logger.error(f"browser_scroll error: {e}")
        return f"Error scrolling: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 6: browser_get_text — Extract visible text
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_get_text",
    description=(
        "Extract visible text from the current page or a specific element. "
        "Useful for reading page content, checking what's displayed, or "
        "finding elements to interact with."
    ),
)
@serialize_browser_action
async def browser_get_text(selector: str = "", max_length: str = "3000", **kwargs) -> str:
    """Extract text from the page or a specific element."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        try:
            limit = int(max_length)
        except ValueError:
            limit = 3000

        if selector:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.inner_text()
                    text = text.strip()[:limit]
                    return f"Text from '{selector}':\n\n{text}"
            except Exception:
                pass
            return f"Error: Element '{selector}' not found."
        else:
            text = await page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            clean = "\n".join(lines)[:limit]
            title = await page.title()
            return f"Page: {title} ({page.url})\n\n{clean}"

    except Exception as e:
        logger.error(f"browser_get_text error: {e}")
        return f"Error getting text: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 7: browser_navigate — Back, forward, or go to URL
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_navigate",
    description=(
        "Navigate the browser: 'back', 'forward', 'reload', or a URL. "
        "Use this to go back to a previous page or navigate to a new one."
    ),
)
@serialize_browser_action
async def browser_navigate(action: str, **kwargs) -> str:
    """Navigate: back, forward, reload, or go to URL."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()

        action = action.strip()

        if action.lower() == "back":
            await page.go_back(timeout=10000)
        elif action.lower() == "forward":
            await page.go_forward(timeout=10000)
        elif action.lower() == "reload":
            await page.reload(timeout=15000)
        elif action.startswith("http"):
            if not _is_safe_url(action):
                return "Error: URL blocked — cannot access private/internal network addresses."
            await page.goto(action, wait_until="domcontentloaded", timeout=30000)
        else:
            return f"Error: Unknown action '{action}'. Use 'back', 'forward', 'reload', or a URL."

        await page.wait_for_timeout(1500)
        title = await page.title()
        return f"✅ Navigated: {action}\nNow on: {title} ({page.url})"

    except Exception as e:
        error_msg = str(e)
        if "Download is starting" in error_msg:
            logger.info(f"browser_navigate intercepted download for {action}. Deferring to read_url_content.")
            return f"Error: The URL '{action}' points to a raw file or PDF (Download is starting). Please use the `read_url_content` tool instead to parse this document."
        logger.error(f"browser_navigate error: {e}")
        return f"Error navigating: {error_msg}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 8: browser_fill_form — Fill a form field by label
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_fill_form",
    description=(
        "Fill a form field identified by its label text. "
        "Example: browser_fill_form(label='Email', value='user@example.com'). "
        "More reliable than CSS selectors for labeled form fields."
    ),
)
@serialize_browser_action
async def browser_fill_form(label: str, value: str, **kwargs) -> str:
    """Fill a form field by its label."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        # Try label
        try:
            element = page.get_by_label(label).first
            if await element.count() > 0:
                await element.fill(value)
                return f"✅ Filled '{label}' with '{value}'"
        except Exception:
            pass

        # Try placeholder
        try:
            element = page.get_by_placeholder(label).first
            if await element.count() > 0:
                await element.fill(value)
                return f"✅ Filled placeholder '{label}' with '{value}'"
        except Exception:
            pass

        return f"Error: Could not find form field with label '{label}'."

    except Exception as e:
        logger.error(f"browser_fill_form error: {e}")
        return f"Error filling form: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 9: browser_select — Select from dropdown
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_select",
    description=(
        "Select an option from a dropdown/select element. Specify the "
        "dropdown by CSS selector or label, and the option value or text."
    ),
)
@serialize_browser_action
async def browser_select(
    selector: str, option: str, **kwargs
) -> str:
    """Select an option from a dropdown."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        # Try CSS selector
        try:
            element = page.locator(selector).first
            if await element.count() > 0:
                # Try by value first, then by label
                try:
                    await element.select_option(value=option)
                except Exception:
                    await element.select_option(label=option)
                return f"✅ Selected '{option}' from '{selector}'"
        except Exception:
            pass

        # Try by label
        try:
            element = page.get_by_label(selector).first
            if await element.count() > 0:
                try:
                    await element.select_option(value=option)
                except Exception:
                    await element.select_option(label=option)
                return f"✅ Selected '{option}' from '{selector}'"
        except Exception:
            pass

        return f"Error: Could not find dropdown '{selector}'."

    except Exception as e:
        logger.error(f"browser_select error: {e}")
        return f"Error selecting: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 10: browser_wait — Wait for element
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_wait",
    description=(
        "Wait for an element to appear on the page. Useful after actions "
        "that trigger loading (form submission, navigation, AJAX). "
        "Timeout is in seconds (default 10)."
    ),
)
@serialize_browser_action
async def browser_wait(
    selector: str, timeout: str = "10", **kwargs
) -> str:
    """Wait for an element to appear."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        try:
            timeout_ms = int(float(timeout) * 1000)
        except ValueError:
            timeout_ms = 10000

        try:
            await page.wait_for_selector(selector, timeout=timeout_ms)
            return f"✅ Element '{selector}' is now visible"
        except Exception:
            return f"⏱️ Timeout: Element '{selector}' did not appear within {timeout}s"

    except Exception as e:
        logger.error(f"browser_wait error: {e}")
        return f"Error waiting: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 11: browser_close — Close the session
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_close",
    description=(
        "Close the browser session. Frees up resources. A new session "
        "will be created automatically if you use browser_open again."
    ),
)
@serialize_browser_action
async def browser_close(**kwargs) -> str:
    """Close the browser session."""
    user_id = _get_user_id(**kwargs)
    try:
        await _manager.close_session(user_id)
        return "✅ Browser session closed"
    except Exception as e:
        logger.error(f"browser_close error: {e}")
        return f"Error closing browser: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 12: browser_evaluate — Run JavaScript
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_evaluate",
    description=(
        "Run JavaScript code on the current page and return the result. "
        "The code should be an expression that returns a value. "
        "Example: browser_evaluate(code=\"document.querySelectorAll('a').length\")"
    ),
)
@serialize_browser_action
async def browser_evaluate(code: str, **kwargs) -> str:
    """Evaluate JavaScript on the page."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        result = await page.evaluate(code)
        return f"✅ JavaScript result:\n{result}"

    except Exception as e:
        logger.error(f"browser_evaluate error: {e}")
        return f"Error evaluating JS: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════
# Tool 13: browser_get_links — Extract all links
# ═══════════════════════════════════════════════════════════════════════

@ToolRegistry.register(
    name="browser_get_links",
    description=(
        "Extract all links from the current page. Returns a list of "
        "link text and URLs. Useful for finding navigation options."
    ),
)
@serialize_browser_action
async def browser_get_links(max_links: str = "50", **kwargs) -> str:
    """Extract all links from the page."""
    user_id = _get_user_id(**kwargs)
    session = _manager.get_session(user_id)

    try:
        page = await session.ensure_open()
        if page.url == "about:blank":
            return "Error: No page loaded. Use browser_open first."

        try:
            limit = int(max_links)
        except ValueError:
            limit = 50

        links = await page.evaluate("""
            () => {
                const anchors = document.querySelectorAll('a[href]');
                return Array.from(anchors).slice(0, %d).map(a => ({
                    text: a.innerText.trim().substring(0, 100),
                    href: a.href
                })).filter(l => l.text && l.href);
            }
        """ % limit)

        if not links:
            return "No links found on this page."

        result = f"Found {len(links)} links:\n\n"
        for i, link in enumerate(links, 1):
            result += f"{i}. [{link['text']}] → {link['href']}\n"

        return result

    except Exception as e:
        logger.error(f"browser_get_links error: {e}")
        return f"Error getting links: {str(e)}"
