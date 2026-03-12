"""
Regression tests for three live bot errors:
1. Discord interaction expired (NotFound) in views.py
2. DDGS deprecated backends ('html', 'lite') in web.py
3. HTTP/2 protocol error in browser.py
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ═══════════════════════════════════════════════════════════════════════
# 1. views.py — Verify NotFound is caught (source inspection)
# ═══════════════════════════════════════════════════════════════════════

class TestViewsNotFoundGuard:
    def test_like_has_notfound_guard(self):
        """Regression: like_button must catch discord.NotFound."""
        import inspect
        from src.ui.views import ResponseFeedbackView
        source = inspect.getsource(ResponseFeedbackView)
        # Check that the like_button method has NotFound handling
        assert "discord.NotFound" in source, "like_button missing discord.NotFound guard"

    def test_dislike_has_notfound_guard(self):
        """Regression: dislike_button must catch discord.NotFound."""
        import inspect
        from src.ui.views import ResponseFeedbackView
        source = inspect.getsource(ResponseFeedbackView)
        # Both like and dislike should have the guard
        # Count occurrences: at minimum 2 (like + dislike)
        count = source.count("discord.NotFound")
        assert count >= 2, f"Expected >=2 discord.NotFound guards, found {count}"

    def test_tts_has_notfound_guard(self):
        """Regression: tts_button must catch discord.NotFound."""
        import inspect
        from src.ui.views import ResponseFeedbackView
        source = inspect.getsource(ResponseFeedbackView)
        # TTS has multiple interaction points that need guarding
        count = source.count("discord.NotFound")
        assert count >= 3, f"Expected >=3 discord.NotFound guards, found {count}"

    def test_log_feedback(self):
        """_log_feedback should work without raising."""
        import discord
        with patch("discord.ui.View.__init__", return_value=None):
            from src.ui.views import ResponseFeedbackView
            view = ResponseFeedbackView.__new__(ResponseFeedbackView)
            view.bot = MagicMock()
            view.response_text = "Test"
            view.audio_msg = None
            with patch("builtins.open", MagicMock()):
                view._log_feedback(12345, "positive", "Test response")


# ═══════════════════════════════════════════════════════════════════════
# 2. web.py — DDGS backend regression
# ═══════════════════════════════════════════════════════════════════════

class TestDDGSBackends:
    def test_no_deprecated_backends(self):
        """Regression: _robust_ddgs_text should NOT use 'html' or 'lite' backends."""
        import inspect
        from src.tools.web import _robust_ddgs_text
        source = inspect.getsource(_robust_ddgs_text)
        assert "'html'" not in source, "Dead backend 'html' still in _robust_ddgs_text"
        assert "'lite'" not in source, "Dead backend 'lite' still in _robust_ddgs_text"

    def test_uses_auto_backend(self):
        """_robust_ddgs_text should use 'auto' backend."""
        import inspect
        from src.tools.web import _robust_ddgs_text
        source = inspect.getsource(_robust_ddgs_text)
        assert "'auto'" in source

    def test_returns_empty_on_all_failures(self):
        """_robust_ddgs_text should return [] not None when all backends fail."""
        from src.tools.web import _robust_ddgs_text
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text.side_effect = Exception("rate limited")
        mock_ddgs_class = MagicMock(return_value=mock_ddgs_instance)
        with patch("src.tools.web._get_ddgs", return_value=mock_ddgs_class), \
             patch("time.sleep"):
            result = _robust_ddgs_text("test query", max_results=3)
        assert result == []

    def test_returns_results_on_success(self):
        """_robust_ddgs_text should return results when backend works."""
        from src.tools.web import _robust_ddgs_text
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text.return_value = [{"title": "Test", "href": "http://example.com", "body": "body"}]
        mock_ddgs_class = MagicMock(return_value=mock_ddgs_instance)
        with patch("src.tools.web._get_ddgs", return_value=mock_ddgs_class):
            result = _robust_ddgs_text("test", max_results=3)
        assert len(result) == 1
        assert result[0]["title"] == "Test"


# ═══════════════════════════════════════════════════════════════════════
# 3. browser.py — HTTP/2 error handling
# ═══════════════════════════════════════════════════════════════════════

class TestBrowserOpenHTTP2:
    def test_http2_retry_in_source(self):
        """Regression: browser_open must contain HTTP/2 retry logic."""
        import inspect
        from src.tools.browser import browser_open
        source = inspect.getsource(browser_open)
        assert "ERR_HTTP2_PROTOCOL_ERROR" in source, "HTTP/2 error detection missing from browser_open"

    @pytest.mark.asyncio
    async def test_http2_error_message(self):
        """Regression: browser_open should give user-friendly HTTP/2 error."""
        from src.tools.browser import browser_open, _manager
        mock_session = MagicMock()
        mock_page = AsyncMock()
        # Both goto calls fail with HTTP/2 error
        mock_page.goto = AsyncMock(side_effect=Exception(
            "Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at https://example.com"
        ))
        mock_page.context.new_cdp_session = AsyncMock(return_value=AsyncMock())
        mock_session.ensure_open = AsyncMock(return_value=mock_page)
        with patch.object(_manager, 'get_session', return_value=mock_session):
            result = await browser_open("https://example.com", user_id="test")
        assert "HTTP/2 protocol error" in result

    @pytest.mark.asyncio
    async def test_normal_error_still_works(self):
        """browser_open should still handle normal errors properly."""
        from src.tools.browser import browser_open, _manager
        mock_session = MagicMock()
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=Exception("Timeout waiting for page"))
        mock_session.ensure_open = AsyncMock(return_value=mock_page)
        with patch.object(_manager, 'get_session', return_value=mock_session):
            result = await browser_open("https://example.com", user_id="test")
        assert "Error" in result
        assert "Timeout" in result
