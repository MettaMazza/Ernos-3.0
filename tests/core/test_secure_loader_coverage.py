"""
Coverage tests for src/core/secure_loader.py.
Targets 20 uncovered lines: decrypt_bytes, load_prompt (all branches).
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── _derive_key ──────────────────────────────────────────
class TestDeriveKey:
    def test_default_key(self):
        from src.core.secure_loader import _derive_key
        key = _derive_key()
        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_custom_passphrase(self):
        from src.core.secure_loader import _derive_key
        key = _derive_key("custom_pass")
        assert len(key) == 32

    def test_different_passphrases_produce_different_keys(self):
        from src.core.secure_loader import _derive_key
        k1 = _derive_key("pass1")
        k2 = _derive_key("pass2")
        assert k1 != k2


# ── decrypt_bytes ────────────────────────────────────────
class TestDecryptBytes:
    def test_roundtrip(self):
        """Encrypt then decrypt to verify roundtrip."""
        from src.core.secure_loader import decrypt_bytes, _derive_key
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        import os

        key = _derive_key()
        plaintext = "Hello, this is a secret prompt!"

        # Encrypt manually
        iv = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = iv + (encryptor.update(padded) + encryptor.finalize())

        result = decrypt_bytes(ciphertext, key)
        assert result == plaintext

    def test_wrong_key_fails(self):
        """Wrong key should raise an error."""
        from src.core.secure_loader import decrypt_bytes, _derive_key
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        import os

        key = _derive_key("correct")
        wrong_key = _derive_key("wrong")
        plaintext = "secret data"

        iv = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = iv + (encryptor.update(padded) + encryptor.finalize())

        with pytest.raises(Exception):
            decrypt_bytes(ciphertext, wrong_key)


# ── load_prompt ──────────────────────────────────────────
class TestLoadPrompt:
    def test_txt_file_exists(self, tmp_path):
        """Loading a .txt file that exists."""
        from src.core.secure_loader import load_prompt
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello prompt")
        result = load_prompt(str(txt_file))
        assert result == "Hello prompt"

    def test_txt_file_not_found(self):
        """Loading a nonexistent file returns empty."""
        from src.core.secure_loader import load_prompt
        result = load_prompt("/nonexistent/path/prompt.txt")
        assert result == ""

    def test_enc_file_preferred(self, tmp_path):
        """If .enc exists, it's used instead of .txt."""
        from src.core.secure_loader import load_prompt, _derive_key
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        import os

        key = _derive_key()
        plaintext = "encrypted content"

        iv = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = iv + (encryptor.update(padded) + encryptor.finalize())

        enc_file = tmp_path / "test.enc"
        enc_file.write_bytes(ciphertext)
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("plaintext fallback")

        result = load_prompt(str(txt_file))
        assert result == "encrypted content"

    def test_enc_path_directly(self, tmp_path):
        """Loading a .enc path directly."""
        from src.core.secure_loader import load_prompt, _derive_key
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        import os

        key = _derive_key()
        plaintext = "direct enc"

        iv = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = iv + (encryptor.update(padded) + encryptor.finalize())

        enc_file = tmp_path / "test.enc"
        enc_file.write_bytes(ciphertext)

        result = load_prompt(str(enc_file))
        assert result == "direct enc"

    def test_bare_name_lookup(self, tmp_path):
        """Loading by bare name resolves to src/prompts dir."""
        from src.core.secure_loader import load_prompt
        # Without patching the prompts dir, this will look in src/prompts/
        # If neither .enc nor .txt exists, returns empty
        result = load_prompt("nonexistent_prompt_name_xyz")
        assert result == ""

    def test_unknown_extension(self):
        """Non-.txt/.enc extension — enc_path is None."""
        from src.core.secure_loader import load_prompt
        result = load_prompt("/nonexistent/file.json")
        assert result == ""

    def test_corrupt_enc_file(self, tmp_path):
        """Corrupt .enc file returns empty (decryption fails)."""
        from src.core.secure_loader import load_prompt
        enc_file = tmp_path / "corrupt.enc"
        enc_file.write_bytes(b"this is not valid ciphertext at all!!")
        result = load_prompt(str(enc_file))
        assert result == ""

    def test_txt_read_error(self, tmp_path):
        """Error reading .txt file returns empty."""
        from src.core.secure_loader import load_prompt
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("content")
        with patch.object(Path, "read_text", side_effect=Exception("read error")):
            result = load_prompt(str(txt_file))
        assert result == ""
