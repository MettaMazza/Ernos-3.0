"""
Privacy Guard - Scope Enforcement Decorators
Ensures PUBLIC scope cannot access PRIVATE or CORE data.
"""
import functools
import logging
from typing import Callable, Any
from .scopes import PrivacyScope, ScopeManager
from src.core.data_paths import data_dir

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
    
    user_path = Path(str(data_dir()) + f"/users/{folder_name}")
    
    # If folder with this ID already exists under a different name, find it
    users_dir = data_dir() / "users"
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
    if scope == PrivacyScope.CORE_PRIVATE:
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
    
    DENY-BY-DEFAULT for all memory/ paths:
    - memory/public/                         -> PUBLIC (anyone)
    - memory/core/research|media|exports|skills -> PUBLIC (Ernos's shareable artifacts)
    - memory/core/**                         -> CORE only
    - memory/users/{id}/                     -> ONLY the owning user or CORE
    - memory/users/{id}/projects/public/     -> PUBLIC (user's public projects)
    - memory/users/{id}/research/public/     -> PUBLIC (user's public research)
    - memory/backups/**                      -> CORE only
    - memory/cache/**                        -> CORE only
    - memory/chroma/**                       -> CORE only
    - memory/system/**                       -> CORE only
    - memory/debug*                          -> CORE only
    - memory/security*                       -> CORE only
    - memory/quarantine*                     -> CORE only
    - memory/** (anything else)              -> CORE only (deny-by-default)
    - Non-memory paths (src/, docs/, etc.)   -> PUBLIC (readable by all)
    
    CRITICAL PRIVACY: PRIVATE users can ONLY access their own user folder.
    Cross-user access (User A reading User B's files) is blocked.
    
    Args:
        path: File path being accessed
        request_scope: Scope of the requester
        user_id: Requesting user's ID (required for PRIVATE scope user folder access)
        
    Returns:
        True if access is allowed, False otherwise
    """
    import re
    import os
    from urllib.parse import unquote
    
    # ── PATH NORMALIZATION — PREVENT TRAVERSAL ATTACKS ──────────────────
    # 1. Normalize backslashes to forward slashes
    normalized = path.replace("\\", "/")
    # 2. Percent-decode (e.g. %2F → /)
    normalized = unquote(normalized)
    # 3. Strip null bytes, newlines, and control characters
    normalized = re.sub(r'[\x00-\x1f\x7f]', '', normalized)
    # 4. Resolve ../ traversal via os.path.normpath (converts a/b/../c → a/c)
    normalized = os.path.normpath(normalized).replace("\\", "/")
    
    path_lower = normalized.lower()
    
    # ── TRAVERSAL ESCAPE DETECTION ──────────────────────────────────────
    # If original path referenced memory/ but normpath resolved outside it,
    # this is a breakout attack (e.g. memory/public/../../backups/master.json → backups/master.json)
    original_lower = path.lower().replace("\\", "/")
    original_references_memory = "memory/" in original_lower or original_lower.startswith("memory")
    normalized_references_memory = "memory/" in path_lower or path_lower.startswith("memory")
    if original_references_memory and not normalized_references_memory:
        logger.warning(
            f"TRAVERSAL ESCAPE BLOCKED: path '{path}' normalized to '{normalized}' "
            f"(escaped memory/ boundary)"
        )
        return False
    
    # Reject paths that resolve to parent directory escape
    if path_lower.startswith(".."):
        return False  # Breaking out of project root
    
    # ── NON-MEMORY PATHS ────────────────────────────────────────────────
    # src/, docs/, config/, etc. are PUBLIC — Ernos can read its own code
    if path_lower.startswith("src/") or path_lower.startswith("tests/") or path_lower.startswith("docs/"):
        return True
        
    if "memory/" not in path_lower and not path_lower.startswith("memory"):
        return True  # PUBLIC access
    
    # ── ALL MEMORY PATHS — DENY-BY-DEFAULT ──────────────────────────────
    
    # 1. memory/public/ → PUBLIC (anyone can access)
    if "memory/public" in path_lower:
        return True  # PUBLIC access
    
    # 2. memory/core/ → Check for shareable artifact sub-dirs
    if "memory/core" in path_lower:
        _SELF_ARTIFACT_DIRS = (
            "memory/core/research", "memory/core/media",
            "memory/core/exports", "memory/core/skills",
        )
        if any(d in path_lower for d in _SELF_ARTIFACT_DIRS):
            return True  # PUBLIC access — Ernos's shareable artifacts
        # Everything else under memory/core → CORE only
        resource_scope = PrivacyScope.CORE_PRIVATE
        return ScopeManager.check_access(request_scope, resource_scope)
    
    # 3. memory/users/{id}/ → PRIVATE with cross-user blocking
    if "memory/users" in path_lower:
        # Public project artifacts are readable from any scope
        if ("/projects/public/" in path_lower or "/research/public/" in path_lower
                or path_lower.endswith("/projects/public") or path_lower.endswith("/research/public")):
            return True  # PUBLIC access
        
        resource_scope = PrivacyScope.PRIVATE
        
        # CROSS-USER ACCESS CHECK: Extract target user_id from path
        match = re.search(r'memory/users/(\d+)', path_lower)
        if match and user_id:
            path_user_id = match.group(1)
            if str(user_id) != path_user_id and request_scope != PrivacyScope.CORE_PRIVATE:
                logger.warning(
                    f"CROSS-USER ACCESS BLOCKED: User {user_id} tried to access "
                    f"User {path_user_id}'s files at {path}"
                )
                return False
        elif match and not user_id:
            # No user_id provided — block all user directories unless CORE
            if request_scope != PrivacyScope.CORE_PRIVATE:
                return False
        elif not match:
            # Path is memory/users/ itself (listing the directory) — block unless CORE
            if request_scope != PrivacyScope.CORE_PRIVATE:
                logger.warning(
                    f"USER DIRECTORY LISTING BLOCKED: scope={request_scope.name} "
                    f"tried to list {path}"
                )
                return False
        
        return ScopeManager.check_access(request_scope, resource_scope)
    
    # 4. ALL OTHER memory/ PATHS → CORE ONLY (deny-by-default)
    #    This covers: memory/backups/, memory/cache/, memory/chroma/,
    #    memory/system/, memory/debug*, memory/security*, memory/quarantine*,
    #    and any future memory/ subdirectories.
    logger.warning(
        f"MEMORY PATH BLOCKED (deny-by-default): scope={request_scope.name} "
        f"user={user_id} tried to access {path}"
    )
    resource_scope = PrivacyScope.CORE_PRIVATE
    return ScopeManager.check_access(request_scope, resource_scope)
