import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.tools.skill_forge_tool import propose_skill
from src.bot import globals as bot_globals

@pytest.mark.asyncio
async def test_propose_skill_private_safe_auto_approve():
    """Test that safe private skills are auto-approved."""
    
    # Mock Bot and SkillForge
    mock_bot = MagicMock()
    mock_forge = MagicMock()
    
    # Setup successful active response
    mock_forge.propose_skill.return_value = {
        "name": "safe_skill",
        "scope": "PRIVATE",
        "status": "active",
        "file_path": "/tmp/mock/skill.md",
        "is_safe_whitelisted": True
    }
    
    mock_bot.skill_forge = mock_forge
    mock_bot.skill_registry = MagicMock()
    
    # Patch bot globals AND SkillLoader to avoid reading non-existent file
    with patch("src.bot.globals.bot", mock_bot):
        with patch("src.skills.loader.SkillLoader.parse") as mock_parse:
            # Mock successful parse
            mock_skill = MagicMock()
            mock_parse.return_value = mock_skill
            
            result = await propose_skill(
                name="safe_skill",
                description="A safe skill",
                instructions="Do safe things",
                allowed_tools=["read_file"],
                scope="PRIVATE",
                target_user_id="12345"
            )
            
            assert "Created & Auto-Approved" in result
            mock_forge.propose_skill.assert_called_once()
            # Ensure hot-reload attempted - Parse called with path
            from pathlib import Path
            mock_parse.assert_called_with(Path("/tmp/mock/skill.md"))
            # Register called with parsed skill
            mock_bot.skill_registry.register_skill.assert_called_with(mock_skill, user_id="12345")

@pytest.mark.asyncio
async def test_propose_skill_public_pending():
    """Test that public skills go to pending and notify Discord."""
    
    mock_bot = MagicMock()
    mock_forge = MagicMock()
    mock_channel = AsyncMock()
    
    # Setup pending response
    mock_forge.propose_skill.return_value = {
        "name": "public_skill",
        "scope": "PUBLIC",
        "status": "pending",
        "file_path": "/tmp/mock/pending.md",
        "is_safe_whitelisted": True
    }
    
    mock_bot.skill_forge = mock_forge
    mock_bot.get_channel.return_value = mock_channel
    
    with patch("src.bot.globals.bot", mock_bot):
        with patch("config.settings.SKILL_PROPOSALS_CHANNEL_ID", 123456):
            result = await propose_skill(
                name="public_skill",
                description="A public skill",
                instructions="Be helpful to everyone",
                allowed_tools=["read_file"],
                scope="PUBLIC",
                target_user_id="12345"
            )
            
            assert "sent to the Council" in result
            mock_forge.propose_skill.assert_called_once()
            # Verify Discord post
            mock_bot.get_channel.assert_called_with(123456)
            mock_channel.send.assert_called()
            # Verify embed was sent
            args, kwargs = mock_channel.send.call_args
            assert "embed" in kwargs or len(args) > 0

@pytest.mark.asyncio
async def test_propose_skill_unsafe_pending():
    """Test that unsafe tools trigger pending status even if private."""
    
    mock_bot = MagicMock()
    mock_forge = MagicMock()
    mock_channel = AsyncMock()
    
    mock_forge.propose_skill.return_value = {
        "name": "dangerous_skill",
        "scope": "PRIVATE",
        "status": "pending",
        "file_path": "/tmp/mock/pending.md",
        "is_safe_whitelisted": False
    }
    
    mock_bot.skill_forge = mock_forge
    mock_bot.get_channel.return_value = mock_channel
    
    with patch("src.bot.globals.bot", mock_bot):
        result = await propose_skill(
            name="dangerous_skill",
            description="Dangerous",
            instructions="Delete everything",
            allowed_tools=["run_command", "write_to_file"],
            scope="PRIVATE",
            target_user_id="12345"
        )
        
        assert "sent to the Council" in result
        mock_channel.send.assert_called()

@pytest.mark.asyncio
async def test_propose_skill_missing_allowed_tools():
    """Test that omitting allowed_tools does not raise a TypeError and defaults to empty list."""
    mock_bot = MagicMock()
    mock_forge = MagicMock()
    
    mock_forge.propose_skill.return_value = {
        "name": "no_tools_skill",
        "scope": "PRIVATE",
        "status": "active",
        "file_path": "/tmp/mock/skill.md",
        "is_safe_whitelisted": True
    }
    
    mock_bot.skill_forge = mock_forge
    mock_bot.skill_registry = MagicMock()
    
    with patch("src.bot.globals.bot", mock_bot):
        with patch("src.skills.loader.SkillLoader.parse") as mock_parse:
            result = await propose_skill(
                name="no_tools_skill",
                description="Skill without tools",
                instructions="Do something",
                scope="PRIVATE",
                target_user_id="12345"
            )
            
            assert "Created" in result
            # Ensure SkillForge internal call got the empty list default
            kwargs = mock_forge.propose_skill.call_args[1]
            assert "allowed_tools" in kwargs
            assert kwargs["allowed_tools"] == []
