"""
Skill definition types for the Skills Framework.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SkillDefinition:
    """
    A parsed skill definition from a SKILL.md file.
    
    Skills are natural-language instructions that guide the LLM's tool usage
    within a whitelisted boundary. They cannot execute arbitrary code.
    """
    name: str
    description: str
    instructions: str
    allowed_tools: List[str] = field(default_factory=list)
    author: str = "unknown"
    version: str = "1.0.0"
    checksum: str = ""         # SHA256 of the SKILL.md file
    scope: str = "PUBLIC"      # Minimum PrivacyScope required to use this skill
    source_path: str = ""      # Absolute path to the SKILL.md file

    def __repr__(self):
        return f"Skill({self.name} v{self.version} by {self.author}, {len(self.allowed_tools)} tools)"


@dataclass
class SkillExecutionResult:
    """Result of a sandboxed skill execution."""
    success: bool
    output: str
    tools_used: List[str] = field(default_factory=list)
    error: Optional[str] = None
    skill_name: str = ""
    user_id: str = ""
    scope: str = ""
