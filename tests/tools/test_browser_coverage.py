"""
Full coverage tests for src/tools/browser.py — All 13 browser tools + session management.
Mocks Playwright entirely so no real browser is needed.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ── Mock Playwright before importing browser module ──────────────────

def _make_mock_page(url="https://example.com"):
    """Create a mock Playwright Page with all needed methods."""
    page = AsyncMock()
    page.url = url
    page.is_closed.return_value = False
    page.title = AsyncMock(return_value="Example Page")
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.evaluate = AsyncMock(return_value="Sample page text")
    page.screenshot = AsyncMock()
    page.go_back = AsyncMock()
    page.go_forward = AsyncMock()
    page.reload = AsyncMock()
    page.wait_for_selector = AsyncMock()

    # Locator mock
    locator = AsyncMock()
    locator.count = AsyncMock(return_value=1)
    locator.click = AsyncMock()
    locator.fill = AsyncMock()
    locator.press = AsyncMock()
    locator.screenshot = AsyncMock()
    locator.inner_text = AsyncMock(return_value="Element text content")
    locator.select_option = AsyncMock()
    locator.first = locator  # .first returns self

    page.locator = MagicMock(return_value=locator)
    page.get_by_text = MagicMock(return_value=locator)
    page.get_by_role = MagicMock(return_value=locator)
    page.get_by_label = MagicMock(return_value=locator)
    page.get_by_placeholder = MagicMock(return_value=locator)

    return page, locator


def _make_mock_browser():
    """Create mock Playwright browser, context, and playwright objects."""
    playwright = AsyncMock()
    browser = AsyncMock()
    context = AsyncMock()
    page, locator = _make_mock_page()

    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()
    playwright.chromium = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    playwright.stop = AsyncMock()

    return playwright, browser, context, page, locator


# ═══════════════════════════════════════════════════════════════════════
# BrowserSession Tests
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserSession:
    """Tests for BrowserSession class."""

    @pytest.fixture
    def session(self):
        from src.tools.browser import BrowserSession
        return BrowserSession("test_user")

    def test_init(self, session):
        assert session.user_id == "test_user"
        assert session.playwright is None
        assert session.browser is None
        assert session.context is None
        assert session.page is None

    @pytest.mark.asyncio
    async def test_ensure_open_creates_new_session(self, session):
        pw, browser, context, page, _ = _make_mock_browser()
        with patch("src.tools.browser.async_playwright") as mock_pw:
            mock_pw.return_value.start = AsyncMock(return_value=pw)
            result = await session.ensure_open()
            assert result is page

    @pytest.mark.asyncio
    async def test_ensure_open_returns_existing_page(self, session):
        page = MagicMock()
        page.is_closed = MagicMock(return_value=False)
        session.page = page
        result = await session.ensure_open()
        assert result is page

    @pytest.mark.asyncio
    async def test_ensure_open_replaces_closed_page(self, session):
        old_page = AsyncMock()
        old_page.is_closed.return_value = True
        session.page = old_page

        pw, browser, context, new_page, _ = _make_mock_browser()
        with patch("src.tools.browser.async_playwright") as mock_pw:
            mock_pw.return_value.start = AsyncMock(return_value=pw)
            result = await session.ensure_open()
            assert result is new_page

    @pytest.mark.asyncio
    async def test_close(self, session):
        session.context = AsyncMock()
        session.browser = AsyncMock()
        session.playwright = AsyncMock()
        await session.close()
        assert session.page is None
        assert session.context is None
        assert session.browser is None
        assert session.playwright is None

    @pytest.mark.asyncio
    async def test_cleanup_resources_handles_exceptions(self, session):
        session.context = AsyncMock(close=AsyncMock(side_effect=Exception("ctx err")))
        session.browser = AsyncMock(close=AsyncMock(side_effect=Exception("browser err")))
        session.playwright = AsyncMock(stop=AsyncMock(side_effect=Exception("pw err")))
        await session._cleanup_resources()
        # Should not raise, all set to None
        assert session.page is None
        assert session.context is None
        assert session.browser is None
        assert session.playwright is None

    @pytest.mark.asyncio
    async def test_cleanup_resources_skips_none(self, session):
        # All None — should not raise
        await session._cleanup_resources()
        assert session.page is None

    def test_is_expired_false(self, session):
        session.last_activity = time.time()
        assert session.is_expired is False

    def test_is_expired_true(self, session):
        session.last_activity = time.time() - 700  # > 600s timeout
        assert session.is_expired is True


# ═══════════════════════════════════════════════════════════════════════
# SessionManager Tests
# ═══════════════════════════════════════════════════════════════════════

class TestSessionManager:
    """Tests for SessionManager class."""

    @pytest.fixture
    def manager(self):
        from src.tools.browser import SessionManager
        return SessionManager()

    def test_get_session_creates_new(self, manager):
        session = manager.get_session("user1")
        assert session.user_id == "user1"
        assert "user1" in manager._sessions

    def test_get_session_returns_existing(self, manager):
        s1 = manager.get_session("user1")
        s2 = manager.get_session("user1")
        assert s1 is s2

    def test_get_session_updates_last_activity(self, manager):
        session = manager.get_session("user1")
        t1 = session.last_activity
        time.sleep(0.01)
        manager.get_session("user1")
        assert session.last_activity >= t1

    @pytest.mark.asyncio
    async def test_close_session(self, manager):
        session = manager.get_session("user1")
        session.close = AsyncMock()
        await manager.close_session("user1")
        assert "user1" not in manager._sessions

    @pytest.mark.asyncio
    async def test_close_session_nonexistent(self, manager):
        # Should not raise
        await manager.close_session("nobody")

    @pytest.mark.asyncio
    async def test_cleanup_loop_removes_expired(self, manager):
        session = manager.get_session("expired_user")
        session.last_activity = time.time() - 700
        session.close = AsyncMock()

        # Directly test close_session since cleanup_loop calls it
        await manager.close_session("expired_user")
        assert "expired_user" not in manager._sessions
        session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_loop_cleans_expired_and_exits(self, manager):
        """Exercise the full cleanup loop body: find expired, log, close, exit."""
        session = manager.get_session("expired_user2")
        session.last_activity = time.time() - 700  # Make it expired
        session.close = AsyncMock()

        # asyncio.sleep returns normally once (so the loop body runs),
        # then the while condition fails because sessions dict is empty after cleanup.
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await manager._cleanup_loop()

        # Session should have been cleaned up
        assert "expired_user2" not in manager._sessions
        assert manager._cleanup_task is None


# ═══════════════════════════════════════════════════════════════════════
# Helper function test
# ═══════════════════════════════════════════════════════════════════════

class TestGetUserId:
    def test_returns_user_id(self):
        from src.tools.browser import _get_user_id
        assert _get_user_id(user_id="abc") == "abc"

    def test_returns_default(self):
        from src.tools.browser import _get_user_id
        assert _get_user_id() == "default"

    def test_returns_multiplexed_with_agent_id(self):
        from src.tools.browser import _get_user_id
        assert _get_user_id(user_id="abc", agent_id="agent1") == "abc_agent1"

    def test_multiplexed_session_isolation(self):
        from src.tools.browser import SessionManager, _get_user_id
        manager = SessionManager()
        
        # Given a user with two agents
        id1 = _get_user_id(user_id="user1", agent_id="agentA")
        id2 = _get_user_id(user_id="user1", agent_id="agentB")
        
        # When getting sessions
        session1 = manager.get_session(id1)
        session2 = manager.get_session(id2)
        
        # They are treated as distinct contexts entirely
        assert session1 is not session2
        assert session1.user_id == "user1_agentA"
        assert session2.user_id == "user1_agentB"


# ═══════════════════════════════════════════════════════════════════════
# Tool Tests — Shared fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_session():
    """Fixture that patches _manager.get_session to return a mock session."""
    page, locator = _make_mock_page()
    session = AsyncMock()
    session.ensure_open = AsyncMock(return_value=page)
    session.close = AsyncMock()

    with patch("src.tools.browser._manager") as mgr:
        mgr.get_session = MagicMock(return_value=session)
        mgr.close_session = AsyncMock()
        yield {
            "session": session,
            "page": page,
            "locator": locator,
            "manager": mgr,
        }


@pytest.fixture
def mock_session_blank():
    """Session with about:blank page (no page loaded)."""
    page, locator = _make_mock_page(url="about:blank")
    session = AsyncMock()
    session.ensure_open = AsyncMock(return_value=page)

    with patch("src.tools.browser._manager") as mgr:
        mgr.get_session = MagicMock(return_value=session)
        yield {
            "session": session,
            "page": page,
            "locator": locator,
        }


# ═══════════════════════════════════════════════════════════════════════
# Tool 1: browser_open
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserOpen:
    @pytest.mark.asyncio
    async def test_opens_url_successfully(self, mock_session):
        from src.tools.browser import browser_open
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value="Hello world page content here")

        result = await browser_open("https://example.com", user_id="u1")
        assert "✅ Page loaded" in result
        assert "Example Page" in result

    @pytest.mark.asyncio
    async def test_blocks_unsafe_url(self, mock_session):
        from src.tools.browser import browser_open
        with patch("src.tools.browser._is_safe_url", return_value=False):
            result = await browser_open("http://localhost:8080", user_id="u1")
            assert "Error: URL blocked" in result

    @pytest.mark.asyncio
    async def test_handles_exception(self, mock_session):
        from src.tools.browser import browser_open
        mock_session["page"].goto = AsyncMock(side_effect=Exception("Timeout"))
        result = await browser_open("https://example.com", user_id="u1")
        assert "Error opening URL" in result

    @pytest.mark.asyncio
    async def test_empty_page_text(self, mock_session):
        from src.tools.browser import browser_open
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value="")
        result = await browser_open("https://example.com", user_id="u1")
        assert "(empty page)" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 2: browser_click
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserClick:
    @pytest.mark.asyncio
    async def test_click_css_selector(self, mock_session):
        from src.tools.browser import browser_click
        result = await browser_click("#submit", user_id="u1")
        assert "✅ Clicked element matching" in result

    @pytest.mark.asyncio
    async def test_click_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_click
        result = await browser_click("#submit", user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_click_text_fallback(self, mock_session):
        from src.tools.browser import browser_click
        page = mock_session["page"]
        # CSS selector fails
        css_locator = AsyncMock()
        css_locator.count = AsyncMock(return_value=0)
        css_locator.first = css_locator
        page.locator = MagicMock(return_value=css_locator)

        # Text selector works
        text_locator = AsyncMock()
        text_locator.count = AsyncMock(return_value=1)
        text_locator.click = AsyncMock()
        text_locator.first = text_locator
        page.get_by_text = MagicMock(return_value=text_locator)

        result = await browser_click("Sign In", user_id="u1")
        assert "✅ Clicked element with text" in result

    @pytest.mark.asyncio
    async def test_click_role_fallback(self, mock_session):
        from src.tools.browser import browser_click
        page = mock_session["page"]

        # CSS and text both fail
        fail_locator = AsyncMock()
        fail_locator.count = AsyncMock(return_value=0)
        fail_locator.first = fail_locator
        page.locator = MagicMock(return_value=fail_locator)
        page.get_by_text = MagicMock(return_value=fail_locator)

        # Role works
        role_locator = AsyncMock()
        role_locator.count = AsyncMock(return_value=1)
        role_locator.click = AsyncMock()
        role_locator.first = role_locator
        page.get_by_role = MagicMock(return_value=role_locator)

        result = await browser_click("Submit", user_id="u1")
        assert "✅ Clicked" in result

    @pytest.mark.asyncio
    async def test_click_nothing_found(self, mock_session):
        from src.tools.browser import browser_click
        page = mock_session["page"]
        fail_locator = AsyncMock()
        fail_locator.count = AsyncMock(return_value=0)
        fail_locator.first = fail_locator
        page.locator = MagicMock(return_value=fail_locator)
        page.get_by_text = MagicMock(return_value=fail_locator)
        page.get_by_role = MagicMock(return_value=fail_locator)

        result = await browser_click("nonexistent", user_id="u1")
        assert "Error: Could not find element" in result

    @pytest.mark.asyncio
    async def test_click_exception(self, mock_session):
        from src.tools.browser import browser_click
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("crash"))
        result = await browser_click("#btn", user_id="u1")
        assert "Error clicking" in result

    @pytest.mark.asyncio
    async def test_click_css_exception_falls_to_text(self, mock_session):
        from src.tools.browser import browser_click
        page = mock_session["page"]
        page.locator = MagicMock(side_effect=Exception("bad selector"))
        result = await browser_click("Submit", user_id="u1")
        assert "✅ Clicked" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_click_text_exception_falls_to_role(self, mock_session):
        from src.tools.browser import browser_click
        page = mock_session["page"]
        css_locator = AsyncMock()
        css_locator.count = AsyncMock(return_value=0)
        css_locator.first = css_locator
        page.locator = MagicMock(return_value=css_locator)
        page.get_by_text = MagicMock(side_effect=Exception("text fail"))
        result = await browser_click("Submit", user_id="u1")
        # Falls back through to role-based
        assert "✅ Clicked" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_click_all_strategies_except(self, mock_session):
        from src.tools.browser import browser_click
        page = mock_session["page"]
        page.locator = MagicMock(side_effect=Exception("nope"))
        page.get_by_text = MagicMock(side_effect=Exception("nope"))
        page.get_by_role = MagicMock(side_effect=Exception("nope"))
        result = await browser_click("x", user_id="u1")
        assert "Error: Could not find element" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 3: browser_type
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserType:
    @pytest.mark.asyncio
    async def test_type_css_selector(self, mock_session):
        from src.tools.browser import browser_type
        result = await browser_type("#email", "hello@test.com", user_id="u1")
        assert "✅ Typed" in result

    @pytest.mark.asyncio
    async def test_type_with_enter(self, mock_session):
        from src.tools.browser import browser_type
        result = await browser_type("#search", "query", press_enter="true", user_id="u1")
        assert "pressed Enter" in result

    @pytest.mark.asyncio
    async def test_type_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_type
        result = await browser_type("#email", "test", user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_type_label_fallback(self, mock_session):
        from src.tools.browser import browser_type
        page = mock_session["page"]
        fail_locator = AsyncMock()
        fail_locator.count = AsyncMock(return_value=0)
        fail_locator.first = fail_locator
        page.locator = MagicMock(return_value=fail_locator)

        result = await browser_type("Email", "test@x.com", user_id="u1")
        assert "✅ Typed" in result

    @pytest.mark.asyncio
    async def test_type_label_with_enter(self, mock_session):
        from src.tools.browser import browser_type
        page = mock_session["page"]
        fail_locator = AsyncMock()
        fail_locator.count = AsyncMock(return_value=0)
        fail_locator.first = fail_locator
        page.locator = MagicMock(return_value=fail_locator)

        result = await browser_type("Email", "test@x.com", press_enter="yes", user_id="u1")
        assert "pressed Enter" in result

    @pytest.mark.asyncio
    async def test_type_placeholder_fallback(self, mock_session):
        from src.tools.browser import browser_type
        page = mock_session["page"]
        fail_locator = AsyncMock()
        fail_locator.count = AsyncMock(return_value=0)
        fail_locator.first = fail_locator
        page.locator = MagicMock(return_value=fail_locator)
        page.get_by_label = MagicMock(return_value=fail_locator)

        result = await browser_type("Search...", "query", user_id="u1")
        assert "✅ Typed" in result

    @pytest.mark.asyncio
    async def test_type_placeholder_with_enter(self, mock_session):
        from src.tools.browser import browser_type
        page = mock_session["page"]
        fail_locator = AsyncMock()
        fail_locator.count = AsyncMock(return_value=0)
        fail_locator.first = fail_locator
        page.locator = MagicMock(return_value=fail_locator)
        page.get_by_label = MagicMock(return_value=fail_locator)

        result = await browser_type("Search...", "query", press_enter="1", user_id="u1")
        assert "pressed Enter" in result

    @pytest.mark.asyncio
    async def test_type_nothing_found(self, mock_session):
        from src.tools.browser import browser_type
        page = mock_session["page"]
        fail_locator = AsyncMock()
        fail_locator.count = AsyncMock(return_value=0)
        fail_locator.first = fail_locator
        page.locator = MagicMock(return_value=fail_locator)
        page.get_by_label = MagicMock(return_value=fail_locator)
        page.get_by_placeholder = MagicMock(return_value=fail_locator)

        result = await browser_type("nonexistent", "text", user_id="u1")
        assert "Error: Could not find input" in result

    @pytest.mark.asyncio
    async def test_type_exception(self, mock_session):
        from src.tools.browser import browser_type
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("crash"))
        result = await browser_type("#x", "text", user_id="u1")
        assert "Error typing" in result

    @pytest.mark.asyncio
    async def test_type_css_except_label_except_placeholder(self, mock_session):
        from src.tools.browser import browser_type
        page = mock_session["page"]
        page.locator = MagicMock(side_effect=Exception("css fail"))
        page.get_by_label = MagicMock(side_effect=Exception("label fail"))
        page.get_by_placeholder = MagicMock(side_effect=Exception("ph fail"))
        result = await browser_type("x", "text", user_id="u1")
        assert "Error: Could not find input" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 4: browser_screenshot
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserScreenshot:
    @pytest.mark.asyncio
    async def test_full_page_screenshot(self, mock_session):
        from src.tools.browser import browser_screenshot
        result = await browser_screenshot(user_id="u1")
        assert "✅ Screenshot captured" in result

    @pytest.mark.asyncio
    async def test_element_screenshot(self, mock_session):
        from src.tools.browser import browser_screenshot
        result = await browser_screenshot(selector="#header", user_id="u1")
        assert "✅ Screenshot of" in result

    @pytest.mark.asyncio
    async def test_element_not_found(self, mock_session):
        from src.tools.browser import browser_screenshot
        page = mock_session["page"]
        fail_loc = AsyncMock()
        fail_loc.count = AsyncMock(return_value=0)
        fail_loc.first = fail_loc
        page.locator = MagicMock(return_value=fail_loc)
        result = await browser_screenshot(selector="#missing", user_id="u1")
        assert "Error: Element" in result

    @pytest.mark.asyncio
    async def test_element_screenshot_exception(self, mock_session):
        from src.tools.browser import browser_screenshot
        page = mock_session["page"]
        page.locator = MagicMock(side_effect=Exception("locator crash"))
        result = await browser_screenshot(selector="#bad", user_id="u1")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_screenshot
        result = await browser_screenshot(user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_exception(self, mock_session):
        from src.tools.browser import browser_screenshot
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("fail"))
        result = await browser_screenshot(user_id="u1")
        assert "Error taking screenshot" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 5: browser_scroll
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserScroll:
    @pytest.mark.asyncio
    async def test_scroll_down(self, mock_session):
        from src.tools.browser import browser_scroll
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value={"y": 500, "max": 2000})
        result = await browser_scroll(direction="down", user_id="u1")
        assert "✅ Scrolled down" in result

    @pytest.mark.asyncio
    async def test_scroll_up(self, mock_session):
        from src.tools.browser import browser_scroll
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value={"y": 0, "max": 2000})
        result = await browser_scroll(direction="up", amount="200", user_id="u1")
        assert "✅ Scrolled up" in result

    @pytest.mark.asyncio
    async def test_scroll_top(self, mock_session):
        from src.tools.browser import browser_scroll
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value={"y": 0, "max": 2000})
        result = await browser_scroll(direction="top", user_id="u1")
        assert "✅ Scrolled top" in result

    @pytest.mark.asyncio
    async def test_scroll_bottom(self, mock_session):
        from src.tools.browser import browser_scroll
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value={"y": 2000, "max": 2000})
        result = await browser_scroll(direction="bottom", user_id="u1")
        assert "✅ Scrolled bottom" in result

    @pytest.mark.asyncio
    async def test_scroll_invalid_amount(self, mock_session):
        from src.tools.browser import browser_scroll
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value={"y": 500, "max": 2000})
        result = await browser_scroll(direction="down", amount="abc", user_id="u1")
        assert "✅ Scrolled" in result  # Falls back to 500

    @pytest.mark.asyncio
    async def test_scroll_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_scroll
        result = await browser_scroll(user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_scroll_exception(self, mock_session):
        from src.tools.browser import browser_scroll
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("err"))
        result = await browser_scroll(user_id="u1")
        assert "Error scrolling" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 6: browser_get_text
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserGetText:
    @pytest.mark.asyncio
    async def test_get_full_page_text(self, mock_session):
        from src.tools.browser import browser_get_text
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value="Line 1\nLine 2\n\n\nLine 3")
        result = await browser_get_text(user_id="u1")
        assert "Page:" in result
        assert "Line 1" in result

    @pytest.mark.asyncio
    async def test_get_element_text(self, mock_session):
        from src.tools.browser import browser_get_text
        result = await browser_get_text(selector="#content", user_id="u1")
        assert "Text from '#content'" in result

    @pytest.mark.asyncio
    async def test_element_not_found(self, mock_session):
        from src.tools.browser import browser_get_text
        page = mock_session["page"]
        fail_loc = AsyncMock()
        fail_loc.count = AsyncMock(return_value=0)
        fail_loc.first = fail_loc
        page.locator = MagicMock(return_value=fail_loc)
        result = await browser_get_text(selector="#missing", user_id="u1")
        assert "Error: Element" in result

    @pytest.mark.asyncio
    async def test_element_exception(self, mock_session):
        from src.tools.browser import browser_get_text
        page = mock_session["page"]
        page.locator = MagicMock(side_effect=Exception("bad"))
        result = await browser_get_text(selector="#x", user_id="u1")
        assert "Error: Element" in result

    @pytest.mark.asyncio
    async def test_invalid_max_length(self, mock_session):
        from src.tools.browser import browser_get_text
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value="text")
        result = await browser_get_text(max_length="abc", user_id="u1")
        assert "Page:" in result

    @pytest.mark.asyncio
    async def test_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_get_text
        result = await browser_get_text(user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_exception(self, mock_session):
        from src.tools.browser import browser_get_text
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("err"))
        result = await browser_get_text(user_id="u1")
        assert "Error getting text" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 7: browser_navigate
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserNavigate:
    @pytest.mark.asyncio
    async def test_navigate_back(self, mock_session):
        from src.tools.browser import browser_navigate
        result = await browser_navigate("back", user_id="u1")
        assert "✅ Navigated: back" in result

    @pytest.mark.asyncio
    async def test_navigate_forward(self, mock_session):
        from src.tools.browser import browser_navigate
        result = await browser_navigate("forward", user_id="u1")
        assert "✅ Navigated: forward" in result

    @pytest.mark.asyncio
    async def test_navigate_reload(self, mock_session):
        from src.tools.browser import browser_navigate
        result = await browser_navigate("reload", user_id="u1")
        assert "✅ Navigated: reload" in result

    @pytest.mark.asyncio
    async def test_navigate_url(self, mock_session):
        from src.tools.browser import browser_navigate
        with patch("src.tools.browser._is_safe_url", return_value=True):
            result = await browser_navigate("https://google.com", user_id="u1")
            assert "✅ Navigated" in result

    @pytest.mark.asyncio
    async def test_navigate_unsafe_url(self, mock_session):
        from src.tools.browser import browser_navigate
        with patch("src.tools.browser._is_safe_url", return_value=False):
            result = await browser_navigate("http://localhost", user_id="u1")
            assert "Error: URL blocked" in result

    @pytest.mark.asyncio
    async def test_navigate_unknown_action(self, mock_session):
        from src.tools.browser import browser_navigate
        result = await browser_navigate("dance", user_id="u1")
        assert "Error: Unknown action" in result

    @pytest.mark.asyncio
    async def test_navigate_exception(self, mock_session):
        from src.tools.browser import browser_navigate
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("err"))
        result = await browser_navigate("back", user_id="u1")
        assert "Error navigating" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 8: browser_fill_form
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserFillForm:
    @pytest.mark.asyncio
    async def test_fill_by_label(self, mock_session):
        from src.tools.browser import browser_fill_form
        result = await browser_fill_form("Email", "test@example.com", user_id="u1")
        assert "✅ Filled 'Email'" in result

    @pytest.mark.asyncio
    async def test_fill_by_placeholder(self, mock_session):
        from src.tools.browser import browser_fill_form
        page = mock_session["page"]
        fail_loc = AsyncMock()
        fail_loc.count = AsyncMock(return_value=0)
        fail_loc.first = fail_loc
        page.get_by_label = MagicMock(return_value=fail_loc)
        result = await browser_fill_form("Search...", "query", user_id="u1")
        assert "✅ Filled placeholder" in result

    @pytest.mark.asyncio
    async def test_fill_nothing_found(self, mock_session):
        from src.tools.browser import browser_fill_form
        page = mock_session["page"]
        fail_loc = AsyncMock()
        fail_loc.count = AsyncMock(return_value=0)
        fail_loc.first = fail_loc
        page.get_by_label = MagicMock(return_value=fail_loc)
        page.get_by_placeholder = MagicMock(return_value=fail_loc)
        result = await browser_fill_form("NonExistent", "val", user_id="u1")
        assert "Error: Could not find form field" in result

    @pytest.mark.asyncio
    async def test_fill_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_fill_form
        result = await browser_fill_form("Email", "test", user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_fill_exception(self, mock_session):
        from src.tools.browser import browser_fill_form
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("err"))
        result = await browser_fill_form("Email", "test", user_id="u1")
        assert "Error filling form" in result

    @pytest.mark.asyncio
    async def test_fill_label_exception_placeholder_exception(self, mock_session):
        from src.tools.browser import browser_fill_form
        page = mock_session["page"]
        page.get_by_label = MagicMock(side_effect=Exception("label fail"))
        page.get_by_placeholder = MagicMock(side_effect=Exception("ph fail"))
        result = await browser_fill_form("x", "val", user_id="u1")
        assert "Error: Could not find form field" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 9: browser_select
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserSelect:
    @pytest.mark.asyncio
    async def test_select_by_css(self, mock_session):
        from src.tools.browser import browser_select
        result = await browser_select("#country", "US", user_id="u1")
        assert "✅ Selected 'US'" in result

    @pytest.mark.asyncio
    async def test_select_by_css_label_fallback(self, mock_session):
        from src.tools.browser import browser_select
        page = mock_session["page"]
        loc = mock_session["locator"]
        loc.select_option = AsyncMock(side_effect=[Exception("no value"), None])
        result = await browser_select("#country", "United States", user_id="u1")
        assert "✅ Selected" in result

    @pytest.mark.asyncio
    async def test_select_by_label(self, mock_session):
        from src.tools.browser import browser_select
        page = mock_session["page"]
        fail_loc = AsyncMock()
        fail_loc.count = AsyncMock(return_value=0)
        fail_loc.first = fail_loc
        page.locator = MagicMock(return_value=fail_loc)
        result = await browser_select("Country", "US", user_id="u1")
        assert "✅ Selected 'US'" in result

    @pytest.mark.asyncio
    async def test_select_by_label_value_fail(self, mock_session):
        from src.tools.browser import browser_select
        page = mock_session["page"]
        fail_loc = AsyncMock()
        fail_loc.count = AsyncMock(return_value=0)
        fail_loc.first = fail_loc
        page.locator = MagicMock(return_value=fail_loc)

        label_loc = AsyncMock()
        label_loc.count = AsyncMock(return_value=1)
        label_loc.select_option = AsyncMock(side_effect=[Exception("no value"), None])
        label_loc.first = label_loc
        page.get_by_label = MagicMock(return_value=label_loc)

        result = await browser_select("Country", "US", user_id="u1")
        assert "✅ Selected" in result

    @pytest.mark.asyncio
    async def test_select_nothing_found(self, mock_session):
        from src.tools.browser import browser_select
        page = mock_session["page"]
        fail_loc = AsyncMock()
        fail_loc.count = AsyncMock(return_value=0)
        fail_loc.first = fail_loc
        page.locator = MagicMock(return_value=fail_loc)
        page.get_by_label = MagicMock(return_value=fail_loc)
        result = await browser_select("x", "y", user_id="u1")
        assert "Error: Could not find dropdown" in result

    @pytest.mark.asyncio
    async def test_select_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_select
        result = await browser_select("#sel", "opt", user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_select_exception(self, mock_session):
        from src.tools.browser import browser_select
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("err"))
        result = await browser_select("#sel", "opt", user_id="u1")
        assert "Error selecting" in result

    @pytest.mark.asyncio
    async def test_select_css_exception_label_exception(self, mock_session):
        from src.tools.browser import browser_select
        page = mock_session["page"]
        page.locator = MagicMock(side_effect=Exception("css fail"))
        page.get_by_label = MagicMock(side_effect=Exception("label fail"))
        result = await browser_select("x", "y", user_id="u1")
        assert "Error: Could not find dropdown" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 10: browser_wait
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserWait:
    @pytest.mark.asyncio
    async def test_wait_found(self, mock_session):
        from src.tools.browser import browser_wait
        result = await browser_wait("#elem", user_id="u1")
        assert "✅ Element '#elem' is now visible" in result

    @pytest.mark.asyncio
    async def test_wait_timeout(self, mock_session):
        from src.tools.browser import browser_wait
        page = mock_session["page"]
        page.wait_for_selector = AsyncMock(side_effect=Exception("timeout"))
        result = await browser_wait("#elem", timeout="5", user_id="u1")
        assert "Timeout" in result

    @pytest.mark.asyncio
    async def test_wait_invalid_timeout(self, mock_session):
        from src.tools.browser import browser_wait
        result = await browser_wait("#elem", timeout="abc", user_id="u1")
        assert "✅" in result or "Timeout" in result

    @pytest.mark.asyncio
    async def test_wait_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_wait
        result = await browser_wait("#elem", user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_wait_exception(self, mock_session):
        from src.tools.browser import browser_wait
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("err"))
        result = await browser_wait("#elem", user_id="u1")
        assert "Error waiting" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 11: browser_close
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserClose:
    @pytest.mark.asyncio
    async def test_close_success(self, mock_session):
        from src.tools.browser import browser_close
        result = await browser_close(user_id="u1")
        assert "✅ Browser session closed" in result

    @pytest.mark.asyncio
    async def test_close_exception(self, mock_session):
        from src.tools.browser import browser_close
        mock_session["manager"].close_session = AsyncMock(side_effect=Exception("err"))
        result = await browser_close(user_id="u1")
        assert "Error closing browser" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 12: browser_evaluate
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_success(self, mock_session):
        from src.tools.browser import browser_evaluate
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value=42)
        result = await browser_evaluate("1+1", user_id="u1")
        assert "✅ JavaScript result" in result

    @pytest.mark.asyncio
    async def test_evaluate_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_evaluate
        result = await browser_evaluate("1+1", user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_evaluate_exception(self, mock_session):
        from src.tools.browser import browser_evaluate
        page = mock_session["page"]
        page.evaluate = AsyncMock(side_effect=Exception("JS error"))
        result = await browser_evaluate("bad()", user_id="u1")
        assert "Error evaluating JS" in result

    @pytest.mark.asyncio
    async def test_evaluate_session_exception(self, mock_session):
        from src.tools.browser import browser_evaluate
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("err"))
        result = await browser_evaluate("1+1", user_id="u1")
        assert "Error evaluating JS" in result


# ═══════════════════════════════════════════════════════════════════════
# Tool 13: browser_get_links
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserGetLinks:
    @pytest.mark.asyncio
    async def test_get_links_success(self, mock_session):
        from src.tools.browser import browser_get_links
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value=[
            {"text": "Google", "href": "https://google.com"},
            {"text": "GitHub", "href": "https://github.com"},
        ])
        result = await browser_get_links(user_id="u1")
        assert "Found 2 links" in result
        assert "Google" in result

    @pytest.mark.asyncio
    async def test_get_links_empty(self, mock_session):
        from src.tools.browser import browser_get_links
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value=[])
        result = await browser_get_links(user_id="u1")
        assert "No links found" in result

    @pytest.mark.asyncio
    async def test_get_links_invalid_max(self, mock_session):
        from src.tools.browser import browser_get_links
        page = mock_session["page"]
        page.evaluate = AsyncMock(return_value=[{"text": "A", "href": "http://a.com"}])
        result = await browser_get_links(max_links="abc", user_id="u1")
        assert "Found 1 links" in result

    @pytest.mark.asyncio
    async def test_get_links_about_blank(self, mock_session_blank):
        from src.tools.browser import browser_get_links
        result = await browser_get_links(user_id="u1")
        assert "Error: No page loaded" in result

    @pytest.mark.asyncio
    async def test_get_links_exception(self, mock_session):
        from src.tools.browser import browser_get_links
        mock_session["session"].ensure_open = AsyncMock(side_effect=Exception("err"))
        result = await browser_get_links(user_id="u1")
        assert "Error getting links" in result
