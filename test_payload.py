import asyncio
import logging
import logging
from src.agents.spawner import SubAgent, AgentSpec
from src.engines.rag_ollama import VectorEnhancedOllamaEngine
from config import settings
from src.tools.registry import ToolRegistry
from config import settings

logging.basicConfig(level=logging.INFO)

# Load tools explicitly
from src.tools import web, file_utils

async def run_spawner_test():
    class MockBot:
        pass
    bot = MockBot()
    
    topic = "latest breakthrough in solid state batteries"
    spec = AgentSpec(
        task=(
            f"Deep research the following topic: \n\n"
            f"**{topic}**\n\n"
            f"Instructions:\n"
            f"1. Start with broad web searches to establish the landscape.\n"
            f"2. Browse the most relevant pages for detailed information.\n"
            f"3. Search from multiple angles — different perspectives, controversies, recent developments.\n"
            f"4. Cross-reference findings across sources.\n"
            f"5. Produce a comprehensive markdown report with:\n"
            f"   - Executive summary\n"
            f"   - Key findings organized by theme\n"
            f"   - Sources cited inline\n"
            f"   - Areas of uncertainty or conflicting information noted\n\n"
            f"Be thorough. Use at least 5 different searches and browse at least 3 key pages."
        ),
        max_steps=5, # Short test
        tools_whitelist=["search_web", "browse_site", "read_file"]
    )
    
    agent = SubAgent(spec, bot)
    system_prompt = agent._build_system_prompt()
    full_context = "TURN 1:\nTools Executed:\n" + ("Fake webpage content...\n" * 10000)
    
    engine = VectorEnhancedOllamaEngine(
        model_name=settings.OLLAMA_CLOUD_MODEL, 
        base_url=settings.OLLAMA_BASE_URL,
        embedding_model=settings.OLLAMA_EMBED_MODEL
    )
    print(f"Using engine: {engine.name}")
    print(f"System prompt: {system_prompt[:200]}...")
    
    print("Calling generate_response...")
    # This should be exactly what spawner does
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, engine.generate_response,
        spec.task, full_context, system_prompt
    )
    with open("test_result.txt", "w") as f:
        f.write(f"Using engine: {engine.name}\n")
        f.write(f"System prompt: {system_prompt[:200]}...\n")
        f.write(f"Result length: {len(response) if response else 0}\n")
        f.write(f"Result raw: {repr(response)}\n")

asyncio.run(run_spawner_test())
