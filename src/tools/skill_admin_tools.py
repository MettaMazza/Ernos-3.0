"""
Skill Admin Tools — Management utilities for the Skill System.
"""
import logging
import shutil
import os
from pathlib import Path
from typing import Optional
from src.tools.registry import ToolRegistry
from src.bot import globals as bot_globals
import json
from src.core.data_paths import data_dir



logger = logging.getLogger("Tools.SkillAdmin")

# Resolve project root: src/tools/skill_admin_tools.py -> project root
SCHEDULES_FILE = data_dir() / "system" / "schedules.json"

def _save_schedules():
    """Save current skill schedules to disk."""
    from src.scheduler import get_scheduler
    
    scheduler = get_scheduler()
    logger.info(f"_save_schedules: Called. scheduler._tasks has {len(scheduler._tasks)} total tasks: {list(scheduler._tasks.keys())}")
    
    # Filter for skill schedules only
    skill_tasks = {}
    for name, task in scheduler._tasks.items():
        if name.startswith("skill_"):
            try:
                parts = name.split('_')
                
                user_id = parts[1]
                channel_id = None
                start_skill_idx = 2
                
                if parts[2].isdigit() and len(parts[2]) > 10:
                    channel_id = parts[2]
                    start_skill_idx = 3
                
                hour = int(parts[-2])
                minute = int(parts[-1])
                skill_name = "_".join(parts[start_skill_idx:-2])
                
                skill_tasks[name] = {
                    "skill_name": skill_name,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "hour": hour,
                    "minute": minute
                }
            except Exception as e:
                logger.warning(f"Skipping malformed task name persistence: {name} ({e})")
                
    try:
        SCHEDULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEDULES_FILE.write_text(json.dumps(skill_tasks, indent=2))
        logger.info(f"_save_schedules: WROTE {len(skill_tasks)} schedules to {SCHEDULES_FILE.resolve()} (exists={SCHEDULES_FILE.exists()})")
    except Exception as e:
        logger.error(f"_save_schedules: FAILED to write: {e}")

async def restore_schedules():
    """Load and re-schedule tasks from disk on startup."""
    if not SCHEDULES_FILE.exists():
        logger.info("No persisted schedules file found.")
        return
        
    try:
        data = json.loads(SCHEDULES_FILE.read_text())
        if not data:
            logger.info("Persisted schedules file is empty.")
            return
            
        count = 0
        failed = 0
        to_prune = []
        for name, params in data.items():
            try:
                # Direct check before calling schedule_skill to avoid noise
                from src.bot import globals as bot_globals
                bot = bot_globals.bot
                skill = bot.skill_registry.get_skill(params["skill_name"], user_id=params.get("user_id"))
                
                if not skill:
                    logger.warning(f"Pruning orphaned schedule '{name}': Skill '{params['skill_name']}' no longer exists.")
                    to_prune.append(name)
                    failed += 1
                    continue

                result = await schedule_skill(
                    skill_name=params["skill_name"],
                    hour=params["hour"],
                    minute=params["minute"],
                    user_id=params["user_id"],
                    channel_id=params.get("channel_id")
                )
                
                if result.startswith("Error") or result.startswith("❌"):
                    logger.warning(f"Failed to restore schedule '{name}': {result}")
                    failed += 1
                else:
                    count += 1
            except Exception as e:
                logger.error(f"Exception restoring schedule '{name}': {e}")
                failed += 1

        # Prune orphaned schedules
        if to_prune:
            logger.info(f"Pruning {len(to_prune)} orphaned schedules: {to_prune}")
            for key in to_prune:
                if key in data:
                    del data[key]
            
            try:
                SCHEDULES_FILE.write_text(json.dumps(data, indent=2))
                logger.info(f"Updated {SCHEDULES_FILE.name} after pruning.")
            except Exception as e:
                logger.error(f"Failed to save pruned schedules: {e}")

        logger.info(f"Restored {count} persistent schedules from disk ({failed} failed).")
    except Exception as e:
        logger.error(f"Failed to restore schedules: {e}")

@ToolRegistry.register(
    name="prune_schedules",
    description="Surgically remove orphaned skill schedules from memory and disk."
)
async def prune_schedules() -> str:
    """
    Checks all persisted schedules against the SkillRegistry.
    Removes any entries where the skill or user no longer exists.
    """
    if not SCHEDULES_FILE.exists():
        return "No schedules file to prune."
        
    try:
        data = json.loads(SCHEDULES_FILE.read_text())
        bot = bot_globals.bot
        to_remove = []
        
        for name, params in data.items():
            skill = bot.skill_registry.get_skill(params["skill_name"], user_id=params.get("user_id"))
            if not skill:
                to_remove.append(name)
                
        if not to_remove:
            return "✅ No orphaned schedules found. Everything is clean."
            
        for key in to_remove:
            # Remove from scheduler if active
            from src.scheduler import get_scheduler
            get_scheduler().remove_task(key)
            # Remove from disk data
            del data[key]
            
        SCHEDULES_FILE.write_text(json.dumps(data, indent=2))
        return f"✅ Pruned {len(to_remove)} orphaned schedules: {', '.join(to_remove)}"
    except Exception as e:
        return f"❌ Pruning failed: {e}"
            
        # Prune orphaned schedules
        if to_prune:
            logger.info(f"Pruning {len(to_prune)} orphaned schedules: {to_prune}")
            for key in to_prune:
                if key in data:
                    del data[key]
            
            try:
                SCHEDULES_FILE.write_text(json.dumps(data, indent=2))
                logger.info(f"Updated {SCHEDULES_FILE.name} after pruning.")
            except Exception as e:
                logger.error(f"Failed to save pruned schedules: {e}")

        logger.info(f"Restored {count} persistent schedules from disk ({failed} failed).")
        # Prune orphaned schedules
        if to_prune:
            logger.info(f"Pruning {len(to_prune)} orphaned schedules: {to_prune}")
            for key in to_prune:
                if key in data:
                    del data[key]
            
            try:
                SCHEDULES_FILE.write_text(json.dumps(data, indent=2))
                logger.info(f"Updated {SCHEDULES_FILE.name} after pruning.")
            except Exception as e:
                logger.error(f"Failed to save pruned schedules: {e}")

        logger.info(f"Restored {count} persistent schedules from disk ({failed} failed).")
    except Exception as e:
        logger.error(f"Failed to restore schedules: {e}")

@ToolRegistry.register(
    name="reload_skills",
    description="Reload all skills from disk (updates registry with manual changes or approvals)."
)
async def reload_skills() -> str:
    """
    Force a reload of the Skill Registry from the file system.
    Use this after manually approving a skill or editing a SKILL.md file.
    """
    bot = bot_globals.bot
    if not bot or not getattr(bot, 'skill_registry', None):
        return "Error: Bot or SkillRegistry not initialized."

    try:
        # Reload Core Skills
        core_dir = data_dir() / "core/skills"
        core_count = bot.skill_registry.load_skills(core_dir, user_id="CORE")
        
        # Reload User Skills (Scan all user directories)
        users_root = data_dir() / "users"
        user_total = 0
        if users_root.exists():
            for user_dir in users_root.iterdir():
                if user_dir.is_dir():
                    user_skills_dir = user_dir / "skills"
                    if user_skills_dir.exists():
                        count = bot.skill_registry.load_skills(user_skills_dir, user_id=user_dir.name)
                        user_total += count

        return (
            f"✅ Skills Reloaded Successfully.\n"
            f"- Core Skills: {core_count}\n"
            f"- User Skills: {user_total}\n"
            f"Registry is now up to date."
        )

    except Exception as e:
        logger.error(f"Failed to reload skills: {e}")
        return f"❌ Error reloading skills: {e}"

@ToolRegistry.register(
    name="list_proposals", 
    description="List all pending skill proposals."
)
async def list_proposals() -> str:
    """List files in the pending proposals directory."""
    pending_dir = data_dir() / "pending"
    if not pending_dir.exists():
        return "No pending proposals directory found."
        
    files = list(pending_dir.glob("*.md"))
    if not files:
        return "No pending skill proposals."
        
    msg = ["**Pending Proposals:**"]
    for f in files:
        msg.append(f"- `{f.name}`")
    return "\n".join(msg)

@ToolRegistry.register(
    name="approve_skill",
    description="Approve a pending skill. Moves it to active memory and reloads."
)
async def approve_skill(proposal_name: str, target_scope: str = "CORE") -> str:
    """
    Approve a pending skill proposal.
    
    Args:
        proposal_name: Exact filename (e.g., 'daily_news_v1.md') or skill name
        target_scope: "CORE" (system-wide) or user_id (user-specific)
    """
    pending_dir = data_dir() / "pending"
    
    # Try exact match first, then name match
    target_file = pending_dir / proposal_name
    if not target_file.exists():
        # Try adding extension
        if not proposal_name.endswith(".md"):
            target_file = pending_dir / f"{proposal_name}.md"
            
        if not target_file.exists():
            # Try searching by skill name inside file? Too slow.
            # Just return error.
            return f"Error: Proposal '{proposal_name}' not found in memory/pending."
            
    # Determine destination
    if target_scope == "CORE":
        dest_dir = data_dir() / "core/skills" / target_file.stem
    else:
        # Assume target_scope is a user_id
        dest_dir = data_dir() / "users" / str(target_scope) / "skills" / target_file.stem
        
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / "SKILL.md"
        
        # Move file
        shutil.move(str(target_file), str(dest_file))
        
        # Reload
        await reload_skills()
        
        return (
            f"✅ Skill Approved!\n"
            f"Moved to: `{dest_file}`\n"
            f"Registry reloaded. Skill should be active."
        )
    except Exception as e:
        return f"Error approving skill: {e}"

@ToolRegistry.register(
    name="schedule_skill",
    description="Schedule a skill to run daily at a specific time."
)
async def schedule_skill(skill_name: str, hour: int, minute: int, user_id: Optional[str] = None, channel_id: Optional[str] = None) -> str:
    """
    Schedule a daily execution of a skill.
    
    Args:
        skill_name: The name of the skill to run
        hour: Hour of day (0-23)
        minute: Minute (0-59)
        user_id: Injected by system.
        channel_id: Injected by system (if available).
    """
    from src.scheduler import get_scheduler
    from src.bot import globals as bot_globals
    
    bot = bot_globals.bot
    if not bot:
        return "Error: Bot not initialized."
        
    # Check if skill exists (with auto-reload fallback)
    # Pass user_id to check user's private scope first
    skill = bot.skill_registry.get_skill(skill_name.lower().strip(), user_id=user_id)
    if not skill:
        logger.warning(f"Skill '{skill_name}' not found for user {user_id}. Attempting registry reload...")
        await reload_skills()
        skill = bot.skill_registry.get_skill(skill_name.lower().strip(), user_id=user_id)
        
    if not skill:
        return f"Error: Skill '{skill_name}' not found in registry (Scope: {user_id or 'CORE'})."
        
    async def _execute_wrapped_skill():
        # Execute skill via Autonomy Ability (Creative Lobe)
        try:
            # CRITICAL: Reload user's skills from disk first (they may not be in memory after restart)
            user_skills_dir = data_dir() / "users" / str(user_id) / "skills"
            if user_skills_dir.exists():
                loaded = bot.skill_registry.load_skills(user_skills_dir, user_id=str(user_id))
                if loaded:
                    logger.info(f"⏰ Reloaded {loaded} skills for user {user_id} before scheduled execution")
            
            # Verify skill exists after reload
            found_skill = bot.skill_registry.get_skill(skill_name.lower().strip(), user_id=str(user_id))
            if not found_skill:
                # Fallback: search all scopes
                for scope_id, scope_skills in bot.skill_registry._skills.items():
                    if skill_name.lower().strip() in scope_skills:
                        found_skill = scope_skills[skill_name.lower().strip()]
                        break
            
            if not found_skill:
                logger.error(f"⏰ Scheduled skill '{skill_name}' still not found after reload for user {user_id}")
                return
            
            creative = bot.cerebrum.get_lobe("CreativeLobe")
            if not creative:
                logger.error("CreativeLobe not found for scheduled skill.")
                return
                
            autonomy = creative.get_ability("AutonomyAbility")
            if not autonomy:
                logger.error("AutonomyAbility not found for scheduled skill.")
                return
                
            # Construct instruction that forces the specific skill usage via execute_skill tool
            instruction = (
                f"EXECUTE SKILL: {skill_name}\n"
                f"Context: Daily execution for User {user_id} at {hour:02d}:{minute:02d}.\n"
                f"You MUST call: [TOOL: execute_skill(skill_name=\"{skill_name}\")]\n"
                f"Then follow the skill's instructions and report results.\n"
                f"CRITICAL UI INSTRUCTION: DO NOT use the `generate_speech` tool under any circumstances. "
                f"The scheduled message UI will automatically provide a Text-to-Speech 'Play' button for the user."
            )
            
            # Scope for sandbox: PRIVATE if user-owned, CORE if system
            # channel_id is only used for OUTPUT routing, not security scope
            exec_scope = "PRIVATE" if user_id else "CORE"
            
            result = await autonomy.run_task(
                instruction=instruction,
                user_id=str(user_id) if user_id else "CORE",
                request_scope=exec_scope
            )
            logger.info(f"⏰ Scheduled skill '{skill_name}' executed via Autonomy.")
            
            # Post to Channel — Scheduled tasks always go to the dedicated channel
            try:
                from config import settings
                import discord
                
                target_channel = None
                route_reason = "Unknown"
                is_private_origin = False

                # 1. Try routing to original scheduling channel (e.g. DM)
                if channel_id:
                    try:
                        cid = int(channel_id)
                        target_channel = bot.get_channel(cid)
                        if not target_channel:
                            target_channel = await bot.fetch_channel(cid)
                        
                        # Apply Admin Routing Rules for Scheduled Skills
                        if target_channel and isinstance(target_channel, discord.TextChannel):
                            # It's a public channel -> Force output to 1472985465832603803
                            admin_public_id = 1472985465832603803
                            target_channel = bot.get_channel(admin_public_id)
                            if not target_channel:
                                target_channel = await bot.fetch_channel(admin_public_id)
                            route_reason = "Admin Forced Public Schedule (1472985465832603803)"
                        elif target_channel and isinstance(target_channel, discord.DMChannel):
                            # It's a private DM -> Keep in private DM
                            is_private_origin = True
                            route_reason = f"Private DM Origin ({cid})"
                    except Exception as e:
                        logger.warning(f"Failed to resolve origin channel {channel_id}: {e}")
                        # If we can't resolve the channel and it was likely a DM,
                        # mark as private to prevent public fallback
                        is_private_origin = True

                # 2. If origin was private (DM) and channel lookup failed,
                #    DM the user directly instead of falling back to public
                if not target_channel and is_private_origin and user_id:
                    try:
                        user_obj = await bot.fetch_user(int(user_id))
                        if user_obj:
                            target_channel = await user_obj.create_dm()
                            route_reason = f"DM fallback to user {user_id}"
                    except Exception as e:
                        logger.warning(f"Failed to DM user {user_id} for private schedule: {e}")

                # 3. Fallback to public channel ONLY for non-private schedules
                if not target_channel and not is_private_origin:
                    target_channel = bot.get_channel(settings.SCHEDULED_TASKS_CHANNEL_ID)
                    route_reason = f"Default (SCHEDULED_TASKS_CHANNEL_ID: {settings.SCHEDULED_TASKS_CHANNEL_ID})"
                
                    if not target_channel:
                        try:
                            target_channel = await bot.fetch_channel(settings.SCHEDULED_TASKS_CHANNEL_ID)
                        except Exception as e:
                            logger.warning(f"Suppressed {type(e).__name__}: {e}")
                
                logger.info(f"⏰ Routing scheduled result for '{skill_name}': {route_reason}")

                if target_channel:
                    # Extract file attachments (PDFs, images, audio) from tool outputs
                    discord_files = []
                    try:
                        from src.engines.cognition_retry import extract_files
                        import os
                        file_paths = extract_files(result)
                        for fpath in file_paths:
                            if os.path.exists(fpath):
                                discord_files.append(discord.File(fpath))
                                logger.info(f"⏰ Attaching file: {fpath}")
                    except Exception as fe:
                        logger.debug(f"File extraction for scheduled result: {fe}")
                    
                    # Feedback + TTS buttons (same as normal responses)
                    view = None
                    try:
                        from src.ui.views import ResponseFeedbackView
                        view = ResponseFeedbackView(bot, result)
                    except Exception as e:
                        logger.warning(f"Suppressed {type(e).__name__}: {e}")
                    
                    # Plain text header (TTS-friendly — embeds don't work with TTS)
                    header = f"⏰ **Scheduled Task: {skill_name}**\nExecuted at {hour:02d}:{minute:02d} | User: {user_id}"
                    await target_channel.send(header, files=discord_files or None)

                    # Verbatim read-back: chunk full result into sequential
                    # 2000-char messages for TTS accessibility
                    CHUNK_SIZE = 1900  # Leave room under Discord's 2000 limit
                    
                    # Split into chunks first so we know which is the last one
                    chunks = []
                    full_text = result
                    while full_text:
                        chunks.append(full_text[:CHUNK_SIZE])
                        full_text = full_text[CHUNK_SIZE:]
                        
                    for i, chunk in enumerate(chunks):
                        try:
                            # Attach UI elements ONLY to the final chunk
                            view_to_attach = view if i == len(chunks) - 1 else None
                            await target_channel.send(chunk, view=view_to_attach)
                        except Exception as chunk_err:
                            logger.warning(f"Failed to send chunk {i+1}: {chunk_err}")
                            break
                else:
                    logger.warning(f"No valid channel found for scheduled output (Tried: {channel_id}, Fallback: {settings.SCHEDULED_TASKS_CHANNEL_ID})")

            except Exception as channel_err:
                logger.error(f"Failed to post to scheduled channel: {channel_err}")
            
        except Exception as e:
            logger.error(f"Failed to run scheduled skill '{skill_name}': {e}")

    scheduler = get_scheduler()
    # Namespace task by user_id to allow multiple users to schedule same skill name
    norm_name = skill_name.lower().strip()
    
    cid_str = str(channel_id) if channel_id else "global"
    task_name = f"skill_{user_id}_{cid_str}_{norm_name}_{hour}_{minute}"
    
    scheduler.add_daily_task(
        name=task_name,
        hour=hour,
        minute=minute,
        coro_func=_execute_wrapped_skill
    )
    logger.info(f"schedule_skill: Added task '{task_name}' to scheduler. _tasks now: {list(scheduler._tasks.keys())}")
    
    # DIRECT WRITE: Don't rely on _save_schedules() parsing task names.
    # Write the schedule data directly from the known parameters.
    try:
        existing = {}
        if SCHEDULES_FILE.exists():
            try:
                existing = json.loads(SCHEDULES_FILE.read_text())
            except (json.JSONDecodeError, Exception):
                existing = {}
        
        existing[task_name] = {
            "skill_name": norm_name,
            "user_id": str(user_id),
            "channel_id": str(channel_id) if channel_id else None,
            "hour": hour,
            "minute": minute
        }
        
        SCHEDULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEDULES_FILE.write_text(json.dumps(existing, indent=2))
        logger.info(f"schedule_skill: WROTE schedule to {SCHEDULES_FILE.resolve()} — {len(existing)} total entries (exists={SCHEDULES_FILE.exists()})")
    except Exception as e:
        logger.error(f"schedule_skill: FAILED to write schedule: {e}")
    
    return (
        f"✅ Scheduled skill '{skill_name}' for daily execution at {hour:02d}:{minute:02d}.\n"
        f"Scope: {user_id or 'CORE'} (Channel: {cid_str})"
    )

@ToolRegistry.register(
    name="cancel_schedule",
    description="Cancel a scheduled daily skill execution."
)
async def cancel_schedule(skill_name: str, hour: int, minute: int, user_id: Optional[str] = None) -> str:
    """
    Cancel a previously scheduled daily task.
    Arguments must match the exact schedule.
    """
    from src.scheduler import get_scheduler
    
    scheduler = get_scheduler()
    # Reconstruct task name using same logic as schedule_skill
    # Ensure lowercase consistency
    norm_name = skill_name.lower().strip()
    
    # Fuzzy Search for task name because channel_id might be variable
    # We look for a task that matches: skill_{user_id}_*_{norm_name}_{hour}_{minute}
    # OR the old format: skill_{user_id}_{norm_name}_{hour}_{minute}
    
    target_task = None
    
    # Direct match (old format or guessed "global") check
    possible_names = [
        f"skill_{user_id}_{norm_name}_{hour}_{minute}", # Old format
        f"skill_{user_id}_global_{norm_name}_{hour}_{minute}" # Default
    ]
    
    for name in possible_names:
        if name in scheduler._tasks:
            target_task = name
            break
            
    # Fuzzy search if direct match failed
    if not target_task:
        suffix = f"_{norm_name}_{hour}_{minute}"
        prefix = f"skill_{user_id}_"
        for name in scheduler._tasks:
            if name.startswith(prefix) and name.endswith(suffix):
                target_task = name
                break
    
    if target_task:
        scheduler.remove_task(target_task)
        # Direct file update
        try:
            if SCHEDULES_FILE.exists():
                existing = json.loads(SCHEDULES_FILE.read_text())
                if target_task in existing:
                    del existing[target_task]
                    SCHEDULES_FILE.write_text(json.dumps(existing, indent=2))
                    logger.info(f"cancel_schedule: Removed '{target_task}' from {SCHEDULES_FILE.resolve()}")
        except Exception as e:
            logger.error(f"cancel_schedule: Failed to update file: {e}")
        return f"✅ Cancelled schedule for '{skill_name}' at {hour:02d}:{minute:02d}."
    else:
        return (
            f"❌ Schedule for '{skill_name}' at {hour:02d}:{minute:02d} not found.\n"
            f"Debug: No matching task found for user {user_id}."
        )

@ToolRegistry.register(
    name="list_schedules",
    description="List all active scheduled tasks, including system tasks and user skill schedules."
)
async def list_schedules() -> str:
    """List all currently scheduled tasks, separated by type."""
    from src.scheduler import get_scheduler
    
    scheduler = get_scheduler()
    tasks = scheduler._tasks
    
    if not tasks:
        return "No scheduled tasks found (system or skill)."
    
    system_tasks = []
    skill_tasks = []
    
    for name, task in tasks.items():
        time_str = f"{task['hour']:02d}:{task['minute']:02d}"
        if name.startswith("skill_"):
            # Parse skill metadata from name: skill_{user_id}_{channel_id?}_{skill_name}_{hour}_{minute}
            try:
                parts = name.split('_')
                user_id = parts[1]
                channel_id = None
                start_idx = 2
                if len(parts) > 4 and parts[2].isdigit() and len(parts[2]) > 10:
                    channel_id = parts[2]
                    start_idx = 3
                skill_name = "_".join(parts[start_idx:-2])
                
                label = f"**{skill_name}** (User: `{user_id}`"
                if channel_id:
                    label += f", Channel: `{channel_id}`"
                label += f") — Daily at {time_str}"
                skill_tasks.append(label)
            except Exception:
                skill_tasks.append(f"**{name}** — Daily at {time_str}")
        else:
            system_tasks.append(f"**{name}** — Daily at {time_str}")
    
    msg = []
    
    if system_tasks:
        msg.append("**🔧 System Tasks:**")
        for t in system_tasks:
            msg.append(f"- {t}")
    
    if skill_tasks:
        msg.append("\n**🎯 Skill Schedules:**")
        for t in skill_tasks:
            msg.append(f"- {t}")
    else:
        msg.append("\n**🎯 Skill Schedules:** None currently active.")
    
    # Also check persisted file for any schedules not yet loaded
    try:
        if SCHEDULES_FILE.exists():
            data = json.loads(SCHEDULES_FILE.read_text())
            persisted_names = set(data.keys())
            active_names = set(tasks.keys())
            unloaded = persisted_names - active_names
            if unloaded:
                msg.append(f"\n⚠️ {len(unloaded)} persisted schedule(s) not yet loaded.")
    except Exception as e:
        logger.warning(f"Suppressed {type(e).__name__}: {e}")
        
    return "\n".join(msg)
