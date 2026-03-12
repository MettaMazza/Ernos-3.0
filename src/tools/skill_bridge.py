"""
Skill Bridge — Exposes the Skills Framework to the Cognition Engine.

This tool acts as the adapter between the LLM's tool usage and the
internal SkillSandbox. It strictly enforces the sandbox's security model.
"""
from src.tools.registry import ToolRegistry
import logging

logger = logging.getLogger("Tools.SkillBridge")

@ToolRegistry.register(
    name="execute_skill",
    description=(
        "Execute a specialized skill (Standard Operating Procedure). "
        "Skills are pre-defined workflows for complex tasks like plan execution or efficient coding. "
        "Args: skill_name (str), context (str - optional additional context for the skill)."
    ),
)
async def execute_skill(skill_name: str, context: str = "", **kwargs) -> str:
    """
    Execute a registered skill via the Sandbox.
    
    Returns the skill's INSTRUCTIONS, which the LLM must then follow.
    It does NOT execute the work automatically; it loads the 'software' 
    (instructions) into the 'hardware' (LLM context).
    """
    from src.bot import globals
    bot = globals.bot
    if not bot: return "Error: Bot not initialized."
    
    # 1. Resolve Skill
    # Extract user_id for scope-aware lookup
    user_id = kwargs.get("user_id")
    skill = bot.skill_registry.get_skill(skill_name, user_id=str(user_id) if user_id else None)
    
    if not skill:
        available = ", ".join(s.name for s in bot.skill_registry.list_skills(user_id=str(user_id) if user_id else None))
        return f"Error: Skill '{skill_name}' not found. Available skills: {available}"

    # 2. Extract Security Context
    request_scope = kwargs.get("request_scope", "PUBLIC")
    
    if not user_id:
        return "Error: execute_skill requires a valid user_id for permission checks."

    # 3. Execute via Sandbox
    # The sandbox performs permission checks, rate limiting, and logging.
    result = bot.skill_sandbox.execute(
        skill=skill,
        context=context,
        user_id=user_id,
        scope=request_scope
    )
    
    if not result.success:
        return f"Skill Execution Denied: {result.error}"
        
    # 4. Return Instructions
    return result.output
