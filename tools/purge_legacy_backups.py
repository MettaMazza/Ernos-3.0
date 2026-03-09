import os
import sys
import shutil
import json
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from backup.manager import BackupManager

def purge_legacy_backups():
    """
    Purges all backups (Daily and User Exports) created before BackupManager.MIN_COMPATIBLE_DATE.
    """
    manager = BackupManager()
    min_date = manager.MIN_COMPATIBLE_DATE
    print(f"Purging backups older than {min_date.date()}...")
    
    deleted_count = 0
    kept_count = 0
    
    # 1. Purge Daily Backups (Folders in memory/backups/daily)
    daily_dir = manager.DAILY_DIR
    if daily_dir.exists():
        print(f"\nScanning Daily Backups in {daily_dir}...")
        for backup_folder in daily_dir.iterdir():
            if not backup_folder.is_dir():
                continue
            try:
                # Folder name format: YYYY-MM-DD_HH-MM
                folder_date = datetime.strptime(backup_folder.name[:10], "%Y-%m-%d")
                if folder_date.date() < min_date.date():
                    print(f"DELETING Daily Backup: {backup_folder.name}")
                    shutil.rmtree(backup_folder)
                    deleted_count += 1
                else:
                    # print(f"KEEPING Daily Backup: {backup_folder.name}")
                    kept_count += 1
            except ValueError:
                print(f"Skipping non-timestamp folder: {backup_folder.name}")
                
    # 2. Purge User Exports (Files in memory/backups/user_exports/{user_id}/*.json)
    export_dir = manager.EXPORT_DIR
    if export_dir.exists():
        print(f"\nScanning User Exports in {export_dir}...")
        for user_folder in export_dir.iterdir():
            if not user_folder.is_dir():
                continue
            
            for export_file in user_folder.glob("*.json"):
                try:
                    # Method A: Check filename if it's YYYY-MM-DD.json
                    try:
                        file_date = datetime.strptime(export_file.stem, "%Y-%m-%d")
                        if file_date.date() < min_date.date():
                            print(f"DELETING Export (Name): {export_file.parent.name}/{export_file.name}")
                            os.remove(export_file)
                            deleted_count += 1
                            continue
                    except ValueError:
                        pass # Filename might be different, check content
                    
                    # Method B: Check 'exported_at' in JSON
                    with open(export_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    exported_at_str = data.get("exported_at")
                    if not exported_at_str:
                        continue
                        
                    exported_dt = datetime.fromisoformat(exported_at_str)
                    if exported_dt.date() < min_date.date():
                        print(f"DELETING Export (Content): {export_file.parent.name}/{export_file.name}")
                        os.remove(export_file)
                        deleted_count += 1
                    else:
                        kept_count += 1
                        
                except Exception as e:
                    print(f"Error checking {export_file}: {e}")

    print(f"\nPurge Complete.")
    print(f"Deleted: {deleted_count}")
    print(f"Kept: {kept_count}")

if __name__ == "__main__":
    purge_legacy_backups()
