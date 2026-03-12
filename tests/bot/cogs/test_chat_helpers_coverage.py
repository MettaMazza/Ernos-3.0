"""Tests for ChatHelpers — 8 tests."""
import pytest
import io
from unittest.mock import MagicMock, AsyncMock, patch

from src.bot.cogs.chat_helpers import AttachmentProcessor, ReactionHandler


class TestAttachmentProcessor:
    @pytest.mark.asyncio
    async def test_plain_text(self):
        att = MagicMock()
        att.filename = "readme.txt"
        att.read = AsyncMock(return_value=b"Hello World")
        result = await AttachmentProcessor.extract_text(att)
        assert result == "Hello World"

    @pytest.mark.asyncio
    async def test_pdf_no_module(self):
        att = MagicMock()
        att.filename = "doc.pdf"
        att.read = AsyncMock(return_value=b"%PDF")
        with patch.dict("sys.modules", {"pypdf": None}):
            result = await AttachmentProcessor.extract_text(att)
            # Either extracts or returns error
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_docx_no_module(self):
        att = MagicMock()
        att.filename = "doc.docx"
        att.read = AsyncMock(return_value=b"PK")
        with patch.dict("sys.modules", {"docx": None}):
            result = await AttachmentProcessor.extract_text(att)
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_binary_fallback(self):
        att = MagicMock()
        att.filename = "data.bin"
        att.read = AsyncMock(return_value=bytes(range(128, 256)))
        result = await AttachmentProcessor.extract_text(att)
        assert isinstance(result, str)


class TestReactionHandler:
    @pytest.fixture
    def handler(self):
        bot = MagicMock()
        bot.user = MagicMock(id=999)
        bot.silo_manager = MagicMock()
        bot.silo_manager.check_quorum = AsyncMock()
        return ReactionHandler(bot)

    @pytest.mark.asyncio
    async def test_ignores_bot_reaction(self, handler):
        payload = MagicMock()
        payload.user_id = 999  # Bot's own ID
        await handler.process_reaction(payload)
        handler.bot.silo_manager.check_quorum.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_user_reaction(self, handler):
        payload = MagicMock()
        payload.user_id = 123
        handler.bot.cerebrum = None
        delattr(handler.bot, "cerebrum")
        await handler.process_reaction(payload)
        handler.bot.silo_manager.check_quorum.assert_called_once()

    @pytest.mark.asyncio
    async def test_social_signal_ingestion(self, handler):
        payload = MagicMock()
        payload.user_id = 123
        payload.emoji = "👍"
        payload.message_id = 456
        payload.channel_id = 789
        payload.guild_id = 111
        social = AsyncMock(return_value="positive")
        interaction_lobe = MagicMock()
        interaction_lobe.get_ability.return_value = social
        handler.bot.cerebrum = MagicMock()
        handler.bot.cerebrum.lobes = {"InteractionLobe": interaction_lobe}
        handler.bot.hippocampus = MagicMock()
        await handler.process_reaction(payload)
        social.process_reaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling(self, handler):
        payload = MagicMock()
        payload.user_id = 123
        payload.emoji = "👎"
        payload.message_id = 1
        payload.channel_id = 2
        payload.guild_id = 3
        # Error in cerebrum section is caught by try/except
        handler.bot.cerebrum = MagicMock()
        handler.bot.cerebrum.lobes = {"InteractionLobe": MagicMock(side_effect=Exception("boom"))}
        # Should not raise
        await handler.process_reaction(payload)
        assert True  # No exception: error handled gracefully
