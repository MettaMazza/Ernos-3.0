"""
Telegram Channel Adapter — v3.4 Rhizome.

Stub implementation of ChannelAdapter for Telegram Bot API.
Ready for activation once python-telegram-bot is installed.
"""
import logging
from typing import Any

from src.channels.base import ChannelAdapter
from src.channels.types import Attachment, OutboundResponse, UnifiedMessage

logger = logging.getLogger("Channels.Telegram")


class TelegramAdapter(ChannelAdapter):
    """
    Telegram Bot API adapter.
    
    Converts Telegram Update objects to UnifiedMessage format.
    Handles Telegram-specific features: inline keyboards, 
    markdown v2, file uploads, reply threading.
    
    Requires: python-telegram-bot package
    Config: TELEGRAM_BOT_TOKEN in environment
    """
    
    MAX_MESSAGE_LENGTH = 4096  # Telegram limit
    
    def __init__(self, bot_token: str = ""):
        self._token = bot_token
        self._bot = None  # Will hold telegram.Bot instance
        logger.info("TelegramAdapter initialized (stub)")
    
    async def normalize(self, raw_message: Any) -> UnifiedMessage:
        """Convert telegram.Update to UnifiedMessage."""
        # raw_message expected: telegram.Update object
        msg = getattr(raw_message, 'message', raw_message)
        
        user_id = getattr(getattr(msg, 'from_user', None), 'id', 0)
        username = getattr(getattr(msg, 'from_user', None), 'username', '') or ""
        text = getattr(msg, 'text', '') or getattr(msg, 'caption', '') or ""
        chat_id = getattr(getattr(msg, 'chat', None), 'id', 0)
        
        # Determine scope from chat type
        chat_type = getattr(getattr(msg, 'chat', None), 'type', 'private')
        scope = "PRIVATE" if chat_type == "private" else "PUBLIC"
        
        attachments = []
        # Handle photos, documents, audio, video
        if hasattr(msg, 'photo') and msg.photo:
            attachments.append(Attachment(
                filename="photo.jpg",
                content_type="image/jpeg",
                url=msg.photo[-1].file_id,  # Highest resolution
                size=0
            ))
        if hasattr(msg, 'document') and msg.document:
            attachments.append(Attachment(
                filename=msg.document.file_name or "file",
                content_type=msg.document.mime_type or "application/octet-stream",
                url=msg.document.file_id,
                size=msg.document.file_size or 0
            ))
        
        return UnifiedMessage(
            content=text,
            author_id=str(user_id),
            author_name=username,
            channel_id=str(chat_id),
            is_dm=(chat_type == "private"),
            is_bot=False,
            attachments=attachments,
            platform="telegram",
            raw=raw_message
        )
    
    async def send_response(self, response: OutboundResponse, channel_ref: Any) -> None:
        """Send response via Telegram."""
        if not self._bot:
            logger.warning("Telegram bot not initialized, cannot send")
            return
        
        text = response.content
        chat_id = channel_ref
        
        # Chunk if needed
        while text:
            chunk = text[:self.MAX_MESSAGE_LENGTH]
            text = text[self.MAX_MESSAGE_LENGTH:]
            try:
                await self._bot.send_message(chat_id=chat_id, text=chunk)
            except Exception as e:
                logger.error(f"Telegram send failed: {e}")
    
    async def add_reaction(self, message_ref: Any, emoji: str) -> None:
        """Telegram reactions (limited API support)."""
        logger.debug(f"Telegram reaction not fully supported: {emoji}")
    
    async def fetch_attachment_data(self, attachment: Attachment) -> bytes:
        """Download file from Telegram servers."""
        if not self._bot:
            return b""
        try:
            file = await self._bot.get_file(attachment.url)
            return await file.download_as_bytearray()
        except Exception as e:
            logger.error(f"Telegram file download failed: {e}")
            return b""
    
    @property
    def platform_name(self) -> str:
        return "telegram"
    
    async def format_mentions(self, content: str) -> str:
        """Telegram uses @username format natively."""
        return content
