"""
Web Channel Adapter — v3.4 Rhizome.

Adapter for web-based chat interfaces (REST/WebSocket).
Enables Ernos to run as a web chatbot without Discord.
"""
import logging
from typing import Any

from src.channels.base import ChannelAdapter
from src.channels.types import Attachment, OutboundResponse, UnifiedMessage

logger = logging.getLogger("Channels.Web")


class WebAdapter(ChannelAdapter):
    """
    Web chat adapter for REST API / WebSocket interfaces.
    
    Normalizes HTTP request payloads into UnifiedMessage format.
    Designed for self-hosted web UIs or API integrations.
    
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
        self._response_queue = {}  # session_id -> list of responses
        logger.info("WebAdapter initialized")
    
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
        """Queue response for web client retrieval."""
        session_id = str(channel_ref)
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
        """Retrieve and clear queued responses for a session."""
        responses = self._response_queue.pop(session_id, [])
        return responses
