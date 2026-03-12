"""
Tests for src/agents/aggregator.py — targeting uncovered lines.
Lines: 111-112 (deduplicate replace shorter), 130 (vote fallback),
       157-158 (best_of_n score parse error)
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.aggregator import ResultAggregator


class TestAggregatorCoverageGaps:

    @pytest.mark.asyncio
    async def test_deduplicate_replaces_shorter_with_longer(self):
        """Lines 111-112: When a new result is similar but longer, it replaces the existing one."""
        # 10 shared words. Long adds 2 more → Jaccard = 10/12 ≈ 0.83
        short = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
        long = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        unique = "completely different topic about quantum computing and advanced physics"

        result = await ResultAggregator.synthesize(
            [short, long, unique], strategy="deduplicate"
        )
        # The shorter version should have been replaced by the longer one
        # Check the result has 2 sections (not 3)
        sections = result.split("---")
        assert len(sections) == 2  # unique + long (short removed)
        assert "lambda mu" in result  # long version kept
        assert unique.strip() in result

    @pytest.mark.asyncio
    async def test_vote_fallback_when_no_match(self):
        """Line 130: The fallback when normalized winner doesn't match any result.
        This is technically unreachable normally; force via mock."""
        from collections import Counter
        results = ["Answer A", "Answer B"]
        # Mock Counter.most_common to return a non-matching winner
        with patch.object(Counter, 'most_common', return_value=[("nonexistent", 2)]):
            result = await ResultAggregator.synthesize(results, strategy="vote")
        assert result == "Answer A"  # Falls back to results[0]

    @pytest.mark.asyncio
    async def test_best_of_n_score_parse_error(self):
        """Lines 157-158: When score parsing from LLM output throws an exception."""
        mock_bot = MagicMock()
        mock_engine = MagicMock()
        mock_bot.engine_manager.get_active_engine.return_value = mock_engine

        # Return something where int() parsing raises within the except block
        mock_engine.generate_response.return_value = "no numbers here at all!"

        results = ["Result A is great", "Result B is also great"]
        result = await ResultAggregator.synthesize(
            results, bot=mock_bot, strategy="best_of_n"
        )
        # Should still return a result (defaults to score=5 for both)
        assert result in results

    @pytest.mark.asyncio
    async def test_best_of_n_score_exception_in_extract(self):
        """Lines 157-158: Force the inner except to fire by making re.findall crash."""
        mock_bot = MagicMock()
        mock_engine = MagicMock()
        mock_bot.engine_manager.get_active_engine.return_value = mock_engine
        mock_engine.generate_response.return_value = "7"

        results = ["Result A", "Result B"]

        import re
        original_findall = re.findall

        call_count = [0]
        def crash_findall(pattern, string, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:  # Crash for result scoring calls
                raise ValueError("findall crash")
            return original_findall(pattern, string, *args, **kwargs)

        with patch.object(re, 'findall', side_effect=crash_findall):
            result = await ResultAggregator.synthesize(
                results, bot=mock_bot, strategy="best_of_n"
            )
        # Should fall back to score=5 and still return a result
        assert result in results
