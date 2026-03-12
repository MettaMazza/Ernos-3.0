from ..base import BaseAbility
import logging

logger = logging.getLogger("Lobe.Strategy.Architect")

class ArchitectAbility(BaseAbility):
    """
    Code Intelligence Ability.
    Understand file structures, syntax, and refactoring.
    """
    async def execute(self, task: str):
        logger.info(f"Architect analyzing task: {task}")
        
        engine = self.bot.engine_manager.get_active_engine()
        prompt = (
            f"ROLE: System Architect.\n"
            f"TASK: Analyze the following request and propose a high-level technical plan.\n"
            f"REQUEST: {task}\n\n"
            f"OUTPUT: A concise Implementation Plan."
        )
        
        try:
            response = await self.bot.loop.run_in_executor(
                None, 
                engine.generate_response, 
                prompt
            )
            return f"{response}"
        except Exception as e:
            return f"Architect Failure: {e}"
