"""
Tests for Error Tracker
Targeting 95%+ coverage for src/tools/error_tracker.py
"""
import pytest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
from src.tools.error_tracker import ErrorTracker


class TestErrorTrackerSingleton:
    """Tests for singleton behavior."""
    
    def test_singleton_instance(self):
        """Test that ErrorTracker is a singleton."""
        # Reset singleton for test
        ErrorTracker._instance = None
        ErrorTracker._lock = __import__('threading').Lock()
        
        tracker1 = ErrorTracker()
        tracker2 = ErrorTracker()
        
        assert tracker1 is tracker2
    
    def test_initialization_once(self):
        """Test that initialization only happens once."""
        ErrorTracker._instance = None
        ErrorTracker._lock = __import__('threading').Lock()
        
        tracker = ErrorTracker()
        assert tracker._initialized is True
        
        # Second init should be skipped
        tracker.__init__()
        assert tracker._initialized is True


class TestLogError:
    """Tests for log_error method."""
    
    def setup_method(self):
        """Setup fresh tracker for each test."""
        ErrorTracker._instance = None
        ErrorTracker._lock = __import__('threading').Lock()
        self.temp_dir = tempfile.mkdtemp()
        with patch.object(ErrorTracker, '__init__', lambda self: None):
            self.tracker = ErrorTracker()
            self.tracker._initialized = True
            self.tracker.log_dir = Path(self.temp_dir) / "errors"
            self.tracker.log_dir.mkdir(parents=True, exist_ok=True)
            self.tracker.log_file = self.tracker.log_dir / "error_trace.jsonl"
    
    def teardown_method(self):
        """Cleanup temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_log_error_basic(self):
        """Test basic error logging."""
        self.tracker.log_error(
            category="TOOL",
            source="test_tool",
            error_type="TestError",
            error_message="Test error message"
        )
        
        assert self.tracker.log_file.exists()
        with open(self.tracker.log_file) as f:
            entry = json.loads(f.readline())
        
        assert entry["category"] == "TOOL"
        assert entry["source"] == "test_tool"
        assert entry["error_type"] == "TestError"
        assert entry["error_message"] == "Test error message"
    
    def test_log_error_with_context(self):
        """Test logging with context."""
        self.tracker.log_error(
            category="AGENT",
            source="test_agent",
            error_type="ContextError",
            error_message="Error",
            context={"key": "value"}
        )
        
        with open(self.tracker.log_file) as f:
            entry = json.loads(f.readline())
        
        assert entry["context"]["key"] == "value"
    
    def test_log_error_with_traceback(self):
        """Test logging with traceback."""
        self.tracker.log_error(
            category="LOBE",
            source="test_lobe",
            error_type="TraceError",
            error_message="Error",
            traceback_str="Traceback (most recent call last):\n  File test.py"
        )
        
        with open(self.tracker.log_file) as f:
            entry = json.loads(f.readline())
        
        assert "Traceback" in entry["traceback"]
    
    def test_log_error_with_user_id(self):
        """Test logging with user ID and scope."""
        self.tracker.log_error(
            category="ENGINE",
            source="test_engine",
            error_type="UserError",
            error_message="Error",
            user_id="12345",
            request_scope="PRIVATE"
        )
        
        with open(self.tracker.log_file) as f:
            entry = json.loads(f.readline())
        
        assert entry["user_id"] == "12345"
        assert entry["scope"] == "PRIVATE"
    
    def test_log_error_truncates_long_message(self):
        """Test that long messages are truncated."""
        long_message = "x" * 10000
        self.tracker.log_error(
            category="TOOL",
            source="test",
            error_type="LongError",
            error_message=long_message
        )
        
        with open(self.tracker.log_file) as f:
            entry = json.loads(f.readline())
        
        assert len(entry["error_message"]) <= 5000
    
    def test_log_error_file_write_failure(self):
        """Test graceful handling of file write failure."""
        self.tracker.log_file = Path("/nonexistent/path/error.jsonl")
        
        # Should not raise
        self.tracker.log_error(
            category="TOOL",
            source="test",
            error_type="Error",
            error_message="Test"
        )
        assert True  # No exception: error handled gracefully


class TestConvenienceMethods:
    """Tests for convenience logging methods."""
    
    def setup_method(self):
        """Setup fresh tracker for each test."""
        ErrorTracker._instance = None
        ErrorTracker._lock = __import__('threading').Lock()
        self.temp_dir = tempfile.mkdtemp()
        with patch.object(ErrorTracker, '__init__', lambda self: None):
            self.tracker = ErrorTracker()
            self.tracker._initialized = True
            self.tracker.log_dir = Path(self.temp_dir) / "errors"
            self.tracker.log_dir.mkdir(parents=True, exist_ok=True)
            self.tracker.log_file = self.tracker.log_dir / "error_trace.jsonl"
    
    def teardown_method(self):
        """Cleanup temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_log_tool_failure(self):
        """Test tool failure logging."""
        error = ValueError("Tool failed")
        self.tracker.log_tool_failure(
            tool_name="my_tool",
            error=error,
            params={"arg1": "value1"}
        )
        
        with open(self.tracker.log_file) as f:
            entry = json.loads(f.readline())
        
        assert entry["category"] == "TOOL"
        assert entry["source"] == "my_tool"
        assert entry["error_type"] == "ValueError"
    
    def test_log_lobe_failure(self):
        """Test lobe failure logging."""
        error = RuntimeError("Lobe crashed")
        self.tracker.log_lobe_failure(
            lobe_name="science_lobe",
            error=error,
            instruction="Calculate something"
        )
        
        with open(self.tracker.log_file) as f:
            entry = json.loads(f.readline())
        
        assert entry["category"] == "LOBE"
        assert entry["source"] == "science_lobe"
    
    def test_log_agent_failure(self):
        """Test agent failure logging."""
        error = Exception("Agent error")
        self.tracker.log_agent_failure(
            agent_name="PreProcessor",
            error=error,
            input_text="User input"
        )
        
        with open(self.tracker.log_file) as f:
            entry = json.loads(f.readline())
        
        assert entry["category"] == "AGENT"


class TestGetRecentErrors:
    """Tests for get_recent_errors method."""
    
    def setup_method(self):
        """Setup fresh tracker for each test."""
        ErrorTracker._instance = None
        ErrorTracker._lock = __import__('threading').Lock()
        self.temp_dir = tempfile.mkdtemp()
        with patch.object(ErrorTracker, '__init__', lambda self: None):
            self.tracker = ErrorTracker()
            self.tracker._initialized = True
            self.tracker.log_dir = Path(self.temp_dir) / "errors"
            self.tracker.log_dir.mkdir(parents=True, exist_ok=True)
            self.tracker.log_file = self.tracker.log_dir / "error_trace.jsonl"
    
    def teardown_method(self):
        """Cleanup temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_recent_errors_empty(self):
        """Test when no errors logged."""
        result = self.tracker.get_recent_errors()
        assert result == []
    
    def test_get_recent_errors_single(self):
        """Test retrieving single error."""
        self.tracker.log_error("TOOL", "test", "Error", "message")
        
        result = self.tracker.get_recent_errors()
        
        assert len(result) == 1
        assert result[0]["source"] == "test"
    
    def test_get_recent_errors_limited(self):
        """Test limiting results."""
        for i in range(10):
            self.tracker.log_error("TOOL", f"test_{i}", "Error", "msg")
        
        result = self.tracker.get_recent_errors(count=3)
        
        assert len(result) == 3
    
    def test_get_recent_errors_by_category(self):
        """Test filtering by category."""
        self.tracker.log_error("TOOL", "tool", "Error", "msg")
        self.tracker.log_error("AGENT", "agent", "Error", "msg")
        self.tracker.log_error("LOBE", "lobe", "Error", "msg")
        
        result = self.tracker.get_recent_errors(category="TOOL")
        
        assert len(result) == 1
        assert result[0]["category"] == "TOOL"
    
    def test_get_recent_errors_most_recent_first(self):
        """Test that results are ordered most recent first."""
        self.tracker.log_error("TOOL", "first", "Error", "msg")
        self.tracker.log_error("TOOL", "second", "Error", "msg")
        self.tracker.log_error("TOOL", "third", "Error", "msg")
        
        result = self.tracker.get_recent_errors()
        
        assert result[0]["source"] == "third"
        assert result[2]["source"] == "first"


class TestGetErrorSummary:
    """Tests for get_error_summary method."""
    
    def setup_method(self):
        """Setup fresh tracker for each test."""
        ErrorTracker._instance = None
        ErrorTracker._lock = __import__('threading').Lock()
        self.temp_dir = tempfile.mkdtemp()
        with patch.object(ErrorTracker, '__init__', lambda self: None):
            self.tracker = ErrorTracker()
            self.tracker._initialized = True
            self.tracker.log_dir = Path(self.temp_dir) / "errors"
            self.tracker.log_dir.mkdir(parents=True, exist_ok=True)
            self.tracker.log_file = self.tracker.log_dir / "error_trace.jsonl"
    
    def teardown_method(self):
        """Cleanup temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_summary_empty(self):
        """Test summary when no errors."""
        result = self.tracker.get_error_summary()
        
        assert result["total"] == 0
        assert result["last_24h"] == 0
    
    def test_get_summary_with_errors(self):
        """Test summary with multiple errors."""
        self.tracker.log_error("TOOL", "tool1", "Error", "msg")
        self.tracker.log_error("TOOL", "tool2", "Error", "msg")
        self.tracker.log_error("AGENT", "agent1", "Error", "msg")
        
        result = self.tracker.get_error_summary()
        
        assert result["total"] == 3
        assert result["by_category"]["TOOL"] == 2
        assert result["by_category"]["AGENT"] == 1
        assert result["by_source"]["tool1"] == 1
    
    def test_get_summary_last_24h(self):
        """Test that recent errors are counted."""
        self.tracker.log_error("TOOL", "test", "Error", "msg")
        
        result = self.tracker.get_error_summary()
        
        # Should count as in last 24h since it was just logged
        assert result["last_24h"] >= 1
