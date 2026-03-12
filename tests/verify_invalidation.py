import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from backup.manager import BackupManager

def test_invalidation_logic():
    print("Testing Backup Invalidation Logic...")
    manager = BackupManager()
    
    # helper
    def create_dummy_backup(date_str):
        return {
            "format_version": "2.0",
            "user_id": 12345,
            "exported_at": date_str,
            "context": {},
            "checksum": "dummy" # Will fail checksum, but we want to fail DATE first? 
            # Actually, checksum is checked BEFORE date in the current code?
            # Let's check the code order.
        }
    
    # Mocking _compute_checksum to bypass checksum error for this test?
    # Or just setting checksum to match.
    def mock_compute_checksum(data):
        # Determine what compute_checksum expects
        # It expects user_id + exported_at + context
        return manager._compute_checksum(data)

    # 1. Test OLD Backup (Should Fail)
    old_date = "2026-02-01T12:00:00"
    backup_old = create_dummy_backup(old_date)
    backup_old["checksum"] = mock_compute_checksum(backup_old)
    
    is_valid, reason = manager.verify_backup(backup_old)
    print(f"Old Backup ({old_date}): Valid={is_valid}, Reason='{reason}'")
    
    if is_valid:
        print("FAIL: Old backup was accepted!")
        sys.exit(1)
    if "Backup too old" not in reason:
        print(f"FAIL: Wrong rejection reason. Expected 'Backup too old', got '{reason}'")
        sys.exit(1)
        
    # 2. Test NEW Backup (Should Pass Date check, maybe fail checksum/other if I messed up mock)
    new_date = "2026-02-05T12:00:00"
    backup_new = create_dummy_backup(new_date)
    backup_new["checksum"] = mock_compute_checksum(backup_new)
    
    is_valid, reason = manager.verify_backup(backup_new)
    print(f"New Backup ({new_date}): Valid={is_valid}, Reason='{reason}'")
    
    if not is_valid:
        print(f"FAIL: New backup was rejected! Reason: {reason}")
        # Note: If checksum fails, investigate why mock didn't work.
        sys.exit(1)
        
    print("\nSUCCESS: Invalidation Logic Verified.")
    assert True  # Execution completed without error

if __name__ == "__main__":
    test_invalidation_logic()
