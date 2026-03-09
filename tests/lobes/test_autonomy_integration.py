import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from src.lobes.manager import Cerebrum
from src.lobes.creative.lobe import CreativeLobe
from src.lobes.creative.autonomy import AutonomyAbility

@pytest.fixture
def mock_bot(event_loop):
    bot = MagicMock()
    bot.loop = event_loop
    bot.hippocampus = MagicMock()
    bot.last_interaction = time.time()
    return bot

@pytest.mark.asyncio
async def test_autonomy_trigger(mock_bot):
    c = Cerebrum(mock_bot)
    c.register_lobe(CreativeLobe)
    lobe = c.get_lobe("CreativeLobe")
    dreamer = lobe.get_ability("AutonomyAbility")

    # Set idle time > 180s
    mock_bot.last_interaction = time.time() - 200
    mock_bot.is_processing = False # Ensure getattr returns False, not Mock
    
    # Mock logger to verify trigger
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
        with patch("src.lobes.creative.autonomy.logger") as mock_logger:
            # Start loop task
            task = asyncio.create_task(dreamer.execute())
            
            # Allow loop to run briefly
            # We need sleep(0) to yield control, but Dreamer sleeps 60.
            # So we patch asyncio.sleep to return immediately once.
            with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError]) as mock_sleep:
                 try:
                     await task
                 except asyncio.CancelledError:
                     pass
            
            # Verify logger called
            # "IMA: Detected Idle"
            found = False
            for call in mock_logger.info.call_args_list:
                if "IMA: Detected Idle" in call[0][0]:
                    found = True
                    break
            assert found, "Autonomy loop did not trigger on idle."
