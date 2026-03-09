#!/usr/bin/env python3
"""
Salt Rotation Utility - Invalidates ALL previous backups cryptographically.

Usage:
    python src/security/rotate_salt.py [--confirm]

WARNING: This will permanently invalidate all existing user backups.
They will fail checksum validation and cannot be restored.
This is the intended behavior for security resets.
"""
import secrets
import sys
from pathlib import Path

def rotate_salt(confirm=False):
    """Generate new salt, invalidating all old backups."""
    salt_file = Path("memory/core/shard_salt.secret")
    
    if not confirm:
        print("⚠️  WARNING: Salt rotation will PERMANENTLY INVALIDATE all existing backups!")
        print("   - All user backups will fail checksum validation")
        print("   - Users cannot restore old context")
        print("   - This is cryptographically irreversible")
        print()
        response = input("Type 'ROTATE' to confirm: ")
        if response != "ROTATE":
            print("❌ Aborted.")
            return False
    
    # Backup old salt for audit trail
    if salt_file.exists():
        old_salt = salt_file.read_text().strip()
        backup_file = Path(f"memory/core/shard_salt.{old_salt[:8]}.old")
        backup_file.write_text(old_salt)
        print(f"📁 Old salt backed up to: {backup_file}")
    
    # Generate new salt
    new_salt = secrets.token_hex(32)
    salt_file.parent.mkdir(parents=True, exist_ok=True)
    salt_file.write_text(new_salt)
    
    print(f"✅ Salt rotated successfully")
    print(f"   New salt: {new_salt[:16]}...")
    print(f"   ALL previous backups are now invalid")
    return True

if __name__ == "__main__":
    confirm = "--confirm" in sys.argv
    rotate_salt(confirm=confirm)
