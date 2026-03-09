import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_bot_shutdown():
    """Test ErnosBot graceful shutdown sequence.
    
    Instead of clearing sys.modules (which causes cascading failures in other
    tests), we patch all dependencies at their import sites within src.bot.client.
    """
    with (
        patch("src.bot.client.EngineManager"),
        patch("src.bot.client.Hippocampus") as mock_hippo_cls,
        patch("src.bot.client.LaneQueue") as mock_lq_cls,
        patch("src.bot.client.Cerebrum") as mock_cerebrum_cls,
        patch("src.bot.client.SiloManager"),
        patch("src.bot.client.VoiceManager"),
        patch("src.bot.client.ChannelManager"),
        patch("src.bot.client.SkillRegistry"),
        patch("src.bot.client.SkillSandbox"),
        patch("src.engines.cognition.CognitionEngine"),
        patch("src.daemons.kg_consolidator.KGConsolidator"),
    ):
        # Configure return instances with proper async methods
        mock_lq = MagicMock()
        mock_lq.stop = AsyncMock()
        mock_lq_cls.return_value = mock_lq

        mock_cerebrum = MagicMock()
        mock_cerebrum.shutdown = AsyncMock()
        mock_cerebrum_cls.return_value = mock_cerebrum

        mock_hippo = MagicMock()
        mock_hippo.shutdown = MagicMock()  # sync call in close()
        mock_hippo.set_kg_consolidator = MagicMock()
        mock_hippo_cls.return_value = mock_hippo

        from src.bot.client import ErnosBot
        bot = ErnosBot()

        # Patch super().close() to avoid real Discord teardown
        # close() is defined on BotBase in the MRO, not on Bot directly
        with patch("discord.ext.commands.bot.BotBase.close", new_callable=AsyncMock) as mock_super_close:
            await bot.close()

        mock_cerebrum.shutdown.assert_called_once()
        mock_hippo.shutdown.assert_called_once()
        mock_lq.stop.assert_called_once()
        mock_super_close.assert_called_once()
