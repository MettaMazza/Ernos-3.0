"""
Admin Cog — Re-export shim for backward compatibility.

All admin commands now live in focused cog modules:
  - admin_engine.py      → Engine switching, sync, testing mode
  - admin_lifecycle.py   → Cycle resets, salt rotation, purge
  - admin_moderation.py  → Strike, core talk, prompt tuner
  - admin_reports.py     → User reports, town hall suggestions

This shim re-exports the original class name so existing code
that references AdminFunctions still works.
"""
from src.bot.cogs.admin_engine import AdminEngine as AdminFunctions  # noqa: F401


async def setup(bot):
    """Load all admin sub-cogs."""
    await bot.load_extension("src.bot.cogs.admin_engine")
    await bot.load_extension("src.bot.cogs.admin_lifecycle")
    await bot.load_extension("src.bot.cogs.admin_moderation")
    await bot.load_extension("src.bot.cogs.admin_reports")
