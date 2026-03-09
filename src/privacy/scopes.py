from enum import Enum
from config import settings
import logging

logger = logging.getLogger("Privacy")

class PrivacyScope(Enum):
    CORE = 1
    PRIVATE = 2
    PUBLIC = 3
    OPEN = 4 # Default if disabled


from pathlib import Path

class ScopeManager:
    """Manages file system paths for user scopes."""
    
    @staticmethod
    def _resolve_user_dir(user_id: int) -> Path:
        """
        Internal: Resolves the root user directory (no persona routing).
        Format: memory/users/{user_id}/
        
        Special case: "CORE" string maps to memory/core/
        """
        base = Path("memory")
        
        if user_id == "CORE" or user_id is None:
             path = base / "core"
        else:
             # Search for existing folder starting with ID
             # This supports folders like "123456" OR "123456-Username"
             users_dir = base / "users"
             users_dir.mkdir(parents=True, exist_ok=True)
             
             # Look for matching directory
             found = list(users_dir.glob(f"{user_id}*"))
             if found:
                 # Prioritize exact match or first found
                 # Use the first one found that is a directory
                 for p in found:
                     if p.is_dir():
                         path = p
                         break
                 else:
                     path = users_dir / str(user_id)
             else:
                 path = users_dir / str(user_id)
             
        # Ensure it exists
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_user_home(user_id: int, channel_id: int = None) -> Path:
        """
        Returns the home directory for a specific user.
        
        If channel_id is provided and the channel has a thread-bound persona,
        returns the public persona directory. If the user has an active
        persona in DMs, returns the persona sub-silo. Otherwise returns
        the root user directory.
        """
        root = ScopeManager._resolve_user_dir(user_id)
        
        if user_id != "CORE" and user_id is not None:
            try:
                from src.memory.persona_session import PersonaSessionTracker
                
                # Thread-scoped persona (public threads)
                if channel_id:
                    thread_persona = PersonaSessionTracker.get_thread_persona(str(channel_id))
                    if thread_persona:
                        from src.memory.public_registry import PublicPersonaRegistry
                        public_path = PublicPersonaRegistry.get_persona_path(thread_persona)
                        if public_path:
                            return public_path
                        # Fallback: check user's private personas
                        persona_path = root / "personas" / thread_persona
                        if persona_path.is_dir():
                            return persona_path
                
                # DM-scoped persona (existing behavior)
                active_persona = PersonaSessionTracker.get_active(str(user_id))
                if active_persona:
                    persona_path = root / "personas" / active_persona
                    persona_path.mkdir(parents=True, exist_ok=True)
                    return persona_path
            except ImportError:
                pass  # Module not available — use root
        
        return root

    @staticmethod
    def get_user_root_home(user_id: int) -> Path:
        """
        Always returns the ROOT user directory, bypassing persona routing.
        
        Use this for data that should be shared across all personas:
        - PROFILE.md (user info)
        - usage.json (rate limits)
        - relationship data
        """
        return ScopeManager._resolve_user_dir(user_id)

    @staticmethod
    def get_public_user_silo(user_id: int) -> Path:
        """
        Returns the PUBLIC silo for a specific user.
        Format: memory/public/users/{user_id}/
        """
        path = Path("memory") / "public" / "users" / str(user_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_scope(user_id: int, channel_id: int, is_dm: bool = False) -> PrivacyScope:
        """Determines context scope based on CHANNEL TYPE, not user identity.
        
        - DM channels (is_dm=True) -> PRIVATE
        - Guild channels -> PUBLIC
        - CORE IDENTITY -> CORE
        """
        if not settings.ENABLE_PRIVACY_SCOPES:
            return PrivacyScope.OPEN
            
        # CORE Identity overrides Channel Logic
        if user_id == "CORE":
            return PrivacyScope.CORE
        
        # DMs are PRIVATE, guild channels are PUBLIC
        if is_dm:
            return PrivacyScope.PRIVATE
        
        return PrivacyScope.PUBLIC

    @staticmethod
    def check_access(request_scope: PrivacyScope, resource_scope: PrivacyScope) -> bool:
        """
        Check if request scope has permission to access resource scope.
        Hierarchy: CORE > PRIVATE > PUBLIC
        """
        if not settings.ENABLE_PRIVACY_SCOPES:
            return True
            
        # CORE sees everything
        if request_scope == PrivacyScope.CORE:
            return True
            
        # PRIVATE sees PRIVATE + PUBLIC
        if request_scope == PrivacyScope.PRIVATE:
            return resource_scope in (PrivacyScope.PRIVATE, PrivacyScope.PUBLIC)
            
        # PUBLIC sees ONLY PUBLIC
        # Regular users are PUBLIC scope
        if request_scope == PrivacyScope.PUBLIC:
            return resource_scope == PrivacyScope.PUBLIC
            
        return False

