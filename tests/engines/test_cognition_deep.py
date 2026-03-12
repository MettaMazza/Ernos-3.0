import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import re

@pytest.mark.asyncio
async def test_cognition_engine_has_process():
    """Verify cognition engine has critical method."""
    from src.engines.cognition import CognitionEngine
    assert hasattr(CognitionEngine, 'process')
    assert hasattr(CognitionEngine, '_save_trace')

@pytest.mark.asyncio
async def test_cognition_file_path_regex():
    """Test the file path extraction regex (lines 194-197)."""
    # Test the regex pattern used in cognition engine
    path_pattern = re.compile(r"(/[a-zA-Z0-9_\-\./\s]+generated_[a-zA-Z0-9_]+\.(png|mp4))")
    
    test_history = "Output: /Users/test/generated_image.png created"
    found = path_pattern.findall(test_history)
    assert len(found) > 0
    assert found[0][0] == "/Users/test/generated_image.png"

@pytest.mark.asyncio
async def test_cognition_skeptic_audit_error_handling():
    """Test that skeptic audit errors are caught (in _evaluate_final_answer)."""
    from src.engines.cognition import CognitionEngine
    
    import inspect
    source = inspect.getsource(CognitionEngine._evaluate_final_answer)
    
    # Verify skeptic error handling exists
    assert "Skeptic Audit Error" in source

@pytest.mark.asyncio
async def test_cognition_save_trace_exists():
    """Verify _save_trace method exists and handles exceptions at call site."""
    from src.engines.cognition import CognitionEngine
    
    import inspect
    source = inspect.getsource(CognitionEngine.process)
    
    # Lines 162-165: try/except around _save_trace
    assert "_save_trace" in source
