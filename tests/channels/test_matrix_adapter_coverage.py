"""Tests for MatrixAdapter — 8 tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.channels.matrix_adapter import MatrixAdapter
from src.channels.types import OutboundResponse, Attachment


@pytest.fixture
def adapter():
    return MatrixAdapter(homeserver="https://matrix.example.com", user_id="@bot:example.com", access_token="tok")


class TestNormalize:
    @pytest.mark.asyncio
    async def test_text_message(self, adapter):
        raw = {"sender": "@alice:example.com", "content": {"body": "hello", "msgtype": "m.text"}, "room_id": "!room1"}
        msg = await adapter.normalize(raw)
        assert msg.content == "hello"
        assert msg.author_name == "alice"
        assert msg.platform == "matrix"

    @pytest.mark.asyncio
    async def test_image_attachment(self, adapter):
        raw = {"sender": "@bob:ex.com", "content": {"body": "pic.png", "msgtype": "m.image",
               "url": "mxc://server/abc", "info": {"mimetype": "image/png", "size": 1024}}, "room_id": "!r"}
        msg = await adapter.normalize(raw)
        assert len(msg.attachments) == 1
        assert msg.attachments[0].content_type == "image/png"

    @pytest.mark.asyncio
    async def test_dm_detection(self, adapter):
        raw = {"sender": "@a:b", "content": {"body": "hi"}, "room_id": "!r", "is_direct": True}
        msg = await adapter.normalize(raw)
        assert msg.is_dm is True

    @pytest.mark.asyncio
    async def test_empty_message(self, adapter):
        msg = await adapter.normalize({})
        assert msg.content == ""


class TestSendResponse:
    @pytest.mark.asyncio
    async def test_no_client(self, adapter):
        resp = OutboundResponse(content="test")
        await adapter.send_response(resp, "!room1")  # Should not raise
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_with_client(self, adapter):
        adapter._client = MagicMock()
        adapter._client.room_send = AsyncMock()
        resp = OutboundResponse(content="hello")
        await adapter.send_response(resp, "!room1")
        adapter._client.room_send.assert_called_once()


class TestAddReaction:
    @pytest.mark.asyncio
    async def test_no_client(self, adapter):
        await adapter.add_reaction(None, "👍")  # No-op
        assert True  # No exception: negative case handled correctly


class TestFormatMentions:
    @pytest.mark.asyncio
    async def test_strips_server(self, adapter):
        result = await adapter.format_mentions("Hi @alice:matrix.org!")
        assert "@alice" in result
        assert "matrix.org" not in result
