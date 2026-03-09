import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.security.provenance import ProvenanceManager

@pytest.fixture
def clean_ledger(tmp_path):
    """Setup a temporary ledger and salt for testing."""
    ledger = tmp_path / "provenance_ledger.jsonl"
    salt = tmp_path / "shard_salt.secret"
    
    with patch("src.security.provenance.ProvenanceManager.LEDGER_FILE", ledger), \
         patch("src.security.provenance.ProvenanceManager.SALT_FILE", salt):
        ProvenanceManager._salt_cache = None # Reset cache
        yield ledger

class TestProvenanceManager:

    def test_salt_generation(self, clean_ledger):
        """Verify salt is generated on first use and persisted."""
        salt1 = ProvenanceManager.get_salt()
        assert len(salt1) == 64 # Hex of 32 bytes
        
        # Verify persistence
        ProvenanceManager._salt_cache = None
        salt2 = ProvenanceManager.get_salt()
        assert salt1 == salt2

    def test_sign_and_log_artifact(self, clean_ledger, tmp_path):
        """Verify file signing and ledger logging."""
        test_file = tmp_path / "test_artifact.txt"
        test_file.write_text("Hello World")
        
        checksum = ProvenanceManager.log_artifact(str(test_file), "text", {"author": "Ernos"})
        
        # Verify Ledger
        assert clean_ledger.exists()
        lines = clean_ledger.read_text().strip().split('\n')
        assert len(lines) == 1
        entry = json.loads(lines[0])
        
        assert entry["checksum"] == checksum
        assert entry["type"] == "text"
        assert entry["metadata"]["author"] == "Ernos"
        
        # Verify Verify
        assert ProvenanceManager.verify_file(str(test_file), checksum)
        
    def test_verify_tampering(self, clean_ledger, tmp_path):
        """Verify that modified files fail checksum check."""
        test_file = tmp_path / "test_tamper.txt"
        test_file.write_text("Original content")
        
        checksum = ProvenanceManager.sign_file(str(test_file))
        
        # Tamper
        test_file.write_text("Modified content")
        
        assert not ProvenanceManager.verify_file(str(test_file), checksum)

    def test_backup_manager_integration_mock(self):
        """Verify BackupManager uses ProvenanceManager salt."""
        with patch("src.security.provenance.ProvenanceManager.get_salt", return_value="security_salt"):
            # Mock rate limit (now in export.py after refactor)
            with patch("src.backup.export.BackupExporter._load_rate_limits", return_value={}):
                from src.backup.manager import BackupManager
                mgr = BackupManager()
                assert mgr._salt == "security_salt"

    def test_coding_tool_integration_mock(self):
        """Verify create_program logs provenance."""
        from src.tools.coding import create_program
        
        with patch("src.security.provenance.ProvenanceManager.log_artifact") as mock_log, \
             patch("src.tools.coding.validate_path_scope", return_value=True), \
             patch("builtins.open", MagicMock()) as mock_open:
             
             # Mock open context manager
             mock_file = MagicMock()
             mock_open.return_value.__enter__.return_value = mock_file
             
             # Mock getcwd to allow path check
             with patch("os.getcwd", return_value="/tmp"), patch("pathlib.Path.resolve", return_value=Path("/tmp/foo.py")):
                 create_program("/tmp/foo.py", "print('hi')")
                 
                 mock_log.assert_called_once()
                 args, _ = mock_log.call_args
                 assert "foo.py" in str(args[0])
                 assert args[1] == "code"
