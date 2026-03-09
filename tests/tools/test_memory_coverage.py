import pytest
from unittest.mock import MagicMock, mock_open, patch
from src.tools.memory import update_persona, manage_goals, recall_user

def test_update_persona_invalid_mode():
    res = update_persona("Identity", mode="invalid", request_scope="PRIVATE", user_id="12345")
    assert "Error: Invalid mode" in res

def test_manage_goals_invalid_id(tmp_path, monkeypatch):
    # Test with non-existent goal_id
    monkeypatch.chdir(tmp_path)
    test_user_id = "12345"
    user_silo = tmp_path / "memory" / "users" / test_user_id
    user_silo.mkdir(parents=True)
    (user_silo / "goals.json").write_text('[{"id": "goal_abc123", "description": "Goal", "status": "active", "priority": 3, "progress": 0}]')
    
    res = manage_goals("complete", goal_id="not-a-real-id", user_id=test_user_id)
    assert "not found" in res

def test_manage_goals_unknown_action(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    test_user_id = "12345"
    user_silo = tmp_path / "memory" / "users" / test_user_id
    user_silo.mkdir(parents=True)
    (user_silo / "goals.json").write_text("[]")
    
    res = manage_goals("dance", user_id=test_user_id)
    assert "Unknown action" in res

def test_recall_user_empty_matches(tmp_path, monkeypatch):
    # Test line 152-153: Silo exists but no matches (or empty file)
    monkeypatch.chdir(tmp_path)
    
    user_dir = tmp_path / "memory" / "public" / "users" / "123"
    user_dir.mkdir(parents=True)
    (user_dir / "timeline.jsonl").write_text("") # Empty
    
    # Since we chdir'd, Path("memory") resolves to tmp_path/memory
    # We must ensure we rely on the imported recall_user 
    # but since we are not patching, specific import location matters less
    # as long as it uses pathlib.Path (which is relative to cwd by default)
    
    res = recall_user(user_id="123")
    assert "Silo exists but is empty" in res
