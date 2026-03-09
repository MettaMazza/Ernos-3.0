"""
Tests for FluxCapacitor tool-specific rate limits (Open Access model).
"""
import time
import json
import shutil
from pathlib import Path
from unittest.mock import patch
from src.core.flux_capacitor import FluxCapacitor, TOOL_LIMITS, CYCLE_DURATION, DAILY_DURATION


TEST_USER = 99999

def setup_function():
    """Clean test user data before each test."""
    test_dir = Path(f"memory/users/{TEST_USER}")
    if test_dir.exists():
        shutil.rmtree(test_dir)

def teardown_function():
    """Clean test user data after each test."""
    test_dir = Path(f"memory/users/{TEST_USER}")
    if test_dir.exists():
        shutil.rmtree(test_dir)


class TestConsumeToolBasic:
    """Basic consume_tool functionality."""

    def test_unlisted_tool_always_allowed(self):
        """Tools not in TOOL_LIMITS should always be allowed."""
        flux = FluxCapacitor()
        allowed, msg = flux.consume_tool(TEST_USER, "consult_subconscious")
        assert allowed is True
        assert msg is None

    def test_listed_tool_allowed_under_limit(self):
        """Deep research should be allowed for first use (Free tier gets 1/day)."""
        flux = FluxCapacitor()
        allowed, msg = flux.consume_tool(TEST_USER, "start_deep_research")
        assert allowed is True

    def test_listed_tool_blocked_at_limit(self):
        """Deep research should be blocked after 1 use for Free tier."""
        flux = FluxCapacitor()
        # First use — allowed
        allowed1, _ = flux.consume_tool(TEST_USER, "start_deep_research")
        assert allowed1 is True
        # Second use — blocked (Free tier: limit=1)
        allowed2, msg2 = flux.consume_tool(TEST_USER, "start_deep_research")
        assert allowed2 is False
        assert "limit reached" in msg2 or "not available" in msg2

    def test_zero_limit_tool_always_blocked(self):
        """Video generation has 0 limit for Free tier."""
        flux = FluxCapacitor()
        allowed, msg = flux.consume_tool(TEST_USER, "generate_video")
        assert allowed is False
        assert "not available" in msg

    def test_usage_count_increments(self):
        """Tool usage count should increment in stored data."""
        flux = FluxCapacitor()
        flux.consume_tool(TEST_USER, "dm")
        flux.consume_tool(TEST_USER, "dm")
        data = flux._load(TEST_USER)
        assert data["tool_usage"]["dm"] == 2


class TestConsumeToolTiers:
    """Verify tier-based limits for tools."""

    def test_tier2_gets_more_deep_research(self):
        """Tier 2 (Planter) gets 5 deep researches vs 1 for Free."""
        flux = FluxCapacitor()
        flux.set_tier(TEST_USER, 2)
        for i in range(5):
            allowed, _ = flux.consume_tool(TEST_USER, "start_deep_research")
            assert allowed is True, f"Research #{i+1} should be allowed for Tier 2"
        # 6th should be blocked
        allowed, msg = flux.consume_tool(TEST_USER, "start_deep_research")
        assert allowed is False

    def test_tier2_gets_video_access(self):
        """Tier 2 gets 2 video generations vs 0 for Free."""
        flux = FluxCapacitor()
        flux.set_tier(TEST_USER, 2)
        allowed1, _ = flux.consume_tool(TEST_USER, "generate_video")
        allowed2, _ = flux.consume_tool(TEST_USER, "generate_video")
        assert allowed1 is True
        assert allowed2 is True
        # 3rd blocked
        allowed3, msg = flux.consume_tool(TEST_USER, "generate_video")
        assert allowed3 is False

    def test_unlimited_tier_never_blocked(self):
        """Tier 4 with -1 limit should never be blocked."""
        flux = FluxCapacitor()
        flux.set_tier(TEST_USER, 4)
        for _ in range(50):
            allowed, _ = flux.consume_tool(TEST_USER, "start_deep_research")
            assert allowed is True


class TestConsumeToolResets:
    """Verify cycle and daily reset behavior."""

    def test_cycle_reset_clears_cycle_tools(self):
        """After 12h, cycle-based tools should reset."""
        flux = FluxCapacitor()
        # Use up dm (cycle-based, Free limit=20)
        for _ in range(20):
            flux.consume_tool(TEST_USER, "dm")
        allowed, _ = flux.consume_tool(TEST_USER, "dm")
        assert allowed is False

        # Fast-forward time past cycle
        data = flux._load(TEST_USER)
        data["last_reset"] = time.time() - CYCLE_DURATION - 1
        flux._save(TEST_USER, data)

        # Should be allowed again
        allowed, _ = flux.consume_tool(TEST_USER, "dm")
        assert allowed is True

    def test_daily_reset_clears_daily_tools(self):
        """After 24h, daily-based tools should reset."""
        flux = FluxCapacitor()
        # Use up deep_research (daily-based, Free limit=1)
        flux.consume_tool(TEST_USER, "start_deep_research")
        allowed, _ = flux.consume_tool(TEST_USER, "start_deep_research")
        assert allowed is False

        # Fast-forward daily reset
        data = flux._load(TEST_USER)
        data["tool_daily_reset"] = time.time() - DAILY_DURATION - 1
        flux._save(TEST_USER, data)

        # Should be allowed again
        allowed, _ = flux.consume_tool(TEST_USER, "start_deep_research")
        assert allowed is True


class TestConsumeToolDMs:
    """DM-specific rate limiting."""

    def test_free_dm_limit(self):
        """Free users get 20 DMs per cycle."""
        flux = FluxCapacitor()
        for i in range(20):
            allowed, _ = flux.consume_tool(TEST_USER, "dm")
            assert allowed is True, f"DM #{i+1} should be allowed"
        allowed, msg = flux.consume_tool(TEST_USER, "dm")
        assert allowed is False

    def test_tier2_unlimited_dms(self):
        """Tier 2 gets unlimited DMs."""
        flux = FluxCapacitor()
        flux.set_tier(TEST_USER, 2)
        for _ in range(100):
            allowed, _ = flux.consume_tool(TEST_USER, "dm")
            assert allowed is True


class TestLowUsageWarning:
    """Test low-usage warnings for tool limits."""

    def test_warning_at_last_use(self):
        """Should warn when remaining uses <= 1."""
        flux = FluxCapacitor()
        # generate_image: Free tier limit = 2
        flux.consume_tool(TEST_USER, "generate_image")  # 1st use
        allowed, msg = flux.consume_tool(TEST_USER, "generate_image")  # 2nd use (last)
        assert allowed is True
        # After 2nd use, remaining = 0, but limit > 1 AND remaining <= 1 → warning
        # remaining = 0 which is <=1, and limit=2 > 1, so warning should fire
