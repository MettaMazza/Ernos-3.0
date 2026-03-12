"""
Extended tests for all 4 channel adapters — targeting uncovered lines.
Discord: 94-98, 104-105, 120-123, 132-144
Matrix: 85-86, 92-108, 112-119, 123
Telegram: 59, 93-94, 98, 102-109, 117
Web: 77, 81-88, 96
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ════════════════════════════════════════════════════════
#  Discord Adapter
# ════════════════════════════════════════════════════════

class TestDiscordAdapterExtended:

    def _adapter(self):
        from src.channels.discord_adapter import DiscordChannelAdapter
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 999
        return DiscordChannelAdapter(bot)

    @pytest.mark.asyncio
    async def test_send_response_with_files(self):
        """Lines 94-98: file attachment path."""
        from src.channels.types import OutboundResponse
        adapter = self._adapter()
        resp = OutboundResponse(content="see files", files=["/tmp/test.png"], reactions=[])
        msg = MagicMock()
        msg.reply = AsyncMock()
        msg.add_reaction = AsyncMock()
        with patch("os.path.exists", return_value=True), \
             patch("discord.File"):
            await adapter.send_response(resp, msg)
        msg.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_file_not_found(self):
        """Files that don't exist are skipped."""
        from src.channels.types import OutboundResponse
        adapter = self._adapter()
        resp = OutboundResponse(content="no file", files=["/nonexistent"], reactions=[])
        msg = MagicMock()
        msg.reply = AsyncMock()
        msg.add_reaction = AsyncMock()
        with patch("os.path.exists", return_value=False):
            await adapter.send_response(resp, msg)
        msg.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_file_exception(self):
        """Lines 97-98: discord.File raises."""
        from src.channels.types import OutboundResponse
        adapter = self._adapter()
        resp = OutboundResponse(content="bad file", files=["/tmp/bad.png"], reactions=[])
        msg = MagicMock()
        msg.reply = AsyncMock()
        msg.add_reaction = AsyncMock()
        import discord
        with patch("os.path.exists", return_value=True), \
             patch("discord.File", side_effect=Exception("read error")):
            await adapter.send_response(resp, msg)
        msg.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_reaction_fails(self):
        """Lines 104-105: reaction add fails."""
        from src.channels.types import OutboundResponse
        adapter = self._adapter()
        resp = OutboundResponse(content="hi", files=[], reactions=["👍"])
        msg = MagicMock()
        msg.reply = AsyncMock()
        msg.add_reaction = AsyncMock(side_effect=Exception("forbidden"))
        await adapter.send_response(resp, msg)
        msg.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_reaction_success(self):
        """Lines 120-121: direct add_reaction call."""
        adapter = self._adapter()
        msg = MagicMock()
        msg.add_reaction = AsyncMock()
        await adapter.add_reaction(msg, "🔥")
        msg.add_reaction.assert_called_once_with("🔥")

    @pytest.mark.asyncio
    async def test_add_reaction_fails(self):
        """Lines 122-123: add_reaction exception."""
        adapter = self._adapter()
        msg = MagicMock()
        msg.add_reaction = AsyncMock(side_effect=Exception("rate limit"))
        await adapter.add_reaction(msg, "🔥")
        assert True  # No exception: error handled gracefully

    @pytest.mark.asyncio
    async def test_fetch_attachment_cached_data(self):
        """Line 132: data already present."""
        from src.channels.types import Attachment
        adapter = self._adapter()
        att = Attachment(filename="f.txt", content_type="text/plain", url="http://x", size=10, data=b"hello")
        result = await adapter.fetch_attachment_data(att)
        assert result == b"hello"

    @pytest.mark.asyncio
    async def test_fetch_attachment_from_url(self):
        """Lines 138-144: download via aiohttp."""
        from src.channels.types import Attachment
        adapter = self._adapter()
        att = Attachment(filename="f.txt", content_type="text/plain", url="http://x", size=10)

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=b"data")

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await adapter.fetch_attachment_data(att)
        assert result == b"data"

    @pytest.mark.asyncio
    async def test_fetch_attachment_http_error(self):
        """Lines 142-144: non-200 status."""
        from src.channels.types import Attachment
        adapter = self._adapter()
        att = Attachment(filename="f.txt", content_type="text/plain", url="http://x", size=10)

        mock_resp = AsyncMock()
        mock_resp.status = 404

        mock_get_cm = AsyncMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_get_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_get_cm)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(RuntimeError, match="HTTP 404"):
                await adapter.fetch_attachment_data(att)


# ════════════════════════════════════════════════════════
#  Matrix Adapter
# ════════════════════════════════════════════════════════

class TestMatrixAdapterExtended:

    def _adapter(self, with_client=False):
        from src.channels.matrix_adapter import MatrixAdapter
        a = MatrixAdapter("https://matrix", "@bot:matrix", "tok")
        if with_client:
            a._client = MagicMock()
            a._client.room_send = AsyncMock()
            a._client.download = AsyncMock()
        return a

    @pytest.mark.asyncio
    async def test_send_no_client(self):
        """Lines 85-86: no client, early return."""
        from src.channels.types import OutboundResponse
        a = self._adapter()
        resp = OutboundResponse(content="hi", files=[], reactions=[])
        await a.send_response(resp, "!room:x")
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_send_with_client(self):
        """Lines 80-84: sends via room_send."""
        from src.channels.types import OutboundResponse
        a = self._adapter(with_client=True)
        resp = OutboundResponse(content="hi", files=[], reactions=[])
        await a.send_response(resp, "!room:x")
        a._client.room_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_exception(self):
        """Lines 85-86: room_send fails."""
        from src.channels.types import OutboundResponse
        a = self._adapter(with_client=True)
        a._client.room_send = AsyncMock(side_effect=Exception("send failed"))
        resp = OutboundResponse(content="hi", files=[], reactions=[])
        await a.send_response(resp, "!room:x")
        assert True  # No exception: error handled gracefully

    @pytest.mark.asyncio
    async def test_add_reaction_no_client(self):
        """Line 92: no client returns early."""
        a = self._adapter()
        await a.add_reaction(("!room:x", "$ev:x"), "🔥")
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_add_reaction_no_room_id(self):
        """Lines 94-95: non-tuple message_ref."""
        a = self._adapter(with_client=True)
        await a.add_reaction("bad_ref", "🔥")
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_add_reaction_success(self):
        """Lines 96-106: full reaction path."""
        a = self._adapter(with_client=True)
        await a.add_reaction(("!room:x", "$ev:x"), "🔥")
        a._client.room_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_reaction_exception(self):
        """Lines 107-108: reaction fails."""
        a = self._adapter(with_client=True)
        a._client.room_send = AsyncMock(side_effect=Exception("denied"))
        await a.add_reaction(("!room:x", "$ev:x"), "🔥")
        assert True  # No exception: error handled gracefully

    @pytest.mark.asyncio
    async def test_fetch_attachment_no_client(self):
        """Lines 112-113: no client returns empty."""
        from src.channels.types import Attachment
        a = self._adapter()
        att = Attachment(filename="f", content_type="text/plain", url="mxc://x", size=10)
        result = await a.fetch_attachment_data(att)
        assert result == b""

    @pytest.mark.asyncio
    async def test_fetch_attachment_success(self):
        """Lines 114-116: download succeeds."""
        from src.channels.types import Attachment
        a = self._adapter(with_client=True)
        resp = MagicMock()
        resp.body = b"data"
        a._client.download = AsyncMock(return_value=resp)
        att = Attachment(filename="f", content_type="text/plain", url="mxc://x", size=10)
        result = await a.fetch_attachment_data(att)
        assert result == b"data"

    @pytest.mark.asyncio
    async def test_fetch_attachment_exception(self):
        """Lines 117-119: download fails."""
        from src.channels.types import Attachment
        a = self._adapter(with_client=True)
        a._client.download = AsyncMock(side_effect=Exception("net error"))
        att = Attachment(filename="f", content_type="text/plain", url="mxc://x", size=10)
        result = await a.fetch_attachment_data(att)
        assert result == b""

    def test_platform_name(self):
        """Line 123."""
        a = self._adapter()
        assert a.platform_name == "matrix"


# ════════════════════════════════════════════════════════
#  Telegram Adapter
# ════════════════════════════════════════════════════════

class TestTelegramAdapterExtended:

    def _adapter(self, with_bot=False):
        from src.channels.telegram_adapter import TelegramAdapter
        a = TelegramAdapter("bottoken123")
        if with_bot:
            a._bot = MagicMock()
            a._bot.send_message = AsyncMock()
            a._bot.get_file = AsyncMock()
        return a

    @pytest.mark.asyncio
    async def test_normalize_with_photo(self):
        """Line 59: photo attachment."""
        a = self._adapter()
        msg = MagicMock()
        msg.message = msg  # getattr loops back
        msg.from_user = MagicMock()
        msg.from_user.id = 123
        msg.from_user.username = "user1"
        msg.text = "check this"
        msg.caption = None
        msg.chat = MagicMock()
        msg.chat.id = 456
        msg.chat.type = "private"
        photo = MagicMock()
        photo.file_id = "PHOTO_ID"
        msg.photo = [photo]
        msg.document = None
        unified = await a.normalize(msg)
        assert len(unified.attachments) == 1
        assert unified.attachments[0].content_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_normalize_with_document(self):
        """Lines 63-68: document attachment."""
        a = self._adapter()
        msg = MagicMock()
        msg.message = msg
        msg.from_user = MagicMock()
        msg.from_user.id = 123
        msg.from_user.username = "user1"
        msg.text = None
        msg.caption = "doc here"
        msg.chat = MagicMock()
        msg.chat.id = 456
        msg.chat.type = "group"
        msg.photo = None
        msg.document = MagicMock()
        msg.document.file_name = "report.pdf"
        msg.document.mime_type = "application/pdf"
        msg.document.file_id = "DOC_ID"
        msg.document.file_size = 2048
        unified = await a.normalize(msg)
        assert len(unified.attachments) == 1
        assert unified.attachments[0].filename == "report.pdf"
        assert unified.is_dm is False

    @pytest.mark.asyncio
    async def test_send_no_bot(self):
        """Lines 83-84: no bot, early return."""
        from src.channels.types import OutboundResponse
        a = self._adapter()
        resp = OutboundResponse(content="hi", files=[], reactions=[])
        await a.send_response(resp, 123)
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_send_with_chunking(self):
        """Lines 89-94: chunked send."""
        from src.channels.types import OutboundResponse
        a = self._adapter(with_bot=True)
        resp = OutboundResponse(content="A" * 5000, files=[], reactions=[])
        await a.send_response(resp, 123)
        assert a._bot.send_message.call_count == 2  # 4096 + 904

    @pytest.mark.asyncio
    async def test_send_exception(self):
        """Lines 93-94: send_message fails."""
        from src.channels.types import OutboundResponse
        a = self._adapter(with_bot=True)
        a._bot.send_message = AsyncMock(side_effect=Exception("rate limit"))
        resp = OutboundResponse(content="hi", files=[], reactions=[])
        await a.send_response(resp, 123)
        assert True  # No exception: error handled gracefully

    @pytest.mark.asyncio
    async def test_add_reaction(self):
        """Line 98: reaction is a no-op."""
        a = self._adapter()
        await a.add_reaction(MagicMock(), "🔥")
        assert True  # Execution completed without error

    @pytest.mark.asyncio
    async def test_fetch_no_bot(self):
        """Lines 102-103: no bot returns empty."""
        from src.channels.types import Attachment
        a = self._adapter()
        att = Attachment(filename="f", content_type="text/plain", url="FILE_ID", size=10)
        result = await a.fetch_attachment_data(att)
        assert result == b""

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """Lines 104-106: download succeeds."""
        from src.channels.types import Attachment
        a = self._adapter(with_bot=True)
        mock_file = MagicMock()
        mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"data"))
        a._bot.get_file = AsyncMock(return_value=mock_file)
        att = Attachment(filename="f", content_type="text/plain", url="FILE_ID", size=10)
        result = await a.fetch_attachment_data(att)
        assert result == bytearray(b"data")

    @pytest.mark.asyncio
    async def test_fetch_exception(self):
        """Lines 107-109: download fails."""
        from src.channels.types import Attachment
        a = self._adapter(with_bot=True)
        a._bot.get_file = AsyncMock(side_effect=Exception("net error"))
        att = Attachment(filename="f", content_type="text/plain", url="FILE_ID", size=10)
        result = await a.fetch_attachment_data(att)
        assert result == b""

    @pytest.mark.asyncio
    async def test_format_mentions(self):
        """Line 117: passthrough."""
        a = self._adapter()
        result = await a.format_mentions("Hello @username")
        assert result == "Hello @username"


# ════════════════════════════════════════════════════════
#  Web Adapter
# ════════════════════════════════════════════════════════

class TestWebAdapterExtended:

    def _adapter(self):
        from src.channels.web_adapter import WebAdapter
        return WebAdapter()

    @pytest.mark.asyncio
    async def test_add_reaction(self):
        """Line 77: no-op."""
        a = self._adapter()
        await a.add_reaction(MagicMock(), "🔥")
        assert True  # Execution completed without error

    @pytest.mark.asyncio
    async def test_fetch_attachment_success(self):
        """Lines 81-84: download via aiohttp."""
        from src.channels.types import Attachment
        a = self._adapter()
        att = Attachment(filename="f.txt", content_type="text/plain", url="http://x", size=10)

        mock_resp = MagicMock()
        mock_resp.read = AsyncMock(return_value=b"data")

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_resp), __aexit__=AsyncMock()))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await a.fetch_attachment_data(att)
        assert result == b"data"

    @pytest.mark.asyncio
    async def test_fetch_attachment_exception(self):
        """Lines 86-88: download fails."""
        from src.channels.types import Attachment
        a = self._adapter()
        att = Attachment(filename="f.txt", content_type="text/plain", url="http://x", size=10)

        with patch("aiohttp.ClientSession", side_effect=Exception("connection refused")):
            result = await a.fetch_attachment_data(att)
        assert result == b""

    @pytest.mark.asyncio
    async def test_format_mentions(self):
        """Line 96: passthrough."""
        a = self._adapter()
        result = await a.format_mentions("@user123 hi")
        assert result == "@user123 hi"
