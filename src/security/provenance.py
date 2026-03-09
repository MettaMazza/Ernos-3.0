import os
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union, Dict, Any

logger = logging.getLogger("Security.Provenance")


class ProvenanceManager:
    """
    Manages cryptographic provenance (Anti-Gaslighting) for all system artifacts.
    Maintains a ledger of all generated files with HMAC-SHA256 signatures.
    """
    
    SALT_FILE = Path("memory/core/shard_salt.secret")
    LEDGER_FILE = Path("memory/core/provenance_ledger.jsonl")
    
    _salt_cache = None

    @classmethod
    def get_salt(cls) -> str:
        """Get or create the master provenance salt."""
        if cls._salt_cache:
            return cls._salt_cache
            
        if cls.SALT_FILE.exists():
            cls._salt_cache = cls.SALT_FILE.read_text().strip()
            return cls._salt_cache
            
        # Generate new salt if missing (Should match BackupManager's logic if file shared)
        # Note: BackupManager uses same path.
        import secrets
        salt = secrets.token_hex(32)
        cls.SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls.SALT_FILE.write_text(salt)
        cls._salt_cache = salt
        return salt

    @classmethod
    def get_salt_rotation_date(cls) -> str:
        """Get human-readable date when salt was last rotated."""
        import os
        if not cls.SALT_FILE.exists():
            return "NEVER"
        try:
            stat = os.stat(cls.SALT_FILE)
            from datetime import datetime
            return datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "UNKNOWN"

    @classmethod
    def compute_checksum(cls, data: bytes) -> str:
        """Compute HMAC-SHA256 checksum for data bytes."""
        salt = cls.get_salt()
        return hmac.new(
            salt.encode('utf-8'),
            data,
            hashlib.sha256
        ).hexdigest()

    @classmethod
    def sign_file(cls, file_path: str) -> str:
        """
        Compute checksum for a file on disk.
        Returns the hex checksum.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Cannot sign missing file: {file_path}")
            
        data = path.read_bytes()
        return cls.compute_checksum(data)

    @classmethod
    def log_artifact(cls, file_path: str, artifact_type: str, metadata: dict = None):
        """
        Log an artifact to the immutable ledger.
        """
        try:
            checksum = cls.sign_file(file_path)
            
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "file_path": str(file_path),
                "filename": Path(file_path).name,
                "type": artifact_type,
                "checksum": checksum,
                "metadata": metadata or {}
            }
            
            # Atomic append (using 'a' mode is atomic on POSIX for small writes, good enough here)
            cls.LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(cls.LEDGER_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
                
            logger.info(f"Provenance Logged: {Path(file_path).name} [{artifact_type}]")
            return checksum
            
        except Exception as e:
            logger.error(f"Failed to log provenance for {file_path}: {e}")
            raise

    @classmethod
    def verify_file(cls, file_path: str, expected_checksum: str = None) -> bool:
        """
        Verify a file against the system salt.
        If expected_checksum is provided, verify against it.
        Otherwise, (Optionally) check if it exists in ledger? 
        Function primarily returns current checksum for comparison.
        """
        current_hash = cls.sign_file(file_path)
        if expected_checksum:
            return hmac.compare_digest(current_hash, expected_checksum)
        return True # Just successfully computed logic

    @classmethod
    def is_tracked(cls, checksum: str) -> bool:
        """
        Check if a checksum exists in the ledger.
        Warning: O(N) scan. Optimization needed for large ledgers.
        """
        if not cls.LEDGER_FILE.exists():
            return False
            
        try:
            with open(cls.LEDGER_FILE, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("checksum") == checksum:
                            return True
                    except Exception:
                        continue
        except Exception:
            return False
        return False

    @classmethod
    def lookup_by_checksum(cls, checksum: str) -> Optional[Dict]:
        """
        Look up artifact metadata by checksum.
        Returns full provenance record if found:
        {timestamp, file_path, filename, type, checksum, metadata}
        
        This allows Ernos to identify any artifact it created.
        """
        if not cls.LEDGER_FILE.exists():
            return None
            
        try:
            with open(cls.LEDGER_FILE, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("checksum") == checksum:
                            return entry
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Provenance lookup failed: {e}")
        return None

    @classmethod
    def lookup_by_file(cls, file_path: str) -> Optional[Dict]:
        """
        Compute checksum of a file and look up its provenance.
        Returns full metadata if this file was created by Ernos.
        """
        try:
            checksum = cls.sign_file(file_path)
            return cls.lookup_by_checksum(checksum)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"File lookup failed: {e}")
            return None

    @classmethod
    def get_artifact_info(cls, file_path: str) -> str:
        """
        Human-readable provenance summary for a file.
        Returns a formatted string Ernos can include in responses.
        """
        record = cls.lookup_by_file(file_path)
        if not record:
            return "Unknown artifact (not in provenance ledger)"
        
        meta = record.get("metadata", {})
        return (
            f"**Provenance Verified**\n"
            f"- Created: {record.get('timestamp', 'Unknown')}\n"
            f"- Type: {record.get('type', 'Unknown')}\n"
            f"- User: {meta.get('user_id', 'Unknown')}\n"
            f"- Scope: {meta.get('scope', 'Unknown')}\n"
            f"- Checksum: {record.get('checksum', 'Unknown')[:16]}..."
        )
