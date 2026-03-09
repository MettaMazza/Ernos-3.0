"""Tests for privacy/guard.py — 8 tests."""
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


class TestValidatePathScope:
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
