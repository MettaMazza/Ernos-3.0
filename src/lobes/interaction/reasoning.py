from ..base import BaseAbility
import logging
from config import settings

logger = logging.getLogger("Lobe.Interaction.DeepReasoning")

class DeepReasoningAbility(BaseAbility):
    """
    Ability for complex, multi-step reasoning.
    """
    def __init__(self, lobe):
        super().__init__(lobe)

    async def execute(self, problem: str) -> str:
        """
        Think deeply about a problem.
        """
        # Chain-of-Thought execution
        prompt = (
            f"DEEP THOUGHT REQUEST: {problem}\n\n"
            f"INSTRUCTIONS: Think through this step-by-step. Break the problem down, analyze each component, "
            f"consider counter-arguments, and then synthesize a final conclusion."
        )
        
        # Match EngineManager signature
        engine = self.bot.engine_manager.get_active_engine()
        response = await self.bot.loop.run_in_executor(
            None,
            engine.generate_response,
            prompt,
            "" # context
        )
        return f"[DEEP THOUGHT]: {response}"
