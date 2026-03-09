"""
Tests for the Channel Adapter Framework (Synapse Bridge v3.1).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.channels.types import Attachment, OutboundResponse, UnifiedMessage
from src.channels.manager import ChannelManager
from src.channels.discord_adapter import DiscordChannelAdapter


# === UnifiedMessage Tests ===

class TestUnifiedMessage:
    """Tests for the UnifiedMessage dataclass."""

    def test_creation_with_defaults(self):
        msg = UnifiedMessage(
            content="hello",
            author_id="123",
            author_name="Alice",
            channel_id="456",
            is_dm=False,
            is_bot=False,
        )
        assert msg.content == "hello"
        assert msg.author_id == "123"
        assert msg.author_name == "Alice"
        assert msg.channel_id == "456"
        assert msg.is_dm is False
        assert msg.is_bot is False
        assert msg.attachments == []
        assert msg.reply_to is None
        assert msg.platform == "unknown"
        assert msg.raw is None

    def test_has_images_true(self):
        msg = UnifiedMessage(
            content="look at this",
            author_id="123",
            author_name="Alice",
            channel_id="456",
            is_dm=False,
            is_bot=False,
            attachments=[
                Attachment(filename="pic.png", content_type="image/png", size=1024, url="http://..."),
            ],
        )
        assert msg.has_images is True

    def test_has_images_false(self):
        msg = UnifiedMessage(
            content="here is a file",
            author_id="123",
            author_name="Alice",
            channel_id="456",
            is_dm=False,
            is_bot=False,
            attachments=[
                Attachment(filename="doc.pdf", content_type="application/pdf", size=2048, url="http://..."),
            ],
        )
        assert msg.has_images is False

    def test_image_and_document_filters(self):
        attachments = [
            Attachment(filename="pic.jpg", content_type="image/jpeg", size=500, url="http://..."),
            Attachment(filename="doc.txt", content_type="text/plain", size=100, url="http://..."),
            Attachment(filename="photo.png", content_type="image/png", size=800, url="http://..."),
        ]
        msg = UnifiedMessage(
            content="mixed",
            author_id="123",
            author_name="Alice",
            channel_id="456",
            is_dm=False,
            is_bot=False,
            attachments=attachments,
        )
        assert len(msg.image_attachments) == 2
        assert len(msg.document_attachments) == 1


# === ChannelManager Tests ===

class TestChannelManager:
    """Tests for the ChannelManager registry."""

    def test_register_and_lookup(self):
        manager = ChannelManager()
        adapter = MagicMock()
        adapter.platform_name = "telegram"
        manager.register_adapter(adapter)
        assert manager.get_adapter("telegram") is adapter

    def test_unknown_platform_returns_none(self):
        manager = ChannelManager()
        assert manager.get_adapter("slack") is None

    def test_list_platforms(self):
        manager = ChannelManager()
        a1 = MagicMock()
        a1.platform_name = "discord"
        a2 = MagicMock()
        a2.platform_name = "telegram"
        manager.register_adapter(a1)
        manager.register_adapter(a2)
        assert set(manager.list_platforms()) == {"discord", "telegram"}


# === DiscordChannelAdapter Tests ===

class TestDiscordAdapter:
    """Tests for the Discord-specific adapter."""

    @pytest.mark.asyncio
    async def test_format_mentions_converts_bare_ids(self):
        bot = MagicMock()
        adapter = DiscordChannelAdapter(bot)
        result = await adapter.format_mentions("Hello @764896542170939443!")
        assert result == "Hello <@764896542170939443>!"

    @pytest.mark.asyncio
    async def test_format_mentions_skips_already_wrapped(self):
        bot = MagicMock()
        adapter = DiscordChannelAdapter(bot)
        result = await adapter.format_mentions("Hello <@764896542170939443>!")
        assert result == "Hello <@764896542170939443>!"

    @pytest.mark.asyncio
    async def test_format_mentions_handles_multiple(self):
        bot = MagicMock()
        adapter = DiscordChannelAdapter(bot)
        result = await adapter.format_mentions("@111111111111111111 and @222222222222222222")
        assert result == "<@111111111111111111> and <@222222222222222222>"

    def test_platform_name(self):
        bot = MagicMock()
        adapter = DiscordChannelAdapter(bot)
        assert adapter.platform_name == "discord"


# === OutboundResponse Tests ===

class TestOutboundResponse:
    """Tests for the OutboundResponse dataclass."""

    def test_creation_with_defaults(self):
        response = OutboundResponse(content="Hello!")
        assert response.content == "Hello!"
        assert response.files == []
        assert response.reactions == []
        assert response.reply_to is None
        assert response.tts_audio is None

    def test_creation_with_files(self):
        from pathlib import Path
        response = OutboundResponse(
            content="Here are your files",
            files=[Path("/tmp/test.png")],
            reactions=["✅"],
        )
        assert len(response.files) == 1
        assert len(response.reactions) == 1
