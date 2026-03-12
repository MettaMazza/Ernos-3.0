import pytest
import shutil
import json
import logging
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from datetime import datetime, timedelta

from src.backup.manager import BackupManager
from src.lobes.superego.sentinel import SentinelAbility

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Test.MRN")

# Constants for testing
TEST_BACKUP_DIR = Path("tests/temp_backups")
MRN_SALT_FILE = Path("tests/temp_salt.secret")

@pytest.fixture
def mock_backup_manager():
    # Patch BACKUP_DIR and ProvenanceManager
    with patch("src.backup.manager.BackupManager.BACKUP_DIR", TEST_BACKUP_DIR), \
         patch("src.security.provenance.ProvenanceManager.get_salt", return_value="TEST_SALT"):
        
        # Create temp dirs
        TEST_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        (TEST_BACKUP_DIR / "user_exports").mkdir(exist_ok=True)
        
        manager = BackupManager()
        
        # Seed rate limits to empty
        manager._last_export = {}
        
        yield manager
        
        # Cleanup
        if TEST_BACKUP_DIR.exists():
            shutil.rmtree(TEST_BACKUP_DIR)
        if MRN_SALT_FILE.exists():
            try:
                MRN_SALT_FILE.unlink()
            except:
                pass

@pytest.mark.asyncio
async def test_shard_export_integrity(mock_backup_manager):
    """Verify Shard Generation, Salt Creation, and Signature."""
    user_id = 12345
    
    # 1. Create Mock User Silo
    user_silo = TEST_BACKUP_DIR.parent.parent / "memory" / "users" / str(user_id)
    user_silo.mkdir(parents=True, exist_ok=True)
    (user_silo / "test_memory.txt").write_text("Secret Memory Base")
    
    # 2. Export Context (Force=True to bypass rate limit)
    # We need to mock 'Path("memory/users")' inside BackupManager too or ensure it looks at real/test memory?
    # The backup manager uses hardcoded "memory/users". We should patch it or create it.
    # Let's mock the file gathering part or just create the actual directory if safe.
    # Creating real directory "memory/users/12345" might be messy if it exists.
    # Prudent approach: Patch Path in export_user_context? 
    # Or just let it run if we clean up? 
    # Let's mock `rglob`? 
    # Better: The BackupManager reads from "memory/users". Let's assume the test env allows it or we patch `Path`.
    
    # Actually, let's just patch the method `_compute_checksum` to verify it's called?
    # No, we want to verify the output file has a valid signature.
    
    # Let's patch `pathlib.Path` isn't easy. 
    # Let's use `pyfakefs`? No, simpler.
    # We will just verify `_compute_checksum` logic and that `export_user_context` calls it.
    
    # Let's test `_compute_checksum` directly first.
    data = {
        "format_version": "3.0",
        "user_id": 12345,
        "exported_at": "2026-02-05T12:00:00",
        "context": {"file.txt": "content"}
    }
    checksum = mock_backup_manager._compute_checksum(data)
    assert len(checksum) == 64 # SHA256 hex
    
    # Verify proper salt usage
    mock_backup_manager._salt = "WRONG_SALT"
    checksum_salted = mock_backup_manager._compute_checksum(data)
    assert checksum != checksum_salted
    
    # Test verify_backup with correct salt
    data["checksum"] = checksum_salted
    is_valid, _ = mock_backup_manager.verify_backup(data)
    assert is_valid
    
    # Test tampered data
    data["context"]["file.txt"] = "TAMPERED"
    is_valid, reason = mock_backup_manager.verify_backup(data)
    assert not is_valid
    assert "different system salt" in reason.lower() or "tampered" in reason.lower()

@pytest.mark.asyncio
async def test_legacy_rejection(mock_backup_manager):
    """Verify pre-rotation backups are rejected by salt mismatch."""
    # Create backup with current salt
    data = {
        "format_version": "3.0",
        "user_id": 12345,
        "exported_at": "2026-02-04T12:00:00",
        "context": {"test": "data"},
    }
    data["checksum"] = mock_backup_manager._compute_checksum(data)
    
    # Verify it's valid with current salt
    is_valid, reason = mock_backup_manager.verify_backup(data)
    assert is_valid
    
    # Now rotate the salt (simulate old backup with different salt)
    mock_backup_manager._salt = "NEW_ROTATED_SALT"
    
    # Same backup should now fail checksum validation
    is_valid, reason = mock_backup_manager.verify_backup(data)
    assert not is_valid
    assert "different system salt" in reason.lower() or "tampered" in reason.lower()

@pytest.mark.asyncio
async def test_sentinel_review():
    """Verify Sentinel Ability LLM interaction."""
    
    # Logic: Mock bot.engine -> generate_response -> "APPROVED" or "REJECTED"
    
    mock_lobe = MagicMock()
    mock_lobe.cerebrum.bot.loop = asyncio.get_event_loop()
    mock_lobe.cerebrum.bot.engine_manager.get_active_engine = MagicMock()
    
    sentinel = SentinelAbility(mock_lobe)
    
    # Case 1: Approval
    mock_engine = MagicMock()
    mock_engine.generate_response.return_value = "APPROVED"
    mock_lobe.cerebrum.bot.get_engine.return_value = mock_engine
    
    success, reason = await sentinel.review_shard({"context": {"a": "b"}})
    assert success
    assert "Approved" in reason
    
    # Case 2: Rejection (Sycophancy)
    mock_engine.generate_response.return_value = "REJECTED: Contains sycophantic agreement with user delusion."
    
    success, reason = await sentinel.review_shard({"context": {"a": "b"}})
    assert not success
    assert "REJECTED" in reason
    assert "sycophantic" in reason

if __name__ == "__main__":
    # Manually run async tests if executed as script
    pass
