"""
Regression tests for edit_skill tool.

Tests:
1. SkillForge.edit_skill() backend logic (update instructions, description, tools)
2. edit_skill tool wrapper (integration via bot mock)
3. Edge cases: not found, no changes, dangerous content, version bumping
4. Security: re-approval required for restricted tools
"""
import pytest
import hashlib
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path


# === SkillForge Backend Tests ===

class TestSkillForgeEditSkill:
    """Tests for SkillForge.edit_skill() method."""

    def _make_forge(self, tmp_path):
        """Create a SkillForge with tmp_path-based directories."""
        from src.lobes.strategy.skill_forge import SkillForge
        forge = SkillForge.__new__(SkillForge)
        forge._registry = MagicMock()
        forge._engine = None
        forge._pending = []
        forge._forge_log = []
        # Override class-level paths
        forge.FORGE_DIR = tmp_path / "forge"
        forge.PENDING_DIR = tmp_path / "forge" / "pending"
        forge.QUEUE_FILE = tmp_path / "forge" / "pending.json"
        forge.LOG_FILE = tmp_path / "forge" / "forge_log.json"
        forge.FORGE_DIR.mkdir(parents=True, exist_ok=True)
        return forge

    def _create_skill_file(self, tmp_path, user_id, skill_name, 
                           instructions="Do safe things", 
                           tools=None, version="1.0.0"):
        """Create a valid SKILL.md file in the expected location."""
        if tools is None:
            tools = ["read_file"]
        tools_yaml = "\n".join([f"  - {t}" for t in tools])
        body = instructions.strip()
        approved_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        
        skill_dir = tmp_path / "memory" / "users" / str(user_id) / "skills" / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        content = f"""---
name: {skill_name}
description: A test skill
version: {version}
author: {user_id}
scope: PRIVATE
approved_hash: {approved_hash}
allowed_tools:
{tools_yaml}
---

{instructions}
"""
        skill_file.write_text(content, encoding="utf-8")
        return skill_file

    def test_edit_instructions_updates_file(self, tmp_path):
        """Editing instructions should rewrite the SKILL.md with new content."""
        forge = self._make_forge(tmp_path)
        skill_file = self._create_skill_file(tmp_path, "12345", "test_skill")

        with patch("src.lobes.strategy.skill_forge._PROJECT_ROOT", tmp_path / "memory" / "users" / "12345" / "skills" / "test_skill" and tmp_path):
            # We need to patch _PROJECT_ROOT so skill_path resolves correctly
            pass

        # Directly patch _PROJECT_ROOT in the module
        import src.lobes.strategy.skill_forge as sf_module
        original_root = sf_module._PROJECT_ROOT
        sf_module._PROJECT_ROOT = tmp_path
        
        try:
            with patch("config.settings") as mock_settings:
                mock_settings.ADMIN_ID = "99999"
                mock_settings.ADMIN_IDS = []
                
                result = forge.edit_skill(
                    name="test_skill",
                    user_id="12345",
                    instructions="New improved instructions"
                )
            
            assert result["status"] == "active"
            assert result["name"] == "test_skill"
            assert "instructions" in result["fields_updated"]
            assert result["version"] == "1.0.1"
            
            # Verify file was actually rewritten
            updated_content = skill_file.read_text()
            assert "New improved instructions" in updated_content
        finally:
            sf_module._PROJECT_ROOT = original_root

    def test_edit_description_only(self, tmp_path):
        """Editing only description should preserve instructions."""
        forge = self._make_forge(tmp_path)
        self._create_skill_file(tmp_path, "12345", "test_skill",
                               instructions="Original instructions here")

        import src.lobes.strategy.skill_forge as sf_module
        original_root = sf_module._PROJECT_ROOT
        sf_module._PROJECT_ROOT = tmp_path
        
        try:
            with patch("config.settings") as mock_settings:
                mock_settings.ADMIN_ID = "99999"
                mock_settings.ADMIN_IDS = []
                
                result = forge.edit_skill(
                    name="test_skill",
                    user_id="12345",
                    description="Updated description"
                )
            
            assert result["status"] == "active"
            assert result["fields_updated"] == ["description"]
            
            # Original instructions should be preserved
            skill_file = tmp_path / "memory" / "users" / "12345" / "skills" / "test_skill" / "SKILL.md"
            content = skill_file.read_text()
            assert "Original instructions here" in content
            assert "Updated description" in content
        finally:
            sf_module._PROJECT_ROOT = original_root

    def test_edit_not_found(self, tmp_path):
        """Editing a non-existent skill should return not_found."""
        forge = self._make_forge(tmp_path)
        
        import src.lobes.strategy.skill_forge as sf_module
        original_root = sf_module._PROJECT_ROOT
        sf_module._PROJECT_ROOT = tmp_path
        
        try:
            result = forge.edit_skill(
                name="nonexistent_skill",
                user_id="12345",
                instructions="Doesn't matter"
            )
            assert result["status"] == "not_found"
        finally:
            sf_module._PROJECT_ROOT = original_root

    def test_edit_no_changes(self, tmp_path):
        """Calling edit with no fields should return no_changes."""
        forge = self._make_forge(tmp_path)
        self._create_skill_file(tmp_path, "12345", "test_skill")

        import src.lobes.strategy.skill_forge as sf_module
        original_root = sf_module._PROJECT_ROOT
        sf_module._PROJECT_ROOT = tmp_path
        
        try:
            result = forge.edit_skill(
                name="test_skill",
                user_id="12345",
            )
            assert result["status"] == "no_changes"
        finally:
            sf_module._PROJECT_ROOT = original_root

    def test_edit_version_bumps(self, tmp_path):
        """Each edit should bump the patch version."""
        forge = self._make_forge(tmp_path)
        self._create_skill_file(tmp_path, "12345", "test_skill", version="1.2.3")

        import src.lobes.strategy.skill_forge as sf_module
        original_root = sf_module._PROJECT_ROOT
        sf_module._PROJECT_ROOT = tmp_path
        
        try:
            with patch("config.settings") as mock_settings:
                mock_settings.ADMIN_ID = "99999"
                mock_settings.ADMIN_IDS = []
                
                result = forge.edit_skill(
                    name="test_skill",
                    user_id="12345",
                    description="Version bump test"
                )
            assert result["version"] == "1.2.4"
        finally:
            sf_module._PROJECT_ROOT = original_root

    def test_edit_rejected_dangerous_instructions(self, tmp_path):
        """Instructions with dangerous patterns should be rejected."""
        forge = self._make_forge(tmp_path)
        self._create_skill_file(tmp_path, "12345", "test_skill")

        import src.lobes.strategy.skill_forge as sf_module
        original_root = sf_module._PROJECT_ROOT
        sf_module._PROJECT_ROOT = tmp_path
        
        try:
            result = forge.edit_skill(
                name="test_skill",
                user_id="12345",
                instructions="eval(malicious_code)"
            )
            assert result["status"] == "rejected"
        finally:
            sf_module._PROJECT_ROOT = original_root

    def test_edit_restricted_tools_requires_reapproval(self, tmp_path):
        """Adding restricted tools should send edit to pending."""
        forge = self._make_forge(tmp_path)
        self._create_skill_file(tmp_path, "12345", "test_skill", tools=["read_file"])

        import src.lobes.strategy.skill_forge as sf_module
        original_root = sf_module._PROJECT_ROOT
        sf_module._PROJECT_ROOT = tmp_path
        
        try:
            with patch("config.settings") as mock_settings:
                mock_settings.ADMIN_ID = "99999"
                mock_settings.ADMIN_IDS = []
                
                result = forge.edit_skill(
                    name="test_skill",
                    user_id="12345",
                    allowed_tools=["read_file", "run_command"],  # run_command is restricted
                )
            assert result["status"] == "pending"
            assert len(forge._pending) == 1
        finally:
            sf_module._PROJECT_ROOT = original_root

    def test_edit_approved_hash_recalculated(self, tmp_path):
        """approved_hash should be recalculated after instruction edit."""
        forge = self._make_forge(tmp_path)
        self._create_skill_file(tmp_path, "12345", "test_skill",
                               instructions="Original body")

        import src.lobes.strategy.skill_forge as sf_module
        original_root = sf_module._PROJECT_ROOT
        sf_module._PROJECT_ROOT = tmp_path
        
        try:
            with patch("config.settings") as mock_settings:
                mock_settings.ADMIN_ID = "99999"
                mock_settings.ADMIN_IDS = []
                
                forge.edit_skill(
                    name="test_skill",
                    user_id="12345",
                    instructions="Brand new body"
                )
            
            skill_file = tmp_path / "memory" / "users" / "12345" / "skills" / "test_skill" / "SKILL.md"
            content = skill_file.read_text()
            expected_hash = hashlib.sha256("Brand new body".encode("utf-8")).hexdigest()
            assert expected_hash in content
        finally:
            sf_module._PROJECT_ROOT = original_root


# === Tool Wrapper Tests ===

class TestEditSkillTool:
    """Tests for the edit_skill tool function wrapper."""

    @pytest.mark.asyncio
    async def test_edit_skill_tool_success(self):
        """Tool wrapper should return success message on active edit."""
        from src.tools.skill_forge_tool import edit_skill

        mock_bot = MagicMock()
        mock_forge = MagicMock()
        mock_forge.edit_skill.return_value = {
            "name": "my_skill",
            "status": "active",
            "version": "1.0.1",
            "fields_updated": ["instructions"],
            "is_safe_whitelisted": True,
            "file_path": "/tmp/mock.md",
        }
        mock_bot.skill_forge = mock_forge

        with patch("src.bot.globals.bot", mock_bot):
            result = await edit_skill(
                name="my_skill",
                instructions="Updated SOP",
                user_id="12345",
            )
        
        assert "updated to v1.0.1" in result
        assert "instructions" in result
        mock_forge.edit_skill.assert_called_once_with(
            name="my_skill",
            user_id="12345",
            instructions="Updated SOP",
            description=None,
            allowed_tools=None,
        )

    @pytest.mark.asyncio
    async def test_edit_skill_tool_not_found(self):
        """Tool should return clear message when skill doesn't exist."""
        from src.tools.skill_forge_tool import edit_skill

        mock_bot = MagicMock()
        mock_forge = MagicMock()
        mock_forge.edit_skill.return_value = {
            "name": "missing_skill",
            "status": "not_found",
            "error": "Not found",
        }
        mock_bot.skill_forge = mock_forge

        with patch("src.bot.globals.bot", mock_bot):
            result = await edit_skill(
                name="missing_skill",
                instructions="Doesn't matter",
                user_id="12345",
            )
        
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_edit_skill_tool_pending(self):
        """Tool should indicate when edit needs re-approval."""
        from src.tools.skill_forge_tool import edit_skill

        mock_bot = MagicMock()
        mock_forge = MagicMock()
        mock_forge.edit_skill.return_value = {
            "name": "restricted_skill",
            "status": "pending",
        }
        mock_bot.skill_forge = mock_forge

        with patch("src.bot.globals.bot", mock_bot):
            result = await edit_skill(
                name="restricted_skill",
                allowed_tools=["run_command"],
                user_id="12345",
            )
        
        assert "re-approval" in result

    @pytest.mark.asyncio
    async def test_edit_skill_tool_no_user_id(self):
        """Tool should error when user_id is missing."""
        from src.tools.skill_forge_tool import edit_skill

        mock_bot = MagicMock()
        mock_bot.skill_forge = MagicMock()

        with patch("src.bot.globals.bot", mock_bot):
            result = await edit_skill(
                name="anything",
                instructions="test",
            )
        
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_edit_skill_tool_no_forge(self):
        """Tool should error when SkillForge not initialized."""
        from src.tools.skill_forge_tool import edit_skill

        mock_bot = MagicMock()
        mock_bot.skill_forge = None

        with patch("src.bot.globals.bot", mock_bot):
            result = await edit_skill(
                name="anything",
                instructions="test",
                user_id="12345",
            )
        
        assert "Error" in result


# === Registration Test ===

class TestEditSkillRegistration:
    """Tests that edit_skill is properly registered in ToolRegistry."""

    def test_edit_skill_registered(self):
        """edit_skill should be in the ToolRegistry."""
        from src.tools.registry import ToolRegistry
        tool = ToolRegistry.get_tool("edit_skill")
        assert tool is not None, "edit_skill should be registered"
        assert "edit_skill" == tool.name

    def test_edit_skill_has_description(self):
        """edit_skill should have a non-empty description."""
        from src.tools.registry import ToolRegistry
        tool = ToolRegistry.get_tool("edit_skill")
        assert len(tool.description) > 20

    def test_edit_skill_params_include_name_and_instructions(self):
        """edit_skill params should include name and instructions."""
        from src.tools.registry import ToolRegistry
        tool = ToolRegistry.get_tool("edit_skill")
        assert "name" in tool.parameters
        assert "instructions" in tool.parameters
