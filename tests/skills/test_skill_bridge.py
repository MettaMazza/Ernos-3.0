import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.tools.skill_bridge import execute_skill
from src.bot import globals as bot_globals

@pytest.mark.asyncio
async def test_execute_skill_success():
    """Test successful skill execution via bridge."""
    # Setup Mock Bot
    mock_bot = MagicMock()
    mock_registry = MagicMock()
    mock_sandbox = MagicMock()
    
    # Reset globals
    original_bot = bot_globals.bot
    bot_globals.bot = mock_bot
    
    try:
        mock_bot.skill_registry = mock_registry
        mock_bot.skill_sandbox = mock_sandbox

        # Setup Mock Skill
        mock_skill = MagicMock()
        mock_skill.name = "project_manager"
        mock_registry.get_skill.return_value = mock_skill
        
        # Setup Sandbox Result
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "[SKILL EXECUTION: project_manager]\nINSTRUCTIONS: Do the thing."
        mock_sandbox.execute.return_value = mock_result
        
        # Execute Tool
        result = await execute_skill("project_manager", context="Task 1", user_id="123", request_scope="PUBLIC")
        
        # Verify
        assert "[SKILL EXECUTION: project_manager]" in result
        mock_registry.get_skill.assert_called_with("project_manager", user_id="123")
        mock_sandbox.execute.assert_called_with(
            skill=mock_skill,
            context="Task 1",
            user_id="123",
            scope="PUBLIC"
        )
    finally:
        bot_globals.bot = original_bot

@pytest.mark.asyncio
async def test_execute_skill_not_found():
    """Test explicit error when skill missing."""
    mock_bot = MagicMock()
    mock_registry = MagicMock()
    original_bot = bot_globals.bot
    bot_globals.bot = mock_bot
    
    try:
        mock_bot.skill_registry = mock_registry
        mock_registry.get_skill.return_value = None
        mock_skill_item = MagicMock()
        mock_skill_item.name = "existing_skill"
        mock_registry.list_skills.return_value = [mock_skill_item]
        
        # Execute Tool
        result = await execute_skill("unknown_skill", user_id="123")
        
        # Verify
        assert "Error: Skill 'unknown_skill' not found" in result
        assert "Available skills: existing_skill" in result
    finally:
        bot_globals.bot = original_bot

@pytest.mark.asyncio
async def test_execute_skill_denied():
    """Test when sandbox denies execution."""
    mock_bot = MagicMock()
    mock_registry = MagicMock()
    mock_sandbox = MagicMock()
    original_bot = bot_globals.bot
    bot_globals.bot = mock_bot
    
    try:
        mock_bot.skill_registry = mock_registry
        mock_bot.skill_sandbox = mock_sandbox

        mock_skill = MagicMock()
        mock_skill.name = "dangerous_skill"
        mock_registry.get_skill.return_value = mock_skill
        
        # Setup Sandbox Denial
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Scope denied"
        mock_sandbox.execute.return_value = mock_result
        
        # Execute Tool
        result = await execute_skill("dangerous_skill", user_id="123")
        
        # Verify
        assert "Skill Execution Denied: Scope denied" in result
    finally:
        bot_globals.bot = original_bot
