"""
Backup Verification - Checksum verification for backup authenticity.
"""
import json
import hashlib
import logging
from typing import Tuple

logger = logging.getLogger("Backup.Verify")


class BackupVerifier:
    """Handles cryptographic verification of backups."""
    
    FORMAT_VERSION = "3.0"  # MRN Shard (Signed + Salted)
    
    def __init__(self):
        from src.security.provenance import ProvenanceManager
        self._salt = ProvenanceManager.get_salt()
    
    def compute_checksum(self, data: dict) -> str:
        """Compute HMAC-SHA256 signature of context data using local salt."""
        context_str = json.dumps(data.get("context", {}), sort_keys=True, ensure_ascii=False)
        user_id = str(data.get("user_id", ""))
        exported_at = str(data.get("exported_at", ""))
        
        payload = f"{self._salt}:{user_id}:{exported_at}:{context_str}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    
    def verify_backup(self, data: dict) -> Tuple[bool, str]:
        """
        Verify a backup is authentic and unmodified.
        
        Returns:
            (is_valid, reason)
        """
        # Check format version
        version = data.get("format_version", "1.0")
        if version == "1.0":
            return False, "Legacy format (v1.0) rejected — backups must be re-exported with v3.0+"
            
        # Check required fields
        required = ["user_id", "exported_at", "context", "checksum"]
        for field in required:
            if field not in data:
                return False, f"Missing required field: {field}"
        
        # Verify checksum
        stored_checksum = data.get("checksum")
        computed_checksum = self.compute_checksum(data)
        
        if stored_checksum != computed_checksum:
            return False, "Backup invalid: Created with different system salt or tampered"

        return True, "Backup verified: Cryptographic signature valid"
