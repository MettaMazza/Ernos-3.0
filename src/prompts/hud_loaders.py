"""
HUD Data Loaders — Re-export shim for backward compatibility.

Implementations split into focused modules per <300 line standard:
  - hud_ernos.py   → load_ernos_hud  (system HUD)
  - hud_persona.py → load_persona_hud (public persona threads)
  - hud_fork.py    → load_fork_hud   (per-user Fork HUD)
"""
import os      # noqa: F401 — tests patch src.prompts.hud_loaders.os
import glob    # noqa: F401 — tests patch src.prompts.hud_loaders.glob

from src.prompts.hud_ernos import load_ernos_hud          # noqa: F401
from src.prompts.hud_ernos import _sanitize_logs           # noqa: F401
from src.prompts.hud_ernos import _load_room_roster        # noqa: F401
from src.prompts.hud_ernos import _load_reasoning_context  # noqa: F401
from src.prompts.hud_persona import load_persona_hud       # noqa: F401
from src.prompts.hud_fork import load_fork_hud             # noqa: F401
