import asyncio
import sys
import logging
from unittest.mock import MagicMock, AsyncMock, patch

# Configure logging to see the error
logging.basicConfig(level=logging.ERROR)

async def test_support_crash():
    print("--- Starting Reproduction Test ---")
    
    # Mock dependencies
    bot = MagicMock()
    bot.loop = asyncio.get_event_loop()
    
    # Mock Cerebrum/Hippocampus to avoid attribute errors
    bot.cerebrum = MagicMock()
    bot.hippocampus = MagicMock()
    bot.hippocampus.graph = MagicMock()
    
    # Mock Engine Manager
    engine_manager = MagicMock()
    bot.engine_manager = engine_manager
    
    # Mock sys.modules for missing dependencies
    sys.modules["ollama"] = MagicMock()
    sys.modules["numpy"] = MagicMock()
    sys.modules["PIL"] = MagicMock()
    sys.modules["discord"] = MagicMock()
    sys.modules["src.tools.browser"] = MagicMock() 
    sys.modules["src.tools.document"] = MagicMock()
    sys.modules["src.tools.context_retrieval"] = MagicMock()
    sys.modules["src.tools.chat_tools"] = MagicMock()
    sys.modules["src.tools.support_tools"] = MagicMock()
    
    # Import CognitionEngine
    # We need to make sure src is in path
    sys.path.append(".")
    
    try:
        from src.engines.cognition import CognitionEngine
    except ImportError as e:
        print(f"Import Error: {e}")
        return

    # Instantiate Engine
    engine = CognitionEngine(bot)
    
    # Mock engine.generate_response (the LLM call) to avoid hitting actual API
    # We mock it to return a simple string
    engine.generate_response = MagicMock(return_value="Hello, this is a test response.")
    
    # Mock run_in_executor to execute the mocked generate_response
    bot.loop.run_in_executor = AsyncMock(return_value="Hello, this is a test response.")

    # Arguments used in support.py
    user_input = "I need help with my account."
    context_str = "Prior context here."
    system_prompt = "System prompt."
    user_id = "12345"
    channel_id = "67890"

    print("Invoking engine.process()...")
    try:
        response = await engine.process(
            input_text=user_input,
            context=context_str,
            system_context=system_prompt,
            images=None,
            complexity="HIGH",
            user_id=user_id,
            channel_id=channel_id,
            request_scope="SUPPORT"
        )
        print("Success! Response:", response)
    except Exception as e:
        print("\n!!! CRASH DETECTED !!!")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Message: {e}")
        import traceback
        traceback.print_exc()
    assert response is not None

if __name__ == "__main__":
    asyncio.run(test_support_crash())
