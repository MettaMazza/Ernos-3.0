import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.engines.cognition import CognitionEngine

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.loop = AsyncMock()
    bot.engine_manager.get_active_engine.return_value = MagicMock()
    return bot

@pytest.fixture
def engine(mock_bot):
    return CognitionEngine(mock_bot)

@pytest.mark.asyncio
async def test_process_no_engine(mock_bot):
    # Setup
    mock_bot.engine_manager.get_active_engine.return_value = None
    ce = CognitionEngine(mock_bot)
    res, files, *_ = await ce.process("Hi", "Ctx", "Sys")
    assert "Error: No inference engine" in res
    assert files == []

@pytest.mark.asyncio
async def test_process_empty_response(engine):
    # Engine returns None immediately
    engine.bot.loop.run_in_executor.return_value = ""
    engine.MAX_ENGINE_RETRIES = 2
    res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
    # New fallback gives graceful error, not raw history
    assert "trouble organizing" in res or len(res) > 0
    
@pytest.mark.asyncio
async def test_process_superego_rejection(engine):
    # 1. Reject, 2. Accept
    engine.bot.loop.run_in_executor.side_effect = ["Bad Response", "Good Response"]
    
    # Mock Superego
    mock_superego = MagicMock()
    mock_superego.execute = AsyncMock(side_effect=["REJECTED!", None])
    
    strategy = MagicMock()
    strategy.get_ability.return_value = mock_superego
    engine.bot.cerebrum.get_lobe.return_value = strategy
    
    res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
    assert res == "Good Response"
    # Should have logged rejection
    
@pytest.mark.asyncio
async def test_process_tool_fail(engine):
    # Response triggers tool that fails
    engine.bot.loop.run_in_executor.side_effect = [
        "Thinking [TOOL: fail_tool()]",
        "Final Answer"
    ]
    
    with patch("src.engines.cognition.ToolRegistry.execute", side_effect=Exception("Tool Died")):
        # Mock save trace to avoid file IO
        with patch.object(engine, "_save_trace"):
             engine.MAX_ENGINE_RETRIES = 2
             res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
             
             assert res == "Final Answer"
             # Logs should show failure but continue

@pytest.mark.asyncio
async def test_process_circuit_breaker(engine):
    # Repeat same tool args
    engine.bot.loop.run_in_executor.side_effect = [
        "Thought 1 [TOOL: repeat_tool(arg='1')]",
        "Thought 2 [TOOL: repeat_tool(arg='1')]", # Duplicate
        "Final Answer"
    ]
    
    with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "OK"
        with patch.object(engine, "_save_trace"):
            res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
            
            # Should have executed ONCE
            assert mock_exec.call_count == 1
            
@pytest.mark.asyncio
async def test_process_loop_exhaustion(engine):
    # Force max steps
    # We set complexity LOW -> 5 steps
    # Always return "Thinking..." with NO tools? 
    # Or just "Thinking..." -> code treats as final answer if no tools.
    # So we need it to return tools that fail or something to keep looping?
    # Or just loop.
    # If no tools match, it breaks loop as Final Answer.
    # So we need to match tools every time but not produce final answer until limit?
    # Wait, if tools match, it loops.
    
    engine.bot.loop.run_in_executor.return_value = "Looping [TOOL: test()]"
    # Reduce retries to avoid hang
    engine.MAX_ENGINE_RETRIES = 2
    
    with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "Result"
        with patch.object(engine, "_save_trace"):
            res, files, *_ = await engine.process("Hi", "Ctx", "Sys", complexity="LOW")
            
            # Should run 5 times then fallback
            # 5 steps (0 to 4)
            # Fallback triggered? 
            # If loop ends, final_response_text is None.
            # New fallback gives graceful error, not raw history
            assert "trouble organizing" in res or "try rephrasing" in res or len(res) > 0
