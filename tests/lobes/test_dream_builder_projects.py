import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.lobes.creative.dream_builder import build_dream_prompt

def test_build_dream_prompt_injects_projects():
    """Test that build_dream_prompt finds and injects user projects."""
    
    # Mock Path.glob to return fake todolist files
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.glob") as mock_glob:
            # Setup fake file
            mock_file = MagicMock()
            mock_file.read_text.return_value = """
            # My Project
            - [x] Done thing
            - [ ] Task 1
            - [ ] Task 2
            """
            # path parts: memory, users, 123, projects, private, todolist.md
            mock_file.parts = ("memory", "users", "123", "projects", "private", "todolist.md")
            
            mock_glob.return_value = [mock_file]
            
            # Run builder
            prompt = build_dream_prompt()
            
            # Verify
            assert "ACTIVE USER PROJECTS" in prompt
            assert "[User: 123] [Scope: PRIVATE] Task 1" in prompt
            assert "SUGGESTION: Use [TOOL: execute_skill" in prompt

def test_build_dream_prompt_no_projects():
    """Test behavior with no active projects."""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.glob", return_value=[]):
            prompt = build_dream_prompt()
            assert "ACTIVE USER PROJECTS" not in prompt
