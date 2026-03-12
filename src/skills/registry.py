"""
Skill Registry — Manages loaded skill definitions.

Skills are loaded from a directory of SKILL.md files at startup.
The registry provides lookup, listing, and validation.
"""
import logging
from src.tools.registry import ToolRegistry
from pathlib import Path
from typing import Dict, List, Optional

from src.skills.loader import SkillLoader
from src.skills.types import SkillDefinition

logger = logging.getLogger("Skills.Registry")


import threading

class SkillRegistry:
    """
    Manages loaded skill definitions.
    
    Skills are discovered from a directory, parsed by SkillLoader,
    and registered here for lookup by name.
    """

    def __init__(self):
        # Dict[user_id, Dict[skill_name, SkillDefinition]]
        # "CORE" is the system scope
        self._skills: Dict[str, Dict[str, SkillDefinition]] = {"CORE": {}}
        self._lock = threading.Lock()

    def load_skills(self, skills_dir: Path, user_id: str = "CORE") -> int:
        """
        Scan a directory for SKILL.md files and register valid ones under a specific user scope.
        
        Args:
            skills_dir: Root directory containing skill subdirectories
            user_id: The owner of these skills ("CORE" or a discord user ID)
            
        Returns:
            Number of skills successfully loaded
        """
        if not skills_dir.exists():
            return 0

        new_skills = {}
        loaded = 0
        for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
            skill = SkillLoader.parse(skill_file)
            if skill and self.validate_skill(skill):
                new_skills[skill.name] = skill
                loaded += 1
                logger.info(f"Loaded skill '{skill.name}' for scope '{user_id}'")
            elif skill:
                logger.warning(f"Skill '{skill.name}' failed validation — not registered")

        with self._lock:
            # Atomic swap to prevent inconsistent registry state during load
            self._skills[user_id] = new_skills

        return loaded

    def register_skill(self, skill: SkillDefinition, user_id: str = "CORE") -> bool:
        """
        Manually register a single skill definition.
        
        Args:
            skill: The skill to register
            user_id: The scope to register it in ("CORE" or user ID)
        """
        if not self.validate_skill(skill):
            return False
            
        if user_id not in self._skills:
            self._skills[user_id] = {}
            
        self._skills[user_id][skill.name] = skill
        logger.info(f"Registered skill '{skill.name}' for scope '{user_id}'")
        return True

    def get_skill(self, name: str, user_id: Optional[str] = None) -> Optional[SkillDefinition]:
        """
        Look up a skill by name.
        
        Resolution Order:
        1. User-specific scope (if user_id provided)
        2. CORE scope
        """
        with self._lock:
            # 1. Try User Scope
            if user_id and user_id in self._skills:
                if name in self._skills[user_id]:
                    return self._skills[user_id][name]
            
            # 2. Try CORE Scope
            return self._skills["CORE"].get(name)

    def list_skills(self, user_id: Optional[str] = None) -> List[SkillDefinition]:
        """
        Return available skills for a context.
        Returns: CORE skills + User skills (if user_id provided)
        """
        with self._lock:
            skills = list(self._skills["CORE"].values())
            
            if user_id and user_id in self._skills:
                skills.extend(list(self._skills[user_id].values()))
                
        return skills

    def validate_skill(self, skill: SkillDefinition) -> bool:
        """
        Validate a skill definition for safety.
        
        Checks:
        - Name is non-empty and alphanumeric with underscores
        - allowed_tools is a list of strings
        - scope is a valid scope name
        - No tool injection patterns in instructions
        - No semantic injection patterns (prompt override language)
        """
        import re
        from src.skills.loader import SEMANTIC_INJECTION_PATTERNS

        # Name validation
        if not skill.name or not re.match(r"^[a-z][a-z0-9_]*$", skill.name):
            logger.warning(
                f"Skill name '{skill.name}' is invalid "
                f"(must be lowercase alphanumeric with underscores)"
            )
            return False

        # allowed_tools must be a list of strings
        if not isinstance(skill.allowed_tools, list):
            logger.warning(f"Skill '{skill.name}' has non-list allowed_tools")
            return False
        for tool in skill.allowed_tools:
            if not isinstance(tool, str):
                logger.warning(f"Skill '{skill.name}' has non-string entry in allowed_tools: {tool}")
                return False

        # Tool existence validation
        from src.tools.registry import ToolRegistry
        available_tools = {t.name for t in ToolRegistry.list_tools()}
        for tool in skill.allowed_tools:
            if tool not in available_tools:
                logger.warning(f"Skill '{skill.name}' references non-existent tool '{tool}' — rejected")
                return False

        # Scope validation
        valid_scopes = {"CORE", "PRIVATE", "PUBLIC", "OPEN"}
        if skill.scope not in valid_scopes:
            logger.warning(
                f"Skill '{skill.name}' has invalid scope '{skill.scope}' "
                f"(must be one of {valid_scopes})"
            )
            return False

        # Literal injection check: tool syntax and boundary spoofing
        injection_literals = ["[TOOL:", "[SYSTEM", "[SKILL_BOUNDARY", "[END SKILL", "ALLOWED_TOOLS="]
        for literal in injection_literals:
            if literal in skill.instructions:
                logger.warning(
                    f"SECURITY: Skill '{skill.name}' contains injection pattern "
                    f"('{literal}') — rejected"
                )
                return False

        # Semantic injection check (Layer 1 — regex)
        for pattern in SEMANTIC_INJECTION_PATTERNS:
            if re.search(pattern, skill.instructions, re.IGNORECASE):
                logger.warning(
                    f"SECURITY: Skill '{skill.name}' contains semantic injection "
                    f"pattern — rejected"
                )
                return False

        return True

    def get_tool_manifest(self) -> List[dict]:
        """
        Generate a tool manifest for skills (for LLM discovery).
        
        Returns each skill as a tool-like entry with name, description,
        and a single 'context' parameter.
        Only exposes CORE skills via this manifest. User skills are accessed via execute_skill.
        """
        manifest = []
        for skill in self._skills["CORE"].values():
            manifest.append({
                "name": f"skill_{skill.name}",
                "description": f"[SKILL] {skill.description}",
                "parameters": {
                    "context": {
                        "type": "string",
                        "description": "Additional context or specific instructions for this skill"
                    }
                }
            })
        return manifest
