"""
License key validation — prevents unauthorized use of Docker-distributed Ernos.

The license key serves double duty:
  1. Startup gate — bot refuses to run without a valid key
  2. Prompt decryption seed — encrypted prompts can't be read without it

Key format: ERNOS-XXXX-XXXX-XXXX-XXXX (20 hex chars + dashes)
"""
import os
import hashlib
import hmac
import logging
import sys

logger = logging.getLogger("License")

# This hash is baked into the image at build time by build_image.sh.
# It's the HMAC-SHA256 of the master key, so the master key itself isn't in the image.
# Multiple valid hashes can be listed (one per customer key).
_VALID_KEY_HASHES_FILE = os.path.join(os.path.dirname(__file__), ".license_hashes")

_HMAC_SECRET = b"ErnosV3-LicenseValidation-2026"


def _hash_key(key: str) -> str:
    """Compute the HMAC-SHA256 hash of a license key."""
    return hmac.new(_HMAC_SECRET, key.strip().encode("utf-8"), hashlib.sha256).hexdigest()


def _load_valid_hashes() -> set:
    """Load valid key hashes from the baked-in file."""
    try:
        with open(_VALID_KEY_HASHES_FILE, "r") as f:
            return {line.strip() for line in f if line.strip() and not line.startswith("#")}
    except FileNotFoundError:
        # No hash file = development mode, skip validation
        return set()


def generate_key_hash(key: str) -> str:
    """Generate a hash for a license key (run this to create hashes for customers).
    
    Usage:
        python -c "from src.core.license import generate_key_hash; print(generate_key_hash('ERNOS-ABCD-1234-EF56-7890'))"
    """
    return _hash_key(key)


def validate_license() -> bool:
    """
    Validate the license key from ERNOS_LICENSE_KEY env var.
    
    Returns True if:
      - No .license_hashes file exists (development mode — no restrictions)
      - ERNOS_LICENSE_KEY matches a hash in .license_hashes
    
    Returns False if:
      - .license_hashes exists but ERNOS_LICENSE_KEY is missing or invalid
    """
    valid_hashes = _load_valid_hashes()

    # No hash file = dev mode, always valid
    if not valid_hashes:
        logger.info("No license hash file found — running in development mode")
        return True

    key = os.environ.get("ERNOS_LICENSE_KEY", "").strip()
    if not key:
        logger.error("ERNOS_LICENSE_KEY environment variable is not set")
        return False

    key_hash = _hash_key(key)
    if key_hash in valid_hashes:
        logger.info("License key validated successfully")
        return True

    logger.error("Invalid license key")
    return False


def enforce_license():
    """Check license and exit if invalid. Call at startup."""
    if not validate_license():
        print()
        print("═══════════════════════════════════════════════")
        print("  ❌  Invalid or missing ERNOS_LICENSE_KEY")
        print()
        print("  Add your license key to .env:")
        print("    ERNOS_LICENSE_KEY=your-key-here")
        print()
        print("  Get a key at: https://ernos.dev/license")
        print("═══════════════════════════════════════════════")
        print()
        sys.exit(1)
