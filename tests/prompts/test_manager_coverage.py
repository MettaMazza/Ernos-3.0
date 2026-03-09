"""
Comprehensive coverage tests for src/prompts/manager.py
Targeting 72% → 95% coverage.
"""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open


class TestPromptManagerInit:
    def test_default_init(self):
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        assert pm.prompt_dir == "./src/prompts"
        assert "kernel.txt" in pm.kernel_file

    def test_custom_dir(self, tmp_path):
        from src.prompts.manager import PromptManager
        pm = PromptManager(str(tmp_path))
        assert str(tmp_path) in pm.kernel_file


class TestReadFile:
    def test_success(self, tmp_path):
        from src.prompts.manager import PromptManager
        f = tmp_path / "test.txt"
        f.write_text("hello")
        pm = PromptManager()
        assert pm._read_file(str(f)) == "hello"

    def test_empty_filepath(self):
        """Covers line 28: empty filepath returns empty string."""
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        assert pm._read_file("") == ""

    def test_file_not_found(self):
        """Covers lines 32-34."""
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        assert pm._read_file("/nonexistent/file.txt") == ""

    def test_generic_exception(self):
        """Covers lines 35-37."""
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        with patch("builtins.open", side_effect=PermissionError("denied")):
            assert pm._read_file("/some/file.txt") == ""


class TestCheckUserHasCustomIdentity:
    """Covers lines 39-54."""

    def test_none_user_id(self):
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        assert pm._check_user_has_custom_identity(None) is False

    def test_unknown_user_id(self):
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        assert pm._check_user_has_custom_identity("Unknown") is False

    def test_persona_exists_with_content(self, tmp_path):
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        mock_home = tmp_path / "user_home"
        mock_home.mkdir()
        (mock_home / "persona.txt").write_text("My custom identity")
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=mock_home):
            assert pm._check_user_has_custom_identity("u1") is True

    def test_persona_exists_empty(self, tmp_path):
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        mock_home = tmp_path / "user_home"
        mock_home.mkdir()
        (mock_home / "persona.txt").write_text("  ")
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=mock_home):
            assert pm._check_user_has_custom_identity("u1") is False

    def test_persona_not_exists(self, tmp_path):
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        mock_home = tmp_path / "user_home"
        mock_home.mkdir()
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=mock_home):
            assert pm._check_user_has_custom_identity("u1") is False

    def test_exception(self):
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        with patch("src.privacy.scopes.ScopeManager.get_user_home", side_effect=RuntimeError("fail")):
            assert pm._check_user_has_custom_identity("u1") is False


class TestGenerateToolManifest:
    """Covers lines 56-89."""

    def test_no_tools(self):
        """Covers line 66: empty tool list returns empty."""
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        with patch("src.tools.registry.ToolRegistry.list_tools", return_value=[]):
            assert pm._generate_tool_manifest() == ""

    def test_with_tools(self):
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        tool = MagicMock()
        tool.name = "search_web"
        tool.description = "Search the web"
        tool.parameters = {"query": "str"}
        with patch("src.tools.registry.ToolRegistry.list_tools", return_value=[tool]):
            result = pm._generate_tool_manifest()
        assert "search_web" in result
        assert "query: str" in result

    def test_tool_no_params(self):
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        tool = MagicMock()
        tool.name = "ping"
        tool.description = "Ping system"
        tool.parameters = {}
        with patch("src.tools.registry.ToolRegistry.list_tools", return_value=[tool]):
            result = pm._generate_tool_manifest()
        assert "ping" in result

    def test_exception(self):
        """Covers lines 87-89."""
        from src.prompts.manager import PromptManager
        pm = PromptManager()
        with patch("src.tools.registry.ToolRegistry.list_tools", side_effect=RuntimeError("fail")):
            assert pm._generate_tool_manifest() == ""


class TestGetSystemPrompt:
    """Covers lines 91-252: the main system prompt builder."""

    def _make_pm(self, tmp_path):
        """Create a PromptManager with real template files."""
        from src.prompts.manager import PromptManager
        (tmp_path / "kernel.txt").write_text("KERNEL")
        (tmp_path / "architecture.txt").write_text("ARCH {version}")
        (tmp_path / "identity.txt").write_text("IDENTITY")
        (tmp_path / "identity_core.txt").write_text("CORE_IDENTITY {salt_rotation_date}")
        (tmp_path / "dynamic_context.txt").write_text("DC {timestamp} {scope} {user_id} {user_name} {active_engine} {view_mode}")
        (tmp_path / "dynamic_context_fork.txt").write_text("FORK {timestamp} {scope}")
        return PromptManager(str(tmp_path))

    def test_basic_public(self, tmp_path):
        pm = self._make_pm(tmp_path)
        with patch.object(pm, "_generate_tool_manifest", return_value=""), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=False), \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.prompts.hud_loaders.load_fork_hud", return_value={}), \
             patch("src.prompts.hud_loaders.load_persona_hud", return_value={}), \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", return_value="2024-01-01"):
            result = pm.get_system_prompt(timestamp="now", scope="PUBLIC", user_id="u1", user_name="Alice")
        assert "KERNEL" in result
        assert "CORE_IDENTITY" in result

    def test_architecture_format_exception(self, tmp_path):
        """Covers lines 114-115: KeyError in architecture format."""
        from src.prompts.manager import PromptManager
        (tmp_path / "kernel.txt").write_text("K")
        (tmp_path / "architecture.txt").write_text("ARCH {missing_var}")
        (tmp_path / "identity.txt").write_text("")
        (tmp_path / "identity_core.txt").write_text("ID")
        (tmp_path / "dynamic_context.txt").write_text("")
        (tmp_path / "dynamic_context_fork.txt").write_text("")
        pm = PromptManager(str(tmp_path))
        with patch.object(pm, "_generate_tool_manifest", return_value=""), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=False), \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", return_value="X"):
            result = pm.get_system_prompt()
        # Should not crash — architecture left as-is
        assert "K" in result

    def test_persona_mode(self, tmp_path):
        """Covers lines 121-129: persona mode identity loading."""
        pm = self._make_pm(tmp_path)
        persona_dir = tmp_path / "persona_echo"
        persona_dir.mkdir()
        (persona_dir / "persona.txt").write_text("I am Echo")
        
        with patch.object(pm, "_generate_tool_manifest", return_value=""), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=False), \
             patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", return_value=persona_dir), \
             patch("src.prompts.hud_loaders.load_persona_hud", return_value={}) as mock_phud, \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", return_value="X"):
            result = pm.get_system_prompt(persona_name="Echo")
        assert "I am Echo" in result
        mock_phud.assert_called_once_with("Echo")

    def test_persona_mode_fallback(self, tmp_path):
        """Covers line 129: persona but no persona.txt → fallback."""
        pm = self._make_pm(tmp_path)
        with patch.object(pm, "_generate_tool_manifest", return_value=""), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=False), \
             patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", return_value=None), \
             patch("src.prompts.hud_loaders.load_persona_hud", return_value={}), \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", return_value="X"):
            result = pm.get_system_prompt(persona_name="Echo")
        assert "Echo" in result
        assert "unique AI persona" in result

    def test_private_user_identity(self, tmp_path):
        """Covers lines 131-138: PRIVATE scope loads user persona."""
        pm = self._make_pm(tmp_path)
        user_home = tmp_path / "user_home"
        user_home.mkdir()
        (user_home / "persona.txt").write_text("Custom user identity")
        
        with patch.object(pm, "_generate_tool_manifest", return_value=""), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=True), \
             patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=user_home), \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.prompts.hud_loaders.load_fork_hud", return_value={}) as mock_fhud, \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", return_value="X"):
            result = pm.get_system_prompt(scope="PRIVATE", user_id="u1", user_name="Alice")
        assert "Custom user identity" in result
        mock_fhud.assert_called_once()

    def test_fork_hud_selected(self, tmp_path):
        """Covers lines 152-153: fork HUD template used for custom identity."""
        pm = self._make_pm(tmp_path)
        user_home = tmp_path / "user_home"
        user_home.mkdir()
        (user_home / "persona.txt").write_text("My persona")
        
        with patch.object(pm, "_generate_tool_manifest", return_value=""), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=True), \
             patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=user_home), \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.prompts.hud_loaders.load_fork_hud", return_value={}), \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", return_value="X"):
            result = pm.get_system_prompt(scope="PRIVATE", user_id="u1", user_name="Alice")
        # FORK template used → "FORK" should be in result
        assert "FORK" in result

    def test_core_view_mode(self, tmp_path):
        """Covers line 169: GOD VIEW for core."""
        pm = self._make_pm(tmp_path)
        with patch.object(pm, "_generate_tool_manifest", return_value=""), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=False), \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", return_value="X"):
            result = pm.get_system_prompt(is_core=True)
        assert "GOD VIEW" in result

    def test_salt_rotation_exception(self, tmp_path):
        """Covers line 166: salt rotation fails → UNKNOWN."""
        pm = self._make_pm(tmp_path)
        with patch.object(pm, "_generate_tool_manifest", return_value=""), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=False), \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", side_effect=RuntimeError("no salt")):
            result = pm.get_system_prompt()
        assert "UNKNOWN" in result

    def test_template_format_error(self, tmp_path):
        """Covers lines 238-240: template format error."""
        from src.prompts.manager import PromptManager
        (tmp_path / "kernel.txt").write_text("K")
        (tmp_path / "architecture.txt").write_text("")
        (tmp_path / "identity.txt").write_text("")
        (tmp_path / "identity_core.txt").write_text("ID")
        # Template has missing key
        (tmp_path / "dynamic_context.txt").write_text("DC {nonexistent_key}")
        (tmp_path / "dynamic_context_fork.txt").write_text("")
        pm = PromptManager(str(tmp_path))
        with patch.object(pm, "_generate_tool_manifest", return_value=""), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=False), \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", return_value="X"):
            result = pm.get_system_prompt()
        assert "Template Error" in result

    def test_tool_manifest_included(self, tmp_path):
        pm = self._make_pm(tmp_path)
        with patch.object(pm, "_generate_tool_manifest", return_value="TOOLS_HERE"), \
             patch.object(pm, "_check_user_has_custom_identity", return_value=False), \
             patch("src.prompts.hud_loaders.load_ernos_hud", return_value={}), \
             patch("src.security.provenance.ProvenanceManager.get_salt_rotation_date", return_value="X"):
            result = pm.get_system_prompt()
        assert "TOOLS_HERE" in result
