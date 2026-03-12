import asyncio
import logging
from src.agents.spawner import SubAgent, AgentSpec
from src.tools.registry import ToolRegistry

logging.basicConfig(level=logging.INFO)

# Load basic tools to mock the environment
from src.tools import web, file_utils

async def main():
    spec = AgentSpec(
        task="latest breakthrough in solid state batteries",
        tools_whitelist=["search_web", "browse_site", "read_file", "list_files", "execute_code"],
    )
    class MockBot:
        pass
    
    agent = SubAgent(spec, MockBot())
    prompt = agent._build_system_prompt()
    print(f"System prompt length: {len(prompt)} chars")
    
    # Check if tools were actually loaded
    print(f"Loaded tools count: {len(ToolRegistry.list_tools())}")

asyncio.run(main())
