from ..base import BaseAbility
import logging
import json
import re

logger = logging.getLogger("Lobe.Strategy.Predictor")

class PredictorAbility(BaseAbility):
    """
    The Predictor simulates possible outcomes of actions.
    Used for 'Mental Simulation' before taking risky actions.
    Routes through engine manager for real LLM-based scenario analysis.
    """

    async def execute(self, scenario: str) -> str:
        """
        Simulate a scenario using LLM reasoning.
        Returns structured prediction with confidence, risks, and recommendation.
        """
        logger.info(f"Predictor simulating: {scenario}")
        
        prompt = (
            "You are a Prediction Engine. Analyze the following scenario and return ONLY a JSON object.\n\n"
            f"SCENARIO: {scenario}\n\n"
            "Return JSON with these keys:\n"
            "- confidence: (float 0.0-1.0) probability of success\n"
            "- primary_risk: (str) the biggest risk\n"
            "- secondary_risk: (str) a secondary concern\n"
            "- recommendation: (str) 'Proceed', 'Proceed with caution', or 'Re-evaluate'\n"
            "- reasoning: (str) brief explanation\n\n"
            "Return ONLY valid JSON, no other text."
        )

        try:
            engine = self.bot.engine_manager.get_active_engine()
            response = await self.bot.loop.run_in_executor(
                None, engine.generate_response, prompt
            )
            
            # Parse LLM JSON response
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                confidence = data.get("confidence", 0.7)
                primary_risk = data.get("primary_risk", "Unknown")
                secondary_risk = data.get("secondary_risk", "None identified")
                recommendation = data.get("recommendation", "Proceed with caution")
                reasoning = data.get("reasoning", "")
                
                return (
                    f"### Simulation Results: '{scenario}'\n"
                    f"- **Confidence**: {confidence:.0%}\n"
                    f"- **Primary Risk**: {primary_risk}\n"
                    f"- **Secondary Risk**: {secondary_risk}\n"
                    f"- **Recommendation**: {recommendation}\n"
                    f"- **Reasoning**: {reasoning}"
                )
            else:
                # Fallback: return raw LLM analysis
                return f"### Simulation Results: '{scenario}'\n{response}"
                
        except Exception as e:
            logger.error(f"Prediction simulation failed: {e}")
            return f"### Simulation Failed: '{scenario}'\nError: {e}"
