import os
import logging
from .registry import ToolRegistry
import json
from pathlib import Path
import datetime
from src.privacy.guard import validate_path_scope
from src.privacy.scopes import PrivacyScope

logger = logging.getLogger("Tools.Coding")

@ToolRegistry.register(name="create_program", description="Create or edit code files with surgical precision.")
def create_program(path: str, code: str, mode: str = "overwrite", target: str = "", user_id: str = None, request_scope: str = "PUBLIC") -> str:
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
        if user_id and user_id != "CORE":
            # User projects go to memory/users/{user_id}/projects/{scope}/
            base_dir = Path(f"memory/users/{user_id}/projects/{scope.name.lower()}")
        else:
            # CORE/autonomy writes — check merge gate
            try:
                from src.tools.weekly_quota import is_merge_allowed
                if not is_merge_allowed():
                    # Stage for Friday review instead of direct merge
                    base_dir = Path("memory/core/staging")
                    logger.info(f"Merge gate: staging {path} for Friday review")
                else:
                    base_dir = Path("memory/core/projects")
            except ImportError:
                base_dir = Path("memory/core/projects")
        
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
        
        # P2: Idempotency guard — skip overwrite if content is identical
        if mode == "overwrite" and safe_path.exists():
            import hashlib
            existing_hash = hashlib.md5(safe_path.read_bytes()).hexdigest()
            new_hash = hashlib.md5(code.encode()).hexdigest()
            if existing_hash == new_hash:
                return (f"File `{safe_path.relative_to(cwd)}` already exists with "
                        f"identical content. No changes needed.")

        # Execute surgical edit
        success, message = surgical_edit(str(safe_path), mode, code, target)
        
        if not success:
            return message
            
        # Log Provenance
        from src.security.provenance import ProvenanceManager
        checksum = ProvenanceManager.log_artifact(str(safe_path), "code", {"scope": request_scope, "user_id": user_id, "mode": mode})
            
        return f"Successfully applied '{mode}' to `{safe_path.relative_to(cwd)}` (HMAC: {checksum[:8]})."
    except Exception as e:
        return f"Write Error: {e}"

@ToolRegistry.register(name="manage_project", description="Manage project manifest.")
def manage_project(action: str, key: str = None, value: str = None) -> str:
    """
    CRUD for memory/project_manifest.json
    Actions: init, set, get, list
    """
    manifest_path = Path("memory/project_manifest.json")
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
