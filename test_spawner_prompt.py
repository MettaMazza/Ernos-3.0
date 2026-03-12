import asyncio
from src.agents.spawner import AgentSpawner, AgentSpec
from src.bot.globals import bot

async def main():
    spec = AgentSpec(
        task="latest breakthrough in solid state batteries",
        tools_whitelist=["search_web", "browse_site", "read_file"],
    )
    # mock bot
    class MockBot:
        pass
    agent = AgentSpawner(spec, MockBot())
    prompt = agent._build_system_prompt()
    print(f"System prompt length: {len(prompt)} chars")

asyncio.run(main())
