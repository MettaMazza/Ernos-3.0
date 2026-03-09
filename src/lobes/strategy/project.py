from ..base import BaseAbility
import logging
import json
from datetime import datetime

logger = logging.getLogger("Lobe.Strategy.Project")

class ProjectLeadAbility(BaseAbility):
    """
    Task Management Ability.
    Breaks down vague requests into milestones using LLM.
    
    Features:
    - LLM-driven task decomposition
    - Structured milestone output
    - KnowledgeGraph storage for task tracking
    """
    
    async def execute(self, request: str) -> dict:
        logger.info(f"Project Lead breaking down: {request}")
        
        engine = self.bot.engine_manager.get_active_engine()
        if not engine:
            logger.error("No inference engine available")
            return {"error": "No inference engine available", "milestones": []}
        
        # Build decomposition prompt
        prompt = f"""ROLE: Project Lead / Task Decomposition Expert

REQUEST: {request}

TASK: Break this request into specific, actionable milestones.

OUTPUT FORMAT (JSON):
{{
    "project_name": "concise project name",
    "milestones": [
        {{
            "id": 1,
            "title": "milestone title",
            "description": "what needs to be done",
            "dependencies": [],  // list of milestone IDs this depends on
            "estimated_effort": "small|medium|large",
            "success_criteria": "how to verify completion"
        }}
    ],
    "estimated_total_effort": "overall project size",
    "risks": ["potential risk 1", "potential risk 2"]
}}

Generate 3-7 milestones. Be specific and actionable.
JSON OUTPUT:"""

        try:
            # Call LLM for decomposition
            response = await self.bot.loop.run_in_executor(
                None,
                engine.generate_response,
                prompt,
                ""  # context
            )
            
            # Parse JSON response
            project_plan = self._parse_project_plan(response)
            
            # Store in KnowledgeGraph if valid
            if project_plan.get("milestones") and self.hippocampus and self.hippocampus.graph:
                self._store_milestones_in_kg(project_plan, request)
            
            return project_plan
            
        except Exception as e:
            logger.error(f"Project decomposition failed: {e}")
            return {"error": str(e), "milestones": []}
    
    def _parse_project_plan(self, response: str) -> dict:
        """Extract JSON project plan from LLM response."""
        try:
            # Try to find JSON in response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                plan = json.loads(json_match.group())
                # Validate structure
                if "milestones" in plan and isinstance(plan["milestones"], list):
                    return plan
            
            # Fallback: create simple structure from response
            return {
                "project_name": "Unnamed Project",
                "milestones": [
                    {"id": 1, "title": f"Complete: {response[:100]}...", "description": response}
                ],
                "raw_response": response
            }
        except json.JSONDecodeError:
            return {
                "project_name": "Unnamed Project", 
                "milestones": [
                    {"id": 1, "title": "Parse and execute request", "description": response}
                ],
                "raw_response": response
            }
    
    def _store_milestones_in_kg(self, plan: dict, original_request: str):
        """Store project milestones in KnowledgeGraph for tracking."""
        try:
            from src.memory.types import GraphLayer
            from src.bot import globals
            from src.privacy.scopes import ScopeManager
            
            graph = self.hippocampus.graph
            project_name = plan.get("project_name", "Unnamed Project")
            
            # STRICT: Get user_id from active message context
            user_id = None
            scope = "PUBLIC"  # Default scope
            msg = globals.active_message.get()
            if msg:
                user_id = msg.author.id
                is_dm = not hasattr(msg.channel, 'guild') or msg.channel.guild is None
                scope = ScopeManager.get_scope(user_id, msg.channel.id, is_dm=is_dm).name
            
            if not user_id:
                logger.warning("ProjectLead: Cannot store project without user_id. Aborting KG write.")
                return
            
            # Create project node - owned by user
            graph.add_node(
                label="Project",
                name=project_name,
                layer=GraphLayer.PROCEDURAL,
                properties={
                    "original_request": original_request[:2000],
                    "created_at": datetime.now().isoformat(),
                    "status": "planned",
                    "created_by": str(user_id)
                },
                user_id=user_id,
                scope=scope
            )
            
            # Create milestone nodes and relationships
            for milestone in plan.get("milestones", []):
                milestone_name = f"{project_name}:M{milestone.get('id', 0)}"
                graph.add_node(
                    label="Milestone",
                    name=milestone_name,
                    layer=GraphLayer.PROCEDURAL,
                    properties={
                        "title": milestone.get("title", ""),
                        "description": milestone.get("description", "")[:500],
                        "effort": milestone.get("estimated_effort", "medium"),
                        "status": "pending"
                    },
                    user_id=user_id,
                    scope=scope
                )
                
                # Link milestone to project
                graph.add_relationship(
                    source_name=project_name,
                    rel_type="HAS_MILESTONE",
                    target_name=milestone_name,
                    layer="task",
                    user_id=user_id,
                    scope=scope
                )
            
            logger.info(f"Stored project '{project_name}' with {len(plan.get('milestones', []))} milestones in KG (user={user_id}, scope={scope})")
            
        except Exception as e:
            logger.warning(f"Failed to store project in KG: {e}")

