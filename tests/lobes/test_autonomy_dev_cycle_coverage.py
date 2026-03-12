import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock

from src.lobes.creative.autonomy import AutonomyAbility

class DummyCognition:
    def __init__(self):
        self.process = AsyncMock(return_value="Dev Cycle Complete")

class DummyBot:
    def __init__(self):
        self.is_processing = False
        self.last_interaction = time.time() - 1000
        self.dev_channel_msgs = []
        self.cognition = DummyCognition()
    
    async def send_to_dev_channel(self, msg):
        self.dev_channel_msgs.append(msg)

@pytest.fixture
def mock_bot():
    return DummyBot()

@pytest.fixture(autouse=True)
def mock_sleep():
    with patch("asyncio.sleep", new_callable=AsyncMock) as m:
        yield m

@pytest.fixture(autouse=True)
def mock_prompt_manager():
    """Mock PromptManager so dev cycle can build system_context without real files."""
    with patch('src.prompts.manager.PromptManager') as MockPM:
        instance = MockPM.return_value
        instance.get_system_prompt.return_value = "[MOCK SYSTEM CONTEXT WITH TOOL MANIFEST]"
        yield MockPM

@pytest.fixture
def autonomy(mock_bot):
    lobe = MagicMock()
    lobe.cerebrum.bot = mock_bot
    return AutonomyAbility(lobe)

@pytest.mark.asyncio
async def test_dev_cycle_quota_met_mid_cycle(autonomy, mock_bot):
    with patch('src.tools.weekly_quota.is_quota_met', return_value=True):
        await autonomy._run_dev_work_cycle(1.0)
        assert any("QUOTA MET" in m for m in mock_bot.dev_channel_msgs)

@pytest.mark.asyncio
async def test_dev_cycle_time_cap_reached(autonomy, mock_bot):
    remaining = 1.0 # 4200 max seconds
    call_count = [0]
    
    def mock_time():
        # First call: cycle_start. Second call: elapsed check in loop.
        call_count[0] += 1
        if call_count[0] <= 1:
            return 1000.0  
        return 1000.0 + 4201.0  
        
    with patch('time.time', side_effect=mock_time):
        with patch('src.tools.weekly_quota.is_quota_met', return_value=False):
            await autonomy._run_dev_work_cycle(remaining)
            assert any("TIME CAP" in m for m in mock_bot.dev_channel_msgs)

@pytest.mark.asyncio
async def test_dev_cycle_process_called(autonomy, mock_bot):
    with patch('src.tools.weekly_quota.is_quota_met', return_value=False):
        # Run one iteration then hit time cap
        call_count = [0]
        def mock_time():
            c = call_count[0]
            call_count[0] += 1
            # Allow cycle_start (c=0) and first elapsed check (c=1),
            # then exceed cap on all subsequent calls (c>=2) so only 1 process() runs
            if c < 2:
                return 1000.0
            return 1000.0 + 4201.0
        
        with patch('time.time', side_effect=mock_time):
            await autonomy._run_dev_work_cycle(1.0)
            mock_bot.cognition.process.assert_called_once()
            args, kwargs = mock_bot.cognition.process.call_args
            assert "system_context" in kwargs
            assert "DEV WORK OVERRIDE" in kwargs.get("input_text", "") or len(args) > 0


@pytest.mark.asyncio
async def test_dev_cycle_crash(autonomy, mock_bot):
    mock_bot.cognition.process.side_effect = Exception("Fatal Dev Crash")
    
    with patch('src.lobes.creative.autonomy.logger') as mock_logger:
        with patch('src.tools.weekly_quota.is_quota_met', return_value=False):
            await autonomy._run_dev_work_cycle(1.0)
            mock_logger.error.assert_any_call("IMA Dev Cycle Cognition Pipeline Failed: Fatal Dev Crash")
        
        async def crash_broadcast(*args, **kwargs):
            raise Exception("Also Crash Broadcast")
        mock_bot.send_to_dev_channel = crash_broadcast
        
        await autonomy._run_dev_work_cycle(1.0)

@pytest.mark.asyncio
async def test_build_dev_prompt_with_history_and_queue(autonomy):
    mock_fb = {"weekly_history": [{"week": 1, "rejected_items": ["file1"], "rejection_reasons": ["bad code"]}]}
    mock_queue = {"items": [{"priority": "HIGH", "description": "Fix bug"}]}
    
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    
    call_count = 0
    def read_text_dummy():
        nonlocal call_count
        call_count += 1
        import json
        if call_count == 1:
            return json.dumps(mock_fb)
        return json.dumps(mock_queue)
        
    mock_path.read_text.side_effect = read_text_dummy
    mock_path.__truediv__.return_value = mock_path
    
    with patch('src.lobes.creative.autonomy.data_dir', return_value=mock_path):
        prompt = autonomy._build_dev_prompt(1.0)
        assert "PAST REJECTION FEEDBACK" in prompt
        assert "WORK QUEUE" in prompt

@pytest.mark.asyncio
async def test_build_dev_prompt_exception(autonomy):
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.read_text.side_effect = Exception("File load crash")
    mock_path.__truediv__.return_value = mock_path
    
    with patch('src.lobes.creative.autonomy.data_dir', return_value=mock_path):
        prompt = autonomy._build_dev_prompt(1.0)
        assert "PAST REJECTION FEEDBACK" not in prompt
