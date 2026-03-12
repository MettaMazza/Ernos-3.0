"""
Tests for file_utils.py — surgical_edit replace mode fix.
Verifies the destructive auto-overwrite fallback is removed.
"""

import pytest
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestSurgicalEditReplaceFix:
    """Tests that replace mode no longer silently overwrites files."""

    @pytest.fixture
    def temp_file(self, tmp_path):
        """Create a temp file with known content."""
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\n")
        return str(f)

    def test_replace_target_found(self, temp_file):
        """Replace should work when target exists."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "replace", "REPLACED", "line2")
        assert ok is True
        with open(temp_file) as f:
            assert "REPLACED" in f.read()
            
    def test_replace_target_not_found_short_content(self, temp_file):
        """Replace with short content should error when target not found."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "replace", "x", "NONEXISTENT")
        assert ok is False
        assert "not found" in msg.lower()
        # File should be untouched
        with open(temp_file) as f:
            assert f.read() == "line1\nline2\nline3\n"

    def test_replace_target_not_found_long_content_no_overwrite(self, temp_file):
        """Replace with long content should error, NOT overwrite (the bug fix)."""
        from src.tools.file_utils import surgical_edit

        long_content = "x" * 500
        ok, msg = surgical_edit(temp_file, "replace", long_content, "NONEXISTENT")
        assert ok is False
        assert "not found" in msg.lower()
        # File should be untouched — NOT overwritten
        with open(temp_file) as f:
            content = f.read()
            assert content == "line1\nline2\nline3\n"
            assert long_content not in content

    def test_replace_error_includes_diagnostics(self, temp_file):
        """Error message should include diagnostic info."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "replace", "new", "MISSING_TARGET")
        assert ok is False
        assert "MISSING_TARGET" in msg  # Shows what target was
        assert "line1" in msg  # Shows what file starts with
        assert "overwrite" in msg.lower()  # Suggests explicit overwrite

    def test_replace_all_target_not_found(self, temp_file):
        """replace_all should error when target not found (unchanged)."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "replace_all", "new", "MISSING")
        assert ok is False
        assert "not found" in msg.lower()

    def test_overwrite_mode_still_works(self, temp_file):
        """Explicit overwrite mode should still replace entire file."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "overwrite", "BRAND NEW CONTENT")
        assert ok is True
        with open(temp_file) as f:
            assert f.read() == "BRAND NEW CONTENT"

    def test_append_mode(self, temp_file):
        """Append mode should add to end."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "append", "line4")
        assert ok is True
        with open(temp_file) as f:
            content = f.read()
            assert content.endswith("line4")
            assert "line1" in content

    def test_replace_no_target_param(self, temp_file):
        """Replace without target should error."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "replace", "content", "")
        assert ok is False
        assert "target" in msg.lower()

    def test_valid_modes_constant(self):
        """VALID_MODES should list all supported modes."""
        from src.tools.file_utils import VALID_MODES

        assert "replace" in VALID_MODES
        assert "overwrite" in VALID_MODES
        assert "append" in VALID_MODES
        assert "delete" in VALID_MODES
        assert "insert_after" in VALID_MODES
        assert "insert_before" in VALID_MODES
        assert "regex_replace" in VALID_MODES
        assert "replace_all" in VALID_MODES

    def test_delete_mode(self, temp_file):
        """Delete should remove matching lines."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "delete", "", "line2")
        assert ok is True
        with open(temp_file) as f:
            content = f.read()
            assert "line2" not in content
            assert "line1" in content

    def test_insert_after_mode(self, temp_file):
        """insert_after should add content after target line."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "insert_after", "inserted", "line1")
        assert ok is True
        with open(temp_file) as f:
            lines = f.read().split("\n")
            idx = next(i for i, l in enumerate(lines) if "line1" in l)
            assert lines[idx + 1] == "inserted"

    def test_insert_before_mode(self, temp_file):
        """insert_before should add content before target line."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "insert_before", "inserted", "line2")
        assert ok is True
        with open(temp_file) as f:
            lines = f.read().split("\n")
            idx = next(i for i, l in enumerate(lines) if "line2" in l)
            assert lines[idx - 1] == "inserted"

    def test_regex_replace_mode(self, temp_file):
        """regex_replace should replace matching patterns."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "regex_replace", "REPLACED", r"line\d")
        assert ok is True
        with open(temp_file) as f:
            content = f.read()
            assert "REPLACED" in content
            assert "line1" not in content

    def test_unknown_mode(self, temp_file):
        """Unknown mode should return error."""
        from src.tools.file_utils import surgical_edit

        ok, msg = surgical_edit(temp_file, "nonexistent_mode", "content")
        assert ok is False
        assert "unknown mode" in msg.lower()

    def test_empty_file_replace(self, tmp_path):
        """Replace on empty file should report file starts with (empty file)."""
        from src.tools.file_utils import surgical_edit

        f = tmp_path / "empty.txt"
        f.write_text("")
        ok, msg = surgical_edit(str(f), "replace", "content", "MISSING")
        assert ok is False
        assert "empty file" in msg.lower()
