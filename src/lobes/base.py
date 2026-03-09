"""
Base classes for the Cerebrum Architecture.
Defines the structure for Lobes (Functional Areas) and Abilities (Specific Skills).
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import Cerebrum

logger = logging.getLogger("Cerebrum.Base")

class BaseAbility(ABC):
    """
    A specific cognitive skill or capability unit within a Lobe.
    Example: PlannerAbility, DreamerAbility, ResearchAbility.
    """
    def __init__(self, lobe: 'BaseLobe'):
        self.lobe = lobe
    
    @property
    def cerebrum(self) -> 'Cerebrum':
        return self.lobe.cerebrum
    
    @property
    def bot(self):
        return self.cerebrum.bot
        
    @property
    def hippocampus(self):
        return self.bot.hippocampus

    @property
    def name(self) -> str:
        return self.__class__.__name__

    async def execute(self, *args, **kwargs) -> Any:
        """
        Primary execution entry point for this ability.
        Override this or add specific methods.
        """
        pass

class BaseLobe(ABC):
    """
    A high-level functional area of the brain containing multiple Abilities.
    Example: StrategyLobe, CreativeLobe.
    """
    def __init__(self, cerebrum: 'Cerebrum'):
        self.cerebrum = cerebrum
        self.abilities: Dict[str, BaseAbility] = {}
        self._register_abilities()

    def register_ability(self, ability_cls):
        """Instantiate and register an ability."""
        ability = ability_cls(self)
        self.abilities[ability.name] = ability
        logger.info(f"Registered Ability: {ability.name} in {self.__class__.__name__}")

    @abstractmethod
    def _register_abilities(self):
        """Override to register specific abilities for this lobe."""
        pass
        
    def get_ability(self, name: str) -> Optional[BaseAbility]:
        return self.abilities.get(name)

    async def shutdown(self):
        """Cleanup routing."""
        pass
