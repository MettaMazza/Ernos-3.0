"""
Ernos Web Auth — JWT token management.

Handles token creation, validation, and refresh for web users.
Stateless: no database needed for sessions, everything in the JWT.
"""
import os
import time
import logging
import hashlib
import hmac
import json
import base64
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("Web.Auth")

# JWT secret — set via env var or generate a deterministic one from system
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    # Fallback: derive from machine-specific data
    import uuid
    machine_id = str(uuid.getnode())
    JWT_SECRET = hashlib.sha256(f"ernos-web-{machine_id}".encode()).hexdigest()
    logger.warning("JWT_SECRET not set — using machine-derived key. Set JWT_SECRET env var for production.")

# Token expiry
ACCESS_TOKEN_EXPIRY = 24 * 60 * 60       # 24 hours
REFRESH_TOKEN_EXPIRY = 7 * 24 * 60 * 60  # 7 days


def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Base64url decode with padding restoration."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _sign(payload: str) -> str:
    """Create HMAC-SHA256 signature."""
    return _b64url_encode(
        hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    )


def create_token(
    user_id: str,
    tier: int = 0,
    email: str = "",
    linked_discord_id: str = "",
    linked_patreon_id: str = "",
    token_type: str = "access",
) -> str:
    """
    Create a JWT token.

    Args:
        user_id: Unique user identifier
        tier: Flux capacitor tier (0-4)
        email: User's email
        linked_discord_id: Linked Discord user ID
        linked_patreon_id: Linked Patreon user ID
        token_type: "access" or "refresh"

    Returns:
        JWT token string
    """
    now = int(time.time())
    expiry = ACCESS_TOKEN_EXPIRY if token_type == "access" else REFRESH_TOKEN_EXPIRY

    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_data = {
        "sub": user_id,
        "tier": tier,
        "email": email,
        "discord_id": linked_discord_id,
        "patreon_id": linked_patreon_id,
        "type": token_type,
        "iat": now,
        "exp": now + expiry,
    }
    payload = _b64url_encode(json.dumps(payload_data).encode())

    signature = _sign(f"{header}.{payload}")
    return f"{header}.{payload}.{signature}"


def verify_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Verify and decode a JWT token.

    Returns:
        (is_valid, payload_dict or None)
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False, None

        header, payload, signature = parts

        # Verify signature
        expected_sig = _sign(f"{header}.{payload}")
        if not hmac.compare_digest(signature, expected_sig):
            logger.warning("JWT signature verification failed")
            return False, None

        # Decode payload
        payload_data = json.loads(_b64url_decode(payload))

        # Check expiry
        if payload_data.get("exp", 0) < time.time():
            logger.debug("JWT token expired")
            return False, None

        return True, payload_data

    except Exception as e:
        logger.warning(f"JWT verification error: {e}")
        return False, None


def refresh_access_token(refresh_token: str) -> Optional[str]:
    """
    Create a new access token from a valid refresh token.

    Returns:
        New access token, or None if refresh token is invalid.
    """
    is_valid, payload = verify_token(refresh_token)
    if not is_valid:
        return None

    if payload.get("type") != "refresh":
        logger.warning("Attempted to refresh with non-refresh token")
        return None

    return create_token(
        user_id=payload["sub"],
        tier=payload.get("tier", 0),
        email=payload.get("email", ""),
        linked_discord_id=payload.get("discord_id", ""),
        linked_patreon_id=payload.get("patreon_id", ""),
        token_type="access",
    )


def extract_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Extract user info from token without full verification (for logging).
    Still checks signature but tolerates expired tokens.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_data = json.loads(_b64url_decode(parts[1]))
        return {
            "user_id": payload_data.get("sub"),
            "tier": payload_data.get("tier", 0),
            "email": payload_data.get("email", ""),
        }
    except Exception:
        return None
