from ..base import BaseAbility
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from config import settings

logger = logging.getLogger("Lobe.Strategy.Goal")

class GoalAbility(BaseAbility):
    """
    Ambition Logic.
    Manages long-term goals in GoalManager.
    
    Features:
    - Real goal stagnation detection
    - LLM-driven goal decomposition
    - Timestamp-based auditing
    """
    
    STAGNATION_THRESHOLD_DAYS = 3
    
    async def execute(self):
        logger.info("Goal Ability checking active goals...")
        from src.tools.memory import manage_goals
        from src.bot import globals
        
        # Get user_id from context
        user_id = None
        if globals.active_message.get():
            user_id = str(globals.active_message.get().author.id)
        
        # List active goals
        goals = manage_goals("list", "", user_id=user_id)
        if "No active goals" in goals or not goals.strip():
            logger.info("No active goals found.")
            return None
            
        logger.info(f"Active Goals:\n{goals}")
        return goals

    async def _audit_goals(self, user_id: str = None) -> str:
        """
        Checks for stagnation (>3 days without update).
        Returns detailed audit report.
        """
        logger.info("GoalAbility: Auditing goals...")
        
        # Find user's goals file
        if user_id:
            goal_file = Path(f"memory/users/{user_id}/goals.json")
        else:
            # Try to get from context
            from src.bot import globals
            if globals.active_message.get():
                user_id = str(globals.active_message.get().author.id)
                goal_file = Path(f"memory/users/{user_id}/goals.json")
            else:
                return "❌ Cannot audit goals: No user context available."
        
        if not goal_file.exists():
            return "📋 No goals to audit - goal file doesn't exist."
        
        try:
            goals = json.loads(goal_file.read_text())
        except json.JSONDecodeError:
            return "❌ Cannot audit goals: Invalid goals file format."
        
        if not goals:
            return "📋 No goals to audit."
        
        # Analyze each goal
        now = datetime.now()
        stagnant = []
        active = []
        completed = []
        
        for goal in goals:
            status = goal.get("status", "active")
            
            if status == "completed":
                completed.append(goal)
                continue
            elif status == "removed":
                continue
            
            # Check for timestamps
            created_at = goal.get("created_at")
            updated_at = goal.get("updated_at") or created_at
            
            if updated_at:
                try:
                    last_update = datetime.fromisoformat(updated_at)
                    days_stale = (now - last_update).days
                    goal["_days_stale"] = days_stale
                    
                    if days_stale > self.STAGNATION_THRESHOLD_DAYS:
                        stagnant.append(goal)
                    else:
                        active.append(goal)
                except Exception:
                    # Can't parse timestamp, assume active
                    active.append(goal)
            else:
                # No timestamp, assume active
                active.append(goal)
        
        # Build report
        report = ["### Goal Audit Report"]
        report.append(f"**Active Goals**: {len(active)}")
        report.append(f"**Completed**: {len(completed)}")
        report.append(f"**Stagnant (>{self.STAGNATION_THRESHOLD_DAYS} days)**: {len(stagnant)}")
        
        if stagnant:
            report.append("\n⚠️ **Stagnant Goals (Need Attention)**:")
            for g in stagnant:
                days = g.get("_days_stale", "?")
                report.append(f"- [{g['id']}] {g['text']} - *{days} days without update*")
        
        if not stagnant:
            report.append("\n✅ All goals are on track!")
        
        return "\n".join(report)

    async def _decompose_goal(self, goal: str) -> dict:
        """
        Breaks high-level goals into sub-tasks (JSON).
        Uses LLM for intelligent decomposition.
        """
        logger.info(f"GoalAbility: Decomposing goal '{goal}'...")
        engine = self.bot.engine_manager.get_active_engine()
        
        if not engine:
            return {"error": "No inference engine available", "goal": goal}
        
        prompt = f"""ROLE: Goal Decomposition Expert

GOAL: {goal}

TASK: Break this goal into 3-5 specific, actionable sub-tasks.

OUTPUT FORMAT (JSON):
{{
    "goal": "{goal}",
    "subtasks": [
        {{
            "id": 1,
            "task": "specific subtask",
            "priority": "high|medium|low",
            "estimated_time": "time estimate"
        }}
    ],
    "first_step": "the very first action to take"
}}

JSON OUTPUT:"""
        
        try:
            response = await self.bot.loop.run_in_executor(None, engine.generate_response, prompt)
            
            # Parse JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
            
            return {"goal": goal, "plan": response}
        except Exception as e:
            return {"error": str(e), "goal": goal}
