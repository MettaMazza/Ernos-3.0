from ..base import BaseLobe
from .researcher import ResearchAbility
from .social import SocialAbility
from .reasoning import DeepReasoningAbility
from .science import ScienceAbility
from .bridge import BridgeAbility

class InteractionLobe(BaseLobe):
    """
    The Interaction Center.
    Manages external world, relationships, and truth.
    """
    def _register_abilities(self):
        self.register_ability(ResearchAbility)
        self.register_ability(SocialAbility)
        self.register_ability(DeepReasoningAbility)
        self.register_ability(ScienceAbility)
        self.register_ability(BridgeAbility)
