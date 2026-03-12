"""
Tests for ProvenanceManager
Targeting 95%+ coverage for src/security/provenance.py
"""
import pytest
import tempfile
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.security.provenance import ProvenanceManager


class TestProvenanceManager:
    """Tests for ProvenanceManager class."""
    
    def setup_method(self):
        """Setup temp environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.salt_file = Path(self.temp_dir) / "shard_salt.secret"
        self.ledger_file = Path(self.temp_dir) / "provenance_ledger.jsonl"
        
        # Patch the class-level paths
        self.salt_patcher = patch.object(ProvenanceManager, 'SALT_FILE', self.salt_file)
        self.ledger_patcher = patch.object(ProvenanceManager, 'LEDGER_FILE', self.ledger_file)
        self.salt_patcher.start()
        self.ledger_patcher.start()
        
        # Clear salt cache
        ProvenanceManager._salt_cache = None
    
    def teardown_method(self):
        """Cleanup."""
        self.salt_patcher.stop()
        self.ledger_patcher.stop()
        ProvenanceManager._salt_cache = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_salt_creates_new(self):
        """Test salt is created when missing."""
        salt = ProvenanceManager.get_salt()
        
        assert salt is not None
        assert len(salt) == 64  # 32 bytes hex = 64 chars
        assert self.salt_file.exists()
    
    def test_get_salt_reads_existing(self):
        """Test salt is read from existing file."""
        self.salt_file.parent.mkdir(parents=True, exist_ok=True)
        self.salt_file.write_text("existing_salt_value")
        
        salt = ProvenanceManager.get_salt()
        
        assert salt == "existing_salt_value"
    
    def test_get_salt_caches(self):
        """Test salt is cached."""
        salt1 = ProvenanceManager.get_salt()
        salt2 = ProvenanceManager.get_salt()
        
        assert salt1 == salt2
    
    def test_get_salt_rotation_date_no_file(self):
        """Test rotation date when no file exists."""
        result = ProvenanceManager.get_salt_rotation_date()
        
        assert result == "NEVER"
    
    def test_get_salt_rotation_date_with_file(self):
        """Test rotation date when file exists."""
        self.salt_file.parent.mkdir(parents=True, exist_ok=True)
        self.salt_file.write_text("salt")
        
        result = ProvenanceManager.get_salt_rotation_date()
        
        assert result != "NEVER"
        assert result != "UNKNOWN"
    
    def test_compute_checksum(self):
        """Test HMAC checksum computation."""
        ProvenanceManager.get_salt()  # Ensure salt exists
        
        checksum = ProvenanceManager.compute_checksum(b"test data")
        
        assert len(checksum) == 64  # SHA256 hex
    
    def test_compute_checksum_deterministic(self):
        """Test same input produces same checksum."""
        ProvenanceManager.get_salt()
        
        cs1 = ProvenanceManager.compute_checksum(b"same data")
        cs2 = ProvenanceManager.compute_checksum(b"same data")
        
        assert cs1 == cs2
    
    def test_sign_file_success(self):
        """Test signing a file."""
        ProvenanceManager.get_salt()
        
        # Create test file
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test content")
        
        checksum = ProvenanceManager.sign_file(str(test_file))
        
        assert len(checksum) == 64
    
    def test_sign_file_not_found(self):
        """Test signing non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            ProvenanceManager.sign_file("/nonexistent/file.txt")
    
    def test_log_artifact(self):
        """Test logging an artifact."""
        ProvenanceManager.get_salt()
        
        # Create test file
        test_file = Path(self.temp_dir) / "artifact.png"
        test_file.write_bytes(b"fake image data")
        
        checksum = ProvenanceManager.log_artifact(
            str(test_file),
            artifact_type="image",
            metadata={"user_id": 123}
        )
        
        assert len(checksum) == 64
        assert self.ledger_file.exists()
    
    def test_verify_file_matches(self):
        """Test verifying file with correct checksum."""
        ProvenanceManager.get_salt()
        
        test_file = Path(self.temp_dir) / "verify.txt"
        test_file.write_text("verify me")
        
        expected = ProvenanceManager.sign_file(str(test_file))
        result = ProvenanceManager.verify_file(str(test_file), expected)
        
        assert result is True
    
    def test_verify_file_mismatch(self):
        """Test verifying file with wrong checksum."""
        ProvenanceManager.get_salt()
        
        test_file = Path(self.temp_dir) / "verify2.txt"
        test_file.write_text("verify me")
        
        result = ProvenanceManager.verify_file(str(test_file), "wrong_checksum")
        
        assert result is False
    
    def test_verify_file_no_expected(self):
        """Test verify file without expected checksum returns True."""
        ProvenanceManager.get_salt()
        
        test_file = Path(self.temp_dir) / "verify3.txt"
        test_file.write_text("data")
        
        result = ProvenanceManager.verify_file(str(test_file))
        
        assert result is True
    
    def test_is_tracked_found(self):
        """Test checking if checksum is in ledger."""
        ProvenanceManager.get_salt()
        
        # Create and log a file
        test_file = Path(self.temp_dir) / "tracked.txt"
        test_file.write_text("tracked content")
        checksum = ProvenanceManager.log_artifact(str(test_file), "test")
        
        result = ProvenanceManager.is_tracked(checksum)
        
        assert result is True
    
    def test_is_tracked_not_found(self):
        """Test checking non-existent checksum."""
        result = ProvenanceManager.is_tracked("nonexistent_checksum")
        
        assert result is False
    
    def test_lookup_by_checksum_found(self):
        """Test looking up artifact by checksum."""
        ProvenanceManager.get_salt()
        
        test_file = Path(self.temp_dir) / "lookup.txt"
        test_file.write_text("lookup content")
        checksum = ProvenanceManager.log_artifact(
            str(test_file), "document", {"user_id": 456}
        )
        
        record = ProvenanceManager.lookup_by_checksum(checksum)
        
        assert record is not None
        assert record["type"] == "document"
        assert record["checksum"] == checksum
    
    def test_lookup_by_checksum_not_found(self):
        """Test looking up non-existent checksum."""
        result = ProvenanceManager.lookup_by_checksum("missing")
        
        assert result is None
    
    def test_lookup_by_file(self):
        """Test looking up provenance by file."""
        ProvenanceManager.get_salt()
        
        test_file = Path(self.temp_dir) / "byfile.txt"
        test_file.write_text("file lookup content")
        ProvenanceManager.log_artifact(str(test_file), "code")
        
        record = ProvenanceManager.lookup_by_file(str(test_file))
        
        assert record is not None
        assert record["type"] == "code"
    
    def test_lookup_by_file_not_found(self):
        """Test lookup for non-existent file."""
        result = ProvenanceManager.lookup_by_file("/nonexistent/file.txt")
        
        assert result is None
    
    def test_get_artifact_info_found(self):
        """Test getting human-readable artifact info."""
        ProvenanceManager.get_salt()
        
        test_file = Path(self.temp_dir) / "info.txt"
        test_file.write_text("info content")
        ProvenanceManager.log_artifact(
            str(test_file), "image", {"user_id": 789, "scope": "PRIVATE"}
        )
        
        info = ProvenanceManager.get_artifact_info(str(test_file))
        
        assert "Provenance Verified" in info
        assert "image" in info
    
    def test_get_artifact_info_not_found(self):
        """Test artifact info for untracked file."""
        result = ProvenanceManager.get_artifact_info("/untracked/file.txt")
        
        assert "Unknown artifact" in result
