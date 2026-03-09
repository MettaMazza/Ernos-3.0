"""
ReviewPipeline — Friday auto-review system for staged self-development work.

Tools for Maria to approve/reject staged changes, plus a scheduler hook
that auto-generates a review summary on Friday mornings.
Tracks adoption rates and feeds lessons back to Ernos.
"""
import json
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from .registry import ToolRegistry

logger = logging.getLogger("Tools.ReviewPipeline")

STAGING_DIR = Path("memory/core/staging")
PROJECTS_DIR = Path("memory/core/projects")


def _now_uk() -> datetime:
    """Get current time in UK timezone."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/London"))
    except ImportError:
        return datetime.utcnow()


# ─── Tools ────────────────────────────────────────────────────────

@ToolRegistry.register(
    name="get_review_queue",
    description="List all staged changes awaiting Friday review."
)
def get_review_queue(**kwargs) -> str:
    """Show all staged changes waiting for review."""
    from .weekly_quota import _load_week

    state = _load_week()
    staged = state.get("staged_changes", [])

    if not staged:
        return "📋 No staged changes awaiting review."

    lines = [f"📋 **Review Queue — {state['week']}**",
             f"Total: {len(staged)} change(s)\n"]

    # Group by day
    by_day = {}
    for item in staged:
        day = item.get("day", "unknown")
        by_day.setdefault(day, []).append(item)

    for day, items in by_day.items():
        lines.append(f"── {day.capitalize()} ──")
        for i, item in enumerate(items):
            desc = item.get("description", "No description")
            path = item.get("path", "?")
            lines.append(f"  [{i}] {desc}")
            lines.append(f"      📁 {path}")

    lines.append(f"\nReview status: {state.get('review_status', 'PENDING')}")
    lines.append("Use approve_review or reject_review to process.")

    return "\n".join(lines)


@ToolRegistry.register(
    name="approve_review",
    description="Approve staged changes and merge to projects. Optionally approve specific items."
)
def approve_review(feedback: str = "", approved_indices: str = "",
                   user_id: str = None, **kwargs) -> str:
    """
    Approve staged changes for merge.

    Args:
        feedback: Optional feedback message from Maria
        approved_indices: Pipe-separated indices to approve (empty = approve all)
    """
    from .weekly_quota import _load_week, _save_week, _load_feedback, _save_feedback

    state = _load_week()
    staged = state.get("staged_changes", [])

    if not staged:
        return "Nothing staged for review."

    # Parse which indices to approve
    if approved_indices.strip():
        try:
            indices = set(int(x.strip()) for x in approved_indices.split("|"))
        except ValueError:
            return "Error: approved_indices must be pipe-separated integers."
    else:
        indices = set(range(len(staged)))

    approved_items = []
    rejected_items = []

    for i, item in enumerate(staged):
        path = item.get("path", "")
        if i in indices:
            # Copy from staging to projects if the file exists in staging
            src = STAGING_DIR / Path(path).name
            if src.exists():
                PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
                dst = PROJECTS_DIR / Path(path).name
                shutil.copy2(str(src), str(dst))
                logger.info(f"Merged: {src} -> {dst}")
            approved_items.append(item.get("description", path))
        else:
            rejected_items.append(item.get("description", path))

    # Determine outcome
    if len(rejected_items) == 0:
        outcome = "APPROVED"
        state["review_status"] = "APPROVED"
    else:
        outcome = "PARTIAL"
        state["review_status"] = "APPROVED"  # Still unlock merge for approved items

    # Clear staged
    state["staged_changes"] = []
    _save_week(state)

    # Update feedback history
    fb = _load_feedback()
    total_tasks = _count_week_tasks(state)
    week_entry = {
        "week": state["week"],
        "outcome": outcome,
        "feedback": feedback,
        "approved_items": approved_items[:5],
        "rejected_items": rejected_items[:5],
        "rejection_reasons": [],
        "tasks_submitted": total_tasks,
        "approved_count": len(approved_items),
        "rejected_count": len(rejected_items),
        "reviewed_at": _now_uk().isoformat(),
    }
    fb["weekly_history"].append(week_entry)
    fb["total_weeks"] += 1
    fb["total_tasks_submitted"] += total_tasks
    fb["total_approved"] += len(approved_items)
    if outcome == "APPROVED":
        pass  # Already counted above
    elif outcome == "PARTIAL":
        fb["total_partial"] += 1

    # Recalculate adoption rate
    if fb["total_tasks_submitted"] > 0:
        fb["adoption_rate"] = fb["total_approved"] / fb["total_tasks_submitted"]

    _save_feedback(fb)

    result = f"✅ Review complete: {len(approved_items)} approved"
    if rejected_items:
        result += f", {len(rejected_items)} not approved"
    if feedback:
        result += f"\n📝 Feedback: {feedback}"
    result += f"\n📊 Cumulative adoption rate: {fb['adoption_rate']:.0%}"

    return result


@ToolRegistry.register(
    name="reject_review",
    description="Reject staged changes with feedback on why. Ernos learns from this."
)
def reject_review(feedback: str = "", reasons: str = "",
                  rejected_indices: str = "",
                  user_id: str = None, **kwargs) -> str:
    """
    Reject staged changes with reasoning for Ernos to learn from.

    Args:
        feedback: Overall feedback message
        reasons: Pipe-separated reasons for rejection
        rejected_indices: Pipe-separated indices to reject (empty = reject all)
    """
    from .weekly_quota import _load_week, _save_week, _load_feedback, _save_feedback

    state = _load_week()
    staged = state.get("staged_changes", [])

    if not staged:
        return "Nothing staged for review."

    # Parse indices
    if rejected_indices.strip():
        try:
            indices = set(int(x.strip()) for x in rejected_indices.split("|"))
        except ValueError:
            return "Error: rejected_indices must be pipe-separated integers."
    else:
        indices = set(range(len(staged)))

    rejected_items = []
    kept_items = []

    for i, item in enumerate(staged):
        if i in indices:
            rejected_items.append(item.get("description", item.get("path", "?")))
        else:
            kept_items.append(item)

    reason_list = [r.strip() for r in reasons.split("|") if r.strip()]

    state["staged_changes"] = kept_items
    if not kept_items:
        state["review_status"] = "REJECTED"
    _save_week(state)

    # Update feedback history
    fb = _load_feedback()
    total_tasks = _count_week_tasks(state)
    week_entry = {
        "week": state["week"],
        "outcome": "REJECTED" if not kept_items else "PARTIAL",
        "feedback": feedback,
        "approved_items": [],
        "rejected_items": rejected_items[:5],
        "rejection_reasons": reason_list[:5],
        "tasks_submitted": total_tasks,
        "approved_count": 0,
        "rejected_count": len(rejected_items),
        "reviewed_at": _now_uk().isoformat(),
    }
    fb["weekly_history"].append(week_entry)
    fb["total_weeks"] += 1
    fb["total_tasks_submitted"] += total_tasks
    fb["total_rejected"] += len(rejected_items)

    if fb["total_tasks_submitted"] > 0:
        fb["adoption_rate"] = fb["total_approved"] / fb["total_tasks_submitted"]

    _save_feedback(fb)

    result = f"❌ Rejected: {len(rejected_items)} change(s)"
    if kept_items:
        result += f"\n📦 {len(kept_items)} change(s) still staged"
    if feedback:
        result += f"\n📝 Feedback: {feedback}"
    if reason_list:
        result += f"\n💡 Reasons: {'; '.join(reason_list)}"
    result += f"\n📊 Cumulative adoption rate: {fb['adoption_rate']:.0%}"

    return result


# ─── Scheduler Hook ──────────────────────────────────────────────

async def friday_review_summary(bot=None):
    """
    Scheduler hook: runs Friday at 09:00 UK.
    Auto-generates a review summary and sends to:
    1. Admin DMs
    2. ernos-code channel
    """
    from .weekly_quota import _load_week, WORK_DAYS

    state = _load_week()
    staged = state.get("staged_changes", [])

    if not staged:
        logger.info("Friday review: no staged changes, skipping summary")
        return

    lines = [
        "🗓️ **Friday Review Summary**",
        f"Week: {state['week']}",
        f"Staged changes: {len(staged)}",
        "",
    ]

    # Summarize work done each day
    for day_name in WORK_DAYS:
        day_data = state["days"].get(day_name, {})
        hours = day_data.get("hours_logged", 0)
        tasks = day_data.get("tasks", [])
        completed = sum(1 for t in tasks if t.get("completed_at"))
        if hours > 0 or tasks:
            lines.append(f"  {day_name.capitalize()}: {hours:.1f}h — {completed} task(s)")

    lines.append("")
    lines.append("📦 **Changes for Review:**")
    for i, item in enumerate(staged):
        lines.append(f"  [{i}] {item.get('description', 'No description')}")

    lines.append("")
    lines.append("Use `approve_review` or `reject_review` to process.")

    summary = "\n".join(lines)

    # Send to admin DMs and ernos-code channel
    if bot:
        try:
            from config import settings

            # 1. Send to ernos-code channel
            code_channel_id = getattr(settings, "ERNOS_CODE_CHANNEL_ID", None)
            if code_channel_id:
                code_channel = bot.get_channel(code_channel_id)
                if code_channel:
                    await code_channel.send(summary)
                    logger.info("Friday review summary sent to ernos-code channel")

            # 2. Send to admin DMs
            admin_id = getattr(settings, "ADMIN_USER_ID", None)
            if admin_id:
                try:
                    admin_user = await bot.fetch_user(admin_id)
                    if admin_user:
                        await admin_user.send(summary)
                        logger.info("Friday review summary sent to admin DMs")
                except Exception as dm_err:
                    logger.warning(f"Failed to DM admin: {dm_err}")

        except Exception as e:
            logger.warning(f"Failed to send Friday review summary: {e}")


async def daily_quota_check(bot=None):
    """
    Scheduler hook: runs daily at 08:00 UK.
    Logs remaining quota for the day. Applies every day.
    """
    from .weekly_quota import _day_name, get_remaining_quota

    today = _day_name()
    remaining = get_remaining_quota()
    logger.info(f"Daily quota check: {today.capitalize()} — {remaining:.1f}h remaining")


# ─── Internal Helpers ─────────────────────────────────────────────

def _count_week_tasks(state: dict) -> int:
    """Count total tasks across all days in this week."""
    total = 0
    for day_data in state.get("days", {}).values():
        if isinstance(day_data, dict):
            total += len(day_data.get("tasks", []))
    return total
