"""
Skill Forge Tool — Exposes creation capabilities to the LLM.
"""
import logging
import discord
from typing import List, Optional
from src.tools.registry import ToolRegistry
from src.bot import globals as bot_globals
from config import settings
from src.core.data_paths import data_dir

logger = logging.getLogger("Tools.SkillForge")

@ToolRegistry.register(name="propose_skill", description=(
    "Propose a new skill (Standard Operating Procedure). "
    "Args: name (str, snake_case), description (str), instructions (str — SEE FORMAT BELOW), "
    "allowed_tools (list[str]), scope ('PRIVATE'|'PUBLIC'). "
    "\n\n**INSTRUCTIONS FORMAT — Your 'instructions' argument MUST be structured as a multi-phase "
    "Markdown SOP with the following pattern:**\n"
    "```\n"
    "# Skill Name vX.0\n"
    "> Output: [what the skill delivers]\n"
    "> Tone/Style: [stylistic guidance]\n\n"
    "## PHASE 1: [NAME] (Purpose)\n"
    "1. `tool_name` — What to do with it and what data to extract.\n"
    "2. `tool_name` — Next step, referencing output from step 1.\n"
    "**Checkpoint**: What should be true before moving to Phase 2.\n\n"
    "## PHASE 2: [NAME] (Purpose)\n"
    "3. `tool_name` — Continue numbering across phases.\n"
    "...\n\n"
    "## QUALITY GATES\n"
    "- [ ] Gate 1\n"
    "- [ ] Gate 2\n"
    "```\n\n"
    "**Rules**: Minimum 3 phases. Number ALL tool calls sequentially across phases. "
    "Include checkpoints between phases. End with quality gates. "
    "Each tool call must specify WHAT to do and WHY. "
    "Never create a skill with fewer than 5 chained tool calls. "
    "Never dump instructions as a single paragraph."
))
async def propose_skill(
    name: str, 
    description: str, 
    instructions: str, 
    allowed_tools: Optional[List[str]] = None, 
    scope: str = "PRIVATE",
    target_user_id: Optional[str] = None,
    user_id: Optional[str] = None,
    turn_id: Optional[str] = None
) -> str:
    """
    Propose a new skill.
    
    If successful, the skill is either immediately active (Private + Safe) 
    or sent to #ernos-proposals for approval.
    
    Args:
        name: Skill name (snake_case)
        description: Brief description
        instructions: The SOP/Prompts for the skill
        allowed_tools: List of tools the skill can use
        scope: "PRIVATE" or "PUBLIC"
        target_user_id: The user this skill is for (defaults to caller)
        user_id: The caller's ID (injected by system)
        turn_id: The unique ID of the cognitive cycle (injected by system)
    """
    bot = bot_globals.bot
    if not bot or not bot.skill_forge:
        return "Error: SkillForge is not initialized on the bot."

    # Resolve actual owner
    owner_id = str(target_user_id) if target_user_id else str(user_id)
    
    # --- Rate Limit Check: One Per Turn ---
    # We use the turn_id to strictly enforce "one creation per cognitive cycle".
    if not hasattr(propose_skill, "_turn_tracker"):
         propose_skill._turn_tracker = {} # user_id -> last_turn_id
    
    # Only exempt TRUE autonomy (bot calling itself). Admins are NOT exempt.
    bot_id = str(bot.user.id) if bot.user else None
    is_autonomy = user_id is None or (bot_id and str(user_id) == bot_id)
    
    logger.debug(f"Rate limit check: user_id={user_id}, owner_id={owner_id}, turn_id={turn_id}, is_autonomy={is_autonomy}, bot_id={bot_id}")
    
    if not is_autonomy and turn_id:
        last_turn = propose_skill._turn_tracker.get(owner_id)
        if last_turn == turn_id:
            logger.warning(f"RATE LIMIT HIT: user {owner_id} already proposed a skill on turn {turn_id}")
            return f"RATE LIMIT: You have already proposed a skill this turn. Only ONE proposal is allowed per cognitive cycle."
        
        # Mark this turn as "consumed" for this user
        propose_skill._turn_tracker[owner_id] = turn_id
    elif not is_autonomy and not turn_id:
        # No turn_id means we can't track — enforce a fallback: block if ANY recent proposal exists
        logger.warning(f"RATE LIMIT FALLBACK: No turn_id provided for user {owner_id}. Checking time-based guard.")
        import time
        if not hasattr(propose_skill, "_time_tracker"):
            propose_skill._time_tracker = {}
        last_time = propose_skill._time_tracker.get(owner_id, 0)
        if time.time() - last_time < 30:  # 30 second cooldown as fallback
            logger.warning(f"RATE LIMIT (time-based): user {owner_id} proposed a skill {time.time() - last_time:.0f}s ago")
            return f"RATE LIMIT: You have already proposed a skill recently. Please wait before proposing another."
        propose_skill._time_tracker[owner_id] = time.time()
    # ------------------------
    
    # Robust Parsing for allowed_tools (handle string input from LLM)
    if allowed_tools is None:
        allowed_tools = []
    elif isinstance(allowed_tools, str):
        import json
        import ast
        try:
            # Try JSON
            allowed_tools = json.loads(allowed_tools)
        except (json.JSONDecodeError, ValueError):
            try:
                # Try Python literal (e.g. "['tool1', 'tool2']")
                allowed_tools = ast.literal_eval(allowed_tools)
            except (ValueError, SyntaxError):
                # Fallback: simple split if it looks like a comma-list
                if "," in allowed_tools and "[" not in allowed_tools:
                    allowed_tools = [t.strip() for t in allowed_tools.split(",")]
                else:
                    # Last resort: treat as single item list if cleaned
                    clean = allowed_tools.strip("[]\"' ")
                    if clean:
                         allowed_tools = [clean]
                    else:
                         allowed_tools = []
                         
    # Ensure it's a list
    if not isinstance(allowed_tools, list):
        allowed_tools = [str(allowed_tools)]

    # 1. Create Proposal
    try:
        result = bot.skill_forge.propose_skill(
            name=name,
            description=description,
            instructions=instructions,
            allowed_tools=allowed_tools,
            user_id=owner_id,
            scope=scope
        )
    except Exception as e:
        logger.error(f"SkillForge proposal failed: {e}")
        return f"Error proposing skill: {e}"

    status = result["status"]
    skill_name = result["name"]
    
    # Handle deduplication block
    if status == "duplicate_blocked":
        return f"⚠️ Skill '{skill_name}' already exists. Use a different name or modify the existing skill."
    
    is_public = result["scope"] == "PUBLIC"
    
    # 2. Handle Pending (Notify Admin Channel)
    if status == "pending":
        channel_id = settings.SKILL_PROPOSALS_CHANNEL_ID
        channel = bot.get_channel(channel_id)
        
        msg = (
            f"✅ **Skill successfully proposed!**\n"
            f"It has been sent to the Council for approval."
        )
        
        if channel:
            embed = discord.Embed(
                title="📜 New Skill Proposal",
                description=f"**{skill_name}** ({result['scope']})",
                color=0xF1C40F  # Pending Gold
            )
            embed.add_field(name="Author", value=f"<@{owner_id}>", inline=True)
            embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="Tools", value=", ".join(allowed_tools), inline=False)
            embed.add_field(name="Status", value="PENDING APPROVAL", inline=True)
            
            # Identify why it's pending
            reasons = []
            if is_public:
                reasons.append("Scope is PUBLIC")
            if not result.get("is_safe_whitelisted"):
                reasons.append("Uses Restricted Tools")
            
            embed.set_footer(text=f"Reason: {', '.join(reasons)}")
            
            try:
                # Post to proposals channel
                await channel.send(embed=embed)
                
                # Also upload the instruction file content for easier review
                # Or just truncate if short
                if len(instructions) < 1000:
                    await channel.send(f"```markdown\n{instructions}\n```")
                else:
                    await channel.send(f"*(Instructions length: {len(instructions)} chars - Check file system)*")
                    
            except Exception as e:
                logger.error(f"Failed to post proposal to Discord: {e}")
                msg += f"\n(Warning: Failed to post to proposals channel: {e})"
        else:
            logger.warning(f"Proposals channel {channel_id} not found")
            msg += f"\n(Warning: Proposals channel not found)"

        return msg

    # 3. Handle Active (Auto-Approved)
    elif status == "active":
        # Check if we need to reload registry
        # The registry loads only at startup usually. 
        # But we can try to manually register it if we have access to registry.
        try:
            # We don't have direct access to registry here, but bot does
            # bot.skill_registry.load_skills(data_dir() / "users...", owner_id)
            # This is expensive. Maybe just register single skill?
            # We need to PARSE the file we just wrote.
            path = result["file_path"]
            from pathlib import Path
            from src.skills.loader import SkillLoader
            
            skill_def = SkillLoader.parse(Path(path))
            if skill_def:
                bot.skill_registry.register_skill(skill_def, user_id=owner_id)
                logger.info(f"Hot-reloaded skill {skill_name} for user {owner_id}")
        except Exception as e:
            logger.warning(f"Hot-reload failed: {e}")
            
        return (
            f"✅ **Skill '{skill_name}' Created & Auto-Approved!**\n"
            f"Scope: {scope} (Private)\n"
            f"You can now use it via `execute_skill(skill_name='{skill_name}')`."
        )

    return f"Skill status unknown: {status}"


@ToolRegistry.register(name="edit_skill", description=(
    "Edit an existing skill you own. "
    "Args: name (str, the skill to edit), plus at least one of: "
    "instructions (str, new SOP body), description (str, new description), "
    "allowed_tools (list[str], new tool list). "
    "Only fields you provide will be updated; others remain unchanged. "
    "Version is auto-bumped. If restricted tools are added, the edit goes to pending approval."
))
async def edit_skill(
    name: str,
    instructions: Optional[str] = None,
    description: Optional[str] = None,
    allowed_tools: Optional[List[str]] = None,
    user_id: Optional[str] = None,
    turn_id: Optional[str] = None
) -> str:
    """
    Edit an existing skill.
    
    Args:
        name: Skill name to edit
        instructions: New instructions/SOP (optional)
        description: New description (optional)
        allowed_tools: New tool list (optional)
        user_id: The caller's ID (injected by system)
        turn_id: The unique ID of the cognitive cycle (injected by system)
    """
    bot = bot_globals.bot
    if not bot or not bot.skill_forge:
        return "Error: SkillForge is not initialized on the bot."
    
    if not user_id:
        return "Error: Could not determine your user ID."
    
    owner_id = str(user_id)
    
    # Parse allowed_tools if passed as string
    if allowed_tools is not None and isinstance(allowed_tools, str):
        import json as _json
        import ast
        try:
            allowed_tools = _json.loads(allowed_tools)
        except (ValueError, _json.JSONDecodeError):
            try:
                allowed_tools = ast.literal_eval(allowed_tools)
            except (ValueError, SyntaxError):
                if "," in allowed_tools:
                    allowed_tools = [t.strip() for t in allowed_tools.split(",")]
                elif "|" in allowed_tools:
                    allowed_tools = [t.strip() for t in allowed_tools.split("|")]
                else:
                    allowed_tools = [allowed_tools.strip("[]\"' ")]
    
    if allowed_tools is not None and not isinstance(allowed_tools, list):
        allowed_tools = [str(allowed_tools)]
    
    # Delegate to SkillForge
    try:
        result = bot.skill_forge.edit_skill(
            name=name,
            user_id=owner_id,
            instructions=instructions,
            description=description,
            allowed_tools=allowed_tools,
        )
    except Exception as e:
        logger.error(f"SkillForge edit failed: {e}")
        return f"Error editing skill: {e}"
    
    status = result["status"]
    skill_name = result["name"]
    
    if status == "not_found":
        return f"❌ Skill '{skill_name}' not found. Check the name and try again."
    
    if status == "parse_error":
        return f"❌ Skill '{skill_name}' could not be parsed. The file may be corrupted."
    
    if status == "no_changes":
        return f"⚠️ No changes provided. Specify at least one of: instructions, description, allowed_tools."
    
    if status == "rejected":
        return f"🚫 Edit rejected: {result.get('error', 'Content validation failed.')}"
    
    if status == "pending":
        return (
            f"⏳ **Skill '{skill_name}' edited but requires re-approval.**\n"
            f"Reason: Uses restricted tools.\n"
            f"The edit has been sent to the Council for review."
        )
    
    if status == "active":
        fields = ", ".join(result.get("fields_updated", []))
        version = result.get("version", "?")
        return (
            f"✅ **Skill '{skill_name}' updated to v{version}!**\n"
            f"Updated: {fields}\n"
            f"Changes are live immediately."
        )
    
    return f"Edit status unknown: {status}"

