import pytest
from unittest.mock import MagicMock
from src.engines.cognition import CognitionEngine
from src.memory.types import GraphLayer

@pytest.fixture
def mock_llm_client():
    return MagicMock()

@pytest.mark.asyncio
class TestContextSwitching:
    async def test_social_layer_uses_diplomat_persona(self, mock_llm_client):
        """
        Symbolic Constraint: When thinking in Social layer, System Prompt must set persona to Diplomat.
        """
        # Mock Bot Structure
        mock_bot = MagicMock()
        mock_bot.engine_manager.get_active_engine.return_value = mock_llm_client
        
        
        async def async_runner(executor, func, *args):
            return func(*args)
            
        mock_bot.loop.run_in_executor.side_effect = async_runner
        
        # FIX: Ensure it returns a string, not a Mock
        mock_llm_client.generate_response.return_value = "This is a diplomatically generated response."

        engine = CognitionEngine(bot=mock_bot)
        
        # We invoke process with the new layout argument (driving API change)
        await engine.process("Analyze this interaction", context="", system_context="Base System", layer=GraphLayer.SOCIAL)
        
        # Verify the call to the LLM contained the specific persona instruction
        # engine.generate_response is called via run_in_executor
        
        # Check mock_llm_client.generate_response calls
        call_args = mock_llm_client.generate_response.call_args
        assert call_args is not None
        
        # generate_response(input_text, context, dynamic_system, images)
        args, _ = call_args
        dynamic_system = args[2]
        
        assert "Diplomat" in dynamic_system or "social status" in dynamic_system
        assert "game-theoretic" in dynamic_system

    async def test_causal_layer_uses_scientist_persona(self, mock_llm_client):
        mock_bot = MagicMock()
        mock_bot.engine_manager.get_active_engine.return_value = mock_llm_client
        
        async def async_runner(executor, func, *args):
            return func(*args)
        
        mock_bot.loop.run_in_executor.side_effect = async_runner
        
        mock_llm_client.generate_response.return_value = "The event was caused by a causal loop."

        engine = CognitionEngine(bot=mock_bot)
        await engine.process("Why did this happen?", context="", system_context="Base System", layer=GraphLayer.CAUSAL)
        
        args, _ = mock_llm_client.generate_response.call_args
        dynamic_system = args[2]
        
        assert "Scientist" in dynamic_system or "Causality" in dynamic_system
        assert "DAG" in dynamic_system
