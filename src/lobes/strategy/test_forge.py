"""
Test Forge — v3.5 Photosynthesis.

Self-generating test suite. Ernos can analyze its own code
and propose new tests to improve coverage. All generated
tests require admin review before inclusion.
"""
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("Lobe.Strategy.TestForge")


class TestForge:
    """
    Self-generating test composition engine.
    
    Ernos can:
    - Identify untested code paths
    - Generate test stubs for new features
    - Propose regression tests for bug fixes
    - Track test coverage trends
    
    Safety:
    - Generated tests are saved to a staging directory
    - Admin reviews and moves to tests/ when approved
    - No auto-modification of existing test files
    """
    
    STAGING_DIR = Path("memory/system/test_forge/staging")
    LOG_FILE = Path("memory/system/test_forge/forge_log.json")
    
    def __init__(self):
        self._staged_tests: List[Dict] = []
        self._forge_log: List[Dict] = []
        self._load_state()
    
    def _load_state(self):
        """Load staged tests and log."""
        if self.LOG_FILE.exists():
            try:
                self._forge_log = json.loads(self.LOG_FILE.read_text())
            except Exception:
                pass
        
        if self.STAGING_DIR.exists():
            for f in self.STAGING_DIR.glob("*.py"):
                self._staged_tests.append({
                    "name": f.stem,
                    "path": str(f),
                    "status": "staged"
                })
    
    def _save_log(self):
        """Persist forge log."""
        self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.LOG_FILE.write_text(json.dumps(self._forge_log[-100:], indent=2))
    
    def propose_test(self, test_name: str, target_module: str,
                     test_code: str, rationale: str = "") -> Dict:
        """
        Propose a new test for admin review.
        
        Args:
            test_name: Test file name (without .py)
            target_module: Which module this tests
            test_code: Complete test Python code
            rationale: Why this test is needed
        
        Returns:
            Dict with proposal details
        """
        import re
        safe_name = re.sub(r'[^a-z0-9_]', '', test_name.lower())[:50]
        if not safe_name.startswith("test_"):
            safe_name = f"test_{safe_name}"
        
        # Write to staging
        self.STAGING_DIR.mkdir(parents=True, exist_ok=True)
        staging_path = self.STAGING_DIR / f"{safe_name}.py"
        staging_path.write_text(test_code)
        
        proposal = {
            "name": safe_name,
            "target_module": target_module,
            "staging_path": str(staging_path),
            "rationale": rationale,
            "status": "staged",
            "lines": test_code.count("\n") + 1,
            "proposed_at": datetime.now().isoformat()
        }
        
        self._staged_tests.append(proposal)
        self._forge_log.append({
            "event": "proposed",
            "name": safe_name,
            "target": target_module,
            "timestamp": datetime.now().isoformat()
        })
        self._save_log()
        
        logger.info(f"TestForge: Staged '{safe_name}' for {target_module}")
        return proposal
    
    def approve_test(self, test_name: str) -> bool:
        """
        Move a staged test to the tests/ directory.
        
        Returns True if successful.
        """
        staging_path = self.STAGING_DIR / f"{test_name}.py"
        if not staging_path.exists():
            return False
        
        dest = Path("tests") / f"{test_name}.py"
        try:
            import shutil
            shutil.copy2(staging_path, dest)
            
            # Update status
            for t in self._staged_tests:
                if t["name"] == test_name:
                    t["status"] = "approved"
            
            self._forge_log.append({
                "event": "approved",
                "name": test_name,
                "dest": str(dest),
                "timestamp": datetime.now().isoformat()
            })
            self._save_log()
            
            logger.info(f"TestForge: '{test_name}' promoted to {dest}")
            return True
            
        except Exception as e:
            logger.error(f"TestForge: Failed to promote {test_name}: {e}")
            return False
    
    def reject_test(self, test_name: str, reason: str = "") -> bool:
        """Remove a staged test."""
        staging_path = self.STAGING_DIR / f"{test_name}.py"
        if staging_path.exists():
            staging_path.unlink()
        
        for t in self._staged_tests:
            if t["name"] == test_name:
                t["status"] = "rejected"
        
        self._forge_log.append({
            "event": "rejected",
            "name": test_name,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        self._save_log()
        return True
    
    def get_staged(self) -> List[Dict]:
        """Get all staged tests awaiting review."""
        return [t for t in self._staged_tests if t["status"] == "staged"]
    
    def get_forge_summary(self) -> str:
        """Summary of test forge activity."""
        staged = len(self.get_staged())
        total = len(self._staged_tests)
        return f"TestForge: {staged} staged, {total} total proposals"
