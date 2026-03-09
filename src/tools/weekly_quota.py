"""
WeeklyQuota — Daily self-development quota system with Friday merge gate.

Maria's cadence: 3 hours substantial autonomous work Mon-Thu,
staged for Friday review. Tracks approval/adoption rates over time.

State: memory/core/quota/week_{iso_week}.json
"""
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .registry import ToolRegistry

logger = logging.getLogger("Tools.WeeklyQuota")

# ─── Configuration ────────────────────────────────────────────────
DAILY_HOURS = 3            # 3 hours of substantial dev work per day
WORK_DAYS = ("saturday", "sunday", "monday", "tuesday", "wednesday", "thursday")
REVIEW_DAY = "friday"
TIMEZONE = "Europe/London"  # UK time

# ─── Paths ────────────────────────────────────────────────────────
QUOTA_DIR = Path("memory/core/quota")
FEEDBACK_PATH = QUOTA_DIR / "feedback_history.json"
WORK_MODE_OVERRIDE_PATH = QUOTA_DIR / "work_mode_override.json"


def _now_uk() -> datetime:
    """Get current time in UK timezone."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(TIMEZONE))
    except ImportError:
        # Fallback: UTC (close enough for most of the year)
        return datetime.utcnow()


def _iso_week() -> str:
    """Return ISO week string like '2026-W07'."""
    now = _now_uk()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


def _day_name() -> str:
    """Return lowercase day name in UK time."""
    return _now_uk().strftime("%A").lower()


def _get_week_path(week: str = None) -> Path:
    """Path to this week's quota state file."""
    week = week or _iso_week()
    return QUOTA_DIR / f"week_{week}.json"


def _load_week(week: str = None) -> dict:
    """Load or initialize this week's state."""
    path = _get_week_path(week)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.warning(f"Corrupt quota file {path}: {e}")

    # Initialize fresh week
    state = {
        "week": week or _iso_week(),
        "daily_hours": DAILY_HOURS,
        "days": {},
        "staged_changes": [],
        "review_status": "PENDING",
    }
    for day in WORK_DAYS:
        state["days"][day] = {
            "tasks": [],       # [{description, started_at, completed_at, hours_logged}]
            "hours_logged": 0,
            "status": "PENDING",
        }
    state["days"][REVIEW_DAY] = {"status": "REVIEW_DAY", "tasks": []}
    return state


def _save_week(state: dict):
    """Persist week state to disk."""
    QUOTA_DIR.mkdir(parents=True, exist_ok=True)
    path = _get_week_path(state["week"])
    path.write_text(json.dumps(state, indent=2, default=str))


def _load_feedback() -> dict:
    """Load cumulative feedback history."""
    if FEEDBACK_PATH.exists():
        try:
            return json.loads(FEEDBACK_PATH.read_text())
        except Exception:
            pass
    return {
        "total_weeks": 0,
        "total_tasks_submitted": 0,
        "total_approved": 0,
        "total_rejected": 0,
        "total_partial": 0,
        "adoption_rate": 0.0,
        "weekly_history": [],
    }


def _save_feedback(data: dict):
    """Save feedback history."""
    QUOTA_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK_PATH.write_text(json.dumps(data, indent=2, default=str))


# ─── Merge Gate ───────────────────────────────────────────────────

def is_merge_allowed() -> bool:
    """
    Returns True only if today is Friday OR review has been approved.
    Called by coding.py to gate CORE-scope writes.
    """
    state = _load_week()
    if state["review_status"] == "APPROVED":
        return True
    return _day_name() == REVIEW_DAY


def get_remaining_quota() -> float:
    """Hours remaining in today's quota. Applies Sat-Thu (6-day week, Friday off)."""
    day = _day_name()
    if day not in WORK_DAYS:
        return 0.0  # No quota on Friday (review day)
    state = _load_week()
    day_data = state["days"].get(day, {})
    logged = day_data.get("hours_logged", 0)
    return max(0.0, DAILY_HOURS - logged)


def _is_work_mode_off() -> bool:
    """Check if admin has manually toggled work mode off."""
    try:
        if WORK_MODE_OVERRIDE_PATH.exists():
            data = json.loads(WORK_MODE_OVERRIDE_PATH.read_text())
            return data.get("work_mode") is False
    except Exception:
        pass
    return False


def is_quota_met() -> bool:
    """
    Returns True if today's quota is fully met.
    Used by AgencyDaemon to gate recreational autonomy:
    recreational actions (RESEARCH, REFLECTION, OUTREACH) are blocked
    until the daily dev quota is met.
    Work days are Sat-Thu (6-day week). Only Friday is off.
    Work before play on work days, no exceptions.

    Admin override: if memory/core/quota/work_mode_override.json has
    {"work_mode": false}, quota is always considered met (free autonomy).
    """
    if _is_work_mode_off():
        return True
    return get_remaining_quota() <= 0


# ─── Tools ────────────────────────────────────────────────────────

@ToolRegistry.register(
    name="get_quota_status",
    description="Show today's self-development quota progress and weekly overview."
)
def get_quota_status(**kwargs) -> str:
    """Returns formatted quota status for today and the week."""
    state = _load_week()
    today = _day_name()
    week = state["week"]

    lines = [f"📊 **Weekly Quota — {week}**"]
    lines.append(f"Daily target: {DAILY_HOURS}h substantial work (Sat-Thu)")
    lines.append("")

    for day in WORK_DAYS:
        day_data = state["days"].get(day, {})
        if day == REVIEW_DAY:
            review = state.get("review_status", "PENDING")
            icon = "📋" if review == "PENDING" else ("✅" if review == "APPROVED" else "❌")
            marker = " ◀ TODAY" if today == day else ""
            lines.append(f"  {icon} {day.capitalize()}: Review Day [{review}]{marker}")
        else:
            hours = day_data.get("hours_logged", 0)
            tasks = day_data.get("tasks", [])
            completed = sum(1 for t in tasks if t.get("completed_at"))
            total = len(tasks)
            status = day_data.get("status", "PENDING")

            if today == day:
                remaining = max(0, DAILY_HOURS - hours)
                icon = "🔶" if status == "ACTIVE" else ("✅" if hours >= DAILY_HOURS else "⬜")
                lines.append(f"  {icon} {day.capitalize()}: {hours:.1f}h / {DAILY_HOURS}h "
                             f"({completed}/{total} tasks) — {remaining:.1f}h remaining ◀ TODAY")
            else:
                icon = "✅" if hours >= DAILY_HOURS else "⬜"
                lines.append(f"  {icon} {day.capitalize()}: {hours:.1f}h / {DAILY_HOURS}h "
                             f"({completed}/{total} tasks)")

    staged = len(state.get("staged_changes", []))
    lines.append(f"\n📦 Staged for review: {staged} change(s)")

    return "\n".join(lines)


@ToolRegistry.register(
    name="assign_dev_task",
    description="Self-assign a substantial development task for today's quota."
)
def assign_dev_task(description: str, estimated_hours: float = 1.0, **kwargs) -> str:
    """
    Add a development task to today's quota.

    Args:
        description: What you plan to build/upgrade (substantial, not a tweak)
        estimated_hours: Estimated hours for this task (default 1.0)
    """
    today = _day_name()
    if today not in WORK_DAYS:
        return (f"Today is {today.capitalize()} — "
                f"{'Review day! Use get_review_queue instead.' if today == REVIEW_DAY else 'Not a work day.'}")

    state = _load_week()
    day_data = state["days"][today]

    remaining = DAILY_HOURS - day_data.get("hours_logged", 0)
    if remaining <= 0:
        return (f"✅ Today's {DAILY_HOURS}h quota is met! "
                f"Good work. Save remaining ideas for tomorrow.")

    task = {
        "id": len(day_data["tasks"]),
        "description": description,
        "estimated_hours": estimated_hours,
        "started_at": _now_uk().isoformat(),
        "completed_at": None,
        "hours_logged": 0,
        "outputs": [],
    }
    day_data["tasks"].append(task)
    day_data["status"] = "ACTIVE"
    _save_week(state)

    return (f"📝 Task #{task['id']} assigned: {description}\n"
            f"Est: {estimated_hours}h | Remaining quota: {remaining:.1f}h\n"
            f"When done, call complete_dev_task with hours spent.")


@ToolRegistry.register(
    name="complete_dev_task",
    description="Mark a development task as done. Hours are calculated from real timestamps."
)
def complete_dev_task(task_id: int = None,
                      output_files: str = "", summary: str = "", **kwargs) -> str:
    """
    Complete a dev task and stage its outputs for Friday review.
    Hours are calculated from real timestamps (started_at → now), NOT self-reported.

    Args:
        task_id: Task ID to complete (default: most recent incomplete)
        output_files: Pipe-separated list of files created/modified
        summary: What was accomplished
    """
    today = _day_name()
    if today not in WORK_DAYS:
        return "Not a work day — nothing to complete."

    state = _load_week()
    day_data = state["days"][today]
    tasks = day_data.get("tasks", [])

    if not tasks:
        return "No tasks assigned today. Use assign_dev_task first."

    # Find the task
    if task_id is not None:
        target = next((t for t in tasks if t["id"] == task_id), None)
    else:
        # Most recent incomplete
        target = next((t for t in reversed(tasks) if not t.get("completed_at")), None)

    if not target:
        return "No incomplete task found. All done!"

    now = _now_uk()
    target["completed_at"] = now.isoformat()
    target["summary"] = summary

    # REAL TIME TRACKING: Calculate hours from started_at timestamp
    # The LLM cannot self-report hours — they are measured.
    try:
        started = datetime.fromisoformat(target["started_at"])
        # Handle timezone-naive comparison
        if started.tzinfo and not now.tzinfo:
            started = started.replace(tzinfo=None)
        elif now.tzinfo and not started.tzinfo:
            started = started.replace(tzinfo=now.tzinfo)
        elapsed = (now - started).total_seconds() / 3600.0
        target["hours_logged"] = round(elapsed, 2)
    except Exception:
        # Fallback: if timestamp parsing fails, use estimated_hours
        target["hours_logged"] = target.get("estimated_hours", 1.0)

    files = [f.strip() for f in output_files.split("|") if f.strip()]
    target["outputs"] = files

    # Update day totals from real timestamps
    day_data["hours_logged"] = round(sum(t.get("hours_logged", 0) for t in tasks), 2)

    # Stage outputs for Friday review
    for f in files:
        state["staged_changes"].append({
            "path": f,
            "description": summary or target["description"],
            "staged_at": now.isoformat(),
            "task_id": target["id"],
            "day": today,
        })

    if day_data["hours_logged"] >= DAILY_HOURS:
        day_data["status"] = "DONE"

    _save_week(state)

    hours_logged = target["hours_logged"]
    remaining = max(0, DAILY_HOURS - day_data["hours_logged"])
    return (f"✅ Task #{target['id']} completed ({hours_logged:.2f}h measured)\n"
            f"Today: {day_data['hours_logged']:.2f}h / {DAILY_HOURS}h\n"
            f"{'🎯 Daily quota met! Recreational autonomy unlocked.' if remaining <= 0 else f'⏳ {remaining:.2f}h remaining — recreational autonomy blocked.'}\n"
            f"📦 {len(files)} file(s) staged for Friday review.")


@ToolRegistry.register(
    name="stage_for_review",
    description="Explicitly stage a file/change for Friday review."
)
def stage_for_review(path: str, description: str = "", **kwargs) -> str:
    """Stage a file path for the weekly review batch."""
    state = _load_week()
    state["staged_changes"].append({
        "path": path,
        "description": description,
        "staged_at": _now_uk().isoformat(),
        "task_id": None,
        "day": _day_name(),
    })
    _save_week(state)
    total = len(state["staged_changes"])
    return f"📦 Staged: {path}\nTotal staged: {total} change(s) for Friday review."


@ToolRegistry.register(
    name="get_feedback_report",
    description="Show approval/adoption rates across weeks — what worked and what didn't."
)
def get_feedback_report(**kwargs) -> str:
    """Returns cumulative feedback on self-development work."""
    fb = _load_feedback()

    if fb["total_weeks"] == 0:
        return ("📊 No review history yet. "
                "Feedback will accumulate after your first Friday review.")

    lines = [
        "📊 **Self-Development Feedback Report**",
        f"Weeks tracked: {fb['total_weeks']}",
        f"Tasks submitted: {fb['total_tasks_submitted']}",
        f"Approved: {fb['total_approved']} | "
        f"Rejected: {fb['total_rejected']} | "
        f"Partial: {fb['total_partial']}",
        f"**Adoption rate: {fb['adoption_rate']:.0%}**",
        "",
        "─── Recent Weeks ───",
    ]

    # Show last 4 weeks
    for entry in fb["weekly_history"][-4:]:
        week = entry["week"]
        outcome = entry["outcome"]
        icon = "✅" if outcome == "APPROVED" else ("❌" if outcome == "REJECTED" else "⚠️")
        lines.append(f"  {icon} {week}: {outcome}")
        if entry.get("feedback"):
            lines.append(f"     └ {entry['feedback']}")
        # Show what worked / didn't
        if entry.get("approved_items"):
            lines.append(f"     ✅ Worked: {', '.join(entry['approved_items'][:3])}")
        if entry.get("rejected_items"):
            lines.append(f"     ❌ Didn't work: {', '.join(entry['rejected_items'][:3])}")
        if entry.get("rejection_reasons"):
            lines.append(f"     💡 Why: {'; '.join(entry['rejection_reasons'][:2])}")

    return "\n".join(lines)
