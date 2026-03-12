#!/usr/bin/env python3
"""
Build-time encryption — encrypts all prompt .txt files to .enc using AES-256-CBC.

Usage:
    python scripts/encrypt_assets.py

This encrypts every .txt file in src/prompts/ into a .enc file using the
same baked-in key as secure_loader.py. No arguments needed.

The original .txt files should be deleted from the Docker image afterwards.
"""
import sys
import os
import hashlib
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Must match secure_loader.py exactly ───
_SALT = b"ErnosV3-2026-AES256-Salt"
_INTERNAL_KEY = "Ern0s-V3-2026-Int3rnal-Pr0mpt-Prot3ction-K3y-AES256"
PROMPTS_DIR = Path("src/prompts")


def _derive_key() -> bytes:
    """Derive a 32-byte AES-256 key from the internal passphrase via PBKDF2."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        _INTERNAL_KEY.encode("utf-8"),
        _SALT,
        iterations=100_000,
        dklen=32,
    )


def encrypt_bytes(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt with AES-256-CBC. Returns IV (16 bytes) + ciphertext."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    import secrets

    iv = secrets.token_bytes(16)

    # PKCS7 pad to block size
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    return iv + ciphertext


def encrypt_prompts():
    """Encrypt all .txt prompt files to .enc."""
    key = _derive_key()

    txt_files = list(PROMPTS_DIR.glob("*.txt"))
    if not txt_files:
        print(f"⚠️  No .txt files found in {PROMPTS_DIR}")
        return

    print(f"🔐 Encrypting {len(txt_files)} prompt files...")
    for txt_file in sorted(txt_files):
        plaintext = txt_file.read_bytes()
        encrypted = encrypt_bytes(plaintext, key)

        enc_file = txt_file.with_suffix(".enc")
        enc_file.write_bytes(encrypted)

        print(f"  ✅ {txt_file.name} → {enc_file.name} ({len(plaintext)} → {len(encrypted)} bytes)")

    print(f"\n✅ All {len(txt_files)} prompts encrypted.")
    print(f"   Delete .txt files from the image to complete protection.")


if __name__ == "__main__":
    encrypt_prompts()
