"""Tests for TelegramAdapter — 7 tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.channels.telegram_adapter import TelegramAdapter
from src.channels.types import OutboundResponse, Attachment


@pytest.fixture
def adapter():
    return TelegramAdapter(bot_token="test-token")


class TestNormalize:
    @pytest.mark.asyncio
    async def test_text_message(self, adapter):
        msg = MagicMock()
        msg.from_user = MagicMock(id=123, username="alice")
        msg.text = "hello there"
        msg.caption = None
        msg.chat = MagicMock(id=456, type="private")
        msg.photo = None
        msg.document = None
        raw = MagicMock(message=msg)
        result = await adapter.normalize(raw)
        assert result.content == "hello there"
        assert result.author_id == "123"
        assert result.is_dm is True

    @pytest.mark.asyncio
    async def test_group_message(self, adapter):
        msg = MagicMock()
        msg.from_user = MagicMock(id=1, username="bob")
        msg.text = "yo"
        msg.caption = None
        msg.chat = MagicMock(id=99, type="group")
        msg.photo = None
        msg.document = None
        raw = MagicMock(message=msg)
        result = await adapter.normalize(raw)
        assert result.is_dm is False

    @pytest.mark.asyncio
    async def test_photo_attachment(self, adapter):
        photo = MagicMock(file_id="photo123")
        msg = MagicMock()
        msg.from_user = MagicMock(id=1, username="x")
        msg.text = ""
        msg.caption = "my photo"
        msg.chat = MagicMock(id=1, type="private")
        msg.photo = [MagicMock(file_id="lo"), photo]
        msg.document = None
        raw = MagicMock(message=msg)
        result = await adapter.normalize(raw)
        assert len(result.attachments) == 1
        assert result.attachments[0].url == "photo123"


class TestSendResponse:
    @pytest.mark.asyncio
    async def test_no_bot(self, adapter):
        resp = OutboundResponse(content="test")
        await adapter.send_response(resp, 123)  # Should not raise
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_with_bot(self, adapter):
        adapter._bot = MagicMock()
        adapter._bot.send_message = AsyncMock()
        resp = OutboundResponse(content="hi")
        await adapter.send_response(resp, 456)
        adapter._bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunked_send(self, adapter):
        adapter._bot = MagicMock()
        adapter._bot.send_message = AsyncMock()
        long_text = "x" * 5000
        resp = OutboundResponse(content=long_text)
        await adapter.send_response(resp, 1)
        assert adapter._bot.send_message.call_count == 2


class TestPlatformName:
    def test_name(self, adapter):
        assert adapter.platform_name == "telegram"
