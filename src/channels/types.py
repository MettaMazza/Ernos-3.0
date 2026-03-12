"""
Platform-agnostic message types for the Channel Adapter Framework.
These types decouple the cognitive core from any specific platform SDK.
"""
from dataclasses import dataclass, field
from typing import Any, ClassVar, List, Optional
from pathlib import Path


@dataclass
class Attachment:
    """A normalized file attachment from any platform."""
    filename: str
    content_type: str
    size: int
    url: str
    data: Optional[bytes] = None  # Pre-fetched content (lazy by default)


@dataclass
class UnifiedMessage:
    """
    Platform-agnostic inbound message.
    Every channel adapter converts its native message type into this.
    """
    MAX_CONTENT_LENGTH: ClassVar[int] = 4000  # Discord's message limit

    content: str
    author_id: str
    author_name: str
    channel_id: str
    is_dm: bool
    is_bot: bool
    attachments: List[Attachment] = field(default_factory=list)
    reply_to: Optional[str] = None
    platform: str = "unknown"
    raw: Any = None  # Original platform-specific message object

    def __post_init__(self):
        """Validate and sanitize on construction."""
        # Cap content length to prevent context flooding
        if len(self.content) > self.MAX_CONTENT_LENGTH:
            self.content = self.content[:self.MAX_CONTENT_LENGTH]
        # Strip null bytes (common in binary injection attempts)
        self.content = self.content.replace('\x00', '')

    @property
    def has_images(self) -> bool:
        """Check if any attachments are images."""
        return any(
            a.content_type and a.content_type.startswith("image/")
            for a in self.attachments
        )

    @property
    def image_attachments(self) -> List[Attachment]:
        """Filter to only image attachments."""
        return [
            a for a in self.attachments
            if a.content_type and a.content_type.startswith("image/")
        ]

    @property
    def document_attachments(self) -> List[Attachment]:
        """Filter to non-image attachments."""
        return [
            a for a in self.attachments
            if not (a.content_type and a.content_type.startswith("image/"))
        ]


@dataclass
class OutboundResponse:
    """
    What the cognitive core produces as a response.
    Each channel adapter knows how to send this on its platform.
    """
    content: str
    files: List[Path] = field(default_factory=list)
    reactions: List[str] = field(default_factory=list)
    reply_to: Optional[str] = None      # Message ID to reply to
    tts_audio: Optional[Path] = None    # Voice audio file path
