"""
Analytics — Structured productivity and system health reports.

Provides daily/weekly summaries of Ernos's autonomous work, tool usage,
persona engagement, and system health. Reports written to memory/core/reports/.

Tools:
  - get_daily_report: Generate today's productivity summary
  - get_weekly_summary: Aggregate the week's daily reports
"""
import json
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

from .registry import ToolRegistry
from src.core.data_paths import data_dir

logger = logging.getLogger("Tools.Analytics")

REPORTS_DIR = data_dir() / "core/reports"
LOG_PATH = Path("ernos_bot.log")
QUOTA_DIR = data_dir() / "core/quota"


def _ensure_dirs():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _parse_log_for_date(date_str: str) -> dict:
    """
    Parse ernos_bot.log for entries matching the given date.
    Returns structured metrics.
    """
    metrics = {
        "tool_calls": Counter(),
        "errors": 0,
        "warnings": 0,
        "persona_registrations": [],
        "town_hall_messages": 0,
        "agency_blocks": 0,
        "ima_work_sessions": 0,
        "user_messages": 0,
        "lobe_calls": Counter(),
    }

    if not LOG_PATH.exists():
        return metrics

    try:
        with open(LOG_PATH, "r", errors="ignore") as f:
            for line in f:
                if not line.startswith(date_str):
                    continue

                # Count errors and warnings
                if "[ERROR]" in line:
                    metrics["errors"] += 1
                elif "[WARNING]" in line:
                    metrics["warnings"] += 1

                # Tool calls
                tool_match = re.search(r"Tool Executed: (\w+)", line)
                if tool_match:
                    metrics["tool_calls"][tool_match.group(1)] += 1

                # Persona registrations
                persona_match = re.search(r"Registered persona '(\w+)'", line)
                if persona_match:
                    metrics["persona_registrations"].append(persona_match.group(1))

                # Town Hall activity
                if "TownHall" in line and ("speaking" in line.lower() or "message" in line.lower()):
                    metrics["town_hall_messages"] += 1

                # Agency blocks
                if "Agency BLOCKED" in line:
                    metrics["agency_blocks"] += 1

                # IMA work mode
                if "WORK MODE" in line:
                    metrics["ima_work_sessions"] += 1

                # User messages
                if "Processing message from" in line:
                    metrics["user_messages"] += 1

                # Lobe calls
                lobe_match = re.search(r"Lobe\.(\w+)", line)
                if lobe_match:
                    metrics["lobe_calls"][lobe_match.group(1)] += 1

    except Exception as e:
        logger.error(f"Log parsing failed: {e}")

    # Deduplicate persona registrations
    metrics["persona_registrations"] = list(set(metrics["persona_registrations"]))

    return metrics


def _get_quota_status() -> dict:
    """Read current quota state."""
    try:
        now = datetime.now()
        week = now.strftime("%G-W%V")
        week_file = QUOTA_DIR / f"week_{week}.json"
        if week_file.exists():
            return json.loads(week_file.read_text())
    except Exception as e:
        logger.debug(f"Quota read failed: {e}")
    return {}


def _format_report(date_str: str, metrics: dict, quota: dict) -> str:
    """Format metrics into a readable markdown report."""
    lines = [
        f"# Ernos Daily Report — {date_str}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## System Health",
        f"- **Errors**: {metrics['errors']}",
        f"- **Warnings**: {metrics['warnings']}",
        f"- **Agency Blocks** (quota gate): {metrics['agency_blocks']}",
        "",
        "## User Engagement",
        f"- **Messages Processed**: {metrics['user_messages']}",
        "",
        "## Autonomous Work",
        f"- **IMA Work Sessions**: {metrics['ima_work_sessions']}",
    ]

    # Quota info
    today_key = datetime.now().strftime("%A").lower()
    if quota:
        days = quota.get("days", {})
        today_data = days.get(today_key, {})
        tasks = today_data.get("tasks", [])
        total_hours = sum(t.get("actual_hours", 0) for t in tasks if t.get("status") == "completed")
        lines.append(f"- **Dev Hours Today**: {total_hours:.1f}h / 3.0h quota")

        week_hours = 0
        for day_data in days.values():
            for t in day_data.get("tasks", []):
                if t.get("status") == "completed":
                    week_hours += t.get("actual_hours", 0)
        lines.append(f"- **Dev Hours This Week**: {week_hours:.1f}h")
    else:
        lines.append("- **Dev Hours**: No quota data available")

    # Tool usage
    if metrics["tool_calls"]:
        lines.extend([
            "",
            "## Tool Usage (Top 15)",
        ])
        for tool, count in metrics["tool_calls"].most_common(15):
            lines.append(f"- `{tool}`: {count}")

    # Lobe activity
    if metrics["lobe_calls"]:
        lines.extend([
            "",
            "## Lobe Activity",
        ])
        for lobe, count in metrics["lobe_calls"].most_common(10):
            lines.append(f"- **{lobe}**: {count} activations")

    # Personas
    if metrics["persona_registrations"]:
        lines.extend([
            "",
            "## Active Personas",
            f"- **Registered**: {len(metrics['persona_registrations'])}",
            f"- **Names**: {', '.join(sorted(metrics['persona_registrations']))}",
        ])

    # Town Hall
    lines.extend([
        "",
        "## Town Hall",
        f"- **Messages**: {metrics['town_hall_messages']}",
    ])

    return "\n".join(lines)


@ToolRegistry.register(
    name="get_daily_report",
    description="Generate a structured daily productivity and health report for Ernos."
)
def get_daily_report(date: str = None, **kwargs) -> str:
    """
    Generate today's (or a specific date's) productivity report.
    Args:
        date: Optional date in YYYY-MM-DD format (defaults to today)
    """
    _ensure_dirs()
    if date:
        date_str = date
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    metrics = _parse_log_for_date(date_str)
    quota = _get_quota_status()
    report = _format_report(date_str, metrics, quota)

    # Save to disk
    report_path = REPORTS_DIR / f"{date_str}.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"Daily report written to {report_path}")

    return report


@ToolRegistry.register(
    name="get_weekly_summary",
    description="Aggregate daily reports into a weekly productivity summary."
)
def get_weekly_summary(**kwargs) -> str:
    """Generate a weekly summary from saved daily reports."""
    _ensure_dirs()

    today = datetime.now()
    # Find start of week (Monday)
    monday = today - timedelta(days=today.weekday())

    lines = [
        f"# Ernos Weekly Summary",
        f"Week of {monday.strftime('%Y-%m-%d')}",
        f"Generated: {today.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    total_errors = 0
    total_warnings = 0
    total_messages = 0
    total_work_sessions = 0
    total_tool_calls = Counter()
    days_with_data = 0

    for i in range(7):
        day = monday + timedelta(days=i)
        date_str = day.strftime("%Y-%m-%d")
        day_name = day.strftime("%A")

        if day > today:
            break

        metrics = _parse_log_for_date(date_str)
        has_data = metrics["user_messages"] > 0 or metrics["errors"] > 0

        if has_data:
            days_with_data += 1
            total_errors += metrics["errors"]
            total_warnings += metrics["warnings"]
            total_messages += metrics["user_messages"]
            total_work_sessions += metrics["ima_work_sessions"]
            total_tool_calls.update(metrics["tool_calls"])

            lines.append(
                f"- **{day_name}** ({date_str}): "
                f"{metrics['user_messages']} msgs, "
                f"{metrics['errors']} errors, "
                f"{metrics['ima_work_sessions']} work sessions"
            )
        else:
            lines.append(f"- **{day_name}** ({date_str}): No activity")

    # Quota summary
    quota = _get_quota_status()
    if quota:
        week_hours = 0
        days = quota.get("days", {})
        for day_data in days.values():
            for t in day_data.get("tasks", []):
                if t.get("status") == "completed":
                    week_hours += t.get("actual_hours", 0)
        lines.extend([
            "",
            "## Dev Work Summary",
            f"- **Total Dev Hours**: {week_hours:.1f}h",
        ])

    lines.extend([
        "",
        "## Weekly Totals",
        f"- **Active Days**: {days_with_data}",
        f"- **Total Messages**: {total_messages}",
        f"- **Total Errors**: {total_errors}",
        f"- **Total Warnings**: {total_warnings}",
        f"- **Work Sessions**: {total_work_sessions}",
        f"- **Unique Tools Used**: {len(total_tool_calls)}",
    ])

    if total_tool_calls:
        lines.extend([
            "",
            "## Most Used Tools",
        ])
        for tool, count in total_tool_calls.most_common(10):
            lines.append(f"- `{tool}`: {count}")

    report = "\n".join(lines)

    # Save
    week_str = monday.strftime("%Y-W%V")
    report_path = REPORTS_DIR / f"week_{week_str}.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"Weekly summary written to {report_path}")

    return report
