"""
Web Channel Adapter — v3.4 Rhizome.

Adapter for web-based chat interfaces (REST/WebSocket).
Enables Ernos to run as a web chatbot without Discord.

Updated for WebSocket support — responses are sent directly
through the WebSocket connection instead of being queued.
"""
import logging
from typing import Any, Dict, Optional

from src.channels.base import ChannelAdapter
from src.channels.types import Attachment, OutboundResponse, UnifiedMessage

logger = logging.getLogger("Channels.Web")


class WebAdapter(ChannelAdapter):
    """
    Web chat adapter for WebSocket interfaces.
    
    Normalizes HTTP/WebSocket payloads into UnifiedMessage format.
    Responses are sent directly through active WebSocket connections.
    
    Expected request format:
    {
        "user_id": "...",
        "username": "...",
        "message": "...",
        "session_id": "...",
        "attachments": [...]
    }
    """
    
    def __init__(self):
        self._websockets: Dict[str, Any] = {}  # session_id -> WebSocket
        self._response_queue: Dict[str, list] = {}  # fallback for non-WS
        logger.info("WebAdapter initialized (WebSocket mode)")
    
    def register_websocket(self, session_id: str, websocket) -> None:
        """Register an active WebSocket connection for a session."""
        self._websockets[session_id] = websocket
        logger.debug(f"WebSocket registered for session {session_id}")
    
    def unregister_websocket(self, session_id: str) -> None:
        """Remove a WebSocket connection when disconnected."""
        self._websockets.pop(session_id, None)
        logger.debug(f"WebSocket unregistered for session {session_id}")
    
    async def normalize(self, raw_message: Any) -> UnifiedMessage:
        """Convert web request payload to UnifiedMessage."""
        data = raw_message if isinstance(raw_message, dict) else {}
        
        user_id = str(data.get("user_id", "web_user"))
        username = data.get("username", "Web User")
        message = data.get("message", "")
        session_id = data.get("session_id", "default")
        
        attachments = []
        for att in data.get("attachments", []):
            attachments.append(Attachment(
                filename=att.get("filename", "file"),
                content_type=att.get("content_type", "application/octet-stream"),
                url=att.get("url", ""),
                size=att.get("size", 0)
            ))
        
        return UnifiedMessage(
            content=message,
            author_id=user_id,
            author_name=username,
            channel_id=session_id,
            is_dm=True,
            is_bot=False,
            attachments=attachments,
            platform="web",
            raw=raw_message
        )
    
    async def send_response(self, response: OutboundResponse, channel_ref: Any) -> None:
        """
        Send response through WebSocket if available, otherwise queue it.
        """
        session_id = str(channel_ref)
        
        # Try WebSocket first
        ws = self._websockets.get(session_id)
        if ws:
            try:
                file_paths = [str(f) for f in (response.files or [])]
                await ws.send_json({
                    "type": "response",
                    "content": response.content,
                    "files": file_paths,
                })
                logger.debug(f"Web response sent via WebSocket for session {session_id}")
                return
            except Exception as e:
                logger.warning(f"WebSocket send failed for {session_id}: {e}")
                self._websockets.pop(session_id, None)
        
        # Fallback to queue (for polling-based clients)
        if session_id not in self._response_queue:
            self._response_queue[session_id] = []
        self._response_queue[session_id].append(response.content)
        logger.debug(f"Web response queued for session {session_id}")
    
    async def add_reaction(self, message_ref: Any, emoji: str) -> None:
        """Web doesn't support reactions in the same way."""
        pass
    
    async def fetch_attachment_data(self, attachment: Attachment) -> bytes:
        """Download attachment from URL."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    return await resp.read()
        except Exception as e:
            logger.error(f"Web attachment download failed: {e}")
            return b""
    
    @property
    def platform_name(self) -> str:
        return "web"
    
    async def format_mentions(self, content: str) -> str:
        """Web has no special mention format."""
        return content
    
    def get_responses(self, session_id: str) -> list:
        """Retrieve and clear queued responses for a session (polling fallback)."""
        responses = self._response_queue.pop(session_id, [])
        return responses
