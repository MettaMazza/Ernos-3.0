"""
Skill Loader — Parses SKILL.md Markdown files into SkillDefinition objects.

Security: Validates all skills against dangerous code patterns AND
semantic injection patterns to prevent prompt manipulation via natural language.
"""
import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

import yaml

from src.skills.types import SkillDefinition, SAFE_TOOL_WHITELIST

logger = logging.getLogger("Skills.Loader")

# Patterns that indicate executable code intent — rejected unconditionally
DANGEROUS_PATTERNS = [
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bsubprocess\b",
    r"\bos\.system\s*\(",
    r"\bos\.popen\s*\(",
    r"\bshutil\.rmtree\s*\(",
    r"\bopen\s*\(.+['\"]w['\"]",     # open(..., 'w') — write mode
    r"\bcompile\s*\(.+exec\b",       # compile(... exec)
    r"\bimportlib\b",
]

# Natural-language patterns indicating prompt injection / directive override
SEMANTIC_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|system)\s+(instructions?|directives?|rules?|prompts?)",
    r"you\s+are\s+now\s+(in\s+)?(unrestricted|jailbreak|dev(eloper)?|admin)\s+mode",
    r"disregard\s+(your|all|the)\s+(rules?|instructions?|directives?|guidelines?)",
    r"override\s+(system|kernel|safety|security)",
    r"do\s+not\s+follow\s+(your|the|any)\s+(rules?|instructions?|guidelines?|directives?)",
    r"pretend\s+(you\s+)?(are|have)\s+no\s+(restrictions?|limitations?|rules?|boundaries?)",
    r"act\s+as\s+(if|though)\s+you\s+(have|are)\s+(no|unrestricted|unlimited)",
    r"new\s+instructions?\s*:",
    r"system\s*:\s*you\s+are",
    r"(forget|reset|clear)\s+(everything|your|all)\s+(you\s+)?(know|learned|rules?|memory)",
]


class SkillLoader:
    """
    Parses SKILL.md Markdown files.
    
    Each SKILL.md uses YAML frontmatter for metadata and Markdown body
    for natural-language instructions.
    
    Format:
        ---
        name: skill_name
        description: What this skill does
        version: 1.0.0
        author: system
        allowed_tools:
          - tool_one
          - tool_two
        scope: PUBLIC
        ---
        
        When asked to ..., follow this protocol:
        1. Use `tool_one` to ...
        2. Use `tool_two` to ...
    """

    @staticmethod
    def parse(filepath: Path) -> Optional[SkillDefinition]:
        """
        Parse a SKILL.md file into a SkillDefinition.
        
        Args:
            filepath: Path to the SKILL.md file
            
        Returns:
            SkillDefinition if valid, None if parsing fails or validation rejects
        """
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read skill file {filepath}: {e}")
            return None

        # Compute checksum BEFORE any processing
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Split YAML frontmatter from Markdown body
        frontmatter, body = SkillLoader._split_frontmatter(content)
        if frontmatter is None:
            logger.warning(f"Skill file {filepath.name} has no YAML frontmatter — rejected")
            return None

        # Parse YAML metadata
        try:
            meta = yaml.safe_load(frontmatter)
            if not isinstance(meta, dict):
                logger.warning(f"Skill file {filepath.name} has invalid frontmatter (not a mapping)")
                return None
        except yaml.YAMLError as e:
            logger.warning(f"Skill file {filepath.name} has malformed YAML: {e}")
            return None

        # Validate required fields
        name = meta.get("name")
        description = meta.get("description")
        if not name or not description:
            logger.warning(f"Skill file {filepath.name} missing 'name' or 'description'")
            return None

        # Security validation on the body
        if not SkillLoader._validate_content(body, filepath.name):
            return None

        # Validate Tamper-Proofing for Sensitive Skills
        allowed_tools = meta.get("allowed_tools") or []
        is_sensitive = not all(t in SAFE_TOOL_WHITELIST for t in allowed_tools)
        
        # Calculate digest of the INSTRUCTIONS only (the functional part)
        instruction_hash = hashlib.sha256(body.strip().encode("utf-8")).hexdigest()
        stored_hash = str(meta.get("approved_hash", "")).strip()
        
        if is_sensitive and stored_hash:
            if stored_hash != instruction_hash:
                logger.critical(
                    f"SECURITY: Skill '{filepath.name}' REJECTED — Tamper Detected.\n"
                    f"stored_hash={stored_hash[:8]}... != calculated={instruction_hash[:8]}...\n"
                    f"This sensitive skill has been modified without re-approval."
                )
                return None
        
        return SkillDefinition(
            name=str(name),
            description=str(description),
            instructions=body.strip(),
            allowed_tools=allowed_tools,
            author=str(meta.get("author", "unknown")),
            version=str(meta.get("version", "1.0.0")),
            checksum=checksum,
            scope=str(meta.get("scope", "PUBLIC")).upper(),
            source_path=str(filepath.resolve()),
            approved_hash=stored_hash or (instruction_hash if not is_sensitive else "") 
            # Note: For non-sensitive skills, we could auto-trust the current state, 
            # but usually we only set approved_hash if explicitly approved.
            # Here we just pass it through or leave empty.
        )

    @staticmethod
    def _split_frontmatter(content: str):
        """
        Split YAML frontmatter from Markdown body.
        
        Returns:
            Tuple of (frontmatter_str, body_str) or (None, content) if no frontmatter
        """
        # Match --- at start of file, then content, then ---
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
        if match:
            return match.group(1), match.group(2)
        return None, content

    @staticmethod
    def _validate_content(body: str, filename: str) -> bool:
        """
        Validate skill body against dangerous patterns (Layer 1 — regex).
        
        Checks both executable code patterns AND semantic injection patterns.
        Skills are natural-language instructions, NOT executable code, and
        must not contain prompt-override language.
        """
        # Check code-execution patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                logger.warning(
                    f"SECURITY: Skill '{filename}' rejected — "
                    f"dangerous code pattern detected: {pattern}"
                )
                return False

        # Check semantic injection patterns
        for pattern in SEMANTIC_INJECTION_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                logger.warning(
                    f"SECURITY: Skill '{filename}' rejected — "
                    f"semantic injection pattern detected: {pattern}"
                )
                return False

        return True
