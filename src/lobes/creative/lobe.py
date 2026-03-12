from ..base import BaseLobe
from .autonomy import AutonomyAbility
from .curiosity import CuriosityAbility
from .artist import VisualCortexAbility
from .ascii_art import ASCIIArtAbility

class CreativeLobe(BaseLobe):
    """
    The Creative Center.
    Autonomy, imagination, and novelty.
    """
    def _register_abilities(self):
        self.register_ability(AutonomyAbility)
        self.register_ability(CuriosityAbility)
        self.register_ability(VisualCortexAbility)
        self.register_ability(ASCIIArtAbility)

