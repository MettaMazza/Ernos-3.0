from src.prompts.manager import PromptManager
import os
import pytest

def test_prompt_manager_init(tmp_path):
    """Test initializing manager with custom path."""
    pm = PromptManager(prompt_dir=str(tmp_path))
    assert pm.prompt_dir == str(tmp_path)

def test_get_system_prompt_empty(tmp_path):
    """If directory is empty, should return empty prompt (no errors)."""
    pm = PromptManager(prompt_dir=str(tmp_path))
    res = pm.get_system_prompt()
    # It returns at least the Roster footer
    assert "ROOM ROSTER" in res

def test_get_system_prompt_partial(tmp_path):
    """Test with only kernel file."""
    (tmp_path / "kernel_backup.txt").write_text("Test Kernel")
    pm = PromptManager(prompt_dir=str(tmp_path))
    res = pm.get_system_prompt()
    assert "Test Kernel" in res
    assert "ROOM ROSTER" in res

def test_get_system_prompt_full_stack(tmp_path):
    """Test full Kernel + Identity + Context stack."""
    (tmp_path / "kernel_backup.txt").write_text("Kernel Rules")
    (tmp_path / "identity_core.txt").write_text("My Identity")
    (tmp_path / "dynamic_context.txt").write_text("Context Update")
    
    pm = PromptManager(prompt_dir=str(tmp_path))
    prompt = pm.get_system_prompt()
    
    assert "Kernel Rules" in prompt
    assert "My Identity" in prompt
    assert "Context Update" in prompt
    assert prompt.count("\n\n") >= 2  # Separators included

def test_prompt_manager_missing_file(tmp_path):
    """Test reading non-existent file."""
    pm = PromptManager(prompt_dir=str(tmp_path))
    # Should log warning and return empty string
    assert pm._read_file(str(tmp_path / "missing.txt")) == ""

def test_prompt_manager_read_error(tmp_path, mocker):
    """Test exception during file read."""
    # Ensure file exists so it tries to read
    (tmp_path / "exists.txt").write_text("content")
    pm = PromptManager(prompt_dir=str(tmp_path))
    
    # Mock secure_loader to raise
    mocker.patch("src.core.secure_loader.load_prompt", side_effect=Exception("Read Error"))
    
    assert pm._read_file(str(tmp_path / "exists.txt")) == ""
