import sys
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock
from src.lobes.creative.autonomy import AutonomyAbility

class DummyLoop:
    def __init__(self):
        self.run_behavior = ""
        self.responses = []
        self.idx = 0
        self.autonomy = None
    async def run_in_executor(self, executor, func, *args, **kwargs):
        if self.responses:
            if self.idx < len(self.responses):
                res = self.responses[self.idx]
                self.idx += 1
                return res
            if self.autonomy:
                self.autonomy.is_running = False
            return ""
        if self.autonomy:
            self.autonomy.is_running = False
        return self.run_behavior

class DummyEngineManager:
    def __init__(self):
        self.engine = MagicMock()
    def get_active_engine(self):
        return self.engine

class DummyBot:
    def __init__(self):
        self.loop = DummyLoop()
        self.engine_manager = DummyEngineManager()
        self.is_processing = False
        self.last_interaction = time.time() - 1000
        self.hippocampus = MagicMock()
        self.hippocampus.observe = AsyncMock()

async def test_execute_fatal_crash():
    mock_bot = DummyBot()
    lobe = MagicMock()
    lobe.cerebrum.bot = mock_bot
    autonomy = AutonomyAbility(lobe)
    
    mock_bot.loop.responses = [""]
    mock_bot.loop.autonomy = autonomy
    
    print("STARTING TEST FATAL CRASH")
    
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
        with patch("asyncio.sleep", side_effect=Exception("FATAL")):
            autonomy.is_running = True
            try:
                await autonomy.execute()
                print("Execute finished cleanly.")
            except Exception as e:
                print(f"Execute raised an exception!!! {type(e)}: {e}")
            print(f"autonomy.is_running = {autonomy.is_running}")

if __name__ == "__main__":
    asyncio.run(test_execute_fatal_crash())
