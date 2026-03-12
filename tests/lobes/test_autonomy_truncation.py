import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.lobes.creative.autonomy import AutonomyAbility

@pytest.mark.asyncio
async def test_transparency_report_chunking():
    """Verify that _send_transparency_report chunks large messages."""
    
    lobe_mock = MagicMock()
    lobe_mock.cerebrum.bot.get_channel = MagicMock()
    
    autonomy = AutonomyAbility(lobe_mock)
    autonomy.summary_channel_id = 123
    autonomy.autonomy_log_buffer = ["test log entry"]
    
    # Mock bot channel return
    mock_channel = AsyncMock()
    lobe_mock.cerebrum.bot.get_channel.return_value = mock_channel
    
    # Mock cognition.process directly on the bot instance that _send_transparency_report accesses
    autonomy.bot.cognition.process = AsyncMock(return_value="A" * 5000)

    # Run report
    await autonomy._send_transparency_report()
    
    # Assert multiple calls were made (5000 chars / 1900 chunk size = 3 chunks)
    assert mock_channel.send.call_count >= 3
    
    # Verify content of first call includes header
    calls = mock_channel.send.call_args_list
    assert "**[AUTONOMY 30m REPORT]**" in calls[0][0][0]
    
    assert len(calls[0][0][0]) > 1900  # header + chunk
