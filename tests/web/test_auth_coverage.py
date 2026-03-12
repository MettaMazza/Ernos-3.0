"""
Tests for src/web/auth.py — JWT token management.

Covers: create_token, verify_token, refresh_access_token, extract_user_from_token,
        _b64url_encode, _b64url_decode, _sign, edge cases (expired, tampered, malformed).
"""
import time
import json
import pytest
from unittest.mock import patch


# ── Token Creation & Verification ─────────────────────────

class TestCreateToken:
    def test_creates_valid_token(self):
        from src.web.auth import create_token, verify_token
        token = create_token(user_id="user-123", tier=2, email="test@example.com")
        is_valid, payload = verify_token(token)
        assert is_valid is True
        assert payload["sub"] == "user-123"
        assert payload["tier"] == 2
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"

    def test_creates_refresh_token(self):
        from src.web.auth import create_token, verify_token
        token = create_token(user_id="user-456", token_type="refresh")
        is_valid, payload = verify_token(token)
        assert is_valid is True
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-456"

    def test_includes_linked_ids(self):
        from src.web.auth import create_token, verify_token
        token = create_token(
            user_id="u1", linked_discord_id="d123", linked_patreon_id="p456"
        )
        _, payload = verify_token(token)
        assert payload["discord_id"] == "d123"
        assert payload["patreon_id"] == "p456"

    def test_default_values(self):
        from src.web.auth import create_token, verify_token
        token = create_token(user_id="u1")
        _, payload = verify_token(token)
        assert payload["tier"] == 0
        assert payload["email"] == ""
        assert payload["discord_id"] == ""
        assert payload["patreon_id"] == ""

    def test_token_has_three_parts(self):
        from src.web.auth import create_token
        token = create_token(user_id="u1")
        parts = token.split(".")
        assert len(parts) == 3

    def test_token_expiry_set(self):
        from src.web.auth import create_token, verify_token, ACCESS_TOKEN_EXPIRY
        token = create_token(user_id="u1")
        _, payload = verify_token(token)
        assert payload["exp"] > payload["iat"]
        assert payload["exp"] - payload["iat"] == ACCESS_TOKEN_EXPIRY

    def test_refresh_token_expiry_longer(self):
        from src.web.auth import create_token, verify_token, REFRESH_TOKEN_EXPIRY
        token = create_token(user_id="u1", token_type="refresh")
        _, payload = verify_token(token)
        assert payload["exp"] - payload["iat"] == REFRESH_TOKEN_EXPIRY


class TestVerifyToken:
    def test_valid_token(self):
        from src.web.auth import create_token, verify_token
        token = create_token(user_id="test-user")
        is_valid, payload = verify_token(token)
        assert is_valid is True
        assert payload is not None

    def test_expired_token(self):
        from src.web.auth import create_token, verify_token
        with patch("src.web.auth.time") as mock_time:
            # Create token in the past
            mock_time.time.return_value = 1000000
            token = create_token(user_id="u1")
        # Verify at current time (token is expired)
        is_valid, payload = verify_token(token)
        assert is_valid is False
        assert payload is None

    def test_tampered_payload(self):
        from src.web.auth import create_token, verify_token
        token = create_token(user_id="u1")
        parts = token.split(".")
        # Tamper with payload
        parts[1] = parts[1] + "tampered"
        tampered = ".".join(parts)
        is_valid, payload = verify_token(tampered)
        assert is_valid is False

    def test_tampered_signature(self):
        from src.web.auth import create_token, verify_token
        token = create_token(user_id="u1")
        parts = token.split(".")
        # Tamper with signature
        parts[2] = "invalid_signature"
        tampered = ".".join(parts)
        is_valid, payload = verify_token(tampered)
        assert is_valid is False

    def test_malformed_token_too_few_parts(self):
        from src.web.auth import verify_token
        is_valid, payload = verify_token("only.two")
        assert is_valid is False
        assert payload is None

    def test_malformed_token_too_many_parts(self):
        from src.web.auth import verify_token
        is_valid, payload = verify_token("a.b.c.d")
        assert is_valid is False
        assert payload is None

    def test_empty_token(self):
        from src.web.auth import verify_token
        is_valid, payload = verify_token("")
        assert is_valid is False

    def test_garbage_token(self):
        from src.web.auth import verify_token
        is_valid, payload = verify_token("not-a-jwt-at-all")
        assert is_valid is False


class TestRefreshAccessToken:
    def test_valid_refresh(self):
        from src.web.auth import create_token, verify_token, refresh_access_token
        refresh = create_token(user_id="u1", tier=3, email="a@b.com", token_type="refresh")
        new_access = refresh_access_token(refresh)
        assert new_access is not None
        is_valid, payload = verify_token(new_access)
        assert is_valid is True
        assert payload["sub"] == "u1"
        assert payload["tier"] == 3
        assert payload["type"] == "access"

    def test_refresh_with_access_token_fails(self):
        from src.web.auth import create_token, refresh_access_token
        access = create_token(user_id="u1", token_type="access")
        result = refresh_access_token(access)
        assert result is None

    def test_refresh_with_expired_token(self):
        from src.web.auth import create_token, refresh_access_token
        with patch("src.web.auth.time") as mock_time:
            mock_time.time.return_value = 1000000
            refresh = create_token(user_id="u1", token_type="refresh")
        result = refresh_access_token(refresh)
        assert result is None

    def test_refresh_with_invalid_token(self):
        from src.web.auth import refresh_access_token
        result = refresh_access_token("invalid.token.here")
        assert result is None


class TestExtractUserFromToken:
    def test_extracts_user_info(self):
        from src.web.auth import create_token, extract_user_from_token
        token = create_token(user_id="u1", tier=2, email="test@x.com")
        info = extract_user_from_token(token)
        assert info is not None
        assert info["user_id"] == "u1"
        assert info["tier"] == 2
        assert info["email"] == "test@x.com"

    def test_extracts_from_expired_token(self):
        """extract_user_from_token should still work for expired tokens."""
        from src.web.auth import create_token, extract_user_from_token
        with patch("src.web.auth.time") as mock_time:
            mock_time.time.return_value = 1000000
            token = create_token(user_id="u1")
        # Even expired, extraction should work
        info = extract_user_from_token(token)
        assert info is not None
        assert info["user_id"] == "u1"

    def test_returns_none_for_garbage(self):
        from src.web.auth import extract_user_from_token
        assert extract_user_from_token("not.valid") is None

    def test_returns_none_for_empty(self):
        from src.web.auth import extract_user_from_token
        assert extract_user_from_token("") is None

    def test_returns_none_for_invalid_base64(self):
        from src.web.auth import extract_user_from_token
        assert extract_user_from_token("a.!!!.b") is None


# ── Internal Helpers ──────────────────────────────────────

class TestB64UrlHelpers:
    def test_encode_decode_roundtrip(self):
        from src.web.auth import _b64url_encode, _b64url_decode
        data = b'{"test": "hello, world!"}'
        encoded = _b64url_encode(data)
        decoded = _b64url_decode(encoded)
        assert decoded == data

    def test_encode_strips_padding(self):
        from src.web.auth import _b64url_encode
        encoded = _b64url_encode(b"a")  # Single byte, normally needs padding
        assert "=" not in encoded

    def test_decode_restores_padding(self):
        from src.web.auth import _b64url_encode, _b64url_decode
        # Encode something that would need padding
        original = b"test data with padding needed"
        encoded = _b64url_encode(original)
        assert _b64url_decode(encoded) == original


class TestSign:
    def test_sign_produces_string(self):
        from src.web.auth import _sign
        sig = _sign("test payload")
        assert isinstance(sig, str)
        assert len(sig) > 0

    def test_sign_deterministic(self):
        from src.web.auth import _sign
        sig1 = _sign("same payload")
        sig2 = _sign("same payload")
        assert sig1 == sig2

    def test_sign_differs_for_different_payload(self):
        from src.web.auth import _sign
        sig1 = _sign("payload1")
        sig2 = _sign("payload2")
        assert sig1 != sig2
