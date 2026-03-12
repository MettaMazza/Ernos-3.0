"""
Tests for src/web/accounts.py — User account management.

Covers: register, login, get_account, update_tier, link_discord, link_patreon,
        password hashing (SHA256 fallback), email index, save/load errors.
"""
import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def accounts_dir(tmp_path):
    """Redirect ACCOUNTS_DIR to a temp directory."""
    with patch("src.web.accounts.ACCOUNTS_DIR", tmp_path):
        yield tmp_path


# ── Registration ──────────────────────────────────────────

class TestRegister:
    def test_successful_registration(self, accounts_dir):
        from src.web.accounts import register
        success, message, user_id = register("test@example.com", "password123")
        assert success is True
        assert "successfully" in message.lower() or "created" in message.lower()
        assert user_id is not None
        assert user_id.startswith("web-")

    def test_creates_account_file(self, accounts_dir):
        from src.web.accounts import register
        _, _, user_id = register("test@example.com", "password123")
        account_file = accounts_dir / user_id / "account.json"
        assert account_file.exists()
        data = json.loads(account_file.read_text())
        assert data["email"] == "test@example.com"
        assert data["user_id"] == user_id

    def test_updates_email_index(self, accounts_dir):
        from src.web.accounts import register
        register("indexed@example.com", "password123")
        index_file = accounts_dir / "_email_index.json"
        assert index_file.exists()
        index = json.loads(index_file.read_text())
        assert "indexed@example.com" in index

    def test_invalid_email_rejected(self, accounts_dir):
        from src.web.accounts import register
        success, message, user_id = register("not-an-email", "password123")
        assert success is False
        assert user_id is None

    def test_short_password_rejected(self, accounts_dir):
        from src.web.accounts import register
        success, message, user_id = register("test@example.com", "12345")
        assert success is False
        assert user_id is None

    def test_duplicate_email_rejected(self, accounts_dir):
        from src.web.accounts import register
        register("dup@example.com", "password123")
        success, message, user_id = register("dup@example.com", "otherpass")
        assert success is False
        assert user_id is None
        assert "already exists" in message.lower()

    def test_email_case_insensitive(self, accounts_dir):
        from src.web.accounts import register
        register("Test@Example.Com", "password123")
        success, _, _ = register("test@example.com", "password123")
        assert success is False  # Duplicate

    def test_custom_username(self, accounts_dir):
        from src.web.accounts import register, get_account
        _, _, user_id = register("test@example.com", "password123", username="TestUser")
        account = get_account(user_id)
        assert account["username"] == "TestUser"

    def test_default_username_from_email(self, accounts_dir):
        from src.web.accounts import register, get_account
        _, _, user_id = register("alice@example.com", "password123")
        account = get_account(user_id)
        assert account["username"] == "alice"

    def test_save_failure_returns_error(self, accounts_dir):
        from src.web.accounts import register
        with patch("src.web.accounts._save_account", return_value=False):
            success, message, user_id = register("fail@example.com", "password123")
            assert success is False
            assert user_id is None


# ── Login ─────────────────────────────────────────────────

class TestLogin:
    def test_successful_login(self, accounts_dir):
        from src.web.accounts import register, login
        register("login@example.com", "mypassword")
        success, message, account = login("login@example.com", "mypassword")
        assert success is True
        assert account is not None
        assert account["email"] == "login@example.com"

    def test_wrong_password(self, accounts_dir):
        from src.web.accounts import register, login
        register("login@example.com", "mypassword")
        success, message, account = login("login@example.com", "wrongpassword")
        assert success is False
        assert account is None

    def test_nonexistent_email(self, accounts_dir):
        from src.web.accounts import login
        success, message, account = login("nobody@example.com", "password")
        assert success is False
        assert account is None

    def test_corrupted_account(self, accounts_dir):
        from src.web.accounts import register, login
        register("corrupt@example.com", "password123")
        # Corrupt the account file
        with patch("src.web.accounts._load_account", return_value=None):
            success, message, _ = login("corrupt@example.com", "password123")
            assert success is False
            assert "corrupted" in message.lower() or "contact" in message.lower()

    def test_login_updates_last_login(self, accounts_dir):
        from src.web.accounts import register, login, _load_account
        _, _, user_id = register("time@example.com", "password123")
        initial = _load_account(user_id)["last_login"]
        import time; time.sleep(0.01)
        login("time@example.com", "password123")
        updated = _load_account(user_id)["last_login"]
        assert updated >= initial

    def test_login_returns_all_fields(self, accounts_dir):
        from src.web.accounts import register, login
        register("fields@example.com", "password123", username="FieldUser")
        _, _, account = login("fields@example.com", "password123")
        assert "user_id" in account
        assert "email" in account
        assert "username" in account
        assert "tier" in account
        assert "linked_discord_id" in account
        assert "linked_patreon_id" in account


# ── Get Account ───────────────────────────────────────────

class TestGetAccount:
    def test_returns_account_info(self, accounts_dir):
        from src.web.accounts import register, get_account
        _, _, user_id = register("get@example.com", "password123")
        account = get_account(user_id)
        assert account is not None
        assert account["email"] == "get@example.com"
        assert "created_at" in account

    def test_excludes_password_hash(self, accounts_dir):
        from src.web.accounts import register, get_account
        _, _, user_id = register("safe@example.com", "password123")
        account = get_account(user_id)
        assert "password_hash" not in account

    def test_nonexistent_user(self, accounts_dir):
        from src.web.accounts import get_account
        assert get_account("nonexistent") is None


# ── Update Tier ───────────────────────────────────────────

class TestUpdateTier:
    def test_updates_tier(self, accounts_dir):
        from src.web.accounts import register, update_tier, get_account
        _, _, user_id = register("tier@example.com", "password123")
        with patch("src.core.flux_capacitor.FluxCapacitor", side_effect=ImportError):
            result = update_tier(user_id, 3)
        assert result is True
        account = get_account(user_id)
        assert account["tier"] == 3

    def test_nonexistent_user(self, accounts_dir):
        from src.web.accounts import update_tier
        result = update_tier("nonexistent", 1)
        assert result is False

    def test_flux_capacitor_error_handled(self, accounts_dir):
        from src.web.accounts import register, update_tier
        _, _, user_id = register("flux@example.com", "password123")
        # FluxCapacitor import error should be caught gracefully
        with patch("src.core.flux_capacitor.FluxCapacitor", side_effect=ImportError("no module")):
            result = update_tier(user_id, 2)
            assert result is True


# ── Link Discord ──────────────────────────────────────────

class TestLinkDiscord:
    def test_links_discord(self, accounts_dir):
        from src.web.accounts import register, link_discord, get_account
        _, _, user_id = register("discord@example.com", "password123")
        result = link_discord(user_id, "discord-123")
        assert result is True
        account = get_account(user_id)
        assert account["linked_discord_id"] == "discord-123"

    def test_nonexistent_user(self, accounts_dir):
        from src.web.accounts import link_discord
        result = link_discord("nonexistent", "discord-123")
        assert result is False


# ── Link Patreon ──────────────────────────────────────────

class TestLinkPatreon:
    def test_links_patreon(self, accounts_dir):
        from src.web.accounts import register, link_patreon, get_account
        _, _, user_id = register("patreon@example.com", "password123")
        with patch("src.core.flux_capacitor.FluxCapacitor", side_effect=ImportError):
            result = link_patreon(user_id, "patreon-456", 2)
        assert result is True
        account = get_account(user_id)
        assert account["linked_patreon_id"] == "patreon-456"
        assert account["tier"] == 2

    def test_nonexistent_user(self, accounts_dir):
        from src.web.accounts import link_patreon
        result = link_patreon("nonexistent", "p-id", 1)
        assert result is False


# ── Password Hashing ─────────────────────────────────────

class TestPasswordHashing:
    def test_sha256_fallback_hash_and_verify(self, accounts_dir):
        from src.web.accounts import _hash_password, _verify_password
        with patch("src.web.accounts._HAS_BCRYPT", False):
            hashed = _hash_password("testpassword")
            assert hashed.startswith("sha256:")
            assert _verify_password("testpassword", hashed) is True
            assert _verify_password("wrongpassword", hashed) is False

    def test_sha256_malformed_hash(self):
        from src.web.accounts import _verify_password
        assert _verify_password("password", "sha256:only_salt") is False

    def test_unknown_hash_format(self):
        from src.web.accounts import _verify_password
        assert _verify_password("password", "unknown:format") is False

    def test_bcrypt_path(self, accounts_dir):
        from src.web.accounts import _hash_password, _verify_password, _HAS_BCRYPT
        if _HAS_BCRYPT:
            hashed = _hash_password("bcrypttest")
            assert hashed.startswith("$2")
            assert _verify_password("bcrypttest", hashed) is True
            assert _verify_password("wrong", hashed) is False


# ── Internal I/O ──────────────────────────────────────────

class TestAccountIO:
    def test_load_nonexistent_account(self, accounts_dir):
        from src.web.accounts import _load_account
        assert _load_account("does-not-exist") is None

    def test_load_corrupted_json(self, accounts_dir):
        from src.web.accounts import _load_account
        user_dir = accounts_dir / "corrupt-user"
        user_dir.mkdir()
        (user_dir / "account.json").write_text("not valid json{{{")
        assert _load_account("corrupt-user") is None

    def test_save_failure(self, accounts_dir):
        from src.web.accounts import _save_account
        with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            result = _save_account("test-user", {"test": True})
            assert result is False

    def test_email_index_load_empty(self, accounts_dir):
        from src.web.accounts import _load_email_index
        assert _load_email_index() == {}

    def test_email_index_load_corrupted(self, accounts_dir):
        from src.web.accounts import _load_email_index
        (accounts_dir / "_email_index.json").write_text("corrupted{{{")
        assert _load_email_index() == {}
