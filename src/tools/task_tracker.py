"""
TaskTracker — Step-by-step task tracking for multi-step requests.

Provides plan_task, complete_step, and get_task_status tools so Ernos
can decompose complex requests into steps and track progress.
State is per-user, persisted to memory/users/{id}/active_task.json.
"""
import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional

from .registry import ToolRegistry

logger = logging.getLogger("Tools.TaskTracker")


@dataclass
class TaskStep:
    id: int
    description: str
    status: str = "PENDING"  # PENDING | ACTIVE | DONE | SKIPPED


@dataclass
class TaskState:
    goal: str
    steps: List[TaskStep]
    current_step: int = 0
    created_at: float = field(default_factory=time.time)
    status: str = "ACTIVE"  # ACTIVE | COMPLETED | FAILED


# In-memory cache, keyed by user_id
_active_tasks: dict = {}
EXPIRY_SECONDS = 3600  # 1 hour


def _get_persist_path(user_id: str) -> Path:
    return Path(f"memory/users/{user_id}/active_task.json")


def _load_task(user_id: str) -> Optional[TaskState]:
    """Load from memory or disk."""
    if user_id in _active_tasks:
        task = _active_tasks[user_id]
        if time.time() - task.created_at < EXPIRY_SECONDS:
            return task
        # Expired — clean up
        del _active_tasks[user_id]
    # Try disk
    path = _get_persist_path(user_id)
    if path.exists():
        try:
            data = json.loads(path.read_text())
            if time.time() - data.get("created_at", 0) < EXPIRY_SECONDS:
                steps = [TaskStep(**s) for s in data["steps"]]
                task = TaskState(
                    goal=data["goal"], steps=steps,
                    current_step=data["current_step"],
                    created_at=data["created_at"],
                    status=data.get("status", "ACTIVE"),
                )
                _active_tasks[user_id] = task
                return task
        except Exception as e:
            logger.debug(f"Task load failed for user {user_id}: {e}")
    return None


def _save_task(user_id: str, task: TaskState):
    """Save to memory and disk."""
    _active_tasks[user_id] = task
    path = _get_persist_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "goal": task.goal,
        "steps": [asdict(s) for s in task.steps],
        "current_step": task.current_step,
        "created_at": task.created_at,
        "status": task.status,
    }
    path.write_text(json.dumps(data, indent=2))


def _clear_task(user_id: str):
    """Remove active task from memory and disk."""
    _active_tasks.pop(user_id, None)
    path = _get_persist_path(user_id)
    if path.exists():
        path.unlink()


@ToolRegistry.register(
    name="plan_task",
    description="Break a complex request into numbered steps. Call FIRST for multi-step tasks."
)
def plan_task(goal: str, steps: str, user_id: str = None, **kwargs) -> str:
    """
    Create a task plan.
    Args:
        goal: What the user wants to accomplish
        steps: Pipe-separated step descriptions,
               e.g. "Design layout|Write HTML|Write CSS|Test"
    """
    if not user_id:
        return "Error: user_id required for task tracking."
    step_list = [s.strip() for s in steps.split("|") if s.strip()]
    if not step_list:
        return "Error: provide at least one step (pipe-separated)."
    if len(step_list) > 20:
        return "Error: maximum 20 steps per task."

    task_steps = [TaskStep(id=i, description=desc) for i, desc in enumerate(step_list)]
    task_steps[0].status = "ACTIVE"
    task = TaskState(goal=goal, steps=task_steps)
    _save_task(str(user_id), task)
    logger.info(f"Task created for user {user_id}: {goal} ({len(step_list)} steps)")
    return _format_status(task)


@ToolRegistry.register(
    name="complete_step",
    description="Mark the current step as done and advance to the next step."
)
def complete_step(user_id: str = None, **kwargs) -> str:
    """Mark the current step as done and advance."""
    if not user_id:
        return "Error: user_id required."
    task = _load_task(str(user_id))
    if not task or task.status != "ACTIVE":
        return "No active task. Use plan_task first."

    # Mark current step done
    if task.current_step < len(task.steps):
        task.steps[task.current_step].status = "DONE"

    # Advance
    task.current_step += 1
    if task.current_step >= len(task.steps):
        task.status = "COMPLETED"
        _save_task(str(user_id), task)
        result = _format_status(task)
        # Auto-clear completed tasks after saving final status
        return result
    else:
        task.steps[task.current_step].status = "ACTIVE"

    _save_task(str(user_id), task)
    return _format_status(task)


@ToolRegistry.register(
    name="skip_step",
    description="Skip the current step and move to the next."
)
def skip_step(user_id: str = None, reason: str = "", **kwargs) -> str:
    """Skip a step that isn't needed."""
    if not user_id:
        return "Error: user_id required."
    task = _load_task(str(user_id))
    if not task or task.status != "ACTIVE":
        return "No active task."

    if task.current_step < len(task.steps):
        task.steps[task.current_step].status = "SKIPPED"

    task.current_step += 1
    if task.current_step >= len(task.steps):
        task.status = "COMPLETED"
    else:
        task.steps[task.current_step].status = "ACTIVE"

    _save_task(str(user_id), task)
    return _format_status(task)


@ToolRegistry.register(
    name="get_task_status",
    description="Show current task progress."
)
def get_task_status(user_id: str = None, **kwargs) -> str:
    """Returns formatted task status."""
    if not user_id:
        return "No active task."
    task = _load_task(str(user_id))
    if not task:
        return "No active task."
    return _format_status(task)


def get_active_task_context(user_id) -> str:
    """
    Called by cognition.py to inject task progress into the LLM context.
    Returns empty string if no active task.
    """
    if not user_id:
        return ""
    task = _load_task(str(user_id))
    if not task or task.status != "ACTIVE":
        return ""

    icons = {"PENDING": "⬜", "ACTIVE": "🔶", "DONE": "✅", "SKIPPED": "⏭️"}
    lines = [f"[ACTIVE TASK: {task.goal}]"]
    for s in task.steps:
        icon = icons.get(s.status, "❓")
        lines.append(f"  {icon} Step {s.id}: {s.description} [{s.status}]")
    lines.append(
        f"[CURRENT: Step {task.current_step} — "
        f"Focus on this step ONLY. Do NOT repeat completed steps.]"
    )
    return "\n".join(lines)


def _format_status(task: TaskState) -> str:
    """Format task status for tool output."""
    icons = {"PENDING": "⬜", "ACTIVE": "🔶", "DONE": "✅", "SKIPPED": "⏭️"}
    lines = [f"Task: {task.goal} [{task.status}]"]
    for s in task.steps:
        icon = icons.get(s.status, "❓")
        lines.append(f"  {icon} {s.id}: {s.description}")
    if task.status == "COMPLETED":
        lines.append("✅ All steps complete!")
    elif task.current_step < len(task.steps):
        lines.append(
            f"▶ Next: Step {task.current_step} — "
            f"{task.steps[task.current_step].description}"
        )
    return "\n".join(lines)
