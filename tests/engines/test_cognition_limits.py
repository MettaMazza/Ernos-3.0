import pytest
import asyncio
from unittest.mock import MagicMock, patch

from src.engines.cognition import CognitionEngine

@pytest.mark.asyncio
async def test_cognition_per_step_tool_cap():
    """
    Ensures that if the LLM glitches and emits > 15 tool calls in a single step,
    the engine violently trims it back to 15 to prevent DDOSing the machine/external APIs.
    """
    bot = MagicMock()
    bot.cerebrum.get_lobe.return_value = None  # No skeptic for this minimal test
    
    # Mock engine that spits out 50 tool calls at once
    engine = MagicMock()
    spam_response = "".join(["[TOOL: search_web(query=\"spam\")]" for _ in range(50)])
    # We want it to stop after one step, so we'll mock execute_tool_step to return (__CONTINUE__, count, True) or something, 
    # but the easiest way is just let it run and raise an exception or run out of tools.
    # We'll just have it return the spam then return a final answer saying done.
    engine.generate_response.side_effect = [
        spam_response,
        "Final Answer"
    ]
    bot.engine_manager.get_active_engine.return_value = engine

    async def mock_executor(executor, func, *args, **kwargs):
        return func(*args, **kwargs)
    bot.loop.run_in_executor.side_effect = mock_executor

    loop = CognitionEngine(bot)

    # Patch the actual tool executor so it doesn't really run
    with patch("src.engines.cognition.execute_tool_step") as mock_exec:
        mock_exec.return_value = ("Success", 0, True)

        await loop.process(
            input_text="Do a lot of searches",
            context="",
            system_context=""
        )

        # The engine should have only executed 15 tools, NOT 50
        assert mock_exec.call_count == 15

