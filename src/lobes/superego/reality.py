import logging
import datetime
from ..base import BaseAbility
from src.tools.registry import ToolRegistry

logger = logging.getLogger("Lobe.Superego.Reality")

class RealityAbility(BaseAbility):
    """
    The Reality Guardian.
    Verifies claims against external truth via web search.
    """
    async def execute(self, claim: str) -> str:
        """
        Alias for check_claim to match standard ability interface.
        """
        return await self.check_claim(claim)
    
    async def check_claim(self, claim: str) -> str:
        """
        Conducts a Reality Check on a specific claim.
        1. Search Web
        2. Synthesize with Skeptic Prompt
        """
        logger.info(f"Reality Check: {claim}")
        
        # 1. Gather Evidence
        try:
            evidence = await ToolRegistry.execute("search_web", claim)
        except Exception as e:
            evidence = f"Search Failed: {e}"
            
        # 2. Neuro-Symbolic Synthesis
        try:
            from src.core.secure_loader import load_prompt
            template = load_prompt("src/prompts/skeptic_reality.txt")
                
            prompt = template.format(
                claim=claim,
                evidence=evidence, # Send full evidence
                date=datetime.date.today().isoformat()
            )
            
            engine = self.bot.engine_manager.get_active_engine()
            import functools
            call = functools.partial(engine.generate_response, prompt, caller="Lobe.Superego.Reality")
            response = await self.bot.loop.run_in_executor(None, call)
            
            return f"### [REALITY CHECK]\n{response}\n\n**Evidence**:\n{evidence}"
            
        except Exception as e:
            logger.error(f"Reality Check Failed: {e}")
            return f"Reality Check Error: {e}"
