from ..base import BaseLobe
from .architect import ArchitectAbility
from .project import ProjectLeadAbility
from .goal import GoalAbility
from .performance import PerformanceAbility
from .gardener import GardenerAbility
from .predictor import PredictorAbility
from .coder import CoderAbility
from .prompt_tuner import PromptTunerAbility

class StrategyLobe(BaseLobe):
    """
    The Strategic Center.
    Handles planning, code understanding, and long-term goals.
    """
    def _register_abilities(self):
        self.register_ability(ArchitectAbility)
        self.register_ability(ProjectLeadAbility)
        self.register_ability(GoalAbility)
        self.register_ability(PerformanceAbility)
        self.register_ability(GardenerAbility)
        self.register_ability(PredictorAbility)
        self.register_ability(CoderAbility)
        self.register_ability(PromptTunerAbility)

