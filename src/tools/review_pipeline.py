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
from src.core.data_paths import data_dir

logger = logging.getLogger("Tools.ReviewPipeline")

STAGING_DIR = data_dir() / "core/staging"
PROJECTS_DIR = data_dir() / "core/projects"


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
    description="Approve staged changes and merge to intended paths. Optionally approve specific items."
)
def approve_review(feedback: str = "", approved_indices: str = "",
                   user_id: str = None, **kwargs) -> str:
    """
    Approve staged changes for merge.
    Uses staging_manifest.json to determine intended paths (src/, tests/, etc.).
    Runs pytest after merge — rolls back if tests fail.

    Args:
        feedback: Optional feedback message from Maria
        approved_indices: Pipe-separated indices to approve (empty = approve all)
    """
    import subprocess
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

    # Load staging manifest for intended paths
    manifest = []
    manifest_path = STAGING_DIR / "staging_manifest.json"
    try:
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
    except Exception:
        pass

    # Build lookup: staged_as -> intended_path
    intent_lookup = {}
    for entry in manifest:
        staged_as = entry.get("staged_as", "")
        intended = entry.get("intended_path", "")
        if staged_as and intended:
            intent_lookup[staged_as] = intended

    approved_items = []
    rejected_items = []
    merged_files = []  # Track for rollback

    for i, item in enumerate(staged):
        path = item.get("path", "")
        basename = Path(path).name
        if i in indices:
            src = STAGING_DIR / basename
            if src.exists():
                # Check manifest for intended path
                intended = intent_lookup.get(basename, "")
                
                if intended and (intended.startswith("src/") or intended.startswith("tests/")):
                    # Merge to intended production path
                    dst = Path(intended)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Back up existing file for rollback
                    backup = None
                    if dst.exists():
                        backup = dst.read_bytes()
                    
                    shutil.copy2(str(src), str(dst))
                    merged_files.append({"dst": str(dst), "backup": backup, "intended": intended})
                    logger.info(f"Merged to production: {src} -> {dst}")
                else:
                    # Fallback: merge to projects dir
                    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
                    dst = PROJECTS_DIR / basename
                    shutil.copy2(str(src), str(dst))
                    merged_files.append({"dst": str(dst), "backup": None, "intended": str(dst)})
                    logger.info(f"Merged to projects: {src} -> {dst}")
                    
            approved_items.append(item.get("description", path))
        else:
            rejected_items.append(item.get("description", path))

    # POST-MERGE SAFETY: Run pytest if any files merged to src/ or tests/
    prod_merges = [m for m in merged_files if m["intended"].startswith("src/") or m["intended"].startswith("tests/")]
    test_result = None
    if prod_merges:
        try:
            result = subprocess.run(
                ["python3", "-m", "pytest", "tests/", "-q", "--tb=short"],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                # ROLLBACK: Tests failed — revert all production merges
                for m in prod_merges:
                    dst = Path(m["dst"])
                    if m["backup"] is not None:
                        dst.write_bytes(m["backup"])
                        logger.warning(f"Rolled back: {dst}")
                    elif dst.exists():
                        dst.unlink()
                        logger.warning(f"Removed (new file): {dst}")
                
                test_output = (result.stdout + "\n" + result.stderr)[-500:]
                return (f"⛔ MERGE ROLLED BACK — pytest failed after merging to production!\n"
                        f"Merged {len(prod_merges)} file(s) to src/tests, but tests broke.\n"
                        f"All changes reverted. Fix the code before re-approving.\n\n"
                        f"Test output:\n```\n{test_output}\n```")
            else:
                test_result = "✅ pytest passed after merge"
        except subprocess.TimeoutExpired:
            test_result = "⚠️ pytest timed out (120s) — check manually"
        except Exception as e:
            test_result = f"⚠️ Could not run pytest: {e}"

    # Determine outcome
    if len(rejected_items) == 0:
        outcome = "APPROVED"
        state["review_status"] = "APPROVED"
    else:
        outcome = "PARTIAL"
        state["review_status"] = "APPROVED"

    # Clear staged
    state["staged_changes"] = []
    _save_week(state)

    # Clear staging manifest
    try:
        if manifest_path.exists():
            manifest_path.unlink()
    except Exception:
        pass

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
    if outcome == "PARTIAL":
        fb["total_partial"] += 1

    if fb["total_tasks_submitted"] > 0:
        fb["adoption_rate"] = fb["total_approved"] / fb["total_tasks_submitted"]

    _save_feedback(fb)

    result = f"✅ Review complete: {len(approved_items)} approved"
    if rejected_items:
        result += f", {len(rejected_items)} not approved"
    if prod_merges:
        result += f"\n🏗️ {len(prod_merges)} file(s) merged to production paths"
    if test_result:
        result += f"\n{test_result}"
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
