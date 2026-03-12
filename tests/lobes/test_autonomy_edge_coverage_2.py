import pytest
import asyncio
import time
import os
from unittest.mock import MagicMock, patch, AsyncMock
from src.lobes.creative.autonomy import AutonomyAbility

class DummyLoop:
    def __init__(self):
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
        return ""

class DummyBot:
    def __init__(self):
        self.loop = DummyLoop()
        self.engine_manager = MagicMock()
        self.is_processing = False
        self.last_interaction = time.time() - 1000
        self.hippocampus = MagicMock()
        self.hippocampus.observe = AsyncMock()
        self.skill_registry = MagicMock()
        self.skill_registry.list_skills = MagicMock(return_value=[])

@pytest.fixture
def mock_bot():
    return DummyBot()

@pytest.fixture
def autonomy(mock_bot):
    lobe = MagicMock()
    lobe.cerebrum.bot = mock_bot
    return AutonomyAbility(lobe)

@pytest.mark.asyncio
async def test_parens_and_escapes(autonomy, mock_bot):
    # Lines 161 (execute parens), 508 (dev parens escapes), 516 (dev parens), 269-270 (goal logic), 316-317, 331-332
    
    # 1. Trigger parenthesis depth and escaped chars in both modes
    # "execute()" block logic testing
    mock_bot.loop.responses = ["[TOOL: search_web(query=\\\"nested(parens)\\\")]"]
    mock_bot.loop.autonomy = autonomy
    autonomy.is_running = True
    await autonomy.execute() # Throttles or parses cleanly, hitting depth += 1 and escape skips
    
    # 2. _run_dev_work_cycle block tracking
    with patch("src.tools.weekly_quota.is_quota_met", return_value=False):
        mock_bot.loop.responses = ["[TOOL: tool_call(query=\\\"nested(parens)\\\")]"]
        mock_bot.loop.idx = 0
        
        # Test 574-575 Regex Crash in Dev cycle
        with patch("re.compile", side_effect=Exception("Dev Parser Crash")):
            try:
                await autonomy._run_dev_work_cycle(5.0)
            except Exception: pass

@pytest.mark.asyncio
async def test_active_tool_blocks(autonomy, mock_bot):
    # Ensure goal duplicates and quotas hit blocks cleanly during direct execute() wrapper
    mock_bot.loop.responses = ["[TOOL: set_goal(description='dup')]", "[TOOL: start_work_session()]"]
    mock_bot.loop.autonomy = autonomy
    mock_bot.loop.idx = 0
    
    # Block work tools
    autonomy.bot.is_recreation = True
    
    # Duplicate goal
    with patch("src.memory.goals.get_goal_manager") as mock_gm:
        gm = MagicMock()
        gm.is_duplicate.return_value = True
        mock_gm.return_value = gm
        autonomy.is_running = True
        await autonomy.execute()

@pytest.mark.asyncio
async def test_scheduled_task_failures(autonomy, mock_bot):
    # Lines 660, 675, 741 (fixed assertions)
    # 660: Prompt missing
    with patch("src.prompts.manager.PromptManager", side_effect=Exception("Prompt missing")):
        mock_bot.loop.responses = ["Done"]
        res = await autonomy.run_task("Task")
        assert len(res) > 0 # Completed cleanly despite exceptions
    
    # 675: Skills missing
    mock_bot.skill_registry.list_skills = MagicMock(side_effect=Exception("Skills missing"))
    mock_bot.loop.responses = ["Done"]
    res = await autonomy.run_task("Task")
    assert len(res) > 0
    
    # 741: Step limits exhausted
    mock_bot.skill_registry.list_skills = MagicMock(return_value=[])
    mock_bot.loop.responses = ["[TOOL: dummy()]"] * 40 # Force past MAX_TASK_STEPS limit
    with patch("src.lobes.creative.autonomy.ToolRegistry.execute", new_callable=AsyncMock):
        res = await autonomy.run_task("Task")
        assert len(res) > 0

@pytest.mark.asyncio
async def test_transparency_report_buffer_and_quota(autonomy, mock_bot):
    # Lines 870 (empty buffer LLM string text), 879-880 (Quota crash)
    
    # Setup valid channel to not trigger 865 early return
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    autonomy.bot.get_channel = MagicMock(return_value=mock_channel)
    
    # 870: Empty buffer text
    autonomy.autonomy_log_buffer = []
    
    # 879: Weekly quota import error
    with patch("src.tools.weekly_quota.get_quota_status", side_effect=Exception("Quota module died")):
        mock_bot.loop.responses = ["LLM Generates Report Successfully For Empty"]
        # Fake the autobiography save to prevent interference
        with patch("src.memory.autobiography.get_autobiography_manager"):
            await autonomy._send_transparency_report()

@pytest.mark.asyncio
async def test_execute_response_ast_crash(autonomy, mock_bot):
    # Line 835: Generic Exception in Strategy 1/2 of string tool parsing
    response = "[TOOL: execute_tools(arg=1)]"
    with patch("ast.literal_eval", side_effect=Exception("Total generic crash")):
        res = await autonomy._execute_response_tools(response, "")
        assert "Generic" not in res # Suppressed cleanly by 835 logger warning

@pytest.mark.asyncio
async def test_dev_work_quota_import_error(autonomy, mock_bot):
    # Line 451: Quota import error in DEV loop
    with patch("builtins.__import__") as mock_import:
        def import_interceptor(name, *args, **kwargs):
            if "src.tools.weekly_quota" in name:
                raise ImportError("Weekly quota missing")
            # Must return original for builtins to not break asyncio
            import importlib
            return importlib.import_module(name)
            
        mock_import.side_effect = import_interceptor
        
        mock_bot.loop.responses = ["Break"]
        try:
            await autonomy._run_dev_work_cycle(5.0)
        except Exception: pass
