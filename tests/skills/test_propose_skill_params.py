"""
Regression tests for propose_skill parameter handling.

Tests that:
1. The tool works with all parameters correctly provided
2. PARAM_ALIASES correctly map alternative names (prompt, sop, steps, procedure) to 'instructions'
3. The ToolRegistry interceptor corrects parameters before execution
4. String-format allowed_tools are correctly parsed
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.tools.registry import ToolRegistry, PARAM_ALIASES
from src.tools.skill_forge_tool import propose_skill
from src.bot import globals as bot_globals
import inspect


# === PARAM_ALIASES Tests ===

class TestProposeSkillParamAliases:
    """Tests that PARAM_ALIASES include correct mappings for propose_skill."""

    def test_prompt_maps_to_instructions(self):
        assert PARAM_ALIASES.get("prompt") == "instructions"

    def test_sop_maps_to_instructions(self):
        assert PARAM_ALIASES.get("sop") == "instructions"

    def test_steps_maps_to_instructions(self):
        assert PARAM_ALIASES.get("steps") == "instructions"

    def test_procedure_maps_to_instructions(self):
        assert PARAM_ALIASES.get("procedure") == "instructions"


# === Parameter Correction Tests ===

class TestProposeSkillParamCorrection:
    """Tests that _correct_params remaps aliases to 'instructions' for propose_skill."""

    def _get_propose_skill_params(self):
        """Get the actual parameter names from propose_skill function."""
        sig = inspect.signature(propose_skill)
        return sig.parameters

    def test_prompt_corrected_to_instructions(self):
        params = self._get_propose_skill_params()
        kwargs = {
            "name": "test_skill",
            "description": "A test",
            "prompt": "Do the thing",  # Wrong name
            "allowed_tools": ["read_file"],
        }
        corrected = ToolRegistry._correct_params("propose_skill", kwargs, params)
        assert "instructions" in corrected, "prompt should be remapped to instructions"
        assert corrected["instructions"] == "Do the thing"
        assert "prompt" not in corrected, "original alias should be removed"

    def test_sop_corrected_to_instructions(self):
        params = self._get_propose_skill_params()
        kwargs = {
            "name": "test_skill",
            "description": "A test",
            "sop": "# Phase 1\n1. Do stuff",  # Wrong name
            "allowed_tools": ["read_file"],
        }
        corrected = ToolRegistry._correct_params("propose_skill", kwargs, params)
        assert "instructions" in corrected
        assert corrected["instructions"] == "# Phase 1\n1. Do stuff"

    def test_steps_corrected_to_instructions(self):
        params = self._get_propose_skill_params()
        kwargs = {
            "name": "test_skill",
            "description": "A test",
            "steps": "Step 1: gather data",  # Wrong name
            "allowed_tools": ["read_file"],
        }
        corrected = ToolRegistry._correct_params("propose_skill", kwargs, params)
        assert "instructions" in corrected
        assert corrected["instructions"] == "Step 1: gather data"

    def test_procedure_corrected_to_instructions(self):
        params = self._get_propose_skill_params()
        kwargs = {
            "name": "test_skill",
            "description": "A test",
            "procedure": "Procedure outline",  # Wrong name
            "allowed_tools": ["read_file"],
        }
        corrected = ToolRegistry._correct_params("propose_skill", kwargs, params)
        assert "instructions" in corrected
        assert corrected["instructions"] == "Procedure outline"

    def test_instructions_not_double_mapped(self):
        """When 'instructions' is already correct, it should pass through unchanged."""
        params = self._get_propose_skill_params()
        kwargs = {
            "name": "test_skill",
            "description": "A test",
            "instructions": "Correct param name",
            "allowed_tools": ["read_file"],
        }
        corrected = ToolRegistry._correct_params("propose_skill", kwargs, params)
        assert corrected["instructions"] == "Correct param name"


# === End-to-End Tool Execution Tests ===

class TestProposeSkillExecution:
    """Tests that propose_skill executes correctly with various parameter patterns."""

    @pytest.mark.asyncio
    async def test_propose_skill_with_instructions_works(self):
        """Standard call with 'instructions' should succeed."""
        mock_bot = MagicMock()
        mock_forge = MagicMock()
        mock_forge.propose_skill.return_value = {
            "name": "test_skill",
            "scope": "PRIVATE",
            "status": "active",
            "file_path": "/tmp/mock/skill.md",
            "is_safe_whitelisted": True,
        }
        mock_bot.skill_forge = mock_forge
        mock_bot.skill_registry = MagicMock()

        with patch("src.bot.globals.bot", mock_bot):
            with patch("src.skills.loader.SkillLoader.parse") as mock_parse:
                mock_parse.return_value = MagicMock()
                result = await propose_skill(
                    name="test_skill",
                    description="A test",
                    instructions="# Phase 1\n1. Do stuff",
                    allowed_tools=["read_file"],
                    scope="PRIVATE",
                )
                assert "Created & Auto-Approved" in result
                # Verify instructions were passed through to forge
                call_kwargs = mock_forge.propose_skill.call_args[1]
                assert call_kwargs["instructions"] == "# Phase 1\n1. Do stuff"

    @pytest.mark.asyncio
    async def test_propose_skill_via_registry_with_prompt_alias(self):
        """Calling via ToolRegistry.execute with 'prompt' instead of 'instructions'."""
        mock_bot = MagicMock()
        mock_forge = MagicMock()
        mock_forge.propose_skill.return_value = {
            "name": "alias_test",
            "scope": "PRIVATE",
            "status": "active",
            "file_path": "/tmp/mock/skill.md",
            "is_safe_whitelisted": True,
        }
        mock_bot.skill_forge = mock_forge
        mock_bot.skill_registry = MagicMock()
        mock_bot.user = MagicMock()
        mock_bot.user.id = 999

        with patch("src.bot.globals.bot", mock_bot):
            with patch("src.skills.loader.SkillLoader.parse") as mock_parse:
                mock_parse.return_value = MagicMock()
                result = await ToolRegistry.execute(
                    "propose_skill",
                    name="alias_test",
                    description="Test alias",
                    prompt="# Phase 1\n1. Step one",  # Using alias!
                    allowed_tools=["read_file"],
                    scope="PRIVATE",
                    user_id="12345",
                )
                assert "Created & Auto-Approved" in result
                call_kwargs = mock_forge.propose_skill.call_args[1]
                assert call_kwargs["instructions"] == "# Phase 1\n1. Step one"

    @pytest.mark.asyncio
    async def test_propose_skill_string_allowed_tools_parsed(self):
        """allowed_tools passed as pipe-delimited string should be parsed to list."""
        mock_bot = MagicMock()
        mock_forge = MagicMock()
        mock_forge.propose_skill.return_value = {
            "name": "str_tools",
            "scope": "PRIVATE",
            "status": "active",
            "file_path": "/tmp/mock/skill.md",
            "is_safe_whitelisted": True,
        }
        mock_bot.skill_forge = mock_forge
        mock_bot.skill_registry = MagicMock()

        with patch("src.bot.globals.bot", mock_bot):
            with patch("src.skills.loader.SkillLoader.parse") as mock_parse:
                mock_parse.return_value = MagicMock()
                result = await propose_skill(
                    name="str_tools",
                    description="Test",
                    instructions="Do things",
                    allowed_tools="read_file, search_web, browse_site",
                    scope="PRIVATE",
                )
                assert "Created & Auto-Approved" in result
                call_kwargs = mock_forge.propose_skill.call_args[1]
                assert isinstance(call_kwargs["allowed_tools"], list)
                assert len(call_kwargs["allowed_tools"]) == 3

    @pytest.mark.asyncio
    async def test_propose_skill_duplicate_blocked(self):
        """Duplicate skill names should be blocked."""
        mock_bot = MagicMock()
        mock_forge = MagicMock()
        mock_forge.propose_skill.return_value = {
            "name": "existing_skill",
            "scope": "PRIVATE",
            "status": "duplicate_blocked",
        }
        mock_bot.skill_forge = mock_forge

        with patch("src.bot.globals.bot", mock_bot):
            result = await propose_skill(
                name="existing_skill",
                description="Already exists",
                instructions="Doesn't matter",
                allowed_tools=["read_file"],
            )
            assert "already exists" in result
