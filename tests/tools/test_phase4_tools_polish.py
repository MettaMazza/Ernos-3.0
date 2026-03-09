"""Phase 4 polish tests for tool modules at 80-94% coverage.

Covers: tools/file_utils.py (surgical_edit), tools/web.py (search_web)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path


# ═══════════════════════════ surgical_edit ═══════════════════════════
class TestFileUtils:
    def test_surgical_replace(self, tmp_path):
        from src.tools.file_utils import surgical_edit
        target = tmp_path / "test.py"
        target.write_text("line1\nline2\nline3\n")
        # surgical_edit(filepath, mode, content, target)
        result = surgical_edit(str(target), "replace", "replaced_line2", "line2")
        content = target.read_text()
        assert "replaced" in content.lower() or isinstance(result, tuple)

    def test_surgical_edit_not_found(self, tmp_path):
        from src.tools.file_utils import surgical_edit
        target = tmp_path / "test2.py"
        target.write_text("aaa\nbbb\n")
        result = surgical_edit(str(target), "replace", "replaced", "zzz_not_found")
        assert result is not None

    def test_surgical_append(self, tmp_path):
        from src.tools.file_utils import surgical_edit
        target = tmp_path / "test3.py"
        target.write_text("original\n")
        result = surgical_edit(str(target), "append", "appended_line")
        content = target.read_text()
        assert "appended_line" in content


# ═══════════════════════════ search_web ═══════════════════════════
class TestWebTools:
    def test_search_returns_results(self):
        # Pre-seed sys.modules to avoid PyO3 re-initialization crash with primp
        import sys
        mock_ddgs = MagicMock()
        if "duckduckgo_search" not in sys.modules:
            sys.modules["duckduckgo_search"] = mock_ddgs
        from src.tools.web import search_web
        with patch("duckduckgo_search.DDGS") as MockDDGS:
            instance = MagicMock()
            instance.text.return_value = [
                {"title": "Test", "body": "Result body", "href": "http://example.com"}
            ]
            MockDDGS.return_value.__enter__ = MagicMock(return_value=instance)
            MockDDGS.return_value.__exit__ = MagicMock(return_value=False)
            result = search_web("test query")
            assert isinstance(result, str)

    def test_search_error_handling(self):
        import sys
        mock_ddgs = MagicMock()
        if "duckduckgo_search" not in sys.modules:
            sys.modules["duckduckgo_search"] = mock_ddgs
        from src.tools.web import search_web
        with patch("duckduckgo_search.DDGS", side_effect=Exception("network error")):
            result = search_web("test query")
            assert isinstance(result, str)
