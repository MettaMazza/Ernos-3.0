"""
Backup Manager - Coordinator for backup operations.
Delegates to focused submodules for specific functionality.
"""
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

from .verify import BackupVerifier
from .export import BackupExporter
from .restore import BackupRestorer
from src.core.data_paths import data_dir

logger = logging.getLogger("Backup.Manager")


class BackupManager:
    """
    Manages system backups and user context exports.
    
    - Daily 2pm backup: Full system backup (internal only)
    - Cycle reset export: User context sent via DM (once per 24hrs)
    - Retention: Only last 7 days of daily backups kept
    - Verification: SHA-256 checksum for authenticity
    """
    
    BACKUP_DIR = data_dir() / "backups"
    DAILY_DIR = BACKUP_DIR / "daily"
    RETENTION_DAYS = 7
    FORMAT_VERSION = "3.0"
    
    def __init__(self, bot=None):
        self.bot = bot
        self._verifier = BackupVerifier()
        self._exporter = BackupExporter(bot)
        self._restorer = BackupRestorer(bot)
    
    # --- Compatibility shim for tests ---
    
    def _compute_checksum(self, data: dict) -> str:
        """Compatibility: delegates to verifier."""
        return self._verifier.compute_checksum(data)
    
    @property
    def _salt(self):
        """Compatibility: delegates to verifier."""
        return self._verifier._salt
    
    @_salt.setter
    def _salt(self, value):
        """Compatibility: delegates to verifier."""
        self._verifier._salt = value
    
    # --- Verification (delegated) ---
    
    def verify_backup(self, data: dict) -> Tuple[bool, str]:
        """Verify a backup is authentic and unmodified."""
        return self._verifier.verify_backup(data)
    
    # --- Export Operations (delegated) ---
    
    async def export_user_context(self, user_id: int, force: bool = False) -> Optional[Path]:
        """Export user's FULL context to JSON."""
        return await self._exporter.export_user_context(user_id, force)
    
    async def send_user_backup_dm(self, user_id: int, force: bool = False) -> bool:
        """Export user context and send via DM."""
        return await self._exporter.send_user_backup_dm(user_id, force)
    
    async def export_all_users_on_reset(self) -> int:
        """Export context for all users before cycle reset."""
        return await self._exporter.export_all_users_on_reset()
    
    async def export_master_backup(self) -> Optional[Path]:
        """Export COMPLETE system backup for admin."""
        return await self._exporter.export_master_backup()
    
    # --- Import Operations (delegated) ---
    
    async def import_user_context(self, user_id: int, data: dict) -> Tuple[bool, str]:
        """Verify and restore user context from export."""
        return await self._restorer.import_user_context(user_id, data)
    
    # --- Maintenance Operations ---
    
    async def daily_backup(self) -> str:
        """
        Run daily backup at 2pm. Copies core and users directories.
        Cleans up backups older than 7 days.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_path = self.DAILY_DIR / timestamp
        
        try:
            backup_path.mkdir(parents=True, exist_ok=True)
            
            core_dir = data_dir() / "core"
            if core_dir.exists():
                shutil.copytree(core_dir, backup_path / "core", dirs_exist_ok=True)
                
            users_dir = data_dir() / "users"
            if users_dir.exists():
                shutil.copytree(users_dir, backup_path / "users", dirs_exist_ok=True)
                
            logger.info(f"Daily backup completed: {backup_path}")
            
            # Cleanup old backups
            await self._cleanup_old_backups()
            
            return f"Backup completed: {timestamp}"
            
        except Exception as e:
            logger.error(f"Daily backup failed: {e}")
            return f"Backup failed: {e}"
    
    async def _cleanup_old_backups(self):
        """Delete backups older than RETENTION_DAYS."""
        if not self.DAILY_DIR.exists():
            return
            
        cutoff = datetime.now() - timedelta(days=self.RETENTION_DAYS)
        
        for backup_folder in self.DAILY_DIR.iterdir():
            if not backup_folder.is_dir():
                continue
            try:
                folder_date = datetime.strptime(backup_folder.name[:10], "%Y-%m-%d")
                if folder_date < cutoff:
                    shutil.rmtree(backup_folder)
                    logger.info(f"Deleted old backup: {backup_folder.name}")
            except ValueError as e:
                logger.debug(f"Suppressed {type(e).__name__}: {e}")
                continue
