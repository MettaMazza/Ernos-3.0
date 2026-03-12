"""
Ernos Web Accounts — User account management.

Storage: memory/web_users/{user_id}/account.json
Passwords: bcrypt-hashed (falls back to SHA256 if bcrypt unavailable)
"""
import json
import hashlib
import secrets
import time
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from src.core.data_paths import data_dir

logger = logging.getLogger("Web.Accounts")

ACCOUNTS_DIR = data_dir() / "web_users"

# Try bcrypt, fall back to SHA256
try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False
    logger.warning("bcrypt not installed — using SHA256 for password hashing. Install bcrypt for production.")


# ═══════════════════════════════════════════════════════════
# Password Hashing
# ═══════════════════════════════════════════════════════════

def _hash_password(password: str) -> str:
    """Hash a password using bcrypt or SHA256 fallback."""
    if _HAS_BCRYPT:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    else:
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return f"sha256:{salt}:{hashed}"


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    if _HAS_BCRYPT and hashed.startswith("$2"):
        return bcrypt.checkpw(password.encode(), hashed.encode())
    elif hashed.startswith("sha256:"):
        parts = hashed.split(":", 2)
        if len(parts) != 3:
            return False
        _, salt, expected = parts
        actual = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return secrets.compare_digest(actual, expected)
    return False


# ═══════════════════════════════════════════════════════════
# Account CRUD
# ═══════════════════════════════════════════════════════════

def _user_dir(user_id: str) -> Path:
    """Get the directory for a user's account data."""
    return ACCOUNTS_DIR / user_id


def _account_path(user_id: str) -> Path:
    return _user_dir(user_id) / "account.json"


def _load_account(user_id: str) -> Optional[Dict[str, Any]]:
    """Load account data from disk."""
    path = _account_path(user_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.error(f"Failed to load account {user_id}: {e}")
        return None


def _save_account(user_id: str, data: Dict[str, Any]) -> bool:
    """Save account data to disk."""
    path = _account_path(user_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
        return True
    except Exception as e:
        logger.error(f"Failed to save account {user_id}: {e}")
        return False


def _email_index_path() -> Path:
    """Index mapping email → user_id for login lookups."""
    return ACCOUNTS_DIR / "_email_index.json"


def _load_email_index() -> Dict[str, str]:
    path = _email_index_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save_email_index(index: Dict[str, str]):
    path = _email_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2))


# ═══════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════

def register(email: str, password: str, username: str = "") -> Tuple[bool, str, Optional[str]]:
    """
    Register a new account.

    Args:
        email: User's email address
        password: Plain text password (will be hashed)
        username: Optional display name

    Returns:
        (success, message, user_id or None)
    """
    email = email.strip().lower()

    # Validate email
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return False, "Invalid email address.", None

    # Validate password
    if len(password) < 6:
        return False, "Password must be at least 6 characters.", None

    # Check if email already exists
    index = _load_email_index()
    if email in index:
        return False, "An account with this email already exists.", None

    # Generate user ID
    user_id = f"web-{secrets.token_hex(8)}"

    # Create account
    account = {
        "user_id": user_id,
        "email": email,
        "username": username or email.split("@")[0],
        "password_hash": _hash_password(password),
        "tier": 0,
        "created_at": time.time(),
        "linked_discord_id": "",
        "linked_patreon_id": "",
        "discord_verified": False,
        "last_login": time.time(),
    }

    if not _save_account(user_id, account):
        return False, "Failed to create account.", None

    # Update email index
    index[email] = user_id
    _save_email_index(index)

    logger.info(f"New account registered: {user_id} ({email})")
    return True, "Account created successfully!", user_id


def login(email: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Authenticate a user.

    Returns:
        (success, message, account_data or None)
    """
    email = email.strip().lower()

    # Find user by email
    index = _load_email_index()
    user_id = index.get(email)
    if not user_id:
        return False, "Invalid email or password.", None

    # Load account
    account = _load_account(user_id)
    if not account:
        return False, "Account data corrupted. Contact support.", None

    # Verify password
    if not _verify_password(password, account.get("password_hash", "")):
        return False, "Invalid email or password.", None

    # Update last login
    account["last_login"] = time.time()
    _save_account(user_id, account)

    logger.info(f"Login successful: {user_id} ({email})")
    return True, "Login successful!", {
        "user_id": account["user_id"],
        "email": account["email"],
        "username": account.get("username", ""),
        "tier": account.get("tier", 0),
        "linked_discord_id": account.get("linked_discord_id", ""),
        "linked_patreon_id": account.get("linked_patreon_id", ""),
    }


def get_account(user_id: str) -> Optional[Dict[str, Any]]:
    """Get public account info (no password hash)."""
    account = _load_account(user_id)
    if not account:
        return None
    return {
        "user_id": account["user_id"],
        "email": account["email"],
        "username": account.get("username", ""),
        "tier": account.get("tier", 0),
        "linked_discord_id": account.get("linked_discord_id", ""),
        "linked_patreon_id": account.get("linked_patreon_id", ""),
        "created_at": account.get("created_at", 0),
    }


def update_tier(user_id: str, tier: int) -> bool:
    """Update a user's tier (called by Patreon integration)."""
    account = _load_account(user_id)
    if not account:
        return False

    account["tier"] = tier
    _save_account(user_id, account)

    # Also update flux capacitor
    try:
        from src.core.flux_capacitor import FluxCapacitor
        fc = FluxCapacitor()
        fc.set_tier(int(user_id.replace("web-", "", 1), 16) if user_id.startswith("web-") else hash(user_id), tier)
    except Exception as e:
        logger.debug(f"Flux capacitor tier sync skipped: {e}")

    logger.info(f"Tier updated for {user_id}: {tier}")
    return True



# ═══════════════════════════════════════════════════════════
# Discord Verification Codes
# ═══════════════════════════════════════════════════════════

# In-memory store: {user_id: {"code": "123456", "discord_id": "...", "expires": timestamp}}
_pending_discord_codes: Dict[str, Dict[str, Any]] = {}
DISCORD_CODE_TTL = 300  # 5 minutes


def generate_discord_code(user_id: str, discord_id: str) -> str:
    """
    Generate a 6-digit verification code for Discord linking.
    
    Returns the code string. Caller is responsible for sending it via DM.
    Code expires after 5 minutes.
    """
    import random
    code = f"{random.randint(100000, 999999)}"
    
    _pending_discord_codes[user_id] = {
        "code": code,
        "discord_id": discord_id,
        "expires": time.time() + DISCORD_CODE_TTL,
    }
    
    # Cleanup expired codes
    now = time.time()
    expired = [uid for uid, data in _pending_discord_codes.items() if data["expires"] < now]
    for uid in expired:
        del _pending_discord_codes[uid]
    
    logger.info(f"Discord verification code generated for {user_id} → {discord_id}")
    return code


def verify_discord_code(user_id: str, discord_id: str, code: str) -> Tuple[bool, str]:
    """
    Verify a Discord linking code.
    
    Returns:
        (success, message)
    """
    pending = _pending_discord_codes.get(user_id)
    if not pending:
        return False, "No pending verification. Request a new code."
    
    # Check expiry
    if pending["expires"] < time.time():
        del _pending_discord_codes[user_id]
        return False, "Verification code expired. Request a new one."
    
    # Check Discord ID matches
    if pending["discord_id"] != discord_id:
        return False, "Discord ID doesn't match the pending verification."
    
    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(pending["code"], code.strip()):
        return False, "Incorrect verification code."
    
    # Success — link the account
    del _pending_discord_codes[user_id]
    link_discord(user_id, discord_id)
    
    return True, "Discord account linked successfully!"


def link_discord(user_id: str, discord_id: str) -> bool:
    """Link a Discord account to a web account."""
    account = _load_account(user_id)
    if not account:
        return False

    account["linked_discord_id"] = discord_id
    account["discord_verified"] = True
    _save_account(user_id, account)

    logger.info(f"Discord linked: {user_id} → {discord_id}")
    return True


def link_patreon(user_id: str, patreon_id: str, tier: int) -> bool:
    """Link a Patreon account and set tier."""
    account = _load_account(user_id)
    if not account:
        return False

    account["linked_patreon_id"] = patreon_id
    account["tier"] = tier
    _save_account(user_id, account)

    # Sync tier to flux capacitor
    update_tier(user_id, tier)

    logger.info(f"Patreon linked: {user_id} → {patreon_id} (tier {tier})")
    return True
