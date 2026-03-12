import asyncio
import logging
from src.tools.web import start_deep_research
from src.bot.client import ErnosBot
from src.bot import globals

logging.basicConfig(level=logging.INFO)

async def run_direct_research():
    from unittest.mock import AsyncMock
    bot = ErnosBot()
    bot.tree.sync = AsyncMock()
    bot.maintenance_loop.start = lambda: None
    await bot.setup_hook()
    globals.bot = bot # inject bot explicitly into global scope
    
    # Disable autonomy loop
    from src.lobes.creative.autonomy import AutonomyAbility
    AutonomyAbility.execute = AsyncMock()
    
    from src.lobes.interaction.researcher import ResearchAbility
    print("\n\n--- STARTING DEEP RESEARCH NATIVELY ---")
    interaction_lobe = bot.cerebrum.get_lobe("InteractionLobe")
    researcher = interaction_lobe.get_ability("ResearchAbility") if interaction_lobe else None
    if not researcher:
        print("Failed to get ResearchAbility")
        return
        
    result = await researcher.execute(
        query="latest breakthrough in solid state batteries"
    )
    print("\n--- DEEP RESEARCH FINISHED ---")
    print(f"Result returned to user: {result[:500]}...")

asyncio.run(run_direct_research())
