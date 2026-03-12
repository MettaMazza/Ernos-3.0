"""
Central data directory resolution.

All path construction for user/system/core data MUST use data_dir()
instead of hardcoding Path("memory"). This ensures paths respect
ERNOS_DATA_DIR for Docker volume mapping.
"""
from pathlib import Path
import os

# Cache the resolved path
_DATA_DIR: Path = Path(os.getenv("ERNOS_DATA_DIR", "memory"))


def data_dir() -> Path:
    """Return the root data directory (default: 'memory', overridable via ERNOS_DATA_DIR)."""
    return _DATA_DIR
