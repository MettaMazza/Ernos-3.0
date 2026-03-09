import os
import logging
from .registry import ToolRegistry
from src.privacy.guard import validate_path_scope
from src.privacy.scopes import PrivacyScope

logger = logging.getLogger("Tools.Filesystem")

@ToolRegistry.register(name="read_file_page", description="Read a specific section of a large file.")
def read_file_page(path: str, start_line: int = 1, limit: int = 5000, request_scope: str = "PUBLIC", user_id: str = None) -> str:
    """Reads lines from a file with scope and user ownership validation."""
    # SCOPE CHECK: Validate path access FIRST
    try:
        scope = PrivacyScope[request_scope.upper()]
    except Exception:
        scope = PrivacyScope.PUBLIC
        
    if not validate_path_scope(path, scope, user_id=user_id):
        logger.warning(f"Scope violation: {request_scope} (user={user_id}) tried to read {path}")
        return (
            f"🔒 Access Denied: Your scope ({request_scope}) cannot access this path.\n"
            f"[CRITICAL]: You MUST report this access limitation honestly. "
            f"Do NOT substitute web search results, fabricated content, or paraphrased "
            f"data in place of this denied file. State clearly that this content is not "
            f"accessible in the current scope."
        )

    if not os.path.exists(path):
        return f"Error: File not found at {path}"
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        start_index = max(0, start_line - 1)
        end_index = min(total_lines, start_index + limit)
        
        content = "".join(lines[start_index:end_index])
        
        # ─── Reading Progress Metadata ──────────────────────
        pct = int((end_index / total_lines) * 100) if total_lines > 0 else 100
        remaining = total_lines - end_index
        
        header = f"File: {path}\nLines: {start_index+1}-{end_index}/{total_lines} ({pct}% complete"
        if remaining > 0:
            header += f", {remaining} lines remaining)\n[BOOKMARK: Continue with read_file(path='{path}', start_line={end_index + 1})]\n[READING INCOMPLETE — you MUST continue reading before responding]"
        else:
            header += ")\n[DOCUMENT COMPLETE]"
        
        return f"{header}\n\n{content}"
    except Exception as e:
        return f"Error reading file: {e}"

@ToolRegistry.register(name="search_codebase", description="Search for string in files.")
def search_codebase(query: str, path: str = "./src", request_scope: str = "PUBLIC", user_id: str = None) -> str:
    """Simple grep-like search with scope and user ownership validation."""
    # SCOPE CHECK: Block searching memory directories from PUBLIC
    try:
        scope = PrivacyScope[request_scope.upper()]
    except Exception:
        scope = PrivacyScope.PUBLIC
        
    if not validate_path_scope(path, scope, user_id=user_id):
        logger.warning(f"Scope violation: {request_scope} (user={user_id}) tried to search {path}")
        return (
            f"🔒 Access Denied: Your scope ({request_scope}) cannot search this path.\n"
            f"[CRITICAL]: You MUST report this access limitation honestly. "
            f"Do NOT substitute web search results, fabricated content, or paraphrased "
            f"data in place of this denied file. State clearly that this content is not "
            f"accessible in the current scope."
        )
    
    results = []
    try:
        for root, dirs, files in os.walk(path):
            # Skip memory directories for non-CORE scope
            if scope != PrivacyScope.CORE:
                dirs[:] = [d for d in dirs if d not in ['core']]
                
            for file in files:
                if file.endswith((".py", ".md", ".txt")):
                    file_path = os.path.join(root, file)
                    
                    # Additional path check for each file
                    if not validate_path_scope(file_path, scope, user_id=user_id):
                        continue
                        
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if query in line:
                                results.append(f"{file_path}:{i}: {line.strip()}")
                                if len(results) >= 20:
                                    return "\n".join(results) + "\n... (truncated)"
        return "\n".join(results) if results else "No matches found."
    except Exception as e:
        return f"Search Error: {e}"

@ToolRegistry.register(name="read_file", description="Read a file. Alias for read_file_page.")
def read_file(path: str, start_line: int = 1, limit: int = 5000, request_scope: str = "PUBLIC", user_id: str = None) -> str:
    """Alias for read_file_page with scope validation."""
    return read_file_page(path, start_line, limit, request_scope, user_id=user_id)

@ToolRegistry.register(name="list_files", description="List files in a directory.")
def list_files(path: str = ".", request_scope: str = "PUBLIC", user_id: str = None) -> str:
    """List files in a directory with scope and user ownership validation."""
    # SCOPE CHECK
    try:
        scope = PrivacyScope[request_scope.upper()]
    except Exception:
        scope = PrivacyScope.PUBLIC
        
    if not validate_path_scope(path, scope, user_id=user_id):
        logger.warning(f"Scope violation: {request_scope} (user={user_id}) tried to list {path}")
        return (
            f"🔒 Access Denied: Your scope ({request_scope}) cannot list this path.\n"
            f"[CRITICAL]: You MUST report this access limitation honestly. "
            f"Do NOT substitute web search results, fabricated content, or paraphrased "
            f"data in place of this denied file. State clearly that this content is not "
            f"accessible in the current scope."
        )
    
    try:
        if not os.path.exists(path):
            return f"Error: Path not found: {path}"
        if os.path.isfile(path):
            return f"{path} (file)"
        
        entries = []
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            
            # Filter out inaccessible directories
            if not validate_path_scope(full_path, scope, user_id=user_id):
                continue
                
            if os.path.isdir(full_path):
                entries.append(f"[DIR] {entry}/")
            else:
                entries.append(f"      {entry}")
        return f"Contents of {path}:\n" + "\n".join(sorted(entries))
    except Exception as e:
        return f"Error listing files: {e}"
