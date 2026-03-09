"""
Skill Forge — v3.5 Photosynthesis.

Enables Ernos to compose new skills by combining existing
skill primitives and LLM-generated code. All self-authored
skills require admin approval before activation.
"""
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("Lobe.Strategy.SkillForge")


class SkillForge:
    """
    Self-authoring skill composition engine.
    
    Flow:
    1. Ernos identifies a capability gap (e.g., "no skill for X")
    2. Forge analyzes existing skills for reusable components
    3. Generates a draft skill definition
    4. Queues for admin review
    5. On approval, skill is loaded into the SkillRegistry
    
    Safety:
    - All generated skills are sandboxed
    - Admin must approve via `/skill approve <name>`
    - Skills are logged to memory/system/skill_forge_log.json
    """
    
    FORGE_DIR = Path("memory/system/skill_forge")
    QUEUE_FILE = Path("memory/system/skill_forge/pending.json")
    LOG_FILE = Path("memory/system/skill_forge/forge_log.json")
    
    def __init__(self, skill_registry=None, engine=None):
        """
        Args:
            skill_registry: Existing SkillRegistry for skill loading
            engine: LLM engine for code generation
        """
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
            except Exception:
                pass
        if self.LOG_FILE.exists():
            try:
                self._forge_log = json.loads(self.LOG_FILE.read_text())
            except Exception:
                pass
    
    def _save_state(self):
        """Persist state."""
        self.FORGE_DIR.mkdir(parents=True, exist_ok=True)
        self.QUEUE_FILE.write_text(json.dumps(self._pending, indent=2))
        self.LOG_FILE.write_text(json.dumps(self._forge_log[-100:], indent=2))
    
    def propose_skill(self, name: str, description: str, 
                      trigger: str, action_code: str,
                      reason: str = "") -> Dict:
        """
        Propose a new skill for admin review.
        
        Args:
            name: Skill name (filesystem-safe)
            description: What the skill does
            trigger: When to activate (keyword/pattern)
            action_code: Python code for the skill action
            reason: Why Ernos thinks this skill is needed
        
        Returns:
            Dict with proposal details and status
        """
        import re
        safe_name = re.sub(r'[^a-z0-9_]', '', name.lower())[:50]
        
        proposal = {
            "name": safe_name,
            "description": description,
            "trigger": trigger,
            "action_code": action_code[:5000],  # Cap code length
            "reason": reason,
            "status": "pending",
            "proposed_at": datetime.now().isoformat(),
            "approved_by": None,
            "approved_at": None
        }
        
        self._pending.append(proposal)
        self._forge_log.append({
            "event": "proposed",
            "name": safe_name,
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_state()
        logger.info(f"SkillForge: Proposed '{safe_name}' — awaiting admin approval")
        
        return proposal
    
    def approve_skill(self, name: str, admin_id: str) -> bool:
        """
        Admin approves a pending skill.
        
        Returns True if skill was found and approved.
        """
        for proposal in self._pending:
            if proposal["name"] == name and proposal["status"] == "pending":
                proposal["status"] = "approved"
                proposal["approved_by"] = admin_id
                proposal["approved_at"] = datetime.now().isoformat()
                
                # Write skill file
                self._write_skill_file(proposal)
                
                self._forge_log.append({
                    "event": "approved",
                    "name": name,
                    "admin": admin_id,
                    "timestamp": datetime.now().isoformat()
                })
                self._save_state()
                
                logger.info(f"SkillForge: '{name}' approved by {admin_id}")
                return True
        
        return False
    
    def reject_skill(self, name: str, admin_id: str, reason: str = "") -> bool:
        """Admin rejects a pending skill."""
        for proposal in self._pending:
            if proposal["name"] == name and proposal["status"] == "pending":
                proposal["status"] = "rejected"
                proposal["rejected_reason"] = reason
                
                self._forge_log.append({
                    "event": "rejected",
                    "name": name,
                    "reason": reason,
                    "admin": admin_id,
                    "timestamp": datetime.now().isoformat()
                })
                self._save_state()
                return True
        return False
    
    def _write_skill_file(self, proposal: Dict):
        """Write approved skill to the skills directory."""
        skills_dir = Path("memory/core/skills")
        skills_dir.mkdir(parents=True, exist_ok=True)
        
        skill_file = skills_dir / f"{proposal['name']}.py"
        
        content = f'''"""
Auto-generated skill: {proposal["name"]}
Description: {proposal["description"]}
Generated by SkillForge at {proposal["proposed_at"]}
Approved by admin at {proposal["approved_at"]}
"""

TRIGGER = "{proposal["trigger"]}"
DESCRIPTION = """{proposal["description"]}"""

{proposal["action_code"]}
'''
        skill_file.write_text(content)
        logger.info(f"SkillForge: Written skill file {skill_file}")
    
    def get_pending(self) -> List[Dict]:
        """Get all pending skill proposals."""
        return [p for p in self._pending if p["status"] == "pending"]
    
    def get_forge_summary(self) -> str:
        """Get a summary of forge activity."""
        pending = len([p for p in self._pending if p["status"] == "pending"])
        approved = len([p for p in self._pending if p["status"] == "approved"])
        rejected = len([p for p in self._pending if p["status"] == "rejected"])
        return f"SkillForge: {pending} pending, {approved} approved, {rejected} rejected"
