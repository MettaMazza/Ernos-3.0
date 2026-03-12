"""
Skill Library for Minecraft

Stores successful action sequences for reuse.
Inspired by Voyager's skill library architecture.
"""

import json
import os
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

SKILLS_FILE = "./memory/public/skills.json"


@dataclass
class Skill:
    """A learned skill that can be reused.
    
    Supports two types:
    - 'steps': Action string sequence (existing behavior)
    - 'code': JavaScript program (Voyager-style, executed via Mineflayer)
    """
    name: str                    # Unique identifier (e.g., "get_iron_pickaxe")
    description: str             # What this skill accomplishes
    goal: str                    # Target item/objective
    steps: List[str]             # Action sequence
    code: str = ""               # JavaScript program (Voyager-style)
    skill_type: str = "steps"    # "steps" or "code"
    success_count: int = 0       # Times succeeded
    failure_count: int = 0       # Times failed
    avg_duration: float = 0.0    # Average execution time (seconds)
    created_at: str = ""         # ISO timestamp
    last_used: str = ""          # ISO timestamp
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Skill':
        return cls(**data)


class SkillLibrary:
    """
    Stores and retrieves learned skills.
    
    When Ernos successfully completes a complex task, the action sequence
    is stored as a skill. Next time a similar goal is requested, the
    skill can be retrieved and reused instead of re-planning.
    """
    
    def __init__(self, skills_file: str = SKILLS_FILE):
        self.skills_file = skills_file
        self.skills: Dict[str, Skill] = {}
        self._load()
    
    def _load(self):
        """Load skills from disk."""
        if os.path.exists(self.skills_file):
            try:
                with open(self.skills_file, 'r') as f:
                    data = json.load(f)
                    for name, skill_data in data.items():
                        self.skills[name] = Skill.from_dict(skill_data)
                logger.info(f"Loaded {len(self.skills)} skills from {self.skills_file}")
            except Exception as e:
                logger.error(f"Failed to load skills: {e}")
                self.skills = {}
        else:
            self.skills = {}
    
    def _save(self):
        """Persist skills to disk."""
        try:
            os.makedirs(os.path.dirname(self.skills_file), exist_ok=True)
            with open(self.skills_file, 'w') as f:
                data = {name: skill.to_dict() for name, skill in self.skills.items()}
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save skills: {e}")
    
    def store(
        self, 
        goal: str, 
        steps: List[str], 
        duration: float = 0.0,
        description: str = ""
    ) -> Skill:
        """
        Store a successful action sequence as a skill.
        
        Args:
            goal: What was accomplished (e.g., "iron_pickaxe")
            steps: List of actions that achieved the goal
            duration: How long it took (seconds)
            description: Human-readable description
            
        Returns:
            The stored Skill object
        """
        name = f"get_{goal.replace(' ', '_')}"
        now = datetime.now().isoformat()
        
        if name in self.skills:
            # Update existing skill
            skill = self.skills[name]
            skill.success_count += 1
            skill.last_used = now
            # Update average duration
            total_uses = skill.success_count + skill.failure_count
            skill.avg_duration = (
                (skill.avg_duration * (total_uses - 1) + duration) / total_uses
            )
        else:
            # Create new skill
            skill = Skill(
                name=name,
                description=description or f"How to obtain {goal}",
                goal=goal,
                steps=steps,
                success_count=1,
                created_at=now,
                last_used=now,
                avg_duration=duration
            )
            self.skills[name] = skill
        
        self._save()
        logger.info(f"Stored skill: {name} ({len(steps)} steps)")
        return skill
    
    def retrieve(self, goal: str) -> Optional[Skill]:
        """
        Find a skill that can achieve the given goal.
        
        Args:
            goal: Target to achieve (e.g., "iron_pickaxe")
            
        Returns:
            Skill if found, None otherwise
        """
        name = f"get_{goal.replace(' ', '_')}"
        
        # Exact match
        if name in self.skills:
            skill = self.skills[name]
            skill.last_used = datetime.now().isoformat()
            self._save()
            return skill
        
        # Partial match (goal contains the item)
        for skill_name, skill in self.skills.items():
            if goal in skill.goal or skill.goal in goal:
                skill.last_used = datetime.now().isoformat()
                self._save()
                return skill
        
        return None
    
    def record_failure(self, goal: str):
        """Record that a skill failed to achieve its goal."""
        name = f"get_{goal.replace(' ', '_')}"
        if name in self.skills:
            self.skills[name].failure_count += 1
            self._save()

    def record_success(self, goal: str):
        """Record that a skill succeeded at its goal."""
        name = f"get_{goal.replace(' ', '_')}"
        if name in self.skills:
            self.skills[name].success_count += 1
            self.skills[name].last_used = datetime.now().isoformat()
            self._save()
    
    def get_all(self) -> List[Skill]:
        """Get all stored skills."""
        return list(self.skills.values())
    
    def get_best_skills(self, limit: int = 10) -> List[Skill]:
        """Get skills sorted by success rate."""
        return sorted(
            self.skills.values(),
            key=lambda s: s.success_rate,
            reverse=True
        )[:limit]
    
    def delete(self, goal: str) -> bool:
        """Delete a skill."""
        name = f"get_{goal.replace(' ', '_')}"
        if name in self.skills:
            del self.skills[name]
            self._save()
            return True
        return False
    
    def clear(self):
        """Clear all skills."""
        self.skills = {}
        self._save()


# Singleton instance
_library = None

def get_skill_library() -> SkillLibrary:
    """Get the global skill library instance."""
    global _library
    if _library is None:
        _library = SkillLibrary()
    return _library
