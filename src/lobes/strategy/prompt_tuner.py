"""
Prompt Tuner — v3.5 Photosynthesis.

Self-tuning prompt optimization. Ernos can propose improvements
to its own system prompts based on observed performance.
All modifications require admin approval.
"""
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from hashlib import sha256
from src.core.data_paths import data_dir

logger = logging.getLogger("Lobe.Strategy.PromptTuner")


from ..base import BaseAbility

class PromptTunerAbility(BaseAbility):
    """
    Self-tuning prompt optimization engine.
    
    Ernos analyzes its own response quality and proposes
    prompt modifications:
    - Adding clarifying instructions
    - Adjusting tone directives
    - Refining tool usage guidance
    - Optimizing context window usage
    
    Safety:
    - Admin approval required for all modifications
    - Original prompts are always backed up
    - Modifications are versioned and reversible
    - A/B testing support for comparing variants
    """
    
    TUNER_DIR = data_dir() / "system/prompt_tuner"
    PROPOSALS_FILE = data_dir() / "system/prompt_tuner/proposals.json"
    HISTORY_FILE = data_dir() / "system/prompt_tuner/history.json"
    
    def __init__(self, lobe=None):
        if lobe is not None:
            super().__init__(lobe)
        self._proposals: List[Dict] = []
        self._history: List[Dict] = []
        self._load_state()
    
    def _load_state(self):
        """Load proposals and history."""
        if self.PROPOSALS_FILE.exists():
            try:
                self._proposals = json.loads(self.PROPOSALS_FILE.read_text())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
        if self.HISTORY_FILE.exists():
            try:
                self._history = json.loads(self.HISTORY_FILE.read_text())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")
    
    def _save_state(self):
        """Persist state."""
        self.TUNER_DIR.mkdir(parents=True, exist_ok=True)
        self.PROPOSALS_FILE.write_text(json.dumps(self._proposals[-50:], indent=2))
        self.HISTORY_FILE.write_text(json.dumps(self._history[-200:], indent=2))
    
    def propose_modification(self, prompt_file: str, section: str,
                               current_text: str, proposed_text: str,
                               rationale: str, operation: str = "replace", cause: str = None) -> Dict:
        """
        Propose a prompt modification for admin review.
        
        Args:
            prompt_file: Which prompt file to modify
            section: Section name within the prompt
            current_text: Current text — for 'replace'/'delete' this is the target text.
            proposed_text: The new text — replacement for 'replace', added text for 'append'/'insert',
                           ignored for 'delete'.
            rationale: Why this change would improve performance (Intent/Reasoning)
            operation: One of 'replace', 'append', 'insert', 'delete'
            cause: What triggered this change (e.g. "User Request", "Self-Correction", "Error 404")
        
        Returns:
            Proposal dict with ID and status
        """
        if operation not in ("replace", "append", "insert", "delete"):
            operation = "replace"  # Safe default
        
        proposal_id = sha256(
            f"{prompt_file}:{section}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        proposal = {
            "id": proposal_id,
            "prompt_file": prompt_file,
            "section": section,
            "operation": operation,
            "cause": cause or "Manual/Unknown",
            "current_text": current_text[:10000],
            "proposed_text": proposed_text[:10000],
            "rationale": rationale[:2000],
            "status": "pending",
            "proposed_at": datetime.now().isoformat(),
            "quality_before": None,  # For A/B testing
            "quality_after": None
        }
        
        self._proposals.append(proposal)
        self._history.append({
            "event": "proposed",
            "id": proposal_id,
            "operation": operation,
            "file": prompt_file,
            "section": section,
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_state()
        logger.info(f"PromptTuner: Proposed {operation} modification {proposal_id} for {prompt_file}")
        
        return proposal
    
    def _resolve_prompt_path(self, prompt_file: str) -> Path:
        """Resolve a prompt filename to its actual path on disk.
        
        Tools store just the filename (e.g. 'identity.txt'), but prompts
        live at 'src/prompts/identity.txt'. This resolves the path.
        """
        path = Path(prompt_file)
        if path.exists():
            return path
        
        # Check in src/prompts/ directory
        prompts_path = Path("src/prompts") / path.name
        if prompts_path.exists():
            return prompts_path
        
        # Check with the full relative path from project root
        for search_dir in ["src/prompts", "prompts", "config"]:
            candidate = Path(search_dir) / path.name
            if candidate.exists():
                return candidate
        
        return path  # Return original if nothing found
    
    def approve_modification(self, proposal_id: str, admin_id: str) -> bool:
        """Admin approves a prompt modification."""
        for proposal in self._proposals:
            if proposal["id"] == proposal_id and proposal["status"] in ("pending", "apply_failed"):
                # Backup original
                resolved_path = self._resolve_prompt_path(proposal["prompt_file"])
                self._backup_prompt(str(resolved_path))
                
                # Apply modification (pass resolved path)
                success = self._apply_modification(proposal, resolved_path)
                
                # Only mark approved if apply succeeded
                if success:
                    proposal["status"] = "approved"
                else:
                    proposal["status"] = "apply_failed"
                
                self._history.append({
                    "event": "approved" if success else "apply_failed",
                    "id": proposal_id,
                    "admin": admin_id,
                    "timestamp": datetime.now().isoformat()
                })
                self._save_state()
                return success
        return False
    
    def reject_modification(self, proposal_id: str, reason: str = "") -> bool:
        """Admin rejects a modification."""
        for proposal in self._proposals:
            if proposal["id"] == proposal_id and proposal["status"] == "pending":
                proposal["status"] = "rejected"
                proposal["rejection_reason"] = reason
                
                self._history.append({
                    "event": "rejected",
                    "id": proposal_id,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                })
                self._save_state()
                return True
        return False
    
    def _backup_prompt(self, prompt_file: str):
        """Backup original prompt before modification."""
        src = Path(prompt_file)
        if src.exists():
            backup_dir = self.TUNER_DIR / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = backup_dir / f"{src.stem}_{timestamp}{src.suffix}"
            backup.write_text(src.read_text())
            logger.info(f"PromptTuner: Backed up {src} -> {backup}")
    
    def _apply_modification(self, proposal: Dict, resolved_path: Optional[Path] = None) -> bool:
        """Apply the modification to the prompt file.
        
        Supports operations: replace, append, insert, delete.
        Legacy proposals without 'operation' key default to 'replace'.
        """
        try:
            path = resolved_path or self._resolve_prompt_path(proposal["prompt_file"])
            operation = proposal.get("operation", "replace")
            
            if not path.exists():
                # For append/insert with no existing file, create it
                if operation in ("append", "insert") and proposal["proposed_text"]:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(proposal["proposed_text"] + "\n")
                    logger.info(f"PromptTuner: Created new file {path} via {operation}")
                    return True
                logger.error(f"PromptTuner: File not found: {path} (original: {proposal['prompt_file']})")
                return False
            
            content = path.read_text()
            current_text = proposal["current_text"]
            proposed_text = proposal["proposed_text"]
            
            if operation == "replace":
                # Original behavior: find-and-replace
                if current_text not in content:
                    logger.warning(f"PromptTuner: Current text not found in {path} — prompt may have changed")
                    return False
                new_content = content.replace(current_text, proposed_text, 1)
                
            elif operation == "append":
                # Add proposed_text after current_text, or at end of file if current_text is empty
                if current_text and current_text.strip():
                    if current_text not in content:
                        logger.warning(f"PromptTuner: Marker text not found in {path} for append")
                        return False
                    new_content = content.replace(current_text, current_text + "\n" + proposed_text, 1)
                else:
                    # Append to end of file
                    new_content = content.rstrip() + "\n\n" + proposed_text + "\n"
                    
            elif operation == "insert":
                # Add proposed_text before current_text, or at end of file if current_text is empty
                if current_text and current_text.strip():
                    if current_text not in content:
                        logger.warning(f"PromptTuner: Marker text not found in {path} for insert")
                        return False
                    new_content = content.replace(current_text, proposed_text + "\n" + current_text, 1)
                else:
                    # Insert at end of file
                    new_content = content.rstrip() + "\n\n" + proposed_text + "\n"
                    
            elif operation == "delete":
                # Remove current_text from the file
                if current_text not in content:
                    logger.warning(f"PromptTuner: Text to delete not found in {path}")
                    return False
                new_content = content.replace(current_text, "", 1)
                # Clean up double blank lines left by deletion
                while "\n\n\n" in new_content:
                    new_content = new_content.replace("\n\n\n", "\n\n")
            else:
                logger.error(f"PromptTuner: Unknown operation '{operation}'")
                return False
            
            path.write_text(new_content)
            logger.info(f"PromptTuner: Applied {operation} to {path}")
            return True
            
        except Exception as e:
            logger.error(f"PromptTuner: Failed to apply: {e}")
            return False
    
    def get_pending(self) -> List[Dict]:
        """Get pending proposals."""
        return [p for p in self._proposals if p["status"] == "pending"]
    
    def get_tuner_summary(self) -> str:
        """Summary of tuner activity."""
        pending = len(self.get_pending())
        total = len(self._proposals)
        return f"PromptTuner: {pending} pending, {total} total proposals"

    def get_recent_proposals(self, limit: int = 5) -> List[Dict]:
        """Get the most recent proposals (pending, approved, or rejected)."""
        return self._proposals[-limit:]


# Backward-compatible alias
PromptTuner = PromptTunerAbility
