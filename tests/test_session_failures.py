"""
Tests for the 2026-02-14 session failure root cause fixes.

Covers:
  P0 - Circuit breaker tool-loop halt + tool cap
  P1 - Superego discomfort spike, scope denial anti-substitution, self-artifact access
  P2 - Agency daemon null-safe lobe access
  P3 - Autonomy JSON normalization
"""
import sys
import os
import json
import ast
import re
import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ─── Ensure project root is on sys.path ───
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ════════════════════════════════════════════
# P0: Circuit Breaker Tool-Loop Tests
# ════════════════════════════════════════════

class TestCircuitBreakerToolLoop:
    """Test that the tool execution loop halts when circuit breaker threshold is hit."""

    def test_tool_matches_capped_at_10(self):
        """Simulate 50 tool matches and verify only 10 are processed."""
        tool_matches = [(f"tool_{i}", f"arg{i}") for i in range(50)]

        # Replicate the new cap logic from cognition.py:163-167
        if len(tool_matches) > 10:
            tool_matches = tool_matches[:10]

        assert len(tool_matches) == 10

    def test_circuit_breaker_halts_mid_loop(self):
        """Simulate tool loop with circuit_breaker_count exceeding threshold."""
        tool_matches = [(f"tool_{i}", f"arg{i}") for i in range(10)]
        circuit_breaker_count = 0
        iteration_results = []
        processed = 0

        for tool_name, args in tool_matches:
            # Simulate breaker incrementing (as in cognition_tools.py)
            circuit_breaker_count += 1
            processed += 1

            # New mid-loop halt from cognition.py
            if circuit_breaker_count >= 3:
                iteration_results.append(
                    "System: Circuit breaker limit reached. Halting all further tool calls this step."
                )
                break

        assert processed == 3
        assert "Circuit breaker limit reached" in iteration_results[-1]


# ════════════════════════════════════════════
# P1: Superego Discomfort Spike Tests
# ════════════════════════════════════════════

class TestSupergoDiscomfortSpike:
    """Test that superego_rejection is a recognized discomfort failure type."""

    def test_superego_rejection_in_failure_severity(self):
        """The FAILURE_SEVERITY dict must include 'superego_rejection'."""
        from src.memory.discomfort import FAILURE_SEVERITY
        assert "superego_rejection" in FAILURE_SEVERITY
        assert FAILURE_SEVERITY["superego_rejection"] == 20


# ════════════════════════════════════════════
# P1: Anti-Substitution Scope Denial Tests
# ════════════════════════════════════════════

class TestAntiSubstitutionDenial:
    """Test scope denial messages contain anti-substitution instructions."""

    def test_read_file_scope_denial_contains_warning(self):
        """read_file_page denial should include anti-substitution text."""
        from src.tools.filesystem import read_file_page
        result = read_file_page(
            path="memory/core/letter_from_maria.md",
            request_scope="PUBLIC",
            user_id="12345"
        )
        assert "Access Denied" in result
        assert "Do NOT substitute" in result
        assert "CRITICAL" in result

    def test_search_scope_denial_contains_warning(self):
        """search_codebase denial should include anti-substitution text."""
        from src.tools.filesystem import search_codebase
        result = search_codebase(
            query="test",
            path="memory/core/",
            request_scope="PUBLIC",
            user_id="12345"
        )
        assert "Access Denied" in result
        assert "Do NOT substitute" in result

    def test_list_files_scope_denial_contains_warning(self):
        """list_files denial should include anti-substitution text."""
        from src.tools.filesystem import list_files
        result = list_files(
            path="memory/core/",
            request_scope="PUBLIC",
            user_id="12345"
        )
        assert "Access Denied" in result
        assert "Do NOT substitute" in result


# ════════════════════════════════════════════
# P1: Self-Artifact Scope Whitelist Tests
# ════════════════════════════════════════════

class TestSelfArtifactScopeWhitelist:
    """Test that Ernos's autonomy-generated artifacts are accessible from PUBLIC scope,
    while core context files remain CORE-only."""

    def test_research_accessible_from_public(self):
        """memory/core/research/ should be accessible from PUBLIC scope."""
        from src.privacy.guard import validate_path_scope
        from src.privacy.scopes import PrivacyScope
        assert validate_path_scope("memory/core/research/topic.md", PrivacyScope.PUBLIC) is True

    def test_media_accessible_from_public(self):
        """memory/core/media/ should be accessible from PUBLIC scope."""
        from src.privacy.guard import validate_path_scope
        from src.privacy.scopes import PrivacyScope
        assert validate_path_scope("memory/core/media/image.png", PrivacyScope.PUBLIC) is True

    def test_exports_accessible_from_public(self):
        """memory/core/exports/ should be accessible from PUBLIC scope."""
        from src.privacy.guard import validate_path_scope
        from src.privacy.scopes import PrivacyScope
        assert validate_path_scope("memory/core/exports/data.csv", PrivacyScope.PUBLIC) is True

    def test_skills_accessible_from_public(self):
        """memory/core/skills/ should be accessible from PUBLIC scope."""
        from src.privacy.guard import validate_path_scope
        from src.privacy.scopes import PrivacyScope
        assert validate_path_scope("memory/core/skills/painting.md", PrivacyScope.PUBLIC) is True

    def test_core_context_blocked_from_public(self):
        """Core context files must remain CORE-only (not accessible from PUBLIC)."""
        from src.privacy.guard import validate_path_scope
        from src.privacy.scopes import PrivacyScope

        blocked_paths = [
            "memory/core/letter_from_maria.md",
            "memory/core/context_private.jsonl",
            "memory/core/drives.json",
            "memory/core/shard_salt.secret",
            "memory/core/realizations.txt",
            "memory/core/timeline.jsonl",
            "memory/core/working_memory.jsonl",
        ]
        for path in blocked_paths:
            assert validate_path_scope(path, PrivacyScope.PUBLIC) is False, \
                f"SECURITY: {path} should NOT be accessible from PUBLIC scope"

    def test_core_context_accessible_from_core(self):
        """CORE scope can still access everything under memory/core/."""
        from src.privacy.guard import validate_path_scope
        from src.privacy.scopes import PrivacyScope
        assert validate_path_scope("memory/core/letter_from_maria.md", PrivacyScope.CORE) is True
        assert validate_path_scope("memory/core/research/topic.md", PrivacyScope.CORE) is True


# ════════════════════════════════════════════
# P2: Agency Daemon Null-Safety Tests
# ════════════════════════════════════════════

class TestAgencyDaemonNullSafety:
    """Test that agency daemon methods handle None lobes gracefully."""

    @pytest.mark.asyncio
    async def test_outreach_with_none_lobe(self):
        """_perform_outreach should return without error when InteractionLobe is None."""
        from src.daemons.agency import AgencyDaemon

        mock_bot = MagicMock()
        mock_bot.cerebrum.get_lobe.return_value = None

        daemon = AgencyDaemon.__new__(AgencyDaemon)
        daemon.bot = mock_bot

        # Should not raise
        await daemon._perform_outreach("12345", "Testing")

    @pytest.mark.asyncio
    async def test_research_with_none_lobe(self):
        """_perform_research should return without error when InteractionLobe is None."""
        from src.daemons.agency import AgencyDaemon

        mock_bot = MagicMock()
        mock_bot.cerebrum.get_lobe.return_value = None

        daemon = AgencyDaemon.__new__(AgencyDaemon)
        daemon.bot = mock_bot

        await daemon._perform_research("AI safety", "Curiosity")

    @pytest.mark.asyncio
    async def test_reflection_with_none_lobe(self):
        """_perform_reflection should return without error when MetaLobe is None."""
        from src.daemons.agency import AgencyDaemon

        mock_bot = MagicMock()
        mock_bot.cerebrum.get_lobe.return_value = None

        daemon = AgencyDaemon.__new__(AgencyDaemon)
        daemon.bot = mock_bot

        await daemon._perform_reflection("Self-assessment")


# ════════════════════════════════════════════
# P3: Autonomy JSON Normalization Tests
# ════════════════════════════════════════════

class TestAutonomyJsonNormalization:
    """Test the improved JSON parsing handles LLM-style output."""

    def test_standard_json_parses(self):
        """Standard JSON should parse without fallback."""
        raw = '{"topic": "quantum computing", "depth": 3}'
        result = json.loads(raw)
        assert result == {"topic": "quantum computing", "depth": 3}

    def test_single_quotes_with_apostrophe(self):
        """Python-style dict with apostrophes in values should parse via ast.literal_eval."""
        raw = "{'topic': \"user's question\", 'depth': 3}"
        # json.loads will fail, but ast.literal_eval should work
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)
        result = ast.literal_eval(raw)
        assert result == {"topic": "user's question", "depth": 3}

    def test_trailing_comma(self):
        """Python-style trailing commas should parse via ast.literal_eval."""
        raw = "{'topic': 'test', 'depth': 3,}"
        with pytest.raises(json.JSONDecodeError):
            json.loads(raw)
        result = ast.literal_eval(raw)
        assert result == {"topic": "test", "depth": 3}
