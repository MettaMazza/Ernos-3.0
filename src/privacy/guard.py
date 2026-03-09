"""
Privacy Guard - Scope Enforcement Decorators
Ensures PUBLIC scope cannot access PRIVATE or CORE data.
"""
import functools
import logging
from typing import Callable, Any
from .scopes import PrivacyScope, ScopeManager

logger = logging.getLogger("Privacy.Guard")


def scope_protected(required_scope: PrivacyScope):
    """
    Decorator to enforce scope on functions that access scoped data.
    
    Usage:
        @scope_protected(PrivacyScope.PRIVATE)
        async def read_user_data(user_id: int, request_scope: PrivacyScope = None):
            ...
    
    The decorated function MUST accept `request_scope` as a kwarg.
    If request_scope lacks permission, returns Access Denied message.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, request_scope: PrivacyScope = None, **kwargs):
            # Default to PUBLIC (most restrictive for callers)
            if request_scope is None:
                request_scope = PrivacyScope.PUBLIC
                
            # Check permission
            if not ScopeManager.check_access(request_scope, required_scope):
                logger.warning(
                    f"Access Denied: {request_scope.name} tried to access {required_scope.name} resource in {func.__name__}"
                )
                return f"🔒 Access Denied: {required_scope.name} data requires higher privileges."
            
            # Permission granted
            return await func(*args, request_scope=request_scope, **kwargs)
        return wrapper
    return decorator


def get_user_silo_path(user_id: int, username: str = None) -> str:
    """
    Get or create user-specific memory silo path with username for identification.
    
    Format: memory/users/{id}_{sanitized_username}/
    Falls back to: memory/users/{id}/ if no username provided
    
    The username is sanitized to remove special characters for filesystem safety.
    """
    import os
    import re
    from pathlib import Path
    
    if username and isinstance(username, str):
        # Sanitize username: keep alphanumeric, underscores, dashes only
        safe_username = re.sub(r'[^a-zA-Z0-9_-]', '', username.lower())
        folder_name = f"{user_id}_{safe_username}"
    else:
        folder_name = str(user_id)
    
    user_path = Path(f"memory/users/{folder_name}")
    
    # If folder with this ID already exists under a different name, find it
    users_dir = Path("memory/users")
    if users_dir.exists():
        for existing in users_dir.iterdir():
            if existing.is_dir() and existing.name.startswith(str(user_id)):
                # Found existing folder for this user ID
                return str(existing)
    
    return str(user_path)


def scope_write_path(scope: PrivacyScope, user_id: int = None, username: str = None) -> str:
    """
    Get the appropriate write path for a given scope.
    
    Args:
        scope: The privacy scope of the operation
        user_id: Optional user ID for user-specific paths
        
    Returns:
        Base path for the scope
    """
    if scope == PrivacyScope.CORE:
        return "memory/core"
    elif scope == PrivacyScope.PRIVATE and user_id:
        return get_user_silo_path(user_id, username)
    elif scope == PrivacyScope.PUBLIC:
        return "memory/public"
    else:
        return "memory/public"  # Default to PUBLIC (safest)


def validate_path_scope(path: str, request_scope: PrivacyScope, user_id: str = None) -> bool:
    """
    Validate that a path is accessible by the given scope and user.
    
    Protected paths:
    - memory/core -> CORE only
    - memory/users/{id}/ -> ONLY the owning user (matched by user_id) or CORE
    - memory/public/ -> PUBLIC, PRIVATE, or CORE
    - Everything else (src/, docs/, etc.) -> PUBLIC (readable by all)
    
    CRITICAL PRIVACY: PRIVATE users can ONLY access their own user folder.
    Cross-user access (User A reading User B's files) is blocked.
    
    Args:
        path: File path being accessed
        request_scope: Scope of the requester
        user_id: Requesting user's ID (required for PRIVATE scope user folder access)
        
    Returns:
        True if access is allowed, False otherwise
    """
    path_lower = path.lower()
    
    # Determine resource scope from path
    if "memory/core" in path_lower:
        # Ernos's own autonomy-generated artifacts — shareable from any scope
        # These are research files, images, exports, and skills Ernos created himself.
        # Everything else under memory/core (identity, drives, context, keys) stays CORE-only.
        _SELF_ARTIFACT_DIRS = ("memory/core/research", "memory/core/media",
                               "memory/core/exports", "memory/core/skills")
        if any(d in path_lower for d in _SELF_ARTIFACT_DIRS):
            resource_scope = PrivacyScope.PUBLIC
        else:
            resource_scope = PrivacyScope.CORE
    elif "memory/users" in path_lower:
        # Public project artifacts are readable from any scope
        if "/projects/public/" in path_lower:
            resource_scope = PrivacyScope.PUBLIC
        else:
            resource_scope = PrivacyScope.PRIVATE
        
        # CROSS-USER ACCESS CHECK: Extract target user_id from path
        # Path format: memory/users/{user_id}/ or memory/users/{user_id}_{username}/
        import re
        match = re.search(r'memory/users/(\d+)', path_lower)
        if match and user_id:
            path_user_id = match.group(1)
            if str(user_id) != path_user_id and request_scope != PrivacyScope.CORE:
                logger.warning(f"CROSS-USER ACCESS BLOCKED: User {user_id} tried to access User {path_user_id}'s files")
                return False
        elif match and not user_id:
            # No user_id provided — block access to all user directories
            if request_scope != PrivacyScope.CORE:
                return False
                
    elif "memory/public" in path_lower:
        resource_scope = PrivacyScope.PUBLIC
    else:
        # Non-memory paths (src/, docs/, config/, etc.) are PUBLIC
        # This allows Ernos to read its own source code
        resource_scope = PrivacyScope.PUBLIC
    
    return ScopeManager.check_access(request_scope, resource_scope)
