"""Tests for WebAdapter — 6 tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.channels.web_adapter import WebAdapter
from src.channels.types import OutboundResponse, Attachment


@pytest.fixture
def adapter():
    return WebAdapter()


class TestNormalize:
    @pytest.mark.asyncio
    async def test_basic_payload(self, adapter):
        raw = {"user_id": "u1", "username": "Alice", "message": "hello", "session_id": "s1"}
        msg = await adapter.normalize(raw)
        assert msg.content == "hello"
        assert msg.author_name == "Alice"
        assert msg.channel_id == "s1"
        assert msg.is_dm is True
        assert msg.platform == "web"

    @pytest.mark.asyncio
    async def test_with_attachments(self, adapter):
        raw = {"message": "see file", "attachments": [
            {"filename": "doc.pdf", "content_type": "application/pdf", "url": "http://x", "size": 100}
        ]}
        msg = await adapter.normalize(raw)
        assert len(msg.attachments) == 1
        assert msg.attachments[0].filename == "doc.pdf"

    @pytest.mark.asyncio
    async def test_empty_payload(self, adapter):
        msg = await adapter.normalize({})
        assert msg.content == ""


class TestSendAndGet:
    @pytest.mark.asyncio
    async def test_queue_and_retrieve(self, adapter):
        resp = OutboundResponse(content="reply")
        await adapter.send_response(resp, "session1")
        responses = adapter.get_responses("session1")
        assert responses == ["reply"]

    @pytest.mark.asyncio
    async def test_get_clears_queue(self, adapter):
        resp = OutboundResponse(content="a")
        await adapter.send_response(resp, "s2")
        adapter.get_responses("s2")
        assert adapter.get_responses("s2") == []


class TestPlatform:
    def test_name(self, adapter):
        assert adapter.platform_name == "web"
