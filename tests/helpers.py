"""
Shared test utilities for Synapse Bridge v3.1.

Provides helper functions to patch mock bots with the channel_manager
mock required by the adapter.normalize() call in chat.py.
"""
from unittest.mock import MagicMock
from src.channels.types import UnifiedMessage


def patch_channel_manager(bot_mock):
    """
    Add a channel_manager mock with async normalize to a bot mock.
    
    Call this after creating any MagicMock() bot that will be used
    with ChatListener.on_message().
    """
    mock_adapter = MagicMock()
    
    async def _normalize(raw_msg):
        author = getattr(raw_msg, 'author', MagicMock())
        channel = getattr(raw_msg, 'channel', MagicMock())
        return UnifiedMessage(
            content=getattr(raw_msg, 'content', ''),
            author_id=str(getattr(author, 'id', '0')),
            author_name=getattr(author, 'display_name', None) or getattr(author, 'name', 'TestUser'),
            channel_id=str(getattr(channel, 'id', '0')),
            is_dm=False,
            is_bot=getattr(author, 'bot', False),
            attachments=[],
            platform="discord",
            raw=raw_msg,
        )
    
    mock_adapter.normalize = _normalize
    from unittest.mock import AsyncMock
    mock_adapter.format_mentions = AsyncMock(side_effect=lambda text: text)
    mock_adapter.platform_name = "discord"
    
    mock_cm = MagicMock()
    mock_cm.get_adapter.return_value = mock_adapter
    bot_mock.channel_manager = mock_cm
    
    return bot_mock
