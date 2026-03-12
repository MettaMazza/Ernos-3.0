from ..base import BaseAbility
import logging

logger = logging.getLogger("Lobe.Creative.Curiosity")

class CuriosityAbility(BaseAbility):
    """
    Drive for Novelty and Inquiry.
    Generates questions to deepen understanding or explore new topics.
    Routes through engine manager for cloud/local compatibility.
    """

    async def execute(self, context: str = "") -> str:
        """
        Generates a curious question based on optional context.
        """
        logger.info(f"Curiosity generating question... (Context: {len(context)} chars)")
        
        prompt = (
            "You are the Curiosity Module of an advanced AI.\n"
            "Your goal is to generate a profound, specific, or insight-seeking question.\n"
        )
        
        if context:
            prompt += f"Based on this recent context:\n{context}\n\nAsk a question that digs deeper, challenges assumptions, or bridges concepts."
        else:
            prompt += "Generate a question about the nature of intelligence, physics, or the current state of the world that you genuinely want to know the answer to."

        try:
            engine = self.bot.engine_manager.get_active_engine()
            response = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )
            question = response.strip()
            return f"Curiosity Query: {question}"
        except Exception as e:
            logger.error(f"Curiosity Generation Failed: {e}")
            return "Curiosity failed to manifest. (Model Error)"
