from ..base import BaseLobe
from .identity import IdentityAbility
from .audit import AuditAbility
from .reality import RealityAbility
from .sentinel import SentinelAbility
from .mediator import MediatorAbility

class SuperegoLobe(BaseLobe):
    """
    The Unified Guardian System.
    Combines identity protection, response auditing, reality verification,
    memory hygiene (Sentinel), and knowledge arbitration (Mediator)
    into a cohesive system.
    
    Abilities:
    - IdentityAbility: Protects against narrative drift and God complex
    - AuditAbility: Verifies responses against actual tool outputs
    - RealityAbility: Fact-checks claims against external sources
    - SentinelAbility: Reviews external context imports for sycophancy
    - MediatorAbility: Arbitrates disputes between user claims and CORE knowledge
    """
    def _register_abilities(self):
        self.register_ability(IdentityAbility)
        self.register_ability(AuditAbility)
        self.register_ability(RealityAbility)
        self.register_ability(SentinelAbility)
        self.register_ability(MediatorAbility)
