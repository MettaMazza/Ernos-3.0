#!/usr/bin/env python3
"""
License key management — generate keys for customers and their hashes for the image.

Usage:
    # Generate a random license key
    python scripts/generate_license.py generate

    # Generate hash for an existing key (to bake into the image)
    python scripts/generate_license.py hash ERNOS-ABCD-1234-EF56-7890

    # Generate N keys and their hashes at once
    python scripts/generate_license.py batch 5
"""
import sys
import os
import secrets
import hashlib
import hmac

_HMAC_SECRET = b"ErnosV3-LicenseValidation-2026"


def _generate_key() -> str:
    """Generate a random license key in ERNOS-XXXX-XXXX-XXXX-XXXX format."""
    hex_chars = secrets.token_hex(10).upper()  # 20 hex chars
    parts = [hex_chars[i:i+4] for i in range(0, 20, 4)]
    return f"ERNOS-{'-'.join(parts)}"


def _hash_key(key: str) -> str:
    """Compute the HMAC-SHA256 hash of a license key."""
    return hmac.new(_HMAC_SECRET, key.strip().encode("utf-8"), hashlib.sha256).hexdigest()


def cmd_generate():
    """Generate a single key and its hash."""
    key = _generate_key()
    key_hash = _hash_key(key)
    print(f"License Key:  {key}")
    print(f"Hash:         {key_hash}")
    print()
    print(f"Give the KEY to the customer.")
    print(f"Add the HASH to src/core/.license_hashes")


def cmd_hash(key: str):
    """Hash an existing key."""
    key_hash = _hash_key(key)
    print(f"Key:   {key}")
    print(f"Hash:  {key_hash}")


def cmd_batch(count: int):
    """Generate multiple keys and output a hash file."""
    print("# Ernos License Key Hashes")
    print("# Generated keys (KEEP SECRET — give to customers):")
    keys = []
    for i in range(count):
        key = _generate_key()
        key_hash = _hash_key(key)
        keys.append((key, key_hash))
        print(f"#   {i+1}. {key}")

    print()
    print("# Paste lines below into src/core/.license_hashes")
    for key, key_hash in keys:
        print(key_hash)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "generate":
        cmd_generate()
    elif cmd == "hash" and len(sys.argv) >= 3:
        cmd_hash(sys.argv[2])
    elif cmd == "batch" and len(sys.argv) >= 3:
        cmd_batch(int(sys.argv[2]))
    else:
        print(__doc__)
        sys.exit(1)
