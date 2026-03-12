import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from src.lobes.creative.autonomy import AutonomyAbility

class DummyBot:
    def __init__(self):
        self.loop = MagicMock()
        self.is_processing = False
        self.is_recreation = False
        self.last_interaction = time.time() - 1000
        self.last_search_time = 0
        self.hippocampus = MagicMock()
        self.hippocampus.observe = AsyncMock()
        self.skill_registry = MagicMock()
        self.skill_registry.list_skills = MagicMock(return_value=[])

async def test_execute_parsers():
    bot = DummyBot()
    lobe = MagicMock()
    lobe.cerebrum.bot = bot
    autonomy = AutonomyAbility(lobe)
    
    class FakeLoop:
        def __init__(self):
            self.idx = 0
            self.responses = []
            self.autonomy = None
        async def run_in_executor(self, *args):
            res = self.responses[self.idx] if self.idx < len(self.responses) else ""
            self.idx += 1
            if self.idx >= len(self.responses) and self.autonomy:
                self.autonomy.is_running = False
            print(f">>> Engine returned: {res}")
            return res
            
    bot.loop = FakeLoop()
    bot.loop.autonomy = autonomy
    
    print("\n--- TEST PARENS ---")
    bot.loop.responses = ["[TOOL: search_web( (nested), \"escape\" )]"]
    bot.loop.idx = 0
    autonomy.is_running = True
    await autonomy.execute()
    
    print("\n--- TEST SET GOAL COOLDOWN ---")
    bot.loop.responses = ["[TOOL: set_goal(description='cooldown')]"]
    bot.loop.idx = 0
    autonomy._last_goal_time = time.time() - 10
    autonomy.is_running = True
    await autonomy.execute()
    
    print("\n--- TEST SCHEDULED TASK ---")
    bot.loop.responses = ["[TOOL: dummy()]"] * 40
    bot.loop.idx = 0
    res = await autonomy.run_task("Task")
    print(f"run_task final: {len(res)} chars")

asyncio.run(test_execute_parsers())
