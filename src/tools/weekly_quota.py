"""
WeeklyQuota — Daily self-development quota system with Friday merge gate.

Maria's cadence: 3 hours substantial autonomous work Mon-Thu,
staged for Friday review. Tracks approval/adoption rates over time.

State: memory/core/quota/week_{iso_week}.json
"""
import json
import logging
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .registry import ToolRegistry
from src.core.data_paths import data_dir

logger = logging.getLogger("Tools.WeeklyQuota")

# ─── Configuration ────────────────────────────────────────────────
DAILY_HOURS = 3            # 3 hours of substantial dev work per day
WORK_DAYS = ("saturday", "sunday", "monday", "tuesday", "wednesday", "thursday")

# ... (omitted lines) ...

@ToolRegistry.register(
    name="verify_staging_item",
    description="Verify a staged item using an explicit test command."
)
def verify_staging_item(path: str, test_command: str, **kwargs) -> str:
    """
    Run a verification command for a file you intend to stage.
    You MUST call this before completing a task that outputs this file.
    
    Args:
        path: The file path being verified.
        test_command: The command used to verify it (e.g., 'pytest tests/test_foo.py')
    """
    
    state = _load_week()
    today = _day_name()
    day_data = state["days"][today]
    
    # Store verification results
    if "verifications" not in day_data:
        day_data["verifications"] = {}
        
    try:
        # MANDATORY SYNTAX CHECK for Python files
        if path.endswith(".py"):
            syntax_result = subprocess.run(
                ["python3", "-m", "py_compile", path],
                capture_output=True, text=True, timeout=10
            )
            if syntax_result.returncode != 0:
                day_data["verifications"][path] = {
                    "status": "FAILED",
                    "command": f"py_compile {path}",
                    "output": syntax_result.stderr[:500],
                    "timestamp": _now_uk().isoformat()
                }
                _save_week(state)
                return f"❌ SYNTAX ERROR in {path}:\n{syntax_result.stderr[:300]}"

        # Run the test command
        cmd = test_command.split()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        status = "PASSED" if result.returncode == 0 else "FAILED"
        output = result.stdout + "\n" + result.stderr
        
        day_data["verifications"][path] = {
            "status": status,
            "command": test_command,
            "output": output[:500], # Truncate log
            "timestamp": _now_uk().isoformat()
        }
        _save_week(state)
        
        if status == "PASSED":
            return f"✅ Verification PASSED for {path}\nCommand: {test_command}"
        else:
            return f"❌ Verification FAILED for {path}\nCommand: {test_command}\nOutput: {output[:300]}..."
            
    except Exception as e:
        return f"❌ Verification Error: {e}"


@ToolRegistry.register(
    name="complete_dev_task",
    description="Mark a development task as done. REQUIRES verification."
)
def complete_dev_task(task_id: int = None,
                      output_files: str = "", summary: str = "", **kwargs) -> str:
    """
    Complete a dev task and stage its outputs for Friday review.
    REQUIRES 'verify_staging_item' to have PASSED for all output files.
    
    Args:
        task_id: Task ID to complete
        output_files: Pipe-separated list of files created/modified
        summary: What was accomplished
    """
    today = _day_name()
    if today not in WORK_DAYS:
        return "Not a work day — nothing to complete."

    state = _load_week()
    day_data = state["days"][today]
    tasks = day_data.get("tasks", [])
    verifications = day_data.get("verifications", {})

    if not tasks:
        return "No tasks assigned today. Use assign_dev_task first."

    # Find the task
    if task_id is not None:
        target = next((t for t in tasks if t["id"] == task_id), None)
    else:
        target = next((t for t in reversed(tasks) if not t.get("completed_at")), None)

    if not target:
        return "No incomplete task found. All done!"

    files = [f.strip() for f in output_files.split("|") if f.strip()]
    
    # QA GATE 1: MUST declare at least one output file
    if not files:
        return ("⛔ QA GATE: No output files declared.\n"
                "You MUST list the files you created via output_files='file1.py|file2.py'.\n"
                "Every task must produce verifiable output.")

    # QA GATE 2: Block if ANY verification in this session FAILED
    session_fails = [p for p, v in verifications.items() if v["status"] == "FAILED"]
    if session_fails:
        return (f"⛔ QA GATE: {len(session_fails)} verification(s) FAILED this session:\n"
                f"{chr(10).join('  ❌ ' + p for p in session_fails[:5])}\n"
                f"Fix ALL failures before completing any task.")

    # QA GATE 3: Check strict verification for each output file
    unverified = []
    for f in files:
        # Skip verification for markdown/txt files (documentation only)
        if f.endswith(".md") or f.endswith(".txt"):
            continue
            
        record = verifications.get(f)
        if not record or record["status"] != "PASSED":
            unverified.append(f)
            
    if unverified:
        return (f"⛔ QA GATE: Verification missing or failed for: {', '.join(unverified)}\n"
                f"You MUST call [verify_staging_item(path='...', test_command='...')] and get a PASS before completion.\n"
                f"Quality is mandatory.")

    now = _now_uk()
    target["completed_at"] = now.isoformat()
    target["summary"] = summary

    # REAL TIME TRACKING
    try:
        started = datetime.fromisoformat(target["started_at"])
        if started.tzinfo and not now.tzinfo:
            started = started.replace(tzinfo=None)
        elif now.tzinfo and not started.tzinfo:
            started = started.replace(tzinfo=now.tzinfo)
        elapsed = (now - started).total_seconds() / 3600.0
        target["hours_logged"] = round(elapsed, 2)
    except Exception:
        target["hours_logged"] = target.get("estimated_hours", 1.0)

    target["outputs"] = files

    # Update day totals
    day_data["hours_logged"] = round(sum(t.get("hours_logged", 0) for t in tasks), 2)

    # Stage outputs
    for f in files:
        state["staged_changes"].append({
            "path": f,
            "description": summary or target["description"],
            "staged_at": now.isoformat(),
            "task_id": target["id"],
            "day": today,
            "verification": verifications.get(f, "DOC_ONLY")
        })

    if day_data["hours_logged"] >= DAILY_HOURS:
        day_data["status"] = "DONE"

    _save_week(state)

    hours_logged = target["hours_logged"]
    remaining = max(0, DAILY_HOURS - day_data["hours_logged"])
    return (f"✅ Task #{target['id']} completed ({hours_logged:.2f}h measured)\n"
            f"Today: {day_data['hours_logged']:.2f}h / {DAILY_HOURS}h\n"
            f"{'🎯 Checkpoint met.' if remaining <= 0 else f'⏳ {remaining:.2f}h remaining.'}\n"
            f"📦 {len(files)} items staged with QA verification.")
REVIEW_DAY = "friday"
TIMEZONE = "Europe/London"  # UK time

# ─── Paths ────────────────────────────────────────────────────────
QUOTA_DIR = data_dir() / "core/quota"
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
        except Exception as e:
            logger.warning(f"Suppressed {type(e).__name__}: {e}")
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
    """Hours remaining in today's quota. Includes live elapsed time from any running clock."""
    day = _day_name()
    if day not in WORK_DAYS:
        return 0.0  # No quota on Friday (review day)
    state = _load_week()
    day_data = state["days"].get(day, {})
    logged = day_data.get("hours_logged", 0)

    # Include live elapsed time from any running clock
    clock = day_data.get("clock")
    if clock and clock.get("started_at"):
        try:
            started = datetime.fromisoformat(clock["started_at"])
            now = _now_uk()
            # Normalize timezone-awareness for comparison
            if started.tzinfo and not now.tzinfo:
                started = started.replace(tzinfo=None)
            elif now.tzinfo and not started.tzinfo:
                started = started.replace(tzinfo=now.tzinfo)
            live_elapsed = (now - started).total_seconds() / 3600.0
            logged += max(0.0, live_elapsed)
        except Exception as e:
            logger.warning(f"Clock read error: {e}")

    return max(0.0, DAILY_HOURS - logged)


def start_quota_clock():
    """Start a wall-clock timer for the current work cycle."""
    day = _day_name()
    if day not in WORK_DAYS:
        return
    state = _load_week()
    day_data = state["days"].get(day, {})
    # Don't overwrite an already-running clock
    if day_data.get("clock", {}).get("started_at"):
        logger.debug("Quota clock already running, skipping start.")
        return
    day_data["clock"] = {"started_at": _now_uk().isoformat()}
    _save_week(state)
    logger.info("Quota clock STARTED.")


def stop_quota_clock():
    """Stop the wall-clock timer and log elapsed hours to today's quota."""
    day = _day_name()
    if day not in WORK_DAYS:
        return 0.0
    state = _load_week()
    day_data = state["days"].get(day, {})
    clock = day_data.get("clock", {})
    started_at = clock.get("started_at")
    if not started_at:
        return 0.0

    try:
        started = datetime.fromisoformat(started_at)
        now = _now_uk()
        if started.tzinfo and not now.tzinfo:
            started = started.replace(tzinfo=None)
        elif now.tzinfo and not started.tzinfo:
            started = started.replace(tzinfo=now.tzinfo)
        elapsed_hours = max(0.0, (now - started).total_seconds() / 3600.0)
    except Exception as e:
        logger.warning(f"Clock stop error: {e}")
        elapsed_hours = 0.0

    # Accumulate into hours_logged
    day_data["hours_logged"] = round(day_data.get("hours_logged", 0) + elapsed_hours, 4)
    day_data["clock"] = {}  # Clear the clock

    if day_data["hours_logged"] >= DAILY_HOURS:
        day_data["status"] = "DONE"

    _save_week(state)
    logger.info(f"Quota clock STOPPED. Logged {elapsed_hours:.2f}h. Total today: {day_data['hours_logged']:.2f}h.")
    return elapsed_hours


def _is_work_mode_off() -> bool:
    """Check if admin has manually toggled work mode off."""
    try:
        if WORK_MODE_OVERRIDE_PATH.exists():
            data = json.loads(WORK_MODE_OVERRIDE_PATH.read_text())
            return data.get("work_mode") is False
    except Exception as e:
        logger.warning(f"Suppressed {type(e).__name__}: {e}")
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

    # ─── Operation density (from create_program tracking) ─────
    today_data = state["days"].get(today, {})
    ops = today_data.get("operations", [])
    if ops:
        op_files = {}
        op_fails = 0
        for op in ops:
            f = op.get("file", "?")
            op_files[f] = op_files.get(f, 0) + 1
            if not op.get("success", True):
                op_fails += 1

        top_files = sorted(op_files.items(), key=lambda x: -x[1])[:5]
        lines.append(f"\n🔧 Operations today: {len(ops)} tool calls ({op_fails} failed)")
        for fname, count in top_files:
            flag = " ⚠️ HIGH CHURN" if count > 10 else ""
            lines.append(f"  {count:3d}x  {fname}{flag}")

    return "\n".join(lines)


@ToolRegistry.register(
    name="start_work_session",
    description="Start a focused work session by defining a plan and a task limit."
)
def start_work_session(plan: str, predicted_tasks: int = 3, **kwargs) -> str:
    """
    Initialize a work session. You MUST call this before assigning tasks.
    
    Args:
        plan: A brief markdown plan of what you intend to do.
        predicted_tasks: The maximum number of tasks you expect to set (default: 3).
    """
    state = _load_week()
    today = _day_name()
    if today not in WORK_DAYS:
        return f"Cannot start session: Today is {today} (non-work day)."

    day_data = state["days"][today]
    
    # Store session metadata
    day_data["session"] = {
        "status": "ACTIVE",
        "plan": plan,
        "predicted_cap": int(predicted_tasks),
        "started_at": _now_uk().isoformat()
    }
    _save_week(state)
    
    return (f"🚀 Work Session Started\n"
            f"Plan: {plan[:100]}...\n"
            f"Cap: {predicted_tasks} tasks\n"
            f"You may now use [assign_dev_task] to execute your plan.")


@ToolRegistry.register(
    name="assign_dev_task",
    description="Self-assign a substantial development task for today's quota."
)
def assign_dev_task(description: str, estimated_hours: float = 1.0, **kwargs) -> str:
    """
    Add a development task to today's quota.
    REQUIRES an active work session via start_work_session().
    ENFORCES the predicted task cap.

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
    
    # Check for active session
    session = day_data.get("session")
    if not session or session.get("status") != "ACTIVE":
        return "⛔ No active work session. You MUST call [start_work_session(plan='...', predicted_tasks=N)] first."

    # Check Cap
    tasks = day_data.get("tasks", [])
    active_tasks = sum(1 for t in tasks if not t.get("completed_at"))
    predicted_cap = session.get("predicted_cap", 5)
    
    if active_tasks >= predicted_cap:
        return (f"⛔ Task Cap Reached ({active_tasks}/{predicted_cap}).\n"
                f"You predicted this session would take {predicted_cap} tasks.\n"
                f"You must complete an existing task before adding a new one.")

    remaining = DAILY_HOURS - day_data.get("hours_logged", 0)
    if remaining <= 0:
        return (f"✅ Today's {DAILY_HOURS}h quota is met! "
                f"Good work. Save remaining ideas for tomorrow.")

    task = {
        "id": len(tasks),
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
            f"Session: {active_tasks + 1}/{predicted_cap} active tasks\n"
            f"When done, call complete_dev_task with hours spent.")




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
