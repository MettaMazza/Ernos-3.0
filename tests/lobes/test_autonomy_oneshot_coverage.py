import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock
import json

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

class DummyCognition:
    def __init__(self, loop):
        self.loop = loop
    
    async def process(self, *args, **kwargs):
        return await self.loop.run_in_executor(None, None)

class DummyBot:
    def __init__(self):
        self.loop = DummyLoop()
        self.cognition = DummyCognition(self.loop)
        self.engine_manager = DummyEngineManager()
        self.is_processing = False
        self.last_interaction = time.time() - 1000
        self.hippocampus = MagicMock()
        self.hippocampus.observe = AsyncMock()

@pytest.fixture(autouse=True)
def mock_sleep():
    with patch("asyncio.sleep", new_callable=AsyncMock) as m:
        yield m

@pytest.fixture(autouse=True)
def mock_quota():
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True) as m:
        yield m

@pytest.fixture
def mock_bot():
    return DummyBot()

@pytest.fixture
def autonomy(mock_bot):
    lobe = MagicMock()
    lobe.cerebrum.bot = mock_bot
    return AutonomyAbility(lobe)

@pytest.mark.asyncio
async def test_oneshot_trim_context(autonomy, mock_bot):
    string_block = "[TOOL: dummy(1)]\n" + ("x" * 60000)
    mock_bot.loop.responses = [string_block]
    mock_bot.loop.autonomy = autonomy
    
    with patch('src.lobes.creative.autonomy.ToolRegistry.execute', new_callable=AsyncMock) as mock_exec:
        await autonomy.execute()


