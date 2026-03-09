"""
Prompt Manager — Builds multi-tiered system prompts.

Trinity Stack: Kernel (Laws) -> Architecture (Body) -> Identity (Soul)
HUD data loading delegated to hud_loaders module.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger("PromptManager")

class PromptManager:
    """Manages the multi-tiered system prompt (Kernel, Identity, Dynamic Context)."""
    
    def __init__(self, prompt_dir: str = "./src/prompts"):
        self.prompt_dir = prompt_dir
        self.kernel_file = os.path.join(prompt_dir, "kernel.txt")
        self.architecture_file = os.path.join(prompt_dir, "architecture.txt")
        self.identity_file = os.path.join(prompt_dir, "identity.txt")
        self.identity_core_file = os.path.join(prompt_dir, "identity_core.txt")
        self.dynamic_file = os.path.join(prompt_dir, "dynamic_context.txt")
        self.dynamic_fork_file = os.path.join(prompt_dir, "dynamic_context_fork.txt")
        self.manual_file = os.path.join(prompt_dir, "user_manual.txt")
    
    def _read_file(self, filepath: str) -> str:
        """Read a file, returning empty string on failure."""
        if not filepath:
            return ""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {filepath}")
            return ""
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return ""
    
    def _check_user_has_custom_identity(self, user_id: str) -> bool:
        """Check if user has a custom identity/persona configured."""
        if not user_id or user_id == "Unknown":
            return False
        try:
            from src.privacy.scopes import ScopeManager
            user_home = ScopeManager.get_user_home(user_id)
            persona_path = user_home / "persona.txt"
            
            if persona_path.exists():
                with open(persona_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    return bool(content)
        except Exception:
            pass
        return False
    
    def _generate_tool_manifest(self) -> str:
        """
        Dynamically generates a complete tool manifest from ToolRegistry.
        Ensures LLM knows about ALL available tools, not just hardcoded ones.
        """
        try:
            from src.tools.registry import ToolRegistry
            tools = ToolRegistry.list_tools()
            
            if not tools:
                return ""
            
            manifest_lines = ["## AVAILABLE TOOLS\n"]
            for tool in tools:
                name = tool.name
                desc = tool.description
                params = tool.parameters or {}
                
                param_str = ""
                if params:
                    param_parts = []
                    for pname, ptype in params.items():
                        param_parts.append(f"  - {pname}: {ptype}")
                    param_str = "\n".join(param_parts)
                
                manifest_lines.append(f"### {name}\n{desc}")
                if param_str:
                    manifest_lines.append(param_str)
                manifest_lines.append("")
            
            return "\n".join(manifest_lines)
        except Exception as e:
            logger.error(f"Tool manifest generation failed: {e}")
            return ""
    
    def get_system_prompt(self, 
                          timestamp: str = "Unknown",
                          scope: str = "PUBLIC",
                          user_id: str = "Unknown",
                          user_name: str = "Unknown",
                          active_engine: str = "Unknown",
                          system_state_content: str = "",
                          active_goals: str = "",
                          working_memory_summary: str = "",
                          is_core: bool = False,
                          persona_name: str = None
                          ) -> str:
        """
        Combines Kernel, Architecture, Identity, and formatted Dynamic Context.
        The "Trinity Stack": Kernel (Laws) -> Architecture (Body) -> Identity (Soul).
        """
        kernel = self._read_file(self.kernel_file)
        architecture = self._read_file(self.architecture_file)
        manual = self._read_file(self.manual_file)
        # Populate template variables in architecture
        try:
            architecture = architecture.format(
                version=getattr(self, '_version', '3.1 (Synapse Bridge)')
            )
        except (KeyError, IndexError):
            pass  # If no template variables, leave as-is
        
        # SCOPE-AWARE IDENTITY LOADING
        identity = ""
        is_persona_mode = bool(persona_name)
        
        if is_persona_mode:
            # PERSONA THREAD/DM: Load persona identity, NOT Ernos's
            from src.memory.public_registry import PublicPersonaRegistry
            persona_path = PublicPersonaRegistry.get_persona_path(persona_name)
            if persona_path and (persona_path / "persona.txt").exists():
                identity = self._read_file(str(persona_path / "persona.txt"))
                logger.info(f"Loaded public persona identity: {persona_name}")
            if not identity and user_id and user_id != "Unknown":
                # Check user's private persona silo (for DM personas)
                from src.privacy.scopes import ScopeManager
                try:
                    user_root = ScopeManager._resolve_user_dir(user_id)
                    private_persona_file = user_root / "personas" / persona_name / "persona.txt"
                    if private_persona_file.exists():
                        identity = self._read_file(str(private_persona_file))
                        logger.info(f"Loaded private persona identity: {persona_name} for user {user_id}")
                except Exception:
                    pass
            if not identity:
                identity = f"You are {persona_name.title()}. You are a unique AI persona."
            # NO legacy identity appended for personas — they are isolated
        elif scope == "PRIVATE" and user_id and user_id != "Unknown":
            from src.privacy.scopes import ScopeManager
            user_home = ScopeManager.get_user_home(user_id)
            user_persona_path = user_home / "persona.txt"
            
            if user_persona_path.exists():
                identity = self._read_file(str(user_persona_path))
                logger.info(f"Loaded custom persona for user {user_id}")
        
        if not identity:
            identity = self._read_file(self.identity_core_file)
            # Append any dynamic identity additions (legacy compatibility)
            legacy_identity = self._read_file(self.identity_file)
            if legacy_identity:
                identity += "\n\n" + legacy_identity
        
        # HUD TEMPLATE SELECTION
        # Personas and private custom identities use the stripped fork HUD
        # Ernos (default) uses the full HUD with terminal, SoC, etc.
        has_custom_identity = self._check_user_has_custom_identity(user_id) if scope == "PRIVATE" else False
        if is_persona_mode or has_custom_identity:
            dynamic_template = self._read_file(self.dynamic_fork_file)
            logger.info(f"Using fork HUD for {'persona:' + persona_name if is_persona_mode else 'user:' + user_id}")
        else:
            dynamic_template = self._read_file(self.dynamic_file)
        
        # Generate dynamic tool manifest from registry
        tool_manifest = self._generate_tool_manifest()
        
        # Inject dynamic salt rotation date into identity
        try:
            from src.security.provenance import ProvenanceManager
            salt_date = ProvenanceManager.get_salt_rotation_date()
            identity = identity.replace("{salt_rotation_date}", salt_date)
        except Exception:
            identity = identity.replace("{salt_rotation_date}", "UNKNOWN")
        
        # Determine View Mode
        view_mode = "GOD VIEW" if is_core else "USER HUD"
        
        # Load HUD data from extracted loaders
        from .hud_loaders import load_ernos_hud, load_fork_hud, load_persona_hud
        
        if is_persona_mode:
            # Persona threads get ONLY persona-scoped HUD — no Ernos data
            hud = load_persona_hud(persona_name)
        else:
            hud = load_ernos_hud(scope, user_id, is_core)
        
        # Fork HUD (user-specific data for private personas)
        fhud = {}
        if has_custom_identity and not is_persona_mode and user_id and user_id != "Unknown":
            fhud = load_fork_hud(user_id, user_name)
        
        # Build default fork HUD values for template
        fork_defaults = {
            "conversation_summary": "No prior conversations recorded.",
            "recent_topics": "None tracked.",
            "relationship_context": "New relationship - no established context.",
            "user_preferences": "No preferences recorded.",
            "first_interaction": "Unknown",
            "message_count": "0",
            "full_conversation_history": "No conversation history.",
            "topic_history": "No topics tracked.",
            "recurring_themes": "No recurring themes identified.",
            "unfinished_threads": "No unfinished threads.",
            "user_interests": "Unknown",
            "user_values": "Unknown",
            "user_style": "Unknown",
            "questions_asked": "No questions recorded.",
            "private_glossary": "No shared vocabulary.",
            "nicknames": "None",
            "emotional_tone": "Neutral",
            "connection_moments": "None recorded.",
            "sensitive_topics": "None flagged.",
            "implicit_patterns": "No patterns detected.",
            "avoided_topics": "None identified.",
            "promises_made": "None recorded.",
            "remember_next": "Nothing flagged.",
            "open_questions": "None pending.",
            "identity_in_relationship": "Standard persona.",
            "your_role": "Conversational partner.",
            "current_persona_content": "No custom persona defined. Use update_persona to create one.",
        }
        
        # Merge fork data over defaults
        fork_data = {**fork_defaults, **fhud}
        
        # Populate Template
        formatted_dynamic = ""
        if dynamic_template:
            try:
                formatted_dynamic = dynamic_template.format(
                    timestamp=timestamp,
                    scope=scope,
                    user_id=user_id,
                    user_name=user_name,
                    active_engine=active_engine,
                    view_mode=view_mode,
                    system_state_content=system_state_content or "System Nominal.",
                    active_goals=active_goals or "None active.",
                    working_memory_summary=working_memory_summary or "Empty.",
                    # Ernos HUD
                    **hud,
                    # Fork HUD
                    **fork_data,
                )
            except Exception as e:
                formatted_dynamic = f"[Template Error: Missing key {e}]\n{dynamic_template}"
                formatted_dynamic += f"\n\n[SYSTEM AWARENESS]\nTERM:\n{hud.get('terminal_tail', '')}\nERRORS:\n{hud.get('error_log', '')}\nACTIVITY:\n{hud.get('activity_tail', '')}"
        
        # Inject Roster always at bottom of context
        formatted_dynamic += f"\n\n### ROOM ROSTER (Verified Identities)\nActive Users: {hud.get('room_roster', 'Unavailable')}\n(Source: memory/public/timeline.log)"
        
        parts = []
        if kernel: parts.append(kernel)
        if tool_manifest: parts.append(tool_manifest)
        
        # Inject Official User Manual (Single Source of Truth)
        if manual:
             parts.append(f"=== OFFICIAL USER MANUAL & SYSTEM GUIDE ===\n{manual}\n===========================================")

        if architecture: parts.append(architecture)
        if identity: parts.append(identity)
        if formatted_dynamic: parts.append(formatted_dynamic)
        
        return "\n\n".join(parts)
