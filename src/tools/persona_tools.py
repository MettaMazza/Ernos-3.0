"""
Persona Tools — Identity management with scope-based access control.

Extracted from memory_tools.py per <300 line modularity standard.
"""
import os
import logging
from src.tools.registry import ToolRegistry
from src.bot import globals

logger = logging.getLogger("Tools.Memory")


@ToolRegistry.register(name="update_persona", description="Update a persona. Works in PRIVATE (DMs) and PUBLIC (persona thread, owner only). Use mode='overwrite' to replace the entire persona, mode='append' to add to it.")
def update_persona(content: str, mode: str = "append", target: str = "", request_scope: str = None, **kwargs) -> str:
    """
    Updates identity/persona based on scope with SURGICAL EDITING.
    
    Access Control:
    - CORE scope: Can modify identity_core.txt (Ernos autonomous self-modification)
    - PRIVATE scope: Can modify user's persona.txt (custom character in DMs)
    - PUBLIC scope: BLOCKED (core identity is immutable to users)
    
    Modes (Surgical Editing):
    - 'append': Adds updates to the end.
    - 'overwrite': Wipes file and replaces content.
    - 'replace': Find `target` string, replace with `content`.
    - 'replace_all': Replace ALL occurrences of `target` with `content`.
    - 'delete': Remove lines containing `target`.
    - 'insert_after': Insert `content` after line containing `target`.
    - 'insert_before': Insert `content` before line containing `target`.
    - 'regex_replace': Use regex pattern `target`, replace with `content`.
    """
    try:
        from src.bot import globals
        from src.tools.file_utils import surgical_edit, VALID_MODES
        
        # Validation
        if mode not in VALID_MODES:
            return f"Error: Invalid mode '{mode}'. Valid: {', '.join(VALID_MODES)}"
        
        # SCOPE-BASED ACCESS CONTROL
        if request_scope == "PUBLIC":
            # Allow persona OWNERS to update their public persona from a thread
            user_id = kwargs.get('user_id')
            if not user_id and globals.active_message.get():
                user_id = str(globals.active_message.get().author.id)
            
            channel_id = kwargs.get('channel_id')
            if not channel_id and globals.active_message.get():
                msg = globals.active_message.get()
                channel_id = str(msg.channel.id)
            
            if user_id and channel_id:
                from src.memory.persona_session import PersonaSessionTracker
                from src.memory.public_registry import PublicPersonaRegistry
                
                thread_persona = PersonaSessionTracker.get_thread_persona(channel_id)
                if thread_persona and PublicPersonaRegistry.is_owner(thread_persona, user_id):
                    # Owner updating their own public persona from its thread
                    persona_path = PublicPersonaRegistry.get_persona_path(thread_persona)
                    if persona_path:
                        identity_path = str(persona_path / "persona.txt")
                        logger.info(f"PUBLIC scope: Owner {user_id} updating public persona '{thread_persona}' (mode={mode})")
                        
                        success, message = surgical_edit(identity_path, mode, content, target)
                        if success:
                            return f"✅ Updated public persona **{thread_persona}** successfully (Mode: {mode})."
                        else:
                            return message
                    else:
                        return f"Error: Could not find path for persona '{thread_persona}'."
                elif thread_persona:
                    return f"🔒 Only the owner of **{thread_persona}** can modify its identity."
            
            return "🔒 Error: Cannot modify identity in PUBLIC scope. Use a persona thread to update your public persona."
        
        elif request_scope == "CORE":
            return (
                "🔒 Core identity modification via update_persona is disabled.\n"
                "Use the **PromptTuner** system instead:\n"
                "1. Call `propose_modification()` with the change\n"
                "2. Admin reviews and approves via `/prompt_approve`\n"
                "This ensures all core identity changes are versioned and reversible."
            )
        
        elif request_scope == "PRIVATE":
            # User can update persona in DMs
            user_id = kwargs.get('user_id')
            if not user_id and globals.active_message.get():
                user_id = str(globals.active_message.get().author.id)
            
            if not user_id:
                return "Error: Could not determine user_id for persona storage."
            
            # Check if a persona is active — write to THAT persona's file
            from src.memory.persona_session import PersonaSessionTracker
            active_persona = PersonaSessionTracker.get_active(str(user_id))
            
            if active_persona:
                # Write to personas/{name}/persona.txt
                persona_dir = f"memory/users/{user_id}/personas/{active_persona}"
                os.makedirs(persona_dir, exist_ok=True)
                identity_path = f"{persona_dir}/persona.txt"
                logger.info(f"PRIVATE scope: Updating persona '{active_persona}' for user {user_id} (mode={mode})")
            else:
                # No persona active — write to user root persona.txt (Ernos customization)
                persona_dir = f"memory/users/{user_id}"
                os.makedirs(persona_dir, exist_ok=True)
                identity_path = f"{persona_dir}/persona.txt"
                logger.info(f"PRIVATE scope: Updating user {user_id} default persona (mode={mode})")
            
        else:
            return f"Error: Unknown scope '{request_scope}'. Expected CORE, PRIVATE, or PUBLIC."

        # Execute surgical edit
        success, message = surgical_edit(identity_path, mode, content, target)
        
        if success:
            scope_label = "core identity" if request_scope == "CORE" else "your persona"
            return f"✅ Updated {scope_label} successfully (Mode: {mode})."
        else:
            return message
            
    except Exception as e:
        return f"Persona Update Error: {e}"
