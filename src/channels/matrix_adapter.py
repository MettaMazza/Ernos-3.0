"""
Matrix Channel Adapter — v3.4 Rhizome.

Stub implementation of ChannelAdapter for Matrix protocol.
Ready for activation once matrix-nio is installed.
"""
import logging
from typing import Any

from src.channels.base import ChannelAdapter
from src.channels.types import Attachment, OutboundResponse, UnifiedMessage

logger = logging.getLogger("Channels.Matrix")


class MatrixAdapter(ChannelAdapter):
    """
    Matrix protocol adapter (via matrix-nio).
    
    Converts Matrix RoomMessageText events to UnifiedMessage.
    Handles Matrix-specific features: E2EE, room state, 
    media repository, reply threading.
    
    Requires: matrix-nio package
    Config: MATRIX_HOMESERVER, MATRIX_USER_ID, MATRIX_ACCESS_TOKEN
    """
    
    def __init__(self, homeserver: str = "", user_id: str = "", access_token: str = ""):
        self._homeserver = homeserver
        self._user_id = user_id
        self._token = access_token
        self._client = None  # Will hold nio.AsyncClient
        logger.info("MatrixAdapter initialized (stub)")
    
    async def normalize(self, raw_message: Any) -> UnifiedMessage:
        """Convert Matrix event to UnifiedMessage."""
        # raw_message expected: dict with room_id, event data
        event = raw_message if isinstance(raw_message, dict) else {}
        
        sender = event.get("sender", "")
        content = event.get("content", {})
        body = content.get("body", "")
        room_id = event.get("room_id", "")
        
        # Matrix DM detection: room with exactly 2 members
        is_dm = event.get("is_direct", False)
        scope = "PRIVATE" if is_dm else "PUBLIC"
        
        attachments = []
        msgtype = content.get("msgtype", "m.text")
        if msgtype in ("m.image", "m.file", "m.audio", "m.video"):
            url = content.get("url", "")
            attachments.append(Attachment(
                filename=body,
                content_type=content.get("info", {}).get("mimetype", "application/octet-stream"),
                url=url,
                size=content.get("info", {}).get("size", 0)
            ))
        
        return UnifiedMessage(
            content=body,
            author_id=sender,
            author_name=sender.split(":")[0].lstrip("@") if sender else "",
            channel_id=room_id,
            is_dm=is_dm,
            is_bot=False,
            attachments=attachments,
            platform="matrix",
            raw=raw_message
        )
    
    async def send_response(self, response: OutboundResponse, channel_ref: Any) -> None:
        """Send response to Matrix room."""
        if not self._client:
            logger.warning("Matrix client not initialized, cannot send")
            return
        
        room_id = channel_ref
        try:
            await self._client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={"msgtype": "m.text", "body": response.content}
            )
        except Exception as e:
            logger.error(f"Matrix send failed: {e}")
    
    async def add_reaction(self, message_ref: Any, emoji: str) -> None:
        """Add reaction via Matrix reaction events."""
        if not self._client:
            return
        room_id, event_id = message_ref if isinstance(message_ref, tuple) else (None, None)
        if not room_id:
            return
        try:
            await self._client.room_send(
                room_id=room_id,
                message_type="m.reaction",
                content={
                    "m.relates_to": {
                        "rel_type": "m.annotation",
                        "event_id": event_id,
                        "key": emoji
                    }
                }
            )
        except Exception as e:
            logger.error(f"Matrix reaction failed: {e}")
    
    async def fetch_attachment_data(self, attachment: Attachment) -> bytes:
        """Download from Matrix media repository."""
        if not self._client:
            return b""
        try:
            resp = await self._client.download(attachment.url)
            return resp.body if hasattr(resp, 'body') else b""
        except Exception as e:
            logger.error(f"Matrix download failed: {e}")
            return b""
    
    @property
    def platform_name(self) -> str:
        return "matrix"
    
    async def format_mentions(self, content: str) -> str:
        """Matrix uses @user:server format."""
        import re
        return re.sub(r'@(\w+):[\w.]+', r'@\1', content)
