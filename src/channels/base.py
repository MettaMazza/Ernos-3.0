"""
Abstract base class for channel adapters.
Each platform (Discord, Telegram, Slack, etc.) implements this interface.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any

from src.channels.types import Attachment, OutboundResponse, UnifiedMessage

logger = logging.getLogger("Channels.Base")


class ChannelAdapter(ABC):
    """
    Base class for platform channel adapters.
    
    Adapters are responsible for:
    1. Converting platform-native messages into UnifiedMessage
    2. Sending OutboundResponse back through the platform
    3. Platform-specific operations (reactions, file downloads, etc.)
    """

    @abstractmethod
    async def normalize(self, raw_message: Any) -> UnifiedMessage:
        """
        Convert a platform-native message into a UnifiedMessage.
        
        Args:
            raw_message: The platform-specific message object
            
        Returns:
            UnifiedMessage with all fields populated
        """

    @abstractmethod
    async def send_response(self, response: OutboundResponse, channel_ref: Any) -> None:
        """
        Send an OutboundResponse back through the platform channel.
        
        Handles platform-specific concerns like:
        - Message length limits and chunking
        - File attachment formatting
        - Reply threading
        - TTS audio delivery
        
        Args:
            response: The response to send
            channel_ref: Platform-specific channel/message reference for sending
        """

    @abstractmethod
    async def add_reaction(self, message_ref: Any, emoji: str) -> None:
        """
        Add an emoji reaction to a message.
        
        Args:
            message_ref: Platform-specific message reference
            emoji: The emoji to react with
        """

    @abstractmethod
    async def fetch_attachment_data(self, attachment: Attachment) -> bytes:
        """
        Download the raw bytes of an attachment.
        
        Args:
            attachment: The attachment to download
            
        Returns:
            Raw bytes of the attachment content
        """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier string (e.g., 'discord', 'telegram')."""

    @abstractmethod
    async def format_mentions(self, content: str) -> str:
        """
        Convert platform-specific mention formats to a normalized form.
        
        This prevents mention-spoofing across platforms where a user
        could craft content that looks like a mention on another platform.
        
        Args:
            content: Raw message content potentially containing mentions
            
        Returns:
            Content with mentions normalized to @username format
        """
