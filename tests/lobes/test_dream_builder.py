import logging
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.lobes.creative.dream_builder import build_dream_prompt

@pytest.fixture
def mock_data_dir(tmp_path):
    # Setup temporary directory structure resembling data_dir
    core_dir = tmp_path / "core"
    core_dir.mkdir()
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    research_dir = core_dir / "research"
    research_dir.mkdir()
    
    # Mock data_dir to return our tmp_path
    with patch('src.lobes.creative.dream_builder.data_dir', return_value=tmp_path):
        yield tmp_path

def test_build_dream_prompt_empty_system_turns(mock_data_dir, caplog):
    """Test that an empty system_turns.jsonl does not throw a JSONDecodeError."""
    # Create empty system_turns.jsonl
    turns_file = mock_data_dir / "core/system_turns.jsonl"
    
    # Scenario 1: Completely empty file
    turns_file.write_text("")
    with caplog.at_level(logging.WARNING):
        prompt = build_dream_prompt()
        assert "SYSTEM_AUTONOMY_TRIGGER" in prompt
        # We should NOT see any warnings about JSONDecodeError
        assert not any("JSONDecodeError" in rec.message for rec in caplog.records)
        
    caplog.clear()
        
    # Scenario 2: File with only blank lines
    turns_file.write_text("\n\n  \n\n")
    with caplog.at_level(logging.WARNING):
        prompt = build_dream_prompt()
        assert "SYSTEM_AUTONOMY_TRIGGER" in prompt
        # We should NOT see any warnings about JSONDecodeError
        assert not any("JSONDecodeError" in rec.message for rec in caplog.records)

def test_build_dream_prompt_malformed_json_suppressed(mock_data_dir, caplog):
    """Test that truly malformed JSON in system_turns is caught and suppressed correctly."""
    turns_file = mock_data_dir / "core/system_turns.jsonl"
    
    # Write invalid JSON
    turns_file.write_text('{"invalid_json": "missing quote} \n')
    
    with caplog.at_level(logging.WARNING):
        build_dream_prompt()
        # This SHOULD trigger a JSONDecodeError warning because we found a non-empty string that failed to parse
        assert any("JSONDecodeError" in rec.message for rec in caplog.records)

def test_build_dream_prompt_valid_turns(mock_data_dir):
    """Test that valid system_turns are included in the prompt."""
    turns_file = mock_data_dir / "core/system_turns.jsonl"
    valid_turn = json.dumps({"scope": "PUBLIC", "bot_message": "Hello world!"})
    turns_file.write_text(valid_turn + "\n")
    
    prompt = build_dream_prompt()
    assert "RECENT INTERACTIONS" in prompt
    assert "[PUBLIC] Hello world!" in prompt
