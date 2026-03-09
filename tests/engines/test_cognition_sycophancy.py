
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, ANY
from src.engines.cognition import CognitionEngine

@pytest.fixture
def mock_bot_obj():
    bot = MagicMock()
    bot.loop = AsyncMock()
    # Mock global engine manager
    mock_active_engine = MagicMock()
    mock_active_engine.context_limit = 2000 # Fix truncation issue
    mock_active_engine.generate_response = MagicMock()
    bot.engine_manager.get_active_engine.return_value = mock_active_engine
    
    # Mock send_to_mind (AsyncMock)
    bot.send_to_mind = AsyncMock()
    
    # Mock Superego to avoid await error
    mock_superego = MagicMock()
    mock_superego.execute = AsyncMock(return_value=None)
    
    # Mock Skeptic Audit and Integrity
    mock_audit = MagicMock()
    mock_audit.audit_response = AsyncMock(return_value={"allowed": True, "reason": ""})
    mock_audit.verify_response_integrity = MagicMock(return_value=(True, ""))
    
    mock_superego_lobe = MagicMock()
    mock_superego_lobe.get_ability.return_value = mock_audit
    
    mock_strategy = MagicMock()
    mock_strategy.get_ability.return_value = mock_superego
    
    # We need cerebrum.get_lobe to return different things for Strategy vs Superego
    def get_lobe_side_effect(name):
        if name == "StrategyLobe":
            return mock_strategy
        if name == "SuperegoLobe":
            return mock_superego_lobe
        return MagicMock()
        
    bot.cerebrum.get_lobe.side_effect = get_lobe_side_effect
    
    return bot

@pytest.fixture
def engine(mock_bot_obj):
    return CognitionEngine(mock_bot_obj)

@pytest.mark.asyncio
async def test_process_mandatory_reality_check(engine, mock_bot_obj):
    # Setup - mock the engine response
    # Step 1: Reality Check happens BEFORE loop (via ToolRegistry)
    # Step 2: Engine called with injected context
    
    # Mock Engine Response: First turn uses tool, Second turn gives final answer
    # Note: run_in_executor is called for generate_response
    mock_bot_obj.loop.run_in_executor.side_effect = [
        "I need to check... [TOOL: consult_skeptic(claim='Is the earth flat?')]",
        "Final Answer based on reality."
    ]
    
    with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "Skeptic says: False Claim."
        
        # Call process with request_reality_check=True
        # Note: input_text is "Is the earth flat?"
        await engine.process(
            "Is the earth flat?", 
            "Context", 
            "System", 
            request_reality_check=True
        )
        
        # Verify ToolRegistry called with consult_skeptic
        # Note: kwargs user_id=None, request_scope=None might be passed depending on CognitionEngine logic
        # We use assert_any_call to be flexible
        mock_exec.assert_any_call("consult_skeptic", claim="Is the earth flat?", user_id=None, request_scope=None, bot=ANY)
        
        # Verify the context passed to generate_response contained the skeptic result
        # We need to check the call args of run_in_executor
        call_args_list = mock_bot_obj.loop.run_in_executor.call_args_list
        # We look for the call that corresponds to generate_response
        
        found_context = False
        for call_args in call_args_list:
            # Check args
            args = call_args[0]
            # args[0] is None, args[1] is func, args[2] is input, args[3] is context
            if len(args) >= 4 and isinstance(args[3], str):
                # Update string to match code in cognition.py
                if "[SYSTEM: EXTERNAL GROUNDING REQUIRED]" in args[3] and "Skeptic says: False Claim." in args[3]:
                    found_context = True
                    break
        
        assert found_context, "Skeptic result not found in context passed to engine."
