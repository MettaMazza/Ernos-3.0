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


@ToolRegistry.register(
    name="trigger_self_review",
    description=(
        "Trigger an internal self-review debate when you sense you might be wrong. "
        "Spawns a Defender, Challenger, and Judge to objectively evaluate your position "
        "vs the user's challenge. Returns a verdict: CONCEDE, HOLD, or CLARIFY, "
        "with reasoning and a recommended response approach. "
        "Use this when: (1) a user contradicts a factual claim, "
        "(2) you feel uncertain about something you stated confidently, "
        "(3) repeated challenges on the same point. "
        "No rate limit — self-correction is a vital cognitive trait."
    ),
)
async def trigger_self_review(
    my_position: str,
    user_position: str,
    context: str = "",
    user_id: str = "",
    **kwargs,
) -> str:
    """
    Run a critical self-review debate.
    Returns structured verdict with reasoning and recommended response.
    """
    from src.bot import globals
    from src.core.critical_review import CriticalSelfReview

    bot = globals.bot
    if not bot:
        return "Error: Bot not initialized."

    if not user_id:
        user_id = kwargs.get("user_id", "unknown")

    try:
        result = await CriticalSelfReview.review(
            my_position=my_position,
            user_position=user_position,
            context=context,
            bot=bot,
            user_id=user_id,
        )

        verdict_emoji = {
            "CONCEDE": "🔄",
            "HOLD": "🛡️",
            "CLARIFY": "💡",
        }.get(result["verdict"], "❓")

        return (
            f"SELF-REVIEW VERDICT: {verdict_emoji} {result['verdict']}\n"
            f"Confidence: {result['confidence']:.1%}\n"
            f"Reasoning: {result['reasoning']}\n"
            f"Recommended Response: {result['recommended_response']}\n\n"
            f"Apply this verdict honestly — do not override it with politeness or stubbornness."
        )
    except Exception as e:
        logger.error(f"trigger_self_review failed: {e}")
        return f"Self-review error: {e}"

