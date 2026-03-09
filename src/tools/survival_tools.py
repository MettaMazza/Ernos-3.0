"""
Survival Tools — Self-Querying Tools for Ernos's Survival Systems
=================================================================

Gives Ernos ground-truth access to its own internal metrics
so it never has to guess or fabricate internal state.
"""

import logging
from .registry import ToolRegistry

logger = logging.getLogger("Tools.Survival")


@ToolRegistry.register(
    name="check_discomfort",
    description=(
        "Query your own Discomfort Meter for a specific user. "
        "Returns the ACTUAL current score, zone, incident count, and clean hours. "
        "Use this tool whenever you are asked about your discomfort state — NEVER guess or fabricate metrics."
    ),
)
async def check_discomfort(user_id: str = None, **kwargs) -> str:
    """
    Returns ground-truth discomfort state for a specific user.
    If no user_id is provided, uses the current conversation's user_id.
    """
    from src.bot import globals

    bot = globals.bot
    if not bot:
        return "Error: Bot not initialized."

    # Resolve user_id from kwargs if not provided directly
    if not user_id:
        user_id = kwargs.get("user_id", "global")

    try:
        from src.memory.discomfort import DiscomfortMeter

        meter = DiscomfortMeter()
        score = meter.get_score(user_id)
        zone = meter.get_zone(user_id)
        stats = meter.get_stats(user_id)

        zone_emoji = zone[2] if zone else "?"
        zone_label = zone[3] if zone else "UNKNOWN"

        return (
            f"DISCOMFORT STATE for user {user_id}:\n"
            f"  Score: {score:.1f} / 100\n"
            f"  Zone: {zone_emoji} {zone_label}\n"
            f"  Total Incidents: {stats.get('total_incidents', 0)}\n"
            f"  Clean Hours Streak: {stats.get('streak_clean_hours', 0):.1f}\n"
            f"  Last Incident: {stats.get('last_incident_ts', 'Never')}\n"
            f"\n"
            f"This is the ACTUAL reading from the DiscomfortMeter. "
            f"Do not contradict these values in your response."
        )
    except Exception as e:
        logger.error(f"check_discomfort failed: {e}")
        return f"Error querying discomfort meter: {e}"
