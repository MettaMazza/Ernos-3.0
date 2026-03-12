"""
Homeostatic Drive System
Manages the internal state of the agent's needs and drives.
"""
from dataclasses import dataclass, field
import json
from pathlib import Path
from datetime import datetime
import logging
from src.core.data_paths import data_dir

logger = logging.getLogger("Core.Drives")

@dataclass
class Drives:
    uncertainty: float = 0.0      # Drive to learn/explore (increases with time/confusion)
    social_connection: float = 100.0 # Drive to interact (decays with time)
    system_health: float = 100.0  # Drive to maintain self (decays with errors)
    last_updated: float = 0.0

class DriveSystem:
    """
    Manages internal drives that act as a 'metabolic' system for the AI.
    These drives provide the 'signal' for the AgencyDaemon to act upon.
    """
    PERSIST_PATH = data_dir() / "core/drives.json"
    
    # Decay rates per hour (approximate)
    DECAY_RATES = {
        "social_connection": 5.0,  # Loses 5% per hour of silence
        "uncertainty": -2.0        # Increases by 2% per hour naturally (entropy)
    }

    def __init__(self):
        self.drives = Drives(last_updated=datetime.now().timestamp())
        self._load()

    def update(self):
        """Apply passive decay based on time passed."""
        now = datetime.now().timestamp()
        hours_passed = (now - self.drives.last_updated) / 3600.0
        
        if hours_passed > 0:
            # Social Connection decays
            self.drives.social_connection = max(0.0, self.drives.social_connection - (self.DECAY_RATES["social_connection"] * hours_passed))
            
            # Uncertainty increases (entropy)
            self.drives.uncertainty = min(100.0, self.drives.uncertainty - (self.DECAY_RATES["uncertainty"] * hours_passed))
            
            self.drives.last_updated = now
            self._save()

    def modify_drive(self, drive_name: str, amount: float):
        """Active modification of specific drives (e.g. after an action)."""
        if hasattr(self.drives, drive_name):
            current = getattr(self.drives, drive_name)
            new_val = max(0.0, min(100.0, current + amount))
            setattr(self.drives, drive_name, new_val)
            self.drives.last_updated = datetime.now().timestamp()
            self._save()
            logger.info(f"Drive '{drive_name}' updated: {current:.1f} -> {new_val:.1f}")
        else:
            logger.warning(f"Attempted to modify unknown drive: {drive_name}")

    def get_state(self) -> dict:
        self.update() # Ensure fresh check
        return {
            "uncertainty": f"{self.drives.uncertainty:.1f}%",
            "social_connection": f"{self.drives.social_connection:.1f}%",
            "system_health": f"{self.drives.system_health:.1f}%"
        }

    def _save(self):
        try:
            self.PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.PERSIST_PATH, "w", encoding="utf-8") as f:
                f.write(json.dumps(self.drives.__dict__, indent=2))
        except Exception as e:
            logger.error(f"Failed to save drives: {e}")

    def _load(self):
        if self.PERSIST_PATH.exists():
            try:
                data = json.loads(self.PERSIST_PATH.read_text())
                # Handle potentially missing keys if schema changes
                self.drives = Drives(**{k: v for k, v in data.items() if k in self.drives.__dict__})
            except Exception as e:
                logger.error(f"Failed to load drives: {e}")
