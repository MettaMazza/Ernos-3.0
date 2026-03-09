import pytest
from unittest.mock import MagicMock, patch
import os
from src.prompts.manager import PromptManager

@pytest.fixture
def prompt_manager(tmp_path):
    # Setup dummy prompts
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "kernel.txt").write_text("KERNEL")
    (d / "identity.txt").write_text("IDENTITY")
    (d / "dynamic_context.txt").write_text("""[HUD]
Time: {timestamp}
Scope: {scope}
View: {view_mode}
Goals: {active_goals}""")
    
    return PromptManager(prompt_dir=str(d))

def test_prompt_rendering_public(prompt_manager):
    """Verify standard user view."""
    prompt = prompt_manager.get_system_prompt(
        timestamp="2026-02-01",
        scope="PUBLIC",
        user_id="123",
        active_goals="None",
        is_core=False
    )
    
    assert "KERNEL" in prompt
    assert "IDENTITY" in prompt
    assert "Time: 2026-02-01" in prompt
    assert "Scope: PUBLIC" in prompt
    assert "View: USER HUD" in prompt

def test_prompt_rendering_core(prompt_manager):
    """Verify God View for Core."""
    prompt = prompt_manager.get_system_prompt(
        timestamp="2026-02-01",
        scope="CORE",
        user_id="ADMIN",
        active_goals="Global Optimization",
        is_core=True
    )
    
    assert "Scope: CORE" in prompt
    assert "View: GOD VIEW" in prompt
    assert "Goals: Global Optimization" in prompt

def test_missing_template_fallback(prompt_manager):
    """Verify it doesn't crash if dynamic_context.txt is missing."""
    # Delete file
    os.remove(prompt_manager.dynamic_file)
    
    prompt = prompt_manager.get_system_prompt()
    assert "KERNEL" in prompt
    assert "IDENTITY" in prompt
    # Dynamic part should be missing but not crash

def test_broken_template_fallback(prompt_manager):
    """Verify it handles broken template keys gracefully."""
    # Write broken template (missing closing brace)
    with open(prompt_manager.dynamic_file, "w") as f:
        f.write("Time: {timestamp")
        
    prompt = prompt_manager.get_system_prompt(timestamp="Now")
    # Should fallback to raw text or safe failure, checking logic
    # Our code catches exception and returns raw text
    assert "Time: {timestamp" in prompt
