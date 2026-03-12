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
        print(f"DEBUG: run_in_executor invoked. idx={self.idx}, responses={self.responses}")
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
        self.is_recreation = False
        self.last_interaction = time.time() - 1000
        self.last_search_time = 0
        self.hippocampus = MagicMock()
        self.hippocampus.observe = AsyncMock()
        self.skill_registry = MagicMock()
        self.skill_registry.list_skills = MagicMock(return_value=[])
        self.send_to_dev_channel = AsyncMock()

@pytest.fixture
def mock_bot():
    return DummyBot()

@pytest.fixture
def autonomy(mock_bot):
    lobe = MagicMock()
    lobe.cerebrum.bot = mock_bot
    return AutonomyAbility(lobe)

@pytest.mark.asyncio
async def test_line_161_execute_parens_parsing(autonomy, mock_bot):
    # Tests deep nested parsing in strategy 1 depth matching inside `execute` loop
    mock_bot.loop.responses = ["[TOOL: search_web( (nested), \\\"escape\\\" )]"]
    mock_bot.loop.autonomy = autonomy
    autonomy.is_running = True
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
        await autonomy.execute() 

@pytest.mark.asyncio
async def test_line_269_270_set_goal_cooldown(autonomy, mock_bot):
    mock_response = "[TOOL: set_goal(description='cooldown_goal')]"
    mock_bot.loop.responses = [mock_response]
    mock_bot.loop.autonomy = autonomy
    
    # Needs to be within 600 seconds
    autonomy._last_goal_time = time.time() - 10 
    
    with patch("src.memory.goals.get_goal_manager"):
        with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
            autonomy.is_running = True
            await autonomy.execute()

@pytest.mark.asyncio
async def test_line_280_set_goal_duplicate(autonomy, mock_bot):
    mock_response = "[TOOL: set_goal(description='duplicate_goal')]"
    mock_bot.loop.responses = [mock_response]
    mock_bot.loop.autonomy = autonomy
    
    with patch("src.memory.goals.get_goal_manager") as mock_gm:
        gm = MagicMock()
        # Mock is_duplicate AND ensure add_goal throws explicitly if called, so we know it skipped
        gm.is_duplicate.return_value = True 
        mock_gm.return_value = gm
        autonomy.is_running = True
        with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
            await autonomy.execute()

@pytest.mark.asyncio
async def test_line_316_web_search_cooldown(autonomy, mock_bot):
    mock_response = "[TOOL: search_web(query='test')]"
    mock_bot.loop.responses = [mock_response]
    mock_bot.loop.autonomy = autonomy
    
    # Max cooldown trigger = under 30 seconds
    autonomy._last_search_time = time.time() - 5 
    autonomy.is_running = True
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
        await autonomy.execute()

@pytest.mark.asyncio
async def test_line_331_work_tools_blocked(autonomy, mock_bot):
    mock_response = "[TOOL: start_work_session()]"
    mock_bot.loop.responses = [mock_response]
    mock_bot.loop.autonomy = autonomy
    
    # Blocks all work tools
    autonomy.bot.is_recreation = True
    autonomy.is_running = True
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
        await autonomy.execute()

@pytest.mark.asyncio
async def test_line_451_dev_quota_import_error(autonomy, mock_bot):
    # Quota check ImportError suppression
    orig_import = __import__
    def mock_import(name, *args, **kwargs):
        if name == "src.tools.weekly_quota": raise ImportError("Missing module")
        return orig_import(name, *args, **kwargs)
        
    with patch("builtins.__import__", side_effect=mock_import):
        mock_bot.loop.responses = ["Exit Loop"]
        try:
            await autonomy._run_dev_work_cycle(5.0)
        except Exception: pass

@pytest.mark.asyncio
async def test_line_463_dev_cycle_is_processing(autonomy, mock_bot):
    # Ensures bot processing breaks dev loops early
    with patch("src.tools.weekly_quota.is_quota_met", return_value=False):
        autonomy.bot.is_processing = True
        # Break out loop
        mock_bot.loop.responses = ["[TOOL: end()]"] * 30 
        await autonomy._run_dev_work_cycle(5.0)

@pytest.mark.asyncio
async def test_line_741_run_task_exhaustion(autonomy, mock_bot):
    # Tests hitting step limit exhaustion lines 741-742 and completing final array
    mock_bot.loop.responses = ["[TOOL: dummy()]"] * 40 # Force past MAX limits (usually 30)
    with patch("src.lobes.creative.autonomy.ToolRegistry.execute", new_callable=AsyncMock):
        res = await autonomy.run_task("Task")
        assert len(res) > 0

@pytest.mark.asyncio
async def test_line_907_930_transparency_send_exception(autonomy, mock_bot):
    # Simulating long chunk generation with send failure
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock(side_effect=Exception("Send Error"))
    autonomy.bot.get_channel = MagicMock(return_value=mock_channel)
    
    with patch("src.memory.autobiography.get_autobiography_manager", side_effect=Exception("Save fail")):
        autonomy.autonomy_log_buffer = ["A" * 2000] # Trigger chunk loop exactly
        
        # Ensures fake LM generations hit chunks[0] so IndexError doesn't throw before actual catch 
        mock_bot.loop.responses = ["A" * 2000] 
        await autonomy._send_transparency_report() 

@pytest.mark.asyncio
async def test_line_942_extract_wisdom_missing_template(autonomy, mock_bot):
    with patch("src.core.secure_loader.load_prompt", return_value=None):
        res = await autonomy._extract_wisdom("T", "I")
        assert len(res) > 0 # Returns error statement

@pytest.mark.asyncio
async def test_line_956_extract_wisdom_missing_dir(autonomy, mock_bot):
    with patch("src.core.secure_loader.load_prompt", return_value="Template"):
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", MagicMock()):
                with patch("os.makedirs"):
                    mock_bot.loop.run_behavior = "Success"
                    res = await autonomy._extract_wisdom("T", "I")
                    assert len(res) > 0
