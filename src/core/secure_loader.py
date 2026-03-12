"""
Secure asset loader — decrypts AES-256-CBC encrypted prompt files at runtime.

Build-time: scripts/encrypt_assets.py encrypts .txt → .enc
Runtime: this module decrypts .enc → plaintext in memory (never written to disk)

The encryption key is derived from a baked-in secret via PBKDF2.
PyArmor obfuscation makes extracting the key extremely difficult.
"""
import os
import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("SecureLoader")

# ─── Baked-in secrets (protected by PyArmor obfuscation) ───
# These values are compiled into obfuscated bytecode — not readable
# from the Docker image filesystem. Changing them requires rebuilding.
_SALT = b"ErnosV3-2026-AES256-Salt"
_INTERNAL_KEY = "Ern0s-V3-2026-Int3rnal-Pr0mpt-Prot3ction-K3y-AES256"


def _derive_key(passphrase: str = "") -> bytes:
    """Derive a 32-byte AES-256 key from the internal passphrase via PBKDF2."""
    # Use internal key — no external env var needed
    key_material = passphrase if passphrase else _INTERNAL_KEY
    return hashlib.pbkdf2_hmac(
        "sha256",
        key_material.encode("utf-8"),
        _SALT,
        iterations=100_000,
        dklen=32,
    )


def decrypt_bytes(ciphertext: bytes, key: bytes) -> str:
    """Decrypt AES-256-CBC ciphertext. First 16 bytes = IV."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding

    iv = ciphertext[:16]
    encrypted = ciphertext[16:]

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(encrypted) + decryptor.finalize()

    # Remove PKCS7 padding
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()

    return plaintext.decode("utf-8")


def load_prompt(name_or_path: str) -> str:
    """
    Load a prompt file, transparently decrypting if encrypted.

    Accepts:
      - A bare name like "identity" → looks for src/prompts/identity.enc or .txt
      - A full path like "src/prompts/identity.txt" → looks for .enc version first

    Returns the plaintext content, or empty string on failure.
    """
    # Normalize to a Path
    path = Path(name_or_path)

    # If given a .txt path, check for .enc version first
    if path.suffix == ".txt":
        enc_path = path.with_suffix(".enc")
    elif path.suffix == ".enc":
        enc_path = path
    elif path.suffix == "":
        # Bare name — resolve to prompts dir
        prompts_dir = Path("src/prompts")
        enc_path = prompts_dir / f"{path.name}.enc"
        path = prompts_dir / f"{path.name}.txt"
    else:
        enc_path = None

    # Try encrypted version first
    if enc_path and enc_path.exists():
        try:
            key = _derive_key()
            return decrypt_bytes(enc_path.read_bytes(), key)
        except Exception as e:
            logger.error(f"Failed to decrypt {enc_path}: {e}")
            return ""

    # Fall back to plaintext (development mode)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return ""

    logger.warning(f"Prompt file not found: {name_or_path}")
    return ""
