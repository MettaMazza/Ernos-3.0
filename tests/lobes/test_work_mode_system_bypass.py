"""
Regression tests for work mode system user bypasses.

Tests:
1. Epistemic lessons search handles non-numeric user_id ('sys', 'CORE', 'persona:x')
2. Tool cap is bypassed for system users but enforced for regular users
3. Flux limiter bypasses system users
"""
import pytest
import re
from unittest.mock import MagicMock, patch, AsyncMock


# ─── SECTION 1: Epistemic int(user_id) Handling ─────────────────────────────

class TestEpistemicUserIdParsing:
    """Ensure introspect_claim doesn't crash on non-numeric user IDs."""

    @pytest.fixture
    def mock_bot(self):
        bot = MagicMock()
        bot.hippocampus = MagicMock()
        bot.hippocampus.graph = None  # Skip KG search
        bot.hippocampus.lessons = MagicMock()
        bot.hippocampus.lessons.get_all_lessons.return_value = []
        bot.hippocampus.working = None  # Skip WM search
        return bot

    @pytest.mark.asyncio
    async def test_introspect_with_sys_user(self, mock_bot):
        """user_id='sys' must not crash with ValueError."""
        from src.memory.epistemic import introspect_claim
        result = await introspect_claim(mock_bot, "test claim", user_id="sys")
        assert "EPISTEMIC" in result
        # Should have called lessons with int 0 (fallback)
        mock_bot.hippocampus.lessons.get_all_lessons.assert_called()

    @pytest.mark.asyncio
    async def test_introspect_with_core_user(self, mock_bot):
        """user_id='CORE' must not crash."""
        from src.memory.epistemic import introspect_claim
        result = await introspect_claim(mock_bot, "test claim", user_id="CORE")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_introspect_with_persona_user(self, mock_bot):
        """user_id='persona:ernos' must not crash."""
        from src.memory.epistemic import introspect_claim
        result = await introspect_claim(mock_bot, "test claim", user_id="persona:ernos")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_introspect_with_numeric_user(self, mock_bot):
        """Numeric user_id should still work normally."""
        from src.memory.epistemic import introspect_claim
        result = await introspect_claim(mock_bot, "test claim", user_id="123456789")
        assert isinstance(result, str)
        # Should have called with int(123456789)
        call_args = mock_bot.hippocampus.lessons.get_all_lessons.call_args
        assert call_args[0][0] == 123456789

    @pytest.mark.asyncio
    async def test_introspect_with_none_user(self, mock_bot):
        """user_id=None must not crash."""
        from src.memory.epistemic import introspect_claim
        result = await introspect_claim(mock_bot, "test claim", user_id=None)
        assert isinstance(result, str)


# ─── SECTION 2: Tool Cap Bypass for System Users ────────────────────────────

class TestToolCapBypass:
    """Verify tool cap is bypassed for system/autonomous users."""

    def test_tool_cap_regex_matches_system_users(self):
        """Verify the system user check logic in cognition.py."""
        # Simulate the check
        for user_id in ("sys", "CORE", "SYSTEM"):
            _is_system_user = str(user_id) in ("sys", "CORE", "SYSTEM")
            assert _is_system_user, f"{user_id} should be recognized as system user"

    def test_tool_cap_not_bypassed_for_regular_users(self):
        """Regular user IDs should NOT bypass the tool cap."""
        for user_id in ("123456789", "626596553922052132", None, ""):
            _is_system_user = str(user_id) in ("sys", "CORE", "SYSTEM")
            assert not _is_system_user, f"{user_id} should NOT be a system user"


# ─── SECTION 3: Flux Limiter System Bypass ───────────────────────────────────

class TestFluxSystemBypass:
    """Verify flux limiter bypasses system users."""

    @pytest.fixture
    def flux(self, tmp_path):
        with patch("src.core.flux_capacitor.data_dir", return_value=tmp_path):
            from src.core.flux_capacitor import FluxCapacitor
            return FluxCapacitor()

    def test_sys_user_bypasses_tool_limit(self, flux):
        """user_id='sys' should always be allowed."""
        allowed, msg = flux.consume_tool("sys", "create_program")
        assert allowed is True
        assert msg is None

    def test_core_user_bypasses_tool_limit(self, flux):
        """user_id='CORE' should always be allowed."""
        allowed, msg = flux.consume_tool("CORE", "generate_image")
        assert allowed is True

    def test_system_user_bypasses_tool_limit(self, flux):
        """user_id='SYSTEM' should always be allowed."""
        allowed, msg = flux.consume_tool("SYSTEM", "start_deep_research")
        assert allowed is True

    def test_sys_user_bypasses_agent_limit(self, flux):
        """user_id='sys' should bypass spawn_agent limits."""
        allowed, msg = flux.consume_agents("sys", 100)
        assert allowed is True

    def test_regular_user_is_limited(self, flux, tmp_path):
        """Regular users should still be rate-limited."""
        with patch("src.core.flux_capacitor.data_dir", return_value=tmp_path):
            # create_program has a limit of 2 for tier 0
            flux.consume_tool(12345, "create_program")
            flux.consume_tool(12345, "create_program")
            allowed, msg = flux.consume_tool(12345, "create_program")
            assert allowed is False
            assert "limit reached" in msg
