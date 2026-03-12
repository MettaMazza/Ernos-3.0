"""
Surgical File Editing Utilities

Shared functions for surgical file operations used by
update_persona, create_program, and other file tools.
"""
import os
import re
import logging

logger = logging.getLogger("Tools.FileUtils")


def surgical_edit(filepath: str, mode: str, content: str = "", target: str = "") -> tuple[bool, str]:
    """
    Perform surgical file edits.
    
    Args:
        filepath: Path to the file
        mode: Edit mode (append, overwrite, replace, delete, insert_after, insert_before)
        content: New content to write/insert
        target: Pattern to find (for replace/delete/insert operations)
    
    Returns:
        (success: bool, message: str)
    """
    try:
        # Read existing content if file exists
        existing = ""
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                existing = f.read()
        
        # Execute mode-specific operation
        if mode == "append":
            new_content = existing + ("\n" if existing and not existing.endswith("\n") else "") + content
            
        elif mode == "overwrite":
            new_content = content
            
        elif mode == "replace":
            if not target:
                return False, "Error: 'target' parameter required for replace mode."
            if target not in existing:
                # NEVER auto-overwrite — this hides bugs and damages data.
                # Return an error with diagnostic info so the caller can fix the target.
                preview = existing[:80].replace('\n', '\\n') if existing else "(empty file)"
                return False, (
                    f"Error: Replace target not found in '{os.path.basename(filepath)}'. "
                    f"Target starts with: '{target[:80]}...'. "
                    f"File starts with: '{preview}...'. "
                    f"Use mode='overwrite' explicitly if you intend to replace the entire file."
                )
            else:
                new_content = existing.replace(target, content, 1)  # Replace first occurrence
            
        elif mode == "replace_all":
            if not target:
                return False, "Error: 'target' parameter required for replace_all mode."
            if target not in existing:
                return False, f"Error: Target '{target[:50]}...' not found in file."
            new_content = existing.replace(target, content)  # Replace all occurrences
            
        elif mode == "delete":
            if not target:
                return False, "Error: 'target' parameter required for delete mode."
            lines = existing.split("\n")
            new_lines = [line for line in lines if target not in line]
            if len(new_lines) == len(lines):
                return False, f"Error: No lines containing '{target[:50]}...' found."
            new_content = "\n".join(new_lines)
            
        elif mode == "insert_after":
            if not target:
                return False, "Error: 'target' parameter required for insert_after mode."
            lines = existing.split("\n")
            new_lines = []
            inserted = False
            for line in lines:
                new_lines.append(line)
                if target in line and not inserted:
                    new_lines.append(content)
                    inserted = True
            if not inserted:
                return False, f"Error: Target line '{target[:50]}...' not found."
            new_content = "\n".join(new_lines)
            
        elif mode == "insert_before":
            if not target:
                return False, "Error: 'target' parameter required for insert_before mode."
            lines = existing.split("\n")
            new_lines = []
            inserted = False
            for line in lines:
                if target in line and not inserted:
                    new_lines.append(content)
                    inserted = True
                new_lines.append(line)
            if not inserted:
                return False, f"Error: Target line '{target[:50]}...' not found."
            new_content = "\n".join(new_lines)
            
        elif mode == "regex_replace":
            if not target:
                return False, "Error: 'target' parameter required for regex_replace mode."
            try:
                new_content, count = re.subn(target, content, existing)
                if count == 0:
                    return False, f"Error: Regex pattern '{target[:50]}...' had no matches."
            except re.error as e:
                return False, f"Error: Invalid regex pattern - {e}"
                
        else:
            return False, f"Error: Unknown mode '{mode}'. Valid: append, overwrite, replace, replace_all, delete, insert_after, insert_before, regex_replace"
        
        # Write the result
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        return True, f"Successfully applied '{mode}' operation."
        
    except Exception as e:
        logger.error(f"Surgical edit failed: {e}")
        return False, f"Edit Error: {e}"


VALID_MODES = ["append", "overwrite", "replace", "replace_all", "delete", "insert_after", "insert_before", "regex_replace"]
