"""
Backup Export - Handles all export operations.
"""
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Dict

from .verify import BackupVerifier
from src.privacy.scopes import ScopeManager
from src.core.data_paths import data_dir

logger = logging.getLogger("Backup.Export")

try:
    import discord
except ImportError:
    discord = None


class BackupExporter:
    """Handles user context and master backup exports."""
    
    BACKUP_DIR = data_dir() / "backups"
    EXPORT_DIR = BACKUP_DIR / "user_exports"
    RATE_LIMIT_FILE = BACKUP_DIR / "rate_limits.json"
    EXPORT_COOLDOWN_HOURS = 24
    
    def __init__(self, bot=None):
        self.bot = bot
        self._last_export: Dict[int, datetime] = self._load_rate_limits()
        self._verifier = BackupVerifier()
    
    def _load_rate_limits(self) -> Dict[int, datetime]:
        """Load rate limits from persistent storage."""
        if self.RATE_LIMIT_FILE.exists():
            try:
                with open(self.RATE_LIMIT_FILE, "r") as f:
                    data = json.load(f)
                return {int(k): datetime.fromisoformat(v) for k, v in data.items()}
            except Exception as e:
                logger.warning(f"Failed to load rate limits: {e}")
        return {}
    
    def _save_rate_limits(self):
        """Save rate limits to persistent storage."""
        try:
            self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.RATE_LIMIT_FILE, "w") as f:
                json.dump({str(k): v.isoformat() for k, v in self._last_export.items()}, f)
        except Exception as e:
            logger.warning(f"Failed to save rate limits: {e}")
    
    async def export_user_context(self, user_id: int, force: bool = False) -> Optional[Path]:
        """
        Export user's FULL context to JSON for DM delivery.
        Rate limited to once per 24 hours (unless force=True).
        """
        # Check rate limit
        if not force:
            last = self._last_export.get(user_id)
            if last and (datetime.now() - last).total_seconds() < self.EXPORT_COOLDOWN_HOURS * 3600:
                logger.info(f"User {user_id} export rate limited")
                return None
            
        user_silo = ScopeManager.get_user_home(user_id)
        # get_user_home auto-creates the dir, so check if it has any files
        if not any(user_silo.rglob("*")):
            logger.warning(f"No silo content for user {user_id} at {user_silo}")
            return None
            
        export_data = {
            "user_id": user_id,
            "exported_at": datetime.now().isoformat(),
            "format_version": self._verifier.FORMAT_VERSION,
            "context": {},
            "traces": {},
            "knowledge_graph": [],
            "public_timeline": {}
        }
        
        total_files = 0
        
        # Gather user silo files
        for file_path in user_silo.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(user_silo)
                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    export_data["context"][str(rel_path)] = content
                    total_files += 1
                except Exception as e:
                    export_data["context"][str(rel_path)] = f"[Read Error: {e}]"
        
        # Gather traces
        traces_dir = data_dir() / "traces"
        if traces_dir.exists():
            user_str = str(user_id)
            for trace_file in traces_dir.rglob("*"):
                if trace_file.is_file() and user_str in trace_file.name:
                    try:
                        content = trace_file.read_text(encoding="utf-8", errors="replace")
                        export_data["traces"][trace_file.name] = content
                        total_files += 1
                    except Exception as e:
                        export_data["traces"][trace_file.name] = f"[Read Error: {e}]"
        
        # Gather public timeline
        public_silo = data_dir() / "public/users" / str(user_id)
        if public_silo.exists():
            for file_path in public_silo.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(public_silo)
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        export_data["public_timeline"][str(rel_path)] = content
                        total_files += 1
                    except Exception as e:
                        export_data["public_timeline"][str(rel_path)] = f"[Read Error: {e}]"
        
        # Export KG nodes
        try:
            from src.memory.graph import KnowledgeGraph
            kg = KnowledgeGraph()
            with kg.driver.session() as session:
                result = session.run(
                    "MATCH (n {user_id: $uid}) RETURN n.name as name, labels(n) as labels, properties(n) as props",
                    uid=user_id
                )
                for record in result:
                    export_data["knowledge_graph"].append({
                        "name": record["name"],
                        "labels": record["labels"],
                        "properties": record["props"]
                    })
            kg.close()
        except Exception as e:
            logger.warning(f"KG export skipped: {e}")
        
        # Add checksum
        export_data["checksum"] = self._verifier.compute_checksum(export_data)
        export_data["file_count"] = total_files
        export_data["kg_node_count"] = len(export_data["knowledge_graph"])
        
        # Write export
        export_path = self.EXPORT_DIR / str(user_id) / f"{date.today()}.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(export_data, indent=2, ensure_ascii=False))
        
        # Update rate limits
        self._last_export[user_id] = datetime.now()
        self._save_rate_limits()
        
        logger.info(f"User {user_id} context exported: {export_path}")
        return export_path
    
    async def send_user_backup_dm(self, user_id: int, force: bool = False) -> bool:
        """Export user context and send via DM."""
        if not self.bot:
            logger.error("No bot reference for DM delivery")
            return False
            
        export_path = await self.export_user_context(user_id, force=force)
        if not export_path:
            return False
            
        try:
            user = await self.bot.fetch_user(user_id)
            if user:
                dm = await user.create_dm()
                await dm.send(
                    "Your context has been exported. To restore, send this file and say 'restore my context'.",
                    file=discord.File(export_path)
                )
                logger.info(f"Backup sent to user {user_id}")
                export_path.unlink()
                return True
        except Exception as e:
            logger.error(f"Failed to send backup DM: {e}")
            
        return False
    
    async def export_all_users_on_reset(self) -> int:
        """Export context for all users before cycle reset."""
        users_dir = data_dir() / "users"
        if not users_dir.exists():
            return 0
            
        backed_up = 0
        for user_folder in users_dir.iterdir():
            if not user_folder.is_dir():
                continue
            try:
                user_id = int(user_folder.name)
                if await self.send_user_backup_dm(user_id, force=True):
                    backed_up += 1
            except ValueError as e:
                logger.debug(f"Suppressed {type(e).__name__}: {e}")
                continue
                
        logger.info(f"Pre-reset backup complete: {backed_up} users")
        return backed_up
    
    async def export_master_backup(self) -> Optional[Path]:
        """Export COMPLETE system backup for admin."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        export_data = {
            "type": "master_backup",
            "format_version": self._verifier.FORMAT_VERSION,
            "exported_at": datetime.now().isoformat(),
            "all_users": {},
            "core": {},
            "public": {},
            "traces": {},
            "knowledge_graph": [],
            "system_files": {}
        }
        
        total_files = 0
        
        # Export all user silos
        users_dir = data_dir() / "users"
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.is_dir():
                    user_id = user_dir.name
                    export_data["all_users"][user_id] = {}
                    for file_path in user_dir.rglob("*"):
                        if file_path.is_file():
                            rel_path = file_path.relative_to(user_dir)
                            try:
                                content = file_path.read_text(encoding="utf-8", errors="replace")
                                export_data["all_users"][user_id][str(rel_path)] = content
                                total_files += 1
                            except Exception as e:
                                export_data["all_users"][user_id][str(rel_path)] = f"[Read Error: {e}]"
        
        # Export core, public, traces, system files
        for dir_name, key in [("memory/core", "core"), ("memory/public", "public"), ("memory/traces", "traces")]:
            dir_path = Path(dir_name)
            if dir_path.exists():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(dir_path) if key != "traces" else file_path.name
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="replace")
                            export_data[key][str(rel_path)] = content
                            total_files += 1
                        except Exception as e:
                            export_data[key][str(rel_path)] = f"[Read Error: {e}]"
        
        # Export system files
        for sf in ["memory/goals.json", "memory/project_manifest.json", "memory/usage.json"]:
            sf_path = Path(sf)
            if sf_path.exists():
                try:
                    export_data["system_files"][sf] = sf_path.read_text(encoding="utf-8")
                    total_files += 1
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")
        
        # Export KG
        try:
            from src.memory.graph import KnowledgeGraph
            kg = KnowledgeGraph()
            with kg.driver.session() as session:
                result = session.run("MATCH (n) RETURN n LIMIT 10000")
                for record in result:
                    node = record["n"]
                    export_data["knowledge_graph"].append({
                        "labels": list(node.labels),
                        "name": node.get("name"),
                        "properties": dict(node)
                    })
            kg.close()
        except Exception as e:
            logger.warning(f"KG export failed: {e}")
        
        export_data["total_files"] = total_files
        export_data["kg_node_count"] = len(export_data["knowledge_graph"])
        export_data["user_count"] = len(export_data["all_users"])
        
        master_str = json.dumps(export_data, sort_keys=True, ensure_ascii=False)
        export_data["checksum"] = hashlib.sha256(master_str.encode("utf-8")).hexdigest()
        
        self.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_path = self.EXPORT_DIR / f"master_backup_{timestamp}.json"
        
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Master backup exported: {export_path}")
        return export_path
