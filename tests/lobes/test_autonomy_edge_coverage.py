import pytest
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
        self.cognition = MagicMock()
        self.cognition.process = AsyncMock(return_value="Valid Response")

@pytest.fixture(autouse=True)
def mock_sleep():
    with patch("asyncio.sleep", new_callable=AsyncMock) as m:
        m.return_value = None
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
async def test_execute_transparency_report_trigger(autonomy, mock_bot):
    mock_bot.loop.responses = [""]
    mock_bot.loop.autonomy = autonomy
    
    async def sleep_intercept(*args):
        autonomy.last_summary_time = 0
        autonomy.is_running = False
        
    with patch("src.lobes.creative.autonomy.asyncio.sleep", new_callable=AsyncMock) as mock_sleep_local:
        mock_sleep_local.side_effect = sleep_intercept
        
        with patch.object(autonomy, '_send_transparency_report', new_callable=AsyncMock) as mock_report:
            await autonomy.execute()
            mock_report.assert_called()

@pytest.mark.asyncio
async def test_execute_crawler_success(autonomy, mock_bot):
    mock_bot.loop.responses = [""]
    mock_bot.loop.autonomy = autonomy
    autonomy.bot.send_to_mind = AsyncMock()
    
    async def sleep_intercept(*args):
        # By the time it sleeps, the crawler cycle (or the dream thought) will be complete
        autonomy.is_running = False
        
    with patch("src.lobes.creative.autonomy.asyncio.sleep", new_callable=AsyncMock) as mock_sleep_local:
        mock_sleep_local.side_effect = sleep_intercept
        
        with patch("src.lobes.creative.autonomy.get_crawler", create=True) as mock_crawler_getter:
            mock_crawler = MagicMock()
            mock_crawler.crawl_cycle.return_value = {"skipped": False, "source": "test", "new": 5}
            mock_crawler_getter.return_value = mock_crawler
            
            async def custom_run(executor, func, *args, **kwargs):
                if hasattr(func, '__name__') and func.__name__ == 'crawl_cycle' or func == mock_crawler.crawl_cycle:
                    return {"skipped": False, "source": "test", "new": 5}
                return ""
                
            mock_bot.loop.run_in_executor = custom_run
            
            await autonomy.execute()
            autonomy.bot.send_to_mind.assert_called()

@pytest.mark.asyncio
async def test_execute_fatal_crash(autonomy, mock_bot):
    mock_bot.loop.responses = [""]
    mock_bot.loop.autonomy = autonomy
    
    with patch("src.lobes.creative.autonomy.asyncio.sleep", side_effect=Exception("FATAL")):
        await autonomy.execute()
        # Loop should set is_running=False and attempt restart (which also fails gracefully)
        assert autonomy.is_running == False

@pytest.mark.asyncio
async def test_execute_loop_cancelled(autonomy, mock_bot):
    mock_bot.loop.responses = [""]
    mock_bot.loop.autonomy = autonomy
    
    with patch("src.lobes.creative.autonomy.asyncio.sleep", side_effect=asyncio.CancelledError()):
        await autonomy.execute()
        assert autonomy.is_running == False

@pytest.mark.asyncio
async def test_dev_cycle_system_prompt_crash(autonomy, mock_bot):
    with patch("src.tools.weekly_quota.is_quota_met", return_value=False):
        with patch("src.prompts.manager.PromptManager.get_system_prompt", side_effect=Exception("Prompt Crash")):
            mock_bot.loop.responses = [""]
            mock_bot.loop.autonomy = autonomy
            await autonomy._run_dev_work_cycle(5.0)

@pytest.mark.asyncio
async def test_dev_cycle_is_processing_break(autonomy, mock_bot):
    with patch("src.tools.weekly_quota.is_quota_met", return_value=False):
        autonomy.bot.send_to_dev_channel = AsyncMock()
        
        # Override process directly because custom_run on executor isn't used by the main flow anymore
        async def mock_cognition_process(*args, **kwargs):
            autonomy.bot.is_processing = True
            return ""
            
        mock_bot.cognition.process = mock_cognition_process
        await autonomy._run_dev_work_cycle(5.0)
        
        assert mock_bot.is_processing == True

@pytest.mark.asyncio
async def test_dev_cycle_tool_parse_suppress_errors(autonomy, mock_bot):
    with patch("src.tools.weekly_quota.is_quota_met", return_value=False):
        # Line 552 exception
        mock_bot.loop.responses = ['[TOOL: test({"broken": True})]']
        mock_bot.loop.autonomy = autonomy
        
        with patch('ast.literal_eval', side_effect=ValueError("ValErr")):
             await autonomy._run_dev_work_cycle(5.0)

@pytest.mark.asyncio
async def test_dev_cycle_pure_thought_completion(autonomy, mock_bot):
    with patch("src.tools.weekly_quota.is_quota_met", return_value=False):
        # Line 574 logic break
        mock_bot.loop.responses = ["Some text. End of pure thought array. Some more text."]
        mock_bot.loop.autonomy = autonomy
        await autonomy._run_dev_work_cycle(5.0)

@pytest.mark.asyncio
async def test_oneshot_execute_response_tools_exceptions(autonomy, mock_bot):
    # Lines 811-817, 835-836 in execute_response_tools
    response = r"[TOOL: test_tool({\"bad_json\": true})]"
    
    with patch('ast.literal_eval', side_effect=SyntaxError("SynErr")):
        res = await autonomy._execute_response_tools(response, "")
        assert "test_tool" in res

@pytest.mark.asyncio
async def test_oneshot_execute_response_tools_flux_blocked(autonomy, mock_bot):
    response = "[TOOL: dummy(1)]"
    with patch("src.core.flux_capacitor.FluxCapacitor") as mock_fc:
        fc = MagicMock()
        fc.consume_tool.return_value = (False, "Limit reached")
        mock_fc.return_value = fc
        
        with patch('src.lobes.creative.autonomy.ToolRegistry.execute', new_callable=AsyncMock) as mock_exec:
            res = await autonomy._execute_response_tools(response, "", user_id="123")
            assert "BLOCKED" in res
        
        fc.consume_tool.side_effect = Exception("Flux Crash")
        with patch('src.lobes.creative.autonomy.ToolRegistry.execute', new_callable=AsyncMock) as mock_exec:
            res2 = await autonomy._execute_response_tools(response, "", user_id="123")
            assert mock_exec.call_count == 1

@pytest.mark.asyncio
async def test_send_transparency_report_chunking(autonomy, mock_bot):
    autonomy.bot.hippocampus.graph = MagicMock()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    autonomy.bot.get_channel = MagicMock(return_value=mock_channel)
    
    with patch('src.memory.autobiography.get_autobiography_manager') as mock_gm:
        gm = MagicMock()
        mock_gm.return_value = gm
        autonomy.autonomy_log_buffer = ["A"] 
        mock_bot.cognition.process = AsyncMock(return_value="A" * 2000) # Force chunking in report string generated by LLM
        await autonomy._send_transparency_report()
        assert mock_channel.send.call_count >= 2

@pytest.mark.asyncio
async def test_extract_wisdom_dedup(autonomy, mock_bot):
    # Lines 960-975 dedup check
    with patch('os.makedirs'), patch('os.path.exists', return_value=True), patch('builtins.open', MagicMock()) as mock_open:
        mock_open.return_value.__enter__.return_value.readlines.return_value = ["Test Wisdom"]
        
        mock_bot.cognition.process = AsyncMock(return_value="Test Wisdom")
        res = await autonomy._extract_wisdom("Topic", "Insight")
        assert "Duplicate wisdom detected" in res or "already crystallized" in res

@pytest.mark.asyncio
async def test_extract_wisdom_dedup_exception(autonomy, mock_bot):
    with patch('os.path.exists', return_value=True):
        mock_bot.cognition.process = AsyncMock(return_value="New Wisdom")
        # Overwrite SequenceMatcher to raise error only in dedup check
        with patch('difflib.SequenceMatcher', side_effect=Exception("Read Err")):
            res = await autonomy._extract_wisdom("Topic", "Insight")
            assert "Wisdom crystallized and stored" in res

@pytest.mark.asyncio
async def test_build_dev_prompt_feedback(autonomy, mock_bot):
    # Lines 1003-1020 build_dev_prompt with feedback
    with patch('pathlib.Path.exists', return_value=True):
        with patch('pathlib.Path.read_text', return_value='{"weekly_history": [{"week": 1, "rejected_items": ["A"], "rejection_reasons": ["B"]}]}'):
            res = autonomy._build_dev_prompt(5.0)
            assert "REJECTED" in res
