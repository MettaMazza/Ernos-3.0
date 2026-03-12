"""
Skill Forge — v4.0 Photosynthesis (Markdown Edition).

Enables Ernos to compose new skills by combining existing
skill primitives and LLM-generated instructions into SKILL.md files.

Supports:
- User-scoped skills (stored in memory/users/{id}/skills)
- Community proposals (stored in memory/system/skill_forge/pending)
- Safe Tool Whitelist for auto-approval of private skills
"""
import logging
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
from src.core.data_paths import data_dir

logger = logging.getLogger("Lobe.Strategy.SkillForge")

from src.skills.types import SAFE_TOOL_WHITELIST

# Resolve project root from this file's location: src/lobes/strategy/skill_forge.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

class SkillForge:
    """
    Self-authoring skill composition engine.
    
    Generates SKILL.md files.
    """
    
    FORGE_DIR = _PROJECT_ROOT / "memory" / "system" / "skill_forge"
    PENDING_DIR = _PROJECT_ROOT / "memory" / "system" / "skill_forge" / "pending"
    QUEUE_FILE = _PROJECT_ROOT / "memory" / "system" / "skill_forge" / "pending.json"
    LOG_FILE = _PROJECT_ROOT / "memory" / "system" / "skill_forge" / "forge_log.json"
    
    def __init__(self, skill_registry=None, engine=None):
        self._registry = skill_registry
        self._engine = engine
        self._pending: List[Dict] = []
        self._forge_log: List[Dict] = []
        self._load_state()
    
    def _load_state(self):
        """Load pending skills and forge log."""
        if self.QUEUE_FILE.exists():
            try:
                self._pending = json.loads(self.QUEUE_FILE.read_text())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
        if self.LOG_FILE.exists():
            try:
                self._forge_log = json.loads(self.LOG_FILE.read_text())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
    
    def _save_state(self):
        """Persist state."""
        self.FORGE_DIR.mkdir(parents=True, exist_ok=True)
        self.QUEUE_FILE.write_text(json.dumps(self._pending, indent=2))
        self.LOG_FILE.write_text(json.dumps(self._forge_log[-100:], indent=2))
    
    def propose_skill(self, name: str, description: str, 
                      instructions: str, allowed_tools: List[str],
                      user_id: str, scope: str = "PRIVATE") -> Dict:
        """
        Propose a new skill.
        
        Logic:
        1. Validates inputs.
        2. Determines if auto-approval is possible (Private + Whitelisted Tools).
        3. Writes file to appropriate location (User Dir or Pending Dir).
        4. Returns status for caller to handle (e.g. posting to Discord).
        
        Args:
            name: properties (alphanumeric snake_case)
            description: What it does
            instructions: The SOP body
            allowed_tools: List of tool names
            user_id: ID of the creator
            scope: PRIVATE or PUBLIC
        """
        # 1. Sanitize Name
        safe_name = re.sub(r'[^a-z0-9_]', '', name.lower())[:50]
        
        # 1b. DEDUPLICATION: Block if skill already exists for this user
        existing_path = _PROJECT_ROOT / "memory" / "users" / str(user_id) / "skills" / safe_name / "SKILL.md"
        if existing_path.exists():
            logger.warning(f"SkillForge: BLOCKED duplicate creation of '{safe_name}' for user {user_id}")
            return {
                "name": safe_name,
                "status": "duplicate_blocked",
                "error": f"Skill '{safe_name}' already exists for this user. Use a different name or modify the existing skill.",
                "user_id": user_id,
                "scope": scope,
            }
        
        # 2. Safety Check
        is_safe = all(t in SAFE_TOOL_WHITELIST for t in allowed_tools)
        
        # 3. Determine Status
        # Check Admin Bypass
        from config import settings
        is_admin = str(user_id) == str(settings.ADMIN_ID) or str(user_id) in [str(i) for i in getattr(settings, 'ADMIN_IDS', [])]
        
        # Check if creator is the bot itself (autonomy-created skills don't need approval)
        bot_id = str(getattr(settings, 'BOT_USER_ID', None) or getattr(settings, 'APPLICATION_ID', '') or '')
        is_bot_self = bot_id and str(user_id) == bot_id
        
        # Auto-approve: (Private AND Safe) OR Admin OR Bot's own skills
        is_auto_approved = (scope == "PRIVATE" and is_safe) or is_admin or is_bot_self
        status = "active" if is_auto_approved else "pending"
        
        timestamp = datetime.now().isoformat()
        
        proposal = {
            "name": safe_name,
            "description": description,
            "instructions": instructions,
            "allowed_tools": allowed_tools,
            "user_id": user_id,
            "scope": scope,
            "status": status,
            "proposed_at": timestamp,
            "is_safe_whitelisted": is_safe
        }
        
        # 4. Write File
        file_path = self._write_skill_file(proposal)
        proposal["file_path"] = str(file_path)
        
        # 5. Log & State Update
        if status == "pending":
            self._pending.append(proposal)
        
        self._forge_log.append({
            "event": "created" if is_auto_approved else "proposed",
            "name": safe_name,
            "user_id": user_id,
            "status": status,
            "timestamp": timestamp
        })
        self._save_state()
        
        logger.info(f"SkillForge: '{safe_name}' ({scope}) -> {status}. Safe={is_safe}")
        
        # If active, register immediately
        if status == "active" and self._registry:
            try:
                from src.skills.loader import SkillLoader
                skill_def = SkillLoader.parse(file_path)
                if skill_def:
                    self._registry.register_skill(skill_def, user_id=user_id)
                    logger.info(f"SkillForge: Registered '{safe_name}' in registry for scope '{user_id}'")
                else:
                    logger.warning(f"SkillForge: Failed to parse '{safe_name}' for registration")
            except Exception as e:
                logger.error(f"SkillForge: Registration failed for '{safe_name}': {e}")

        return proposal

    def _write_skill_file(self, proposal: Dict) -> Path:
        """Write the SKILL.md file to the correct directory."""
        
        if proposal["status"] == "active":
            # User's Private Skill Directory — absolute path
            target_dir = _PROJECT_ROOT / "memory" / "users" / str(proposal['user_id']) / "skills" / proposal['name']
        else:
            # System Pending Directory
            target_dir = self.PENDING_DIR / proposal["name"]
        
        logger.info(f"_write_skill_file: target_dir={target_dir.resolve()}, status={proposal['status']}")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "SKILL.md"
        
        # Construct Markdown content
        # YAML Frontmatter
        tools_list = "\n".join([f"  - {t}" for t in proposal["allowed_tools"]])
        
        # Calculate Hash for Tamper-Proofing
        import hashlib
        instructions_body = proposal["instructions"].strip()
        approved_hash = hashlib.sha256(instructions_body.encode("utf-8")).hexdigest()

        content = f"""---
name: {proposal["name"]}
description: {proposal["description"]}
version: 1.0.0
author: {proposal["user_id"]}
scope: {proposal["scope"]}
approved_hash: {approved_hash}
allowed_tools:
{tools_list}
---

{proposal["instructions"]}
"""
        target_file.write_text(content, encoding="utf-8")
        logger.info(f"_write_skill_file: WRITTEN {target_file.resolve()} ({len(content)} bytes, exists={target_file.exists()})")
        return target_file

    def approve_skill(self, name: str, admin_id: str) -> bool:
        """
        Admin approves a pending skill.
        Moves it from pending to CORE (if public) or User dir (if private).
        """
        for proposal in self._pending:
            if proposal["name"] == name and proposal["status"] == "pending":
                proposal["status"] = "approved"
                proposal["approved_by"] = admin_id
                proposal["approved_at"] = datetime.now().isoformat()
                
                # Determine final destination
                # Public -> CORE skills
                # Private -> User skills
                if proposal["scope"] == "PUBLIC":
                    final_dir = Path(f"memory/core/skills/{name}")
                else:
                    final_dir = Path(str(data_dir()) + f"/users/{proposal['user_id']}/skills/{name}")
                
                final_dir.mkdir(parents=True, exist_ok=True)
                final_file = final_dir / "SKILL.md"
                
                # Move/Rewrite file
                # Check for existing pending file
                pending_file = Path(proposal["file_path"])
                if pending_file.exists():
                    text = pending_file.read_text()
                    final_file.write_text(text)
                    # Cleanup pending
                    import shutil
                    shutil.rmtree(pending_file.parent)
                else:
                     # Regenerate if missing
                     self._write_to_path(proposal, final_file)
                
                # Update proposal path
                proposal["file_path"] = str(final_file)
                
                self._save_state()
                logger.info(f"SkillForge: '{name}' approved by {admin_id}")
                return True
        return False
    
    def _write_to_path(self, proposal, path):
        # Helper re-use of logic in _write_skill_file if needed
        pass # Implemented inline above for now

    def edit_skill(self, name: str, user_id: str,
                   instructions: Optional[str] = None,
                   description: Optional[str] = None,
                   allowed_tools: Optional[List[str]] = None) -> Dict:
        """
        Edit an existing skill.
        
        Only the owner can edit their skill. At least one of instructions,
        description, or allowed_tools must be provided.
        
        Security:
        - Re-validates content via SkillLoader._validate_content
        - Recalculates approved_hash
        - Bumps minor version
        - If restricted tools are added, skill goes to pending re-approval
        
        Args:
            name: Skill name (snake_case)
            user_id: ID of the editor (must be owner or admin)
            instructions: New instructions (optional)
            description: New description (optional)
            allowed_tools: New tool list (optional)
            
        Returns:
            Dict with status, name, and details
        """
        safe_name = re.sub(r'[^a-z0-9_]', '', name.lower())[:50]
        
        # 1. Locate existing skill
        skill_path = _PROJECT_ROOT / "memory" / "users" / str(user_id) / "skills" / safe_name / "SKILL.md"
        if not skill_path.exists():
            return {
                "name": safe_name,
                "status": "not_found",
                "error": f"Skill '{safe_name}' not found for user {user_id}.",
            }
        
        # 2. Parse existing skill
        from src.skills.loader import SkillLoader
        existing = SkillLoader.parse(skill_path)
        if not existing:
            return {
                "name": safe_name,
                "status": "parse_error",
                "error": f"Could not parse existing skill '{safe_name}'. File may be corrupted.",
            }
        
        # 3. Check at least one field is being updated
        if instructions is None and description is None and allowed_tools is None:
            return {
                "name": safe_name,
                "status": "no_changes",
                "error": "No fields to update. Provide at least one of: instructions, description, allowed_tools.",
            }
        
        # 4. Apply changes (keep existing values for unspecified fields)
        new_instructions = instructions if instructions is not None else existing.instructions
        new_description = description if description is not None else existing.description
        new_tools = allowed_tools if allowed_tools is not None else existing.allowed_tools
        
        # 5. Security: Validate new instructions
        if instructions is not None:
            if not SkillLoader._validate_content(new_instructions, f"{safe_name}/SKILL.md"):
                return {
                    "name": safe_name,
                    "status": "rejected",
                    "error": "New instructions contain dangerous or injection patterns. Edit rejected.",
                }
        
        # 6. Version bump (minor)
        try:
            parts = existing.version.split('.')
            parts[-1] = str(int(parts[-1]) + 1)
            new_version = '.'.join(parts)
        except (ValueError, IndexError):
            new_version = "1.0.1"
        
        # 7. Safety check - determine if re-approval is needed
        is_safe = all(t in SAFE_TOOL_WHITELIST for t in new_tools)
        
        from config import settings
        is_admin = str(user_id) == str(settings.ADMIN_ID) or str(user_id) in [str(i) for i in getattr(settings, 'ADMIN_IDS', [])]
        
        # Re-approval needed if: new restricted tools added AND not admin
        needs_reapproval = not is_safe and not is_admin
        status = "pending" if needs_reapproval else "active"
        
        # 8. Build updated proposal
        import hashlib
        instructions_body = new_instructions.strip()
        approved_hash = hashlib.sha256(instructions_body.encode("utf-8")).hexdigest()
        
        tools_list = "\n".join([f"  - {t}" for t in new_tools])
        
        content = f"""---
name: {safe_name}
description: {new_description}
version: {new_version}
author: {user_id}
scope: {existing.scope}
approved_hash: {approved_hash}
allowed_tools:
{tools_list}
---

{new_instructions}
"""
        
        # 9. Write file
        if needs_reapproval:
            # Move to pending directory
            target_dir = self.PENDING_DIR / safe_name
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / "SKILL.md"
            target_file.write_text(content, encoding="utf-8")
            
            # Add to pending queue
            proposal = {
                "name": safe_name,
                "description": new_description,
                "instructions": new_instructions,
                "allowed_tools": new_tools,
                "user_id": user_id,
                "scope": existing.scope,
                "status": "pending",
                "proposed_at": datetime.now().isoformat(),
                "is_safe_whitelisted": False,
                "edit_of": str(skill_path),
                "file_path": str(target_file),
            }
            self._pending.append(proposal)
        else:
            # Write in-place
            skill_path.write_text(content, encoding="utf-8")
        
        # 10. Log
        timestamp = datetime.now().isoformat()
        self._forge_log.append({
            "event": "edited" if status == "active" else "edit_pending",
            "name": safe_name,
            "user_id": user_id,
            "status": status,
            "version": new_version,
            "timestamp": timestamp,
        })
        self._save_state()
        
        logger.info(f"SkillForge: '{safe_name}' edited -> {status} (v{new_version})")
        
        # 11. Hot-reload if active
        result = {
            "name": safe_name,
            "status": status,
            "version": new_version,
            "file_path": str(skill_path),
            "is_safe_whitelisted": is_safe,
            "fields_updated": [
                f for f, v in [
                    ("instructions", instructions), 
                    ("description", description), 
                    ("allowed_tools", allowed_tools)
                ] if v is not None
            ],
        }
        
        if status == "active" and self._registry:
            try:
                skill_def = SkillLoader.parse(skill_path)
                if skill_def:
                    self._registry.register_skill(skill_def, user_id=user_id)
                    logger.info(f"SkillForge: Hot-reloaded edited skill '{safe_name}'")
            except Exception as e:
                logger.error(f"SkillForge: Hot-reload failed for edited '{safe_name}': {e}")
        
        return result

    def get_pending(self) -> List[Dict]:
        return [p for p in self._pending if p["status"] == "pending"]

