"""
Skill Registry — Manages loaded skill definitions.

Skills are loaded from a directory of SKILL.md files at startup.
The registry provides lookup, listing, and validation.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.skills.loader import SkillLoader
from src.skills.types import SkillDefinition

logger = logging.getLogger("Skills.Registry")


class SkillRegistry:
    """
    Manages loaded skill definitions.
    
    Skills are discovered from a directory, parsed by SkillLoader,
    and registered here for lookup by name.
    """

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}

    def load_skills(self, skills_dir: Path) -> int:
        """
        Scan a directory for SKILL.md files and register valid ones.
        
        Looks for files matching the pattern: skills_dir/*/SKILL.md
        Each skill lives in its own subdirectory.
        
        Args:
            skills_dir: Root directory containing skill subdirectories
            
        Returns:
            Number of skills successfully loaded
        """
        if not skills_dir.exists():
            logger.warning(f"Skills directory does not exist: {skills_dir}")
            return 0

        loaded = 0
        for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
            skill = SkillLoader.parse(skill_file)
            if skill and self.validate_skill(skill):
                self._skills[skill.name] = skill
                loaded += 1
                logger.info(f"Loaded skill: {skill}")
            elif skill:
                logger.warning(f"Skill '{skill.name}' failed validation — not registered")

        logger.info(f"Skill registry loaded {loaded} skill(s) from {skills_dir}")
        return loaded

    def register_skill(self, skill: SkillDefinition) -> bool:
        """
        Manually register a single skill definition.
        
        Returns:
            True if registered, False if validation failed
        """
        if not self.validate_skill(skill):
            return False
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill}")
        return True

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        """Look up a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> List[SkillDefinition]:
        """Return all registered skills."""
        return list(self._skills.values())

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
        """
        manifest = []
        for skill in self._skills.values():
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
