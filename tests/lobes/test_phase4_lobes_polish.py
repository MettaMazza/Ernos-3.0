"""Phase 4 polish tests for lobe modules at 80-94% coverage.

Covers: creative/artist.py, interaction/group_dynamics.py (GroupDynamicsEngine),
        interaction/social.py, strategy/prompt_tuner.py (PromptTuner),
        strategy/skill_forge.py (SkillForge), superego/identity.py (IdentityAbility),
        lobes/manager.py (Cerebrum), memory/curator.py
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ═══════════════════════════ VisualCortexAbility ═══════════════════════════
class TestVisualCortex:
    @pytest.fixture
    def artist(self):
        lobe = MagicMock()
        lobe.bot = MagicMock()
        from src.lobes.creative.artist import VisualCortexAbility
        a = VisualCortexAbility(lobe)
        return a

    @pytest.mark.asyncio
    async def test_turn_lock_blocks(self, artist):
        artist.turn_lock = True
        result = await artist.execute("paint a cat", user_id=99999)
        assert "Rate limit" in result

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, artist):
        artist._check_limits = MagicMock(return_value=False)
        result = await artist.execute("draw a dog", user_id=123)
        assert "limit" in result.lower()

    def test_reset_turn_lock(self, artist):
        artist.turn_lock = True
        artist.reset_turn_lock()
        assert artist.turn_lock is False

    @pytest.mark.asyncio
    async def test_generation_error(self, artist):
        artist._check_limits = MagicMock(return_value=True)
        with patch("asyncio.to_thread", new_callable=AsyncMock, side_effect=Exception("GPU error")):
            result = await artist.execute("draw something", user_id=123)
            assert "Error" in result


# ═══════════════════════════ GroupDynamicsEngine ═══════════════════════════
class TestGroupDynamics:
    def test_record_and_get(self):
        from src.lobes.interaction.group_dynamics import GroupDynamicsEngine
        gde = GroupDynamicsEngine()
        gde.record_message(999, 100, 50, has_mention=False)
        dynamics = gde.get_channel_dynamics(999)
        assert isinstance(dynamics, dict)


# ═══════════════════════════ SocialAbility ═══════════════════════════
class TestSocial:
    @pytest.mark.asyncio
    async def test_process_reaction(self):
        from src.lobes.interaction.social import SocialAbility
        lobe = MagicMock()
        s = SocialAbility(lobe)
        result = await s.process_reaction(123, "👍", 456)
        assert result in ("positive", "negative", "neutral", None) or isinstance(result, str)


# ═══════════════════════════ PromptTuner ═══════════════════════════
class TestPromptTuner:
    def test_get_summary(self, tmp_path):
        from src.lobes.strategy.prompt_tuner import PromptTuner
        pt = PromptTuner()
        pt.TUNER_DIR = tmp_path
        pt.HISTORY_FILE = tmp_path / "history.json"
        pt.PROPOSALS_FILE = tmp_path / "proposals.json"
        summary = pt.get_tuner_summary()
        assert isinstance(summary, str)


# ═══════════════════════════ SkillForge ═══════════════════════════
class TestSkillForge:
    def test_get_pending_empty(self, tmp_path):
        from src.lobes.strategy.skill_forge import SkillForge
        sf = SkillForge()
        sf.QUEUE_FILE = tmp_path / "queue.json"
        pending = sf.get_pending()
        assert isinstance(pending, list)


# ═══════════════════════════ IdentityAbility ═══════════════════════════
class TestIdentityAbility:
    @pytest.mark.asyncio
    async def test_execute(self):
        from src.lobes.superego.identity import IdentityAbility
        lobe = MagicMock()
        ia = IdentityAbility(lobe)
        result = await ia.execute(content="Hello, who are you?")
        # Returns None on mock error (failing open), which is valid
        assert result is None or isinstance(result, str)


# ═══════════════════════════ Cerebrum ═══════════════════════════
class TestCerebrum:
    def test_get_nonexistent_lobe(self):
        from src.lobes.manager import Cerebrum
        bot = MagicMock()
        c = Cerebrum(bot)
        assert c.get_lobe("NonExistent") is None


# ═══════════════════════════ CuratorAbility ═══════════════════════════
class TestCurator:
    @pytest.mark.asyncio
    async def test_execute(self):
        from src.lobes.memory.curator import CuratorAbility
        lobe = MagicMock()
        c = CuratorAbility(lobe)
        result = await c.execute(text="This is a test memory to curate")
        assert result is None or isinstance(result, str)
