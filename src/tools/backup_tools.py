"""
Backup Tools - User-facing tools for backup management.
"""
import json
import logging
from src.tools.registry import ToolRegistry
from src.backup.manager import BackupManager

logger = logging.getLogger("Tools.Backup")


@ToolRegistry.register(
    name="request_my_backup",
    description="Request a backup of your conversation context. Sent to your DM."
)
async def request_my_backup(user_id: int = None) -> str:
    """
    User requests their own data export.
    Rate limited to once per 24 hours.
    """
    if not user_id:
        return "❌ Error: User ID required."
        
    backup_mgr = BackupManager()
    export_path = await backup_mgr.export_user_context(user_id)
    
    if export_path:
        return f"📦 Your context has been exported. Check your DMs for the backup file."
    else:
        return "⏳ Backup rate limited. You can only request a backup once every 24 hours."


@ToolRegistry.register(
    name="verify_backup",
    description="Verify a backup file is authentic and unmodified."
)
async def verify_backup(backup_json: str = None) -> str:
    """
    Ernos verifies a backup is real before restoring.
    Checks SHA-256 checksum.
    """
    if not backup_json:
        return "❌ Error: Backup data required."
        
    try:
        data = json.loads(backup_json)
    except json.JSONDecodeError:
        return "❌ Error: Invalid backup format. Must be valid JSON."
        
    backup_mgr = BackupManager()
    is_valid, reason = backup_mgr.verify_backup(data)
    
    if is_valid:
        file_count = data.get("file_count", len(data.get("context", {})))
        exported_at = data.get("exported_at", "unknown")
        user_id = data.get("user_id", "unknown")
        return f"✅ **Backup Verified**\n- User ID: {user_id}\n- Exported: {exported_at}\n- Files: {file_count}\n- {reason}"
    else:
        return f"❌ **Backup Invalid**\n{reason}"


@ToolRegistry.register(
    name="restore_my_context",
    description="Restore your conversation context from a previous backup."
)
async def restore_my_context(user_id: int = None, backup_json: str = None) -> str:
    """
    User re-imports their context from a backup.
    Ernos verifies the checksum and unpacks into correct categories.
    
    SECURITY: Only allows import for matching user_id.
    """
    if not user_id or not backup_json:
        return "❌ Error: User ID and backup data required."
        
    try:
        data = json.loads(backup_json)
    except json.JSONDecodeError:
        return "❌ Error: Invalid backup format. Must be valid JSON."
    
    # Import globals to get bot reference for hippocampus access
    from src.bot import globals
    backup_mgr = BackupManager(globals.bot)  # CRITICAL: Pass bot so hippocampus is accessible
    
    # Verify and restore in one call
    success, message = await backup_mgr.import_user_context(user_id, data)
    
    if success:
        return f"📦 {message}\nYour context has been restored. I now remember our previous conversations."
    else:
        logger.warning(f"Restore failed for user {user_id}: {message}")
        return message

