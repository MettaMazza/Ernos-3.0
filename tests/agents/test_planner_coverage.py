"""
Tests for src/agents/planner.py — targeting uncovered lines.
Lines targeted: 157-158, 162, 193-194, 201-202, 355
"""

import asyncio
import json
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.planner import (
    ExecutionPlanner, ExecutionPlan, ExecutionStage, PlanStep
)


@pytest.fixture(autouse=True)
def _reset():
    yield


# ─── execute_plan coverage gaps ──────────────────────────────────────────

class TestExecutePlanGaps:

    def _make_plan(self, stages):
        return ExecutionPlan(
            id="test-plan",
            original_request="test request",
            stages=stages
        )

    def _make_agg_result(self, results):
        """Create a mock AggregatedResult."""
        mock = MagicMock()
        mock.results = results
        mock.total_agents = len(results)
        return mock

    def _make_agent_result(self, status="completed", output="result", error=None):
        mock = MagicMock()
        mock.status = MagicMock()
        mock.status.value = status
        mock.output = output
        mock.error = error
        return mock

    @pytest.mark.asyncio
    async def test_progress_callback_error_is_non_fatal(self):
        """Lines 157-158: progress_callback raises during step start."""
        step = PlanStep(id="s1-1", description="test", agent_task="do thing")
        stage = ExecutionStage(stage_number=1, steps=[step], is_parallel=False)
        plan = self._make_plan([stage])

        agent_result = self._make_agent_result("completed", "output")
        agg = self._make_agg_result([agent_result])

        callback = AsyncMock(side_effect=RuntimeError("callback boom"))

        with patch("src.agents.spawner.AgentSpawner") as mock_spawner, \
             patch("src.agents.aggregator.ResultAggregator"):
            mock_spawner.spawn_many = AsyncMock(return_value=agg)
            result = await ExecutionPlanner.execute_plan(
                plan, bot=MagicMock(), progress_callback=callback
            )

        assert result.status == "completed"
        # Callback was called (and failed) but execution continued
        callback.assert_called()

    @pytest.mark.asyncio
    async def test_previous_stage_context_injection(self):
        """Line 162: previous_stage_output is prepended to task_with_context."""
        step1 = PlanStep(id="s1-1", description="research", agent_task="find stuff")
        step2 = PlanStep(id="s2-1", description="synthesize", agent_task="combine")
        stage1 = ExecutionStage(stage_number=1, steps=[step1], is_parallel=False)
        stage2 = ExecutionStage(stage_number=2, steps=[step2], is_parallel=False)
        plan = self._make_plan([stage1, stage2])

        ar1 = self._make_agent_result("completed", "stage 1 findings")
        ar2 = self._make_agent_result("completed", "stage 2 output")
        agg1 = self._make_agg_result([ar1])
        agg2 = self._make_agg_result([ar2])

        call_count = [0]
        async def mock_spawn_many(specs, bot, strategy, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return agg1
            # Check that spec for stage 2 contains stage 1 output
            assert "Previous stage findings" in specs[0].task
            assert "stage 1 findings" in specs[0].task
            return agg2

        with patch("src.agents.spawner.AgentSpawner") as mock_spawner, \
             patch("src.agents.aggregator.ResultAggregator"):
            mock_spawner.spawn_many = AsyncMock(side_effect=mock_spawn_many)
            result = await ExecutionPlanner.execute_plan(plan, bot=MagicMock())

        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_step_with_no_matching_result(self):
        """Lines 193-194: step index >= len(agg_result.results)."""
        step1 = PlanStep(id="s1-1", description="a", agent_task="a")
        step2 = PlanStep(id="s1-2", description="b", agent_task="b")
        stage = ExecutionStage(stage_number=1, steps=[step1, step2], is_parallel=True)
        plan = self._make_plan([stage])

        # Only 1 result for 2 steps → step2 should fail with "no matching result"
        ar1 = self._make_agent_result("completed", "output a")
        agg = self._make_agg_result([ar1])

        with patch("src.agents.spawner.AgentSpawner") as mock_spawner, \
             patch("src.agents.aggregator.ResultAggregator"):
            mock_spawner.spawn_many = AsyncMock(return_value=agg)
            result = await ExecutionPlanner.execute_plan(plan, bot=MagicMock())

        assert step1.status == "completed"
        assert step2.status == "failed"

    @pytest.mark.asyncio
    async def test_completion_emoji_callback(self):
        """Lines 201-202: progress_callback fired with ✅/❌ after step completes."""
        step = PlanStep(id="s1-1", description="test", agent_task="do thing")
        stage = ExecutionStage(stage_number=1, steps=[step], is_parallel=False)
        plan = self._make_plan([stage])

        ar = self._make_agent_result("completed", "output")
        agg = self._make_agg_result([ar])
        callback = AsyncMock()

        with patch("src.agents.spawner.AgentSpawner") as mock_spawner, \
             patch("src.agents.aggregator.ResultAggregator"):
            mock_spawner.spawn_many = AsyncMock(return_value=agg)
            result = await ExecutionPlanner.execute_plan(
                plan, bot=MagicMock(), progress_callback=callback
            )

        # Should have been called with both 🔄 (start) and ✅ (complete)
        calls = [c.args for c in callback.call_args_list]
        emojis = [c[2] for c in calls]
        assert "🔄" in emojis
        assert "✅" in emojis

    @pytest.mark.asyncio
    async def test_failure_emoji_callback(self):
        """Lines 201-202: progress_callback fired with ❌ on failed step."""
        step = PlanStep(id="s1-1", description="test", agent_task="do thing")
        stage = ExecutionStage(stage_number=1, steps=[step], is_parallel=False)
        plan = self._make_plan([stage])

        ar = self._make_agent_result("failed", "", error="oops")
        agg = self._make_agg_result([ar])
        callback = AsyncMock()

        with patch("src.agents.spawner.AgentSpawner") as mock_spawner, \
             patch("src.agents.aggregator.ResultAggregator"):
            mock_spawner.spawn_many = AsyncMock(return_value=agg)
            result = await ExecutionPlanner.execute_plan(
                plan, bot=MagicMock(), progress_callback=callback
            )

        calls = [c.args for c in callback.call_args_list]
        emojis = [c[2] for c in calls]
        assert "❌" in emojis

    @pytest.mark.asyncio
    async def test_completion_callback_error_non_fatal(self):
        """Lines 201-202: progress_callback error on completion is non-fatal."""
        step = PlanStep(id="s1-1", description="test", agent_task="do thing")
        stage = ExecutionStage(stage_number=1, steps=[step], is_parallel=False)
        plan = self._make_plan([stage])

        ar = self._make_agent_result("completed", "output")
        agg = self._make_agg_result([ar])

        call_count = [0]
        async def callback(*args):
            call_count[0] += 1
            if call_count[0] == 2:  # Fail on the completion callback
                raise RuntimeError("completion callback boom")

        with patch("src.agents.spawner.AgentSpawner") as mock_spawner, \
             patch("src.agents.aggregator.ResultAggregator"):
            mock_spawner.spawn_many = AsyncMock(return_value=agg)
            result = await ExecutionPlanner.execute_plan(
                plan, bot=MagicMock(), progress_callback=callback
            )

        assert result.status == "completed"


# ─── _parse_plan_response coverage gaps ──────────────────────────────────

class TestParsePlanResponseGaps:

    def test_parsed_json_with_empty_tasks_yields_no_stages(self):
        """Line 355: Parsed JSON with stages but all have empty tasks → 0 stages logged."""
        response = json.dumps({
            "stages": [
                {"stage": 1, "parallel": True, "tasks": []}
            ]
        })
        stages = ExecutionPlanner._parse_plan_response(response)
        # All stages had empty tasks, so no valid stages
        assert len(stages) == 0
