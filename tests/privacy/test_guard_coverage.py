"""Tests for privacy/guard.py — comprehensive scope enforcement."""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.privacy.guard import scope_protected, get_user_silo_path, scope_write_path, validate_path_scope
from src.privacy.scopes import PrivacyScope


class TestScopeProtected:
    @pytest.mark.asyncio
    async def test_allows_core_to_private(self):
        @scope_protected(PrivacyScope.PRIVATE)
        async def secret_func(request_scope=None):
            return "data"
        result = await secret_func(request_scope=PrivacyScope.CORE)
        assert result == "data"

    @pytest.mark.asyncio
    async def test_blocks_public_from_private(self):
        @scope_protected(PrivacyScope.PRIVATE)
        async def secret_func(request_scope=None):
            return "data"
        result = await secret_func(request_scope=PrivacyScope.PUBLIC)
        assert "Access Denied" in result

    @pytest.mark.asyncio
    async def test_defaults_to_public(self):
        @scope_protected(PrivacyScope.CORE)
        async def core_func(request_scope=None):
            return "data"
        result = await core_func()  # No scope = PUBLIC
        assert "Access Denied" in result


class TestGetUserSiloPath:
    def test_with_username(self):
        # Use a user_id prefix that won't collide with any real Discord user folder on disk.
        # The function scans memory/users/ and returns existing folders matching startswith(str(user_id)),
        # so we need a unique ID that no real folder starts with.
        path = get_user_silo_path(99999999, "Alice")
        assert "99999999" in path
        assert "alice" in path

    def test_without_username(self):
        path = get_user_silo_path(456)
        assert "456" in path


class TestScopeWritePath:
    def test_core(self):
        assert scope_write_path(PrivacyScope.CORE) == "memory/core"

    def test_public(self):
        assert scope_write_path(PrivacyScope.PUBLIC) == "memory/public"


# ═══════════════════════════════════════════════════════════════════════
# SECURITY TESTS — Deny-by-default enforcement for all memory/ paths
# ═══════════════════════════════════════════════════════════════════════

class TestValidatePathScope:
    """Original tests — whitelisted paths."""

    def test_public_can_read_public(self):
        assert validate_path_scope("memory/public/file.txt", PrivacyScope.PUBLIC) is True

    def test_public_cannot_read_core(self):
        assert validate_path_scope("memory/core/secret.txt", PrivacyScope.PUBLIC) is False

    def test_cross_user_blocked(self):
        result = validate_path_scope("memory/users/999/data.json", PrivacyScope.PRIVATE, user_id="123")
        assert result is False

    def test_own_user_allowed(self):
        result = validate_path_scope("memory/users/123/data.json", PrivacyScope.PRIVATE, user_id="123")
        assert result is True


class TestBackupPathBlocked:
    """🔴 CRITICAL: Master backups must be CORE-only."""

    def test_public_cannot_read_master_backup(self):
        path = "memory/backups/user_exports/master_backup_2026-02-18.json"
        assert validate_path_scope(path, PrivacyScope.PUBLIC) is False

    def test_private_cannot_read_master_backup(self):
        path = "memory/backups/user_exports/master_backup_2026-02-18.json"
        assert validate_path_scope(path, PrivacyScope.PRIVATE, user_id="123") is False

    def test_core_can_read_master_backup(self):
        path = "memory/backups/user_exports/master_backup_2026-02-18.json"
        assert validate_path_scope(path, PrivacyScope.CORE) is True

    def test_public_cannot_list_backups_dir(self):
        assert validate_path_scope("memory/backups/", PrivacyScope.PUBLIC) is False

    def test_private_cannot_list_backup_exports(self):
        assert validate_path_scope("memory/backups/user_exports/", PrivacyScope.PRIVATE, user_id="123") is False

    def test_public_cannot_read_daily_backup(self):
        assert validate_path_scope("memory/backups/daily/2026-02-17/data.json", PrivacyScope.PUBLIC) is False


class TestDenyByDefaultMemoryPaths:
    """All unrecognized memory/ paths must be CORE-only."""

    def test_cache_blocked(self):
        assert validate_path_scope("memory/cache/some_data.json", PrivacyScope.PUBLIC) is False

    def test_chroma_blocked(self):
        assert validate_path_scope("memory/chroma/collection/vectors", PrivacyScope.PUBLIC) is False

    def test_system_blocked(self):
        assert validate_path_scope("memory/system/state.json", PrivacyScope.PUBLIC) is False

    def test_debug_prompt_blocked(self):
        assert validate_path_scope("memory/debug_prompt_last.txt", PrivacyScope.PUBLIC) is False

    def test_security_profiles_blocked(self):
        assert validate_path_scope("memory/security_profiles.json", PrivacyScope.PUBLIC) is False

    def test_quarantine_blocked(self):
        assert validate_path_scope("memory/quarantine.json", PrivacyScope.PUBLIC) is False

    def test_crawl_state_blocked(self):
        assert validate_path_scope("memory/crawl_state.json", PrivacyScope.PRIVATE, user_id="123") is False

    def test_future_unknown_subdir_blocked(self):
        assert validate_path_scope("memory/new_subsystem/data.json", PrivacyScope.PUBLIC) is False

    def test_core_can_access_any_memory_path(self):
        for path in [
            "memory/backups/user_exports/master_backup.json",
            "memory/cache/data.json",
            "memory/chroma/vectors",
            "memory/system/state.json",
            "memory/debug_prompt_last.txt",
            "memory/security_profiles.json",
            "memory/quarantine.json",
        ]:
            assert validate_path_scope(path, PrivacyScope.CORE) is True, f"CORE should access {path}"


class TestCrossUserIsolation:
    """User A must never access User B's files."""

    def test_user_reads_other_user_private(self):
        result = validate_path_scope("memory/users/999/profile.json", PrivacyScope.PRIVATE, user_id="888")
        assert result is False

    def test_user_reads_other_user_public_project(self):
        """Public projects inside another user's silo ARE accessible."""
        result = validate_path_scope("memory/users/999/projects/public/readme.md", PrivacyScope.PRIVATE, user_id="888")
        assert result is True

    def test_user_reads_other_user_research_public(self):
        result = validate_path_scope("memory/users/999/research/public/paper.md", PrivacyScope.PRIVATE, user_id="888")
        assert result is True

    def test_no_user_id_blocks_user_dirs(self):
        """If user_id is not provided, all user directories are blocked (except CORE)."""
        result = validate_path_scope("memory/users/123/data.json", PrivacyScope.PRIVATE)
        assert result is False

    def test_listing_users_dir_blocked_for_non_core(self):
        """Listing memory/users/ itself is blocked for non-CORE."""
        result = validate_path_scope("memory/users/", PrivacyScope.PRIVATE, user_id="123")
        assert result is False

    def test_listing_users_dir_allowed_for_core(self):
        result = validate_path_scope("memory/users/", PrivacyScope.CORE)
        assert result is True


class TestWhitelistedPaths:
    """Ensure legitimate access still works."""

    def test_non_memory_paths_public(self):
        assert validate_path_scope("src/tools/browser.py", PrivacyScope.PUBLIC) is True

    def test_docs_public(self):
        assert validate_path_scope("docs/README.md", PrivacyScope.PUBLIC) is True

    def test_core_research_public(self):
        assert validate_path_scope("memory/core/research/paper.md", PrivacyScope.PUBLIC) is True

    def test_core_media_public(self):
        assert validate_path_scope("memory/core/media/image.png", PrivacyScope.PUBLIC) is True

    def test_core_exports_public(self):
        assert validate_path_scope("memory/core/exports/data.json", PrivacyScope.PUBLIC) is True

    def test_core_skills_public(self):
        assert validate_path_scope("memory/core/skills/my_skill.py", PrivacyScope.PUBLIC) is True

    def test_core_identity_blocked(self):
        assert validate_path_scope("memory/core/identity.json", PrivacyScope.PUBLIC) is False

    def test_core_drives_blocked(self):
        assert validate_path_scope("memory/core/drives.json", PrivacyScope.PUBLIC) is False

    def test_own_user_dir_private(self):
        result = validate_path_scope("memory/users/555/notes.md", PrivacyScope.PRIVATE, user_id="555")
        assert result is True

