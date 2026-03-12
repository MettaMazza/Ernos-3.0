import sys
import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock
from src.lobes.creative.autonomy import AutonomyAbility

class DummyLoop:
    def __init__(self):
        self.run_behavior = ""
    async def run_in_executor(self, executor, func, *args, **kwargs):
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

class SequenceExecutor:
    def __init__(self, responses, autonomy_instance):
        self.responses = responses
        self.idx = 0
        self.autonomy = autonomy_instance
    async def __call__(self, *args, **kwargs):
        print(f"SequenceExecutor CALL! len={len(self.responses)} idx={self.idx}")
        if self.idx < len(self.responses):
            res = self.responses[self.idx]
            self.idx += 1
            print(f" -> returning string: {res}")
            return res
        print(" -> ending autonomy loop!")
        self.autonomy.is_running = False
        return ""

async def test_oneshot_advanced_tool_parsing():
    mock_bot = DummyBot()
    lobe = MagicMock()
    lobe.cerebrum.bot = mock_bot
    autonomy = AutonomyAbility(lobe)
    
    responses = [
        r"[TOOL: test_tool(arg='escaped\'val')]",
        '[TOOL: test_tool(arg="parens(inside)")]',
        "[TOOL: test_tool(raw_input_only)]",
        r'[TOOL: test_tool({\"bad_json\": true})]'
    ]
    mock_bot.loop.run_in_executor = SequenceExecutor(responses, autonomy)
    
    with patch("asyncio.sleep", new_callable=AsyncMock) as m:
        with patch("src.tools.weekly_quota.is_quota_met", return_value=True) as q:
            with patch('src.lobes.creative.autonomy.ToolRegistry.execute', new_callable=AsyncMock) as mock_exec:
                print("Starting execute()...")
                task = asyncio.create_task(autonomy.execute())
                await asyncio.wait_for(task, timeout=3.0)
                print("Execute finished!")

if __name__ == "__main__":
    try:
        asyncio.run(test_oneshot_advanced_tool_parsing())
    except Exception as e:
        print("CRASHED:", e)
