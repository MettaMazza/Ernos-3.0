"""
Planning Tools — Enables Ernos to draft plans for user review before execution.

Provides draft_plan and get_plan tools for the plan-before-act workflow.
Plans are saved to memory/users/{user_id}/plans/ for persistence.
"""
import json
import time
import logging
from pathlib import Path

from .registry import ToolRegistry
from src.core.data_paths import data_dir

logger = logging.getLogger("Tools.Planning")


@ToolRegistry.register(
    name="draft_plan",
    description=(
        "Draft an implementation plan for user review before executing complex tasks. "
        "Use for tasks with 3+ steps or multi-file creation."
    )
)
def draft_plan(title: str, steps: str, rationale: str = "",
               user_id: str = None, **kwargs) -> str:
    """
    Save a plan for the user to review.
    Args:
        title: What this plan accomplishes
        steps: Pipe-separated step descriptions
        rationale: Why this approach was chosen
    """
    if not user_id:
        return "Error: user_id required."

    plan_dir = Path(str(data_dir()) + f"/users/{user_id}/plans")
    plan_dir.mkdir(parents=True, exist_ok=True)

    plan_id = f"plan_{int(time.time())}"
    step_list = [s.strip() for s in steps.split("|") if s.strip()]
    if not step_list:
        return "Error: provide at least one step (pipe-separated)."

    plan = {
        "id": plan_id,
        "title": title,
        "steps": step_list,
        "rationale": rationale,
        "status": "DRAFT",
        "created_at": time.time(),
    }
    path = plan_dir / f"{plan_id}.json"
    path.write_text(json.dumps(plan, indent=2))

    # Format for user review
    lines = [f"📋 **Plan: {title}**"]
    if rationale:
        lines.append(f"*Rationale: {rationale}*")
    lines.append("")
    for i, step in enumerate(step_list):
        lines.append(f"  {i + 1}. {step}")
    lines.append("")
    lines.append("Should I proceed with this plan?")

    logger.info(f"Plan drafted for user {user_id}: {title} ({len(step_list)} steps)")
    return "\n".join(lines)


@ToolRegistry.register(
    name="get_plan",
    description="Retrieve a saved plan by ID, or get the most recent plan."
)
def get_plan(plan_id: str = None, user_id: str = None, **kwargs) -> str:
    """
    Retrieve a saved plan.
    Args:
        plan_id: Specific plan ID to retrieve (optional — defaults to most recent)
    """
    if not user_id:
        return "Error: user_id required."

    plan_dir = Path(str(data_dir()) + f"/users/{user_id}/plans")
    if not plan_dir.exists():
        return "No plans found."

    if plan_id:
        path = plan_dir / f"{plan_id}.json"
        if path.exists():
            data = json.loads(path.read_text())
            return _format_plan(data)

    # Return most recent
    plans = sorted(plan_dir.glob("plan_*.json"), reverse=True)
    if plans:
        data = json.loads(plans[0].read_text())
        return _format_plan(data)

    return "No plans found."


def _format_plan(data: dict) -> str:
    """Format a plan dict for display."""
    lines = [f"📋 **{data.get('title', 'Untitled')}** [{data.get('status', '?')}]"]
    if data.get("rationale"):
        lines.append(f"*{data['rationale']}*")
    for i, step in enumerate(data.get("steps", [])):
        lines.append(f"  {i + 1}. {step}")
    return "\n".join(lines)
