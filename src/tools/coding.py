import os
import logging
import time
from .registry import ToolRegistry
import json
from pathlib import Path
import datetime
from src.privacy.guard import validate_path_scope
from src.privacy.scopes import PrivacyScope
from src.core.data_paths import data_dir

logger = logging.getLogger("Tools.Coding")

# ─── Operation Ledger ─────────────────────────────────────────────
# Tracks per-file edit history so the LLM can see its own patterns
# and self-regulate instead of retrying endlessly.
_LEDGER_PATH = data_dir() / "core/staging/operation_ledger.json"


def _load_ledger() -> dict:
    """Load or init the operation ledger. Auto-expire entries older than 1 hour."""
    if _LEDGER_PATH.exists():
        try:
            data = json.loads(_LEDGER_PATH.read_text())
            now = time.time()
            data["files"] = {
                k: v for k, v in data.get("files", {}).items()
                if now - v.get("last_edit_ts", 0) < 3600
            }
            return data
        except Exception:
            pass
    return {"files": {}, "session_ops": 0}


def _save_ledger(ledger: dict):
    """Persist operation ledger to disk."""
    _LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LEDGER_PATH.write_text(json.dumps(ledger, indent=2, default=str))


def _log_operation_to_quota(path: str, mode: str, success: bool):
    """Log a create_program operation to the weekly quota daily state."""
    try:
        from src.tools.weekly_quota import _load_week, _save_week, _day_name, WORK_DAYS
        today = _day_name()
        if today in WORK_DAYS:
            state = _load_week()
            day_data = state["days"][today]
            if "operations" not in day_data:
                day_data["operations"] = []
            day_data["operations"].append({
                "tool": "create_program",
                "file": path,
                "mode": mode,
                "success": success,
                "timestamp": str(datetime.datetime.now()),
            })
            _save_week(state)
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"Failed to log operation to quota: {e}")


@ToolRegistry.register(name="create_program", description="Create or edit code files with surgical precision.")
def create_program(path: str, code: str, mode: str = "overwrite", target: str = "", user_id: str = None, request_scope: str = "PUBLIC", intention: str = None) -> str:
    """
    Writes code to a user-scoped project file path with scope validation.
    
    Modes (Surgical Editing):
    - 'overwrite': Replace entire file (default for backwards compatibility).
    - 'append': Add code to end of file.
    - 'replace': Find `target` string, replace with `code`.
    - 'replace_all': Replace ALL occurrences of `target` with `code`.
    - 'delete': Remove lines containing `target`.
    - 'insert_after': Insert `code` after line containing `target`.
    - 'insert_before': Insert `code` before line containing `target`.
    - 'regex_replace': Use regex pattern `target`, replace with `code`.
    """
    try:
        from src.tools.file_utils import surgical_edit, VALID_MODES
        
        if mode not in VALID_MODES:
            return f"Error: Invalid mode '{mode}'. Valid: {', '.join(VALID_MODES)}"
        
        # Determine scope
        try:
            scope = PrivacyScope[request_scope.upper()]
        except Exception:
            scope = PrivacyScope.PUBLIC
        
        # Route to user-scoped project directory
        is_core = not user_id or user_id == "CORE"
        if not is_core:
            # User projects go to memory/users/{user_id}/projects/{scope}/
            base_dir = Path(str(data_dir()) + f"/users/{user_id}/projects/{scope.name.lower()}")
        else:
            # CORE/autonomy writes — check merge gate
            try:
                from src.tools.weekly_quota import is_merge_allowed
                if not is_merge_allowed():
                    # Stage for Friday review instead of direct merge
                    base_dir = data_dir() / "core/staging"
                    logger.info(f"Merge gate: staging {path} for Friday review")
                else:
                    base_dir = data_dir() / "core/projects"
            except ImportError:
                base_dir = data_dir() / "core/projects"
        
        # Flatten the path for security (prevent traversal)
        filename = Path(path).name
        if not filename:
            return "Error: Invalid filename."
        
        safe_path = (base_dir / filename).resolve()
        
        # Ensure we're still within the project
        cwd = Path(os.getcwd()).resolve()
        if not str(safe_path).startswith(str(cwd)):
            return "Error: Path must be within the project directory."
        
        # Create directory structure
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        
        # ─── Idempotency guard (BEFORE manifest write) ───────────
        # Skip overwrite if content is identical — don't pollute manifest/ledger
        if mode == "overwrite" and safe_path.exists():
            import hashlib
            existing_hash = hashlib.md5(safe_path.read_bytes()).hexdigest()
            new_hash = hashlib.md5(code.encode()).hexdigest()
            if existing_hash == new_hash:
                return (f"File `{safe_path.relative_to(cwd)}` already exists with "
                        f"identical content. No changes needed.")

        # ─── Load operation ledger ────────────────────────────────
        ledger = _load_ledger()
        file_key = filename
        file_record = ledger["files"].get(file_key, {
            "edit_count": 0,
            "fail_count": 0,
            "modes_tried": [],
            "last_error": None,
            "last_edit_ts": 0,
        })

        # ─── Execute surgical edit ────────────────────────────────
        success, message = surgical_edit(str(safe_path), mode, code, target)
        
        # ─── Update operation ledger ──────────────────────────────
        file_record["edit_count"] += 1
        file_record["last_edit_ts"] = time.time()
        file_record["modes_tried"].append(mode)
        # Keep only last 10 modes to prevent unbounded growth
        file_record["modes_tried"] = file_record["modes_tried"][-10:]
        ledger["session_ops"] += 1

        if not success:
            file_record["fail_count"] += 1
            file_record["last_error"] = message
            ledger["files"][file_key] = file_record
            _save_ledger(ledger)
            
            # Log operation to quota (even failures — they count as work)
            if is_core:
                _log_operation_to_quota(path, mode, success=False)
            
            # Return structured feedback with edit history
            history_note = ""
            if file_record["fail_count"] >= 3:
                recent_modes = ", ".join(file_record["modes_tried"][-5:])
                history_note = (
                    f"\n⚠️ EDIT HISTORY: `{file_key}` has been edited "
                    f"{file_record['edit_count']} times this session with "
                    f"{file_record['fail_count']} consecutive failures. "
                    f"Modes tried: {recent_modes}. "
                    f"Consider using mode='overwrite' with the complete correct "
                    f"file content, or move to a different file."
                )
            return message + history_note

        # ─── Success path ─────────────────────────────────────────
        file_record["fail_count"] = 0  # Reset fail streak on success
        file_record["last_error"] = None
        ledger["files"][file_key] = file_record
        _save_ledger(ledger)

        # Log operation to quota
        if is_core:
            _log_operation_to_quota(path, mode, success=True)

        # ─── Update staging manifest (dict-based, not blind list) ─
        if is_core:
            try:
                from src.tools.weekly_quota import is_merge_allowed
                if not is_merge_allowed():
                    manifest_path = base_dir / "staging_manifest.json"
                    manifest = {}
                    if manifest_path.exists():
                        raw = json.loads(manifest_path.read_text())
                        # Migration: handle old list format
                        if isinstance(raw, list):
                            manifest = {}
                            for entry in raw:
                                key = entry.get("staged_as") or Path(
                                    entry.get("intended_path", "")
                                ).name
                                if key:
                                    manifest[key] = entry
                        else:
                            manifest = raw

                    manifest[filename] = {
                        "intended_path": path,
                        "staged_as": filename,
                        "mode": mode,
                        "target": target if target else None,
                        "staged_at": str(datetime.datetime.now()),
                        "edit_count": manifest.get(filename, {}).get(
                            "edit_count", 0
                        ) + 1,
                    }

                    base_dir.mkdir(parents=True, exist_ok=True)
                    manifest_path.write_text(json.dumps(manifest, indent=2))
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"Failed to update staging manifest: {e}")

        # Log Provenance
        from src.security.provenance import ProvenanceManager
        checksum = ProvenanceManager.log_artifact(
            str(safe_path), "code",
            {"scope": request_scope, "user_id": user_id, "mode": mode, "intention": intention}
        )
        
        # Include intended path in response so the bot knows where it will land
        intended_note = ""
        if is_core:
            try:
                from src.tools.weekly_quota import is_merge_allowed
                if not is_merge_allowed():
                    intended_note = f" (intended: {path})"
            except ImportError:
                pass
            
        return f"Successfully applied '{mode}' to `{safe_path.relative_to(cwd)}`{intended_note} (HMAC: {checksum[:8]})."
    except Exception as e:
        return f"Write Error: {e}"

@ToolRegistry.register(name="manage_project", description="Manage project manifest.")
def manage_project(action: str, key: str = None, value: str = None) -> str:
    """
    CRUD for memory/project_manifest.json
    Actions: init, set, get, list
    """
    manifest_path = data_dir() / "project_manifest.json"
    try:
        data = {}
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text())
            
        if action == "init":
            data = {"name": key or "Unnamed Project", "created": str(datetime.datetime.now()), "files": []}
            manifest_path.write_text(json.dumps(data, indent=2))
            return "Project manifest initialized."
            
        elif action == "set":
            if not key: return "Error: Key required."
            data[key] = value
            manifest_path.write_text(json.dumps(data, indent=2))
            return f"Set {key} = {value}"
            
        elif action == "get":
            return f"{key}: {data.get(key, 'Not found')}"
            
        elif action == "list":
            return json.dumps(data, indent=2)
            
        return f"Unknown action: {action}"
    except Exception as e:
        return f"Project Manager Error: {e}"
