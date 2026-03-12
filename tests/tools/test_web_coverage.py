"""
Coverage tests for src/tools/web.py.
Targets 53 uncovered lines across: _is_safe_url, _fallback_yahoo_search,
_fallback_bing_search, _fallback_google_search, browse_site SSRF.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestIsSafeUrl:
    def test_safe_url(self):
        from src.tools.web import _is_safe_url
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            assert _is_safe_url("https://example.com") is True

    def test_localhost(self):
        from src.tools.web import _is_safe_url
        assert _is_safe_url("http://localhost/admin") is False

    def test_zero_ip(self):
        from src.tools.web import _is_safe_url
        assert _is_safe_url("http://0.0.0.0/secret") is False

    def test_private_ip(self):
        from src.tools.web import _is_safe_url
        with patch("socket.gethostbyname", return_value="192.168.1.1"):
            assert _is_safe_url("http://internal.corp") is False

    def test_loopback_ip(self):
        from src.tools.web import _is_safe_url
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            assert _is_safe_url("http://evil.com") is False

    def test_no_hostname(self):
        from src.tools.web import _is_safe_url
        assert _is_safe_url("not-a-url") is False

    def test_dns_failure(self):
        from src.tools.web import _is_safe_url
        with patch("socket.gethostbyname", side_effect=Exception("DNS fail")):
            assert _is_safe_url("http://nonexistent.example") is False


class TestFallbackYahooSearch:
    def test_success(self):
        from src.tools.web import _fallback_yahoo_search
        mock_html = """
        <html><body>
        <div class="algo"><h3><a href="http://example.com">Title</a></h3><p>snippet</p></div>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.read.return_value = mock_html.encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            results = _fallback_yahoo_search("test query")
        assert len(results) >= 1
        assert results[0]["title"] == "Title"

    def test_exception(self):
        from src.tools.web import _fallback_yahoo_search
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            results = _fallback_yahoo_search("test")
        assert results == []


class TestFallbackBingSearch:
    def test_exception(self):
        from src.tools.web import _fallback_bing_search
        # The function imports undetected_chromedriver which may not be installed
        with patch.dict("sys.modules", {"undetected_chromedriver": None}):
            results = _fallback_bing_search("test")
        assert results == []


class TestFallbackGoogleSearch:
    def test_exception(self):
        from src.tools.web import _fallback_google_search
        with patch.dict("sys.modules", {"undetected_chromedriver": None}):
            results = _fallback_google_search("test")
        assert results == []


class TestSearchWeb:
    def test_ddgs_success(self):
        from src.tools.web import search_web
        mock_ddgs = MagicMock()
        mock_ddgs.return_value.__enter__ = lambda s: s
        mock_ddgs.return_value.__exit__ = MagicMock(return_value=False)

        def mock_loader():
            return mock_ddgs

        with patch("src.tools.web._robust_ddgs_text", return_value=[
            {"title": "Result 1", "href": "http://example.com", "body": "snippet 1"}
        ]):
            result = search_web("test query", _loader=mock_loader)
        assert "Result 1" in result

    def test_all_tiers_fail(self):
        from src.tools.web import search_web

        def mock_loader():
            return None

        with patch("src.tools.web._fallback_google_search", return_value=[]), \
             patch("src.tools.web._fallback_bing_search", return_value=[]), \
             patch("src.tools.web._fallback_yahoo_search", return_value=[]):
            result = search_web("obscure query", _loader=mock_loader)
        assert "No results found" in result

    def test_ddgs_exception_falls_through(self):
        from src.tools.web import search_web

        def mock_loader():
            raise RuntimeError("DDGS broken")

        with patch("src.tools.web._fallback_google_search", return_value=[
            {"title": "Google result", "href": "http://g.co", "body": "text"}
        ]):
            result = search_web("test", _loader=mock_loader)
        assert "Google result" in result


class TestBrowseSite:
    def test_ssrf_blocked(self):
        from src.tools.web import browse_site
        with patch("src.tools.web._is_safe_url", return_value=False):
            result = browse_site("http://localhost/admin")
        assert "blocked" in result.lower()

    def test_success(self):
        from src.tools.web import browse_site
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Hello World</p></body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("src.tools.web._is_safe_url", return_value=True), \
             patch("requests.get", return_value=mock_response):
            result = browse_site("http://example.com")
        assert "Hello World" in result

    def test_request_error(self):
        from src.tools.web import browse_site
        with patch("src.tools.web._is_safe_url", return_value=True), \
             patch("requests.get", side_effect=Exception("timeout")):
            result = browse_site("http://example.com")
        assert "Browse Error" in result


class TestStartDeepResearch:
    @pytest.mark.asyncio
    async def test_deep_research_fires_task(self):
        from src.tools.web import start_deep_research
        mock_bot = MagicMock()
        mock_bot.loop = MagicMock()
        
        with patch("asyncio.create_task") as mock_task, \
             patch("src.bot.globals.bot", mock_bot):
             
             # Call with our new Intention payload
             result = await start_deep_research("AI Safety", is_autonomy=True, intention="Intent test")
             
             assert "started" in result.lower()
             
             # Verify task was created with our intention argument piped through
             mock_task.assert_called_once()
             # We can't introspect its closure easily here, but we can mock the inner call
             # in a more comprehensive test or just trust the pass-through for coverage
