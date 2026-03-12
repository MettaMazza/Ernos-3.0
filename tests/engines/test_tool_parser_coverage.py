"""
Coverage tests for src/engines/tool_parser.py.
Targets 8 uncovered lines: triple-quote parsing, escape sequences, literal types.
"""
import pytest
from src.engines.tool_parser import parse_tool_args


class TestParseToolArgs:
    def test_empty_string(self):
        assert parse_tool_args("") == {}

    def test_whitespace_only(self):
        assert parse_tool_args("   ") == {}

    def test_basic_key_value(self):
        result = parse_tool_args('name="hello"')
        assert result == {"name": "hello"}

    def test_multiple_args(self):
        result = parse_tool_args('path="test.py", mode="overwrite"')
        assert result == {"path": "test.py", "mode": "overwrite"}

    def test_triple_quote(self):
        result = parse_tool_args('code="""print("hello")"""')
        assert result["code"] == 'print("hello")'

    def test_triple_quote_multiline(self):
        result = parse_tool_args('code="""line1\nline2\nline3"""')
        assert "line2" in result["code"]

    def test_triple_quote_unterminated(self):
        result = parse_tool_args('code="""unterminated')
        assert result["code"] == "unterminated"

    def test_escape_newline(self):
        result = parse_tool_args(r'msg="hello\nworld"')
        assert result["msg"] == "hello\nworld"

    def test_escape_tab(self):
        result = parse_tool_args(r'msg="col1\tcol2"')
        assert result["msg"] == "col1\tcol2"

    def test_escape_backslash(self):
        result = parse_tool_args(r'path="C:\\Users\\file"')
        assert result["path"] == "C:\\Users\\file"

    def test_escape_quote(self):
        result = parse_tool_args(r'msg="say \"hello\""')
        assert result["msg"] == 'say "hello"'

    def test_unknown_escape(self):
        result = parse_tool_args(r'msg="test\x"')
        assert "\\x" in result["msg"]

    def test_unquoted_true(self):
        result = parse_tool_args("flag=true")
        assert result["flag"] is True

    def test_unquoted_false(self):
        result = parse_tool_args("flag=false")
        assert result["flag"] is False

    def test_unquoted_none(self):
        result = parse_tool_args("value=none")
        assert result["value"] is None

    def test_unquoted_int(self):
        result = parse_tool_args("count=42")
        assert result["count"] == 42

    def test_unquoted_float(self):
        result = parse_tool_args("rate=3.14")
        assert result["rate"] == 3.14

    def test_unquoted_string(self):
        result = parse_tool_args("name=hello")
        assert result["name"] == "hello"

    def test_key_no_equals(self):
        # Should fall through gracefully
        result = parse_tool_args("standalone_text_without_equals")
        assert "content" in result

    def test_empty_value_at_end(self):
        result = parse_tool_args("key=")
        assert result["key"] == ""

    def test_single_quote_value(self):
        result = parse_tool_args("name='hello world'")
        assert result["name"] == "hello world"

    def test_single_quote_triple(self):
        result = parse_tool_args("code='''x = 1'''")
        assert result["code"] == "x = 1"
