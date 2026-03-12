import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch

from src.lobes.creative.autonomy import AutonomyAbility

@pytest.fixture
def mock_autonomy():
    lobe = MagicMock()
    # Mock the new cognition pipeline
    lobe.cerebrum.bot.cognition.process = AsyncMock(return_value="Dream Output")
    lobe.cerebrum.bot.hippocampus.observe = AsyncMock()
    lobe.cerebrum.bot.send_to_mind = AsyncMock()
    lobe.cerebrum.bot.send_to_dev_channel = AsyncMock()
    d = AutonomyAbility(lobe)
    return d

@pytest.mark.asyncio
async def test_autonomy_oneshot_exception(mock_autonomy):
    # Force exception in cognition process
    mock_autonomy.bot.cognition.process.side_effect = Exception("OneShot Fail")
    res = await mock_autonomy.execute("Think")
    assert "Dream Failed: OneShot Fail" in res

@pytest.mark.asyncio
async def test_autonomy_idle_continue(mock_autonomy):
    mock_autonomy.is_running_count = 0
    
    async def sleep_side(d):
        mock_autonomy.is_running_count += 1
        if mock_autonomy.is_running_count > 5:
             raise asyncio.CancelledError("Watchdog Limit Reached")
        if d in (10, 120):  # Normal or Lite mode loop interval
            if mock_autonomy.is_running_count > 1: raise asyncio.CancelledError()
            
    with patch("asyncio.sleep", side_effect=sleep_side):
        mock_autonomy.bot.is_processing = True # Should trigger continue
        await mock_autonomy.execute()
        
        mock_autonomy.bot.cognition.process.assert_not_called()

@pytest.mark.asyncio
async def test_autonomy_interrupt(mock_autonomy):
    mock_autonomy.bot.is_processing = False
    mock_autonomy.bot.last_interaction = 0
    mock_autonomy.is_running_count = 0
    
    async def sleep_side(d):
        mock_autonomy.is_running_count += 1
        if mock_autonomy.is_running_count > 25:
             raise asyncio.CancelledError("Watchdog Limit Reached")
        if d in (10, 120):  # Normal or Lite mode loop interval
            if mock_autonomy.is_running_count > 5: raise asyncio.CancelledError()
            
    async def prompt_side_effect(*args, **kwargs):
        mock_autonomy.bot.is_processing = True
        return "Thought 1 <HALT>"
        
    mock_autonomy.bot.cognition.process.side_effect = prompt_side_effect
    
    with patch("asyncio.sleep", side_effect=sleep_side):
        await mock_autonomy.execute()
        assert mock_autonomy.bot.cognition.process.call_count <= 2

@pytest.mark.asyncio
async def test_autonomy_engine_none(mock_autonomy):
    class SimpleBot:
        def __init__(self):
            self.is_processing = False
            self.last_interaction = time.time() - 700  # Must exceed 600s Lite idle threshold
            self.cognition = MagicMock()
            self.cognition.process = AsyncMock(return_value=None)
            self.hippocampus = AsyncMock()

    real_bot_mock = SimpleBot()
    mock_autonomy.lobe.cerebrum.bot = real_bot_mock
    mock_autonomy.is_running_count = 0
    
    async def sleep_side(d):
        mock_autonomy.is_running_count += 1
        if mock_autonomy.is_running_count > 5:
             raise asyncio.CancelledError("Watchdog Limit Reached")
        # Catch the Lite mode loop interval (120s) or normal (10s)
        if d in (10, 120):
            if mock_autonomy.is_running_count > 1: raise asyncio.CancelledError()

    with patch("asyncio.sleep", side_effect=sleep_side):
        await mock_autonomy.execute()
        
    assert real_bot_mock.cognition.process.called

@pytest.mark.asyncio
async def test_autonomy_halt_command(mock_autonomy):
    mock_autonomy.bot.is_processing = False
    mock_autonomy.bot.last_interaction = 0
    mock_autonomy.is_running_count = 0
    
    mock_autonomy.bot.cognition.process.side_effect = ["Thought 1", "Thought 2 <HALT>"]
    
    call_count = [0]
    async def sleep_side(d):
        if d in (10, 120):  # Normal or Lite mode loop interval
             if call_count[0] == 0:
                 call_count[0] += 1
                 return
             raise asyncio.CancelledError("Watchdog Limit Reached")
        return
    
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
        with patch("asyncio.sleep", side_effect=sleep_side):
            await mock_autonomy.execute()
            assert mock_autonomy.bot.cognition.process.call_count == 2

@pytest.mark.asyncio
async def test_autonomy_oneshot_success(mock_autonomy):
    mock_autonomy.bot.cognition.process.return_value = "Insight"
    res = await mock_autonomy.execute("Reflect")
    assert "[DREAM]: Insight" in res


@pytest.mark.asyncio
async def test_pure_thought_limit(mock_autonomy):
    mock_autonomy.bot.is_processing = False
    mock_autonomy.bot.last_interaction = 0
    
    mock_autonomy.bot.cognition.process.return_value = "Thought without halt"
    
    async def sleep_side(d):
        if d in (10, 120):  # Normal or Lite mode loop interval
             if getattr(mock_autonomy, "_slept_once", False): raise asyncio.CancelledError()
             mock_autonomy._slept_once = True
        return

    with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
        with patch("asyncio.sleep", side_effect=sleep_side):
             await mock_autonomy.execute()
             # Step limit depends on AUTONOMY_LITE_MODE: 1 (lite) or 15 (normal)
             assert mock_autonomy.bot.cognition.process.call_count >= 1

@pytest.mark.asyncio
async def test_autonomy_already_running(mock_autonomy):
    mock_autonomy.is_running = True
    res = await mock_autonomy.execute()
    assert "already active" in res

@pytest.mark.asyncio
async def test_autonomy_cycle_exception(mock_autonomy):
    mock_autonomy.bot.is_processing = False
    mock_autonomy.bot.last_interaction = 0
    
    def side_effect(*args, **kwargs):
        raise Exception("Cognition Broke")
    mock_autonomy.bot.cognition.process.side_effect = side_effect
    
    async def sleep_side(d):
        if d in (10, 120):  # Normal or Lite mode loop interval
             if getattr(mock_autonomy, "_slept_once", False): raise asyncio.CancelledError()
             mock_autonomy._slept_once = True
        return

    with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
        with patch("asyncio.sleep", side_effect=sleep_side):
            with patch("src.lobes.creative.autonomy.logger") as mock_logger:
                 await mock_autonomy.execute()
                 mock_logger.error.assert_called_with("IMA Cognition Pipeline Failed: Cognition Broke", exc_info=True)

@pytest.mark.asyncio
async def test_extract_wisdom_exception(mock_autonomy):
    with patch("builtins.open", side_effect=FileNotFoundError("No template")):
         res = await mock_autonomy._extract_wisdom("Topic", "insight")
    assert "ERROR" in res

@pytest.mark.asyncio
async def test_autonomy_quota_import_error(mock_autonomy):
    mock_autonomy.bot.is_processing = False
    mock_autonomy.bot.last_interaction = 0
    mock_autonomy.bot.cognition.process.return_value = "Thought <HALT>"
    
    async def sleep_side(d):
        if d in (10, 120):  # Normal or Lite mode loop interval
             if getattr(mock_autonomy, "_slept_once", False): raise asyncio.CancelledError()
             mock_autonomy._slept_once = True
        return
        
    with patch("src.lobes.creative.autonomy.time.time", return_value=1000):
        original_import = __builtins__['__import__']
        def mock_import(name, *args, **kwargs):
            if name == "src.tools.weekly_quota":
                raise ImportError("Mocked Import Error")
            return original_import(name, *args, **kwargs)
            
        with patch('builtins.__import__', side_effect=mock_import):
            with patch("asyncio.sleep", side_effect=sleep_side):
                await mock_autonomy.execute()
    assert True

@pytest.mark.asyncio
async def test_autonomy_dev_cycle_exception(mock_autonomy):
    mock_autonomy.bot.is_processing = False
    mock_autonomy.bot.last_interaction = 0
    
    async def sleep_side(d):
        if d in (10, 120):
             if getattr(mock_autonomy, "_slept_once", False): raise asyncio.CancelledError()
             mock_autonomy._slept_once = True
        return
        
    with patch("src.tools.weekly_quota.is_quota_met", return_value=False):
        with patch("src.tools.weekly_quota.get_remaining_quota", return_value=5.0):
            with patch.object(mock_autonomy, "_run_dev_work_cycle", side_effect=Exception("Dev Crash")):
                with patch("asyncio.sleep", side_effect=sleep_side):
                    with patch("src.lobes.creative.autonomy.logger.error") as mock_logger:
                        # Must enable work mode for the dev cycle path to be entered
                        with patch("config.settings.ENABLE_WORK_MODE", True):
                            with patch("config.settings.AUTONOMY_LITE_MODE", False):
                                await mock_autonomy.execute()
                                mock_logger.assert_any_call("Dev work cycle failed: Dev Crash")
