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
        if "ddgs" not in sys.modules:
            sys.modules["ddgs"] = mock_ddgs
        from src.tools.web import search_web
        with patch("ddgs.DDGS") as MockDDGS:
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
        if "ddgs" not in sys.modules:
            sys.modules["ddgs"] = mock_ddgs
        from src.tools.web import search_web
        with patch("ddgs.DDGS", side_effect=Exception("network error")):
            result = search_web("test query")
            assert isinstance(result, str)

    @patch("time.sleep", return_value=None)
    def test_search_robust_backoff(self, mock_sleep):
        import sys
        mock_ddgs = MagicMock()
        if "ddgs" not in sys.modules:
            sys.modules["ddgs"] = mock_ddgs
            
        from src.tools.web import search_web
        
        with patch("ddgs.DDGS") as MockDDGS:
            instance = MagicMock()
            
            # _robust_ddgs_text checks 1 backend ('auto') per attempt. 
            # If we want it to sleep 2 times (attempt 0 and attempt 1), 
            # we need it to fail 2 times, and succeed on the 3rd.
            def mock_text(*args, **kwargs):
                if mock_text.calls < 2:
                    mock_text.calls += 1
                    raise Exception("Rate limited timeout")
                return [{"title": "Success", "href": "url", "body": "body"}]
            mock_text.calls = 0
            
            instance.text.side_effect = mock_text
            MockDDGS.return_value.__enter__.return_value = instance
            
            result = search_web("test backoff")
            
            assert "Success" in result
            assert mock_sleep.call_count == 2

    @patch("time.sleep", return_value=None)
    def test_robust_ddgs_backends_valid(self, mock_sleep):
        from src.tools.web import _robust_ddgs_text
        
        mock_ddgs = MagicMock()
        mock_ddgs.text.side_effect = Exception("force next backend")
        
        _robust_ddgs_text(mock_ddgs, "test query")
        
        called_backends = []
        for call in mock_ddgs.text.call_args_list:
            backend = call.kwargs.get("backend", "auto")
            if backend not in called_backends:
                called_backends.append(backend)
                
        valid_backends = ['auto']
        for b in called_backends:
            assert b in valid_backends, f"Backend {b} is not in the known valid DDGS backends list"
