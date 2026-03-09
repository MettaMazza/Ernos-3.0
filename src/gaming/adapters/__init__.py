"""
Game Adapter Base - Abstract interface for game control.

Enables future adapters for NMS, Pokemon, etc.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class GameAdapter(ABC):
    """Abstract interface for game control."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the game. Returns True on success."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the game."""
        pass
    
    @abstractmethod
    async def execute(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command. Returns result dict with success/data/error."""
        pass
    
    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get current game state."""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass
