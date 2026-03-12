"""
Game Engine Interface — v3.4 Rhizome.

Abstract interface for game world interactions.
Decouples Ernos gaming logic from Minecraft-specific code,
enabling future support for other games.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("Gaming.Interface")


@dataclass
class GameState:
    """Platform-agnostic game state representation."""
    player_position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    player_health: float = 100.0
    player_inventory: List[Dict] = field(default_factory=list)
    nearby_entities: List[Dict] = field(default_factory=list)
    nearby_blocks: List[Dict] = field(default_factory=list)
    current_biome: str = "unknown"
    time_of_day: str = "day"
    weather: str = "clear"
    custom: Dict = field(default_factory=dict)  # Game-specific extras


@dataclass 
class GameAction:
    """Platform-agnostic action to perform."""
    action_type: str  # move, mine, place, attack, craft, etc.
    parameters: Dict = field(default_factory=dict)
    priority: int = 5  # 1 (lowest) to 10 (highest)


class GameEngineInterface(ABC):
    """
    Abstract interface for game world interaction.
    
    Each game engine (Minecraft, Terraria, etc.) implements this
    to provide a unified way for Ernos to perceive and act.
    
    Current implementations:
    - MinecraftEngine (via Mineflayer bridge)
    
    Future:
    - TerrariaEngine
    - RobloxEngine
    - CustomGameEngine
    """
    
    @abstractmethod
    async def get_state(self) -> GameState:
        """Get current game state."""
    
    @abstractmethod
    async def execute_action(self, action: GameAction) -> Dict:
        """
        Execute an action in the game world.
        
        Returns dict with: success (bool), result (str), state (GameState)
        """
    
    @abstractmethod
    async def get_available_actions(self) -> List[str]:
        """Get list of available action types."""
    
    @abstractmethod
    async def connect(self, config: Dict) -> bool:
        """Connect to game server. Returns True on success."""
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from game server."""
    
    @property
    @abstractmethod
    def game_name(self) -> str:
        """Return game identifier (e.g., 'minecraft')."""
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether currently connected to game server."""


class MinecraftEngine(GameEngineInterface):
    """
    Minecraft implementation wrapping the existing Mineflayer bridge.
    
    Translates between the platform-agnostic GameEngineInterface
    and the Minecraft-specific MineflayerBridge.
    """
    
    def __init__(self, bridge=None):
        """
        Args:
            bridge: Existing MineflayerBridge instance
        """
        self._bridge = bridge
        self._connected = False
    
    async def get_state(self) -> GameState:
        """Get Minecraft state via bridge."""
        if not self._bridge:
            return GameState()
        
        try:
            bot_data = await self._bridge.get_bot_state() if hasattr(self._bridge, 'get_bot_state') else {}
            
            return GameState(
                player_position=bot_data.get("position", {"x": 0, "y": 0, "z": 0}),
                player_health=bot_data.get("health", 20),
                player_inventory=bot_data.get("inventory", []),
                nearby_entities=bot_data.get("nearby_entities", []),
                nearby_blocks=bot_data.get("nearby_blocks", []),
                current_biome=bot_data.get("biome", "unknown"),
                time_of_day="day" if bot_data.get("time", 0) < 13000 else "night",
                weather=bot_data.get("weather", "clear"),
                custom={"game_time": bot_data.get("time", 0)}
            )
        except Exception as e:
            logger.error(f"Failed to get Minecraft state: {e}")
            return GameState()
    
    async def execute_action(self, action: GameAction) -> Dict:
        """Execute via Mineflayer bridge."""
        if not self._bridge:
            return {"success": False, "result": "No bridge connection"}
        
        try:
            result = await self._bridge.execute_action(
                action.action_type, 
                action.parameters
            ) if hasattr(self._bridge, 'execute_action') else {}
            
            return {
                "success": result.get("success", False),
                "result": result.get("message", ""),
                "state": await self.get_state()
            }
        except Exception as e:
            return {"success": False, "result": str(e)}
    
    async def get_available_actions(self) -> List[str]:
        """Available Minecraft actions."""
        return [
            "move", "mine", "place", "attack", "craft",
            "smelt", "eat", "equip", "drop", "chat",
            "look", "jump", "sneak", "sprint"
        ]
    
    async def connect(self, config: Dict) -> bool:
        """Connect to Minecraft server."""
        try:
            if self._bridge and hasattr(self._bridge, 'connect'):
                await self._bridge.connect(
                    host=config.get("host", "localhost"),
                    port=config.get("port", 25565),
                    username=config.get("username", "Ernos")
                )
                self._connected = True
                return True
        except Exception as e:
            logger.error(f"Minecraft connection failed: {e}")
        return False
    
    async def disconnect(self) -> None:
        """Disconnect from Minecraft."""
        if self._bridge and hasattr(self._bridge, 'disconnect'):
            await self._bridge.disconnect()
        self._connected = False
    
    @property
    def game_name(self) -> str:
        return "minecraft"
    
    @property
    def is_connected(self) -> bool:
        return self._connected
