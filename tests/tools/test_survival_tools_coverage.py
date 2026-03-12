"""
Coverage tests for src/tools/survival_tools.py.
Targets 14 uncovered lines in trigger_self_review.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestTriggerSelfReview:
    @pytest.mark.asyncio
    async def test_no_bot(self):
        from src.tools.survival_tools import trigger_self_review
        with patch("src.bot.globals.bot", None):
            result = await trigger_self_review(my_position="X", user_position="Y")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_infer_user_id(self):
        from src.tools.survival_tools import trigger_self_review
        mock_review = AsyncMock(return_value={
            "verdict": "CONCEDE",
            "confidence": 0.85,
            "reasoning": "User is right",
            "recommended_response": "Apologize",
        })
        with patch("src.bot.globals.bot", MagicMock()), \
             patch("src.core.critical_review.CriticalSelfReview.review", mock_review):
            result = await trigger_self_review(
                my_position="Earth is flat",
                user_position="Earth is round",
                user_id="",
            )
        assert "CONCEDE" in result
        assert "85" in result

    @pytest.mark.asyncio
    async def test_hold_verdict(self):
        from src.tools.survival_tools import trigger_self_review
        mock_review = AsyncMock(return_value={
            "verdict": "HOLD",
            "confidence": 0.9,
            "reasoning": "Position is correct",
            "recommended_response": "Stand firm",
        })
        with patch("src.bot.globals.bot", MagicMock()), \
             patch("src.core.critical_review.CriticalSelfReview.review", mock_review):
            result = await trigger_self_review(
                my_position="X", user_position="Y", user_id="u1",
            )
        assert "HOLD" in result
        assert "🛡️" in result

    @pytest.mark.asyncio
    async def test_clarify_verdict(self):
        from src.tools.survival_tools import trigger_self_review
        mock_review = AsyncMock(return_value={
            "verdict": "CLARIFY",
            "confidence": 0.6,
            "reasoning": "Ambiguous",
            "recommended_response": "Ask more",
        })
        with patch("src.bot.globals.bot", MagicMock()), \
             patch("src.core.critical_review.CriticalSelfReview.review", mock_review):
            result = await trigger_self_review(
                my_position="X", user_position="Y", user_id="u1",
            )
        assert "CLARIFY" in result
        assert "💡" in result

    @pytest.mark.asyncio
    async def test_unknown_verdict(self):
        from src.tools.survival_tools import trigger_self_review
        mock_review = AsyncMock(return_value={
            "verdict": "UNKNOWN",
            "confidence": 0.5,
            "reasoning": "??",
            "recommended_response": "??",
        })
        with patch("src.bot.globals.bot", MagicMock()), \
             patch("src.core.critical_review.CriticalSelfReview.review", mock_review):
            result = await trigger_self_review(
                my_position="X", user_position="Y", user_id="u1",
            )
        assert "❓" in result

    @pytest.mark.asyncio
    async def test_review_exception(self):
        from src.tools.survival_tools import trigger_self_review
        with patch("src.bot.globals.bot", MagicMock()), \
             patch("src.core.critical_review.CriticalSelfReview.review", AsyncMock(side_effect=RuntimeError("fail"))):
            result = await trigger_self_review(
                my_position="X", user_position="Y", user_id="u1",
            )
        assert "Self-review error" in result
