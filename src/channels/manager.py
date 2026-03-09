"""
Channel Manager — Registry for platform channel adapters.
"""
import logging
from typing import Dict, Optional

from src.channels.base import ChannelAdapter

logger = logging.getLogger("Channels.Manager")


class ChannelManager:
    """
    Manages registered channel adapters.
    
    Each platform registers its adapter during bot startup.
    The cognitive pipeline uses the manager to resolve the correct
    adapter for incoming/outgoing messages.
    """

    def __init__(self):
        self._adapters: Dict[str, ChannelAdapter] = {}

    def register_adapter(self, adapter: ChannelAdapter) -> None:
        """
        Register a channel adapter by its platform name.
        
        Args:
            adapter: The adapter instance to register
        """
        name = adapter.platform_name
        self._adapters[name] = adapter
        logger.info(f"Channel adapter registered: {name}")

    def get_adapter(self, platform: str) -> Optional[ChannelAdapter]:
        """
        Retrieve a registered adapter by platform name.
        
        Args:
            platform: The platform identifier (e.g., 'discord')
            
        Returns:
            The adapter, or None if not registered
        """
        adapter = self._adapters.get(platform)
        if adapter is None:
            logger.warning(f"No adapter registered for platform: {platform}")
        return adapter

    def list_platforms(self) -> list:
        """Return a list of all registered platform names."""
        return list(self._adapters.keys())
