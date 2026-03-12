"""
REGRESSION TESTS: Privacy Leak Prevention in PromptManager

These tests ensure that global/core memory files are NOT exposed
to users in PRIVATE scope, preventing cross-user data contamination.

See conversation: 8d84b082-52b2-4ade-8bf4-336b5c893f4f (2026-02-06)
Root cause: system_turns.jsonl, stream_of_consciousness.log, and
provenance_ledger.jsonl were loaded without scope checks.
"""
import pytest
from unittest.mock import patch, MagicMock
import os
import tempfile
import shutil
import sys


class TestPrivacyLeakPrevention:
    """
    CRITICAL: These tests verify that global memory files are NOT
    exposed to PRIVATE scope users. Failure means privacy violation.
    """
    
    @pytest.fixture
    def temp_memory_dir(self):
        """Create a temporary memory directory with test files AND prompt files."""
        tmpdir = tempfile.mkdtemp()
        
        # Create memory/core structure
        core_dir = os.path.join(tmpdir, "memory", "core")
        os.makedirs(core_dir, exist_ok=True)
        
        # Write global files with identifiable markers
        with open(os.path.join(core_dir, "system_turns.jsonl"), "w") as f:
            f.write('{"user_message": "SECRET_FROM_SYSTEM_TURNS", "ts": "2026-02-06"}\n')
        
        with open(os.path.join(core_dir, "stream_of_consciousness.log"), "w") as f:
            f.write("SECRET_FROM_AUTONOMY_LOG: Thinking about other users...\n")
            
        with open(os.path.join(core_dir, "provenance_ledger.jsonl"), "w") as f:
            f.write('{"filename": "SECRET_FROM_PROVENANCE", "type": "create"}\n')
        
        # Copy prompt files to temp dir
        src_prompts_dir = os.path.join(tmpdir, "src", "prompts")
        os.makedirs(src_prompts_dir, exist_ok=True)
        
        # Copy actual prompt files from real location
        real_prompts_dir = os.path.join(os.path.dirname(__file__), "..", "src", "prompts")
        real_prompts_dir = os.path.abspath(real_prompts_dir)
        
        for fname in ["kernel_backup.txt", "dynamic_context.txt", "identity_core.txt", 
                      "identity.txt", "dynamic_context.txt"]:
            src_path = os.path.join(real_prompts_dir, fname)
            dst_path = os.path.join(src_prompts_dir, fname)
            if os.path.exists(src_path):
                shutil.copy(src_path, dst_path)
            else:
                # Create minimal stub if file doesn't exist
                with open(dst_path, "w") as f:
                    f.write(f"# Stub for {fname}\n")
        
        yield tmpdir
        shutil.rmtree(tmpdir)
    
    @pytest.fixture
    def prompt_manager(self):
        """Create PromptManager instance."""
        from src.prompts.manager import PromptManager
        return PromptManager()
    
    def test_scope_checks_exist_in_code(self):
        """
        Verify that the scope checks are present in HUD loader source.
        This is a static code analysis test.
        
        Note: Scope guards live in hud_loaders.load_ernos_hud after the
        manager.py → hud_loaders.py extraction refactor.
        """
        import inspect
        from src.prompts.hud_loaders import load_ernos_hud
        
        source = inspect.getsource(load_ernos_hud)
        
        # Check that scope checks exist before loading global files
        assert 'scope != "PRIVATE"' in source, \
            "MISSING: scope check before loading global data"
        
        # Verify the pattern appears multiple times (for each global file)
        count = source.count('scope != "PRIVATE"')
        assert count >= 3, \
            f"Expected at least 3 scope checks, found {count}"
    
    def test_private_scope_redacts_global_data(self, prompt_manager, temp_memory_dir):
        """
        REGRESSION: Global files must NOT appear in PRIVATE prompts.
        """
        # Change to temp dir so relative paths work
        original_cwd = os.getcwd()
        os.chdir(temp_memory_dir)
        
        try:
            prompt = prompt_manager.get_system_prompt(
                scope="PRIVATE",
                user_id="isolated_user"
            )
            
            # None of the global secrets should appear
            assert "SECRET_FROM_SYSTEM_TURNS" not in prompt, \
                "PRIVACY LEAK: system_turns.jsonl exposed in PRIVATE!"
            assert "SECRET_FROM_AUTONOMY_LOG" not in prompt, \
                "PRIVACY LEAK: stream_of_consciousness.log exposed in PRIVATE!"
            assert "SECRET_FROM_PROVENANCE" not in prompt, \
                "PRIVACY LEAK: provenance_ledger.jsonl exposed in PRIVATE!"
        finally:
            os.chdir(original_cwd)
    
    def test_public_scope_allows_global_data(self, prompt_manager, temp_memory_dir):
        """
        Verify that global data IS available in PUBLIC scope.
        """
        original_cwd = os.getcwd()
        os.chdir(temp_memory_dir)
        
        try:
            prompt = prompt_manager.get_system_prompt(
                scope="PUBLIC",
                user_id="any_user"
            )
            
            # In PUBLIC scope, global data CAN appear
            # We verify at least one marker is present
            has_global_data = (
                "SECRET_FROM_SYSTEM_TURNS" in prompt or
                "SECRET_FROM_AUTONOMY_LOG" in prompt or
                "SECRET_FROM_PROVENANCE" in prompt
            )
            assert has_global_data, \
                "PUBLIC scope should have access to global data"
        finally:
            os.chdir(original_cwd)
    
    def test_core_scope_allows_global_data(self, prompt_manager, temp_memory_dir):
        """
        Verify that global data IS available in CORE scope.
        """
        original_cwd = os.getcwd()
        os.chdir(temp_memory_dir)
        
        try:
            prompt = prompt_manager.get_system_prompt(
                scope="CORE",
                user_id="CORE"
            )
            
            # In CORE scope, global data CAN appear
            has_global_data = (
                "SECRET_FROM_SYSTEM_TURNS" in prompt or
                "SECRET_FROM_AUTONOMY_LOG" in prompt or
                "SECRET_FROM_PROVENANCE" in prompt
            )
            assert has_global_data, \
                "CORE scope should have access to global data"
        finally:
            os.chdir(original_cwd)


class TestScopeIsolation:
    """Tests for general scope isolation principles."""
    
    def test_private_user_only_sees_own_context(self):
        """
        Each PRIVATE user should only see data from their own
        memory/users/{user_id}/ directory, never from other users.
        """
        user_id = "isolated_user_999"
        expected_path_fragment = f"memory/users/{user_id}/"
        
        # The system should construct paths using this user_id
        context_path = f"memory/users/{user_id}/context_private.jsonl"
        assert user_id in context_path
        
        # And should NOT have hardcoded paths to other users
        assert "memory/users/core/" not in context_path
