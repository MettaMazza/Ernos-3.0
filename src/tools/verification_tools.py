"""
Verification Tools — Post-execution checks for work quality.

Provides verify_files and verify_syntax tools so Ernos can
confirm its work before reporting completion.
"""
import os
import logging
from pathlib import Path

from .registry import ToolRegistry

logger = logging.getLogger("Tools.Verification")


@ToolRegistry.register(
    name="verify_files",
    description="Verify that created/modified files exist and are non-empty."
)
def verify_files(paths: str, user_id: str = None, **kwargs) -> str:
    """
    Check that files exist and report their status.
    Args:
        paths: Pipe-separated file paths to verify (relative to project root)
    """
    file_list = [p.strip() for p in paths.split("|") if p.strip()]
    if not file_list:
        return "No files to verify."

    cwd = Path(os.getcwd()).resolve()
    results = []
    all_ok = True

    for fp in file_list:
        full = (cwd / fp).resolve()

        # Security: ensure path is within project
        if not str(full).startswith(str(cwd)):
            results.append(f"⚠️ {fp}: path outside project directory")
            all_ok = False
            continue

        if full.exists():
            size = full.stat().st_size
            if size == 0:
                results.append(f"⚠️ {fp}: exists but EMPTY (0 bytes)")
                all_ok = False
            else:
                try:
                    line_count = len(full.read_text().splitlines())
                except Exception:
                    line_count = "?"
                results.append(f"✅ {fp}: {size} bytes, {line_count} lines")
        else:
            results.append(f"❌ {fp}: MISSING")
            all_ok = False

    summary = "All files verified ✅" if all_ok else "⚠️ Some files have issues"
    results.append(f"\n{summary}")
    return "\n".join(results)


@ToolRegistry.register(
    name="verify_syntax",
    description="Check Python file syntax without executing it."
)
def verify_syntax(path: str, user_id: str = None, **kwargs) -> str:
    """
    Compile-check a Python file for syntax errors.
    Args:
        path: Path to the Python file (relative to project root)
    """
    import py_compile

    cwd = Path(os.getcwd()).resolve()
    full = (cwd / path).resolve()

    # Security: ensure path is within project
    if not str(full).startswith(str(cwd)):
        return f"⚠️ Path outside project directory: {path}"

    if not full.exists():
        return f"❌ File not found: {path}"
    if full.suffix != ".py":
        return f"⚠️ Not a Python file: {path}"

    try:
        py_compile.compile(str(full), doraise=True)
        return f"✅ {path}: syntax OK"
    except py_compile.PyCompileError as e:
        return f"❌ {path}: syntax error — {e}"
    except Exception as e:
        return f"⚠️ {path}: verification failed — {e}"
