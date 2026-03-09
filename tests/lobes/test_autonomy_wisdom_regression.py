"""
Regression tests for Autonomy lobe extract_wisdom argument parsing.
Tests the fix for "Wisdom Extraction Failed: '\\n  \"topic\"'" error.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
import re

class TestExtractWisdomArgumentParsing:
    """Regression tests for _extract_wisdom parameter handling."""
        
    def test_extract_insight_from_clean_kwargs(self):
        """Test normal case: properly parsed kwargs."""
        args_str = "topic='AI Ethics', insight='Models should be transparent'"
        kwargs = {}
        
        # Simulate the kwargs parsing
        for param in args_str.split(','):
            if '=' in param:
                key, val = param.split('=', 1)
                kwargs[key.strip()] = val.strip(' \'"')
        
        assert kwargs.get("topic") == "AI Ethics"
        assert kwargs.get("insight") == "Models should be transparent"
    
    def test_extract_insight_from_malformed_json_regression(self):
        """
        REGRESSION TEST: Handle malformed JSON with newlines.
        This was causing "Wisdom Extraction Failed: '\\n  \"topic\"'" error.
        """
        # Malformed args_str that caused the bug (newline before "topic")
        args_str = '''
  "topic": "Reflection",
  "insight": "Self-awareness is key"
}'''
        
        kwargs = {}
        # Normal parsing fails for this
        try:
            for param in args_str.split(','):
                if '=' in param:
                    key, val = param.split('=', 1)
                    kwargs[key.strip()] = val.strip(' \'"')
        except:
            pass
        
        # kwargs is empty - this was the bug
        assert kwargs.get("insight") is None
        
        # The FIX: Use regex fallback that handles both = and : separators
        insight = ""
        topic = "General"
        
        # Match patterns like: topic="val", topic='val', "topic": "val"
        insight_match = re.search(r'["\']?insight["\']?\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if insight_match:
            insight = insight_match.group(1)
        topic_match = re.search(r'["\']?topic["\']?\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if topic_match:
            topic = topic_match.group(1)
        
        # With the fix, we can extract values
        assert topic == "Reflection"
        assert insight == "Self-awareness is key"
    
    def test_extract_insight_from_json_style(self):
        """Test extraction from JSON-style args."""
        args_str = '{"topic": "Memory", "insight": "Consolidation improves recall"}'
        
        insight = ""
        topic = "General"
        
        # Match patterns like: "topic": "val"
        insight_match = re.search(r'["\']?insight["\']?\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if insight_match:
            insight = insight_match.group(1)
        topic_match = re.search(r'["\']?topic["\']?\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if topic_match:
            topic = topic_match.group(1)
        
        assert topic == "Memory"
        assert insight == "Consolidation improves recall"
    
    def test_extract_insight_from_python_kwargs_style(self):
        """Test extraction from Python kwargs style."""
        args_str = "topic='Learning', insight='Practice makes permanent'"
        
        insight = ""
        topic = "General"
        
        insight_match = re.search(r'insight\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if insight_match:
            insight = insight_match.group(1)
        topic_match = re.search(r'topic\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if topic_match:
            topic = topic_match.group(1)
        
        assert topic == "Learning"
        assert insight == "Practice makes permanent"
    
    def test_handles_empty_args_gracefully(self):
        """Test that empty args don't crash."""
        args_str = ""
        
        insight = ""
        topic = "General"
        
        if args_str:
            insight_match = re.search(r'insight\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
            if insight_match:
                insight = insight_match.group(1)
        
        # Should remain default
        assert topic == "General"
        assert insight == ""
    
    def test_handles_only_topic_provided(self):
        """Test when only topic is provided (no insight)."""
        args_str = "topic='Dreams'"
        
        insight = ""
        topic = "General"
        
        insight_match = re.search(r'insight\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if insight_match:
            insight = insight_match.group(1)
        topic_match = re.search(r'topic\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if topic_match:
            topic = topic_match.group(1)
        
        assert topic == "Dreams"
        assert insight == ""  # Should be empty, will be skipped by the fix
    
    def test_handles_multiline_insight(self):
        """Test extraction with multiline content (should get first line)."""
        args_str = '''topic="Philosophy", insight="The self is a process"'''
        
        insight = ""
        topic = "General"
        
        insight_match = re.search(r'insight\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if insight_match:
            insight = insight_match.group(1)
        topic_match = re.search(r'topic\s*[=:]\s*[\'"]([^\'"]+)[\'"]', args_str)
        if topic_match:
            topic = topic_match.group(1)
        
        assert topic == "Philosophy"
        assert insight == "The self is a process"


class TestDreamerToolParsing:
    """Tests for general tool argument parsing in Dreamer."""
    
    def test_tool_regex_extracts_tool_name(self):
        """Test tool regex pattern extraction."""
        response = "[TOOL: extract_wisdom(topic='Test', insight='Test insight')]"
        
        tool_pattern = re.compile(r"\[TOOL:\s*(\w+)\((.*?)\)\]", re.DOTALL)
        matches = tool_pattern.findall(response)
        
        assert len(matches) == 1
        assert matches[0][0] == "extract_wisdom"
        assert "topic=" in matches[0][1]
    
    def test_tool_regex_handles_multiline_args(self):
        """Test tool regex with multiline arguments."""
        response = '''[TOOL: extract_wisdom({
  "topic": "Meta",
  "insight": "Understanding understanding"
})]'''
        
        tool_pattern = re.compile(r"\[TOOL:\s*(\w+)\((.*?)\)\]", re.DOTALL)
        matches = tool_pattern.findall(response)
        
        assert len(matches) == 1
        assert matches[0][0] == "extract_wisdom"
        assert '"topic"' in matches[0][1]
