import asyncio
import logging
from src.agents.spawner import AgentSpawner, AgentSpec
from src.engines import VectorEnhancedOllamaEngine
from unittest.mock import MagicMock

logging.basicConfig(level=logging.INFO)

async def test_spawner():
    print("--- STARTING LIGHTWEIGHT SPAWNER TEST ---")
    
    # Mock Bot and Engine Manager
    bot = MagicMock()
    bot.engine_manager = MagicMock()
    
    from config import settings
    # Use real Olamma engine for generation
    engine = VectorEnhancedOllamaEngine(
        model_name=settings.OLLAMA_CLOUD_MODEL, 
        base_url=settings.OLLAMA_BASE_URL
    )
    bot.engine_manager.get_active_engine.return_value = engine
    
    # Set global bot (some tools might depend on it)
    from src.bot import globals
    globals.bot = bot
    
    # Create Spec
    spec = AgentSpec(
        task="Tell me what the largest living organism is. Use the search_web tool.",
        max_steps=5,
        tools_whitelist=["search_web", "calculator"]
    )
    
    result = await AgentSpawner.spawn(spec, bot)
    print("\n--- TEST FINISHED ---")
    print(f"Status: {result.status}")
    print(f"Output: {result.output}")
    print(f"Steps taken: {result.steps_taken}")

if __name__ == "__main__":
    asyncio.run(test_spawner())
