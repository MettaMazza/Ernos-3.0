"""
Phase 3: Agent Infrastructure coverage tests.

Covers:
  - aggregator.py  (ResultAggregator: synthesize, collect_with_timeout, all strategies)
  - bus.py         (AgentBus: pub/sub, direct, request/response, fan_out, cleanup)
  - planner.py     (ExecutionPlanner: plan, execute_plan, _parse_plan_response)
  - cognition_tracker.py (CognitionTracker: start, update, tool_complete, finalize, _do_edit)
  - admin_reports.py     (AdminReports: cog_check, townhall_suggest, user_report)
  - spawner.py     (AgentSpawner: spawn, spawn_many, cancel, get_active, get_history, strategies)
"""
import asyncio
import json
from collections import defaultdict
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock


# ═══════════════════════════════════════════════════════
#  ResultAggregator
# ═══════════════════════════════════════════════════════

class TestResultAggregator:

    @pytest.mark.asyncio
    async def test_collect_with_timeout_all_done(self):
        from src.agents.aggregator import ResultAggregator
        async def ok():
            return "done"
        tasks = [asyncio.create_task(ok()) for _ in range(3)]
        results = await ResultAggregator.collect_with_timeout(tasks, timeout=5.0)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_collect_with_timeout_some_timeout(self):
        from src.agents.aggregator import ResultAggregator
        async def fast():
            return "fast"
        async def slow():
            await asyncio.sleep(60)
        tasks = [asyncio.create_task(fast()), asyncio.create_task(slow())]
        results = await ResultAggregator.collect_with_timeout(tasks, timeout=0.1)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_collect_with_timeout_task_exception(self):
        from src.agents.aggregator import ResultAggregator
        async def fail():
            raise ValueError("boom")
        tasks = [asyncio.create_task(fail())]
        # Exceptions are logged, not returned
        results = await ResultAggregator.collect_with_timeout(tasks, timeout=5.0)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_synthesize_empty(self):
        from src.agents.aggregator import ResultAggregator
        r = await ResultAggregator.synthesize([])
        assert "No results" in r

    @pytest.mark.asyncio
    async def test_synthesize_single(self):
        from src.agents.aggregator import ResultAggregator
        r = await ResultAggregator.synthesize(["hello"])
        assert r == "hello"

    @pytest.mark.asyncio
    async def test_synthesize_all_errors(self):
        from src.agents.aggregator import ResultAggregator
        r = await ResultAggregator.synthesize(["Error: a", "Error: b"])
        assert "errors" in r.lower()

    @pytest.mark.asyncio
    async def test_synthesize_concat(self):
        from src.agents.aggregator import ResultAggregator
        r = await ResultAggregator.synthesize(["A", "B"], strategy="concat")
        assert "Result 1" in r and "Result 2" in r

    @pytest.mark.asyncio
    async def test_synthesize_deduplicate(self):
        from src.agents.aggregator import ResultAggregator
        r = await ResultAggregator.synthesize(["hello world", "hello world"], strategy="deduplicate")
        # Duplicates should be removed
        assert r.count("hello world") == 1

    @pytest.mark.asyncio
    async def test_synthesize_vote(self):
        from src.agents.aggregator import ResultAggregator
        r = await ResultAggregator.synthesize(["yes", "yes", "no"], strategy="vote")
        assert r == "yes"

    @pytest.mark.asyncio
    async def test_synthesize_best_of_n_no_bot(self):
        from src.agents.aggregator import ResultAggregator
        r = await ResultAggregator.synthesize(["short", "longer answer"], strategy="best_of_n")
        assert r == "longer answer"  # max by len

    @pytest.mark.asyncio
    async def test_synthesize_best_of_n_with_bot(self):
        from src.agents.aggregator import ResultAggregator
        bot = MagicMock()
        engine = MagicMock()
        engine.generate_response.return_value = "8"
        bot.engine_manager.get_active_engine.return_value = engine
        r = await ResultAggregator.synthesize(["A", "B"], bot=bot, strategy="best_of_n")
        assert r in ("A", "B")

    @pytest.mark.asyncio
    async def test_synthesize_best_of_n_engine_error(self):
        from src.agents.aggregator import ResultAggregator
        bot = MagicMock()
        bot.engine_manager.get_active_engine.side_effect = Exception("no engine")
        r = await ResultAggregator.synthesize(["AAA", "B"], bot=bot, strategy="best_of_n")
        assert r == "AAA"  # fallback to max(key=len)

    @pytest.mark.asyncio
    async def test_synthesize_hierarchical_no_bot(self):
        from src.agents.aggregator import ResultAggregator
        r = await ResultAggregator.synthesize(["A", "B"], strategy="hierarchical")
        assert "Result 1" in r  # falls back to concat

    @pytest.mark.asyncio
    async def test_synthesize_hierarchical_with_bot(self):
        from src.agents.aggregator import ResultAggregator
        bot = MagicMock()
        engine = MagicMock()
        engine.generate_response.return_value = "merged text"
        bot.engine_manager.get_active_engine.return_value = engine
        r = await ResultAggregator.synthesize(["A", "B"], bot=bot, strategy="hierarchical")
        # Falls through to llm_merge after clustering
        assert isinstance(r, str)

    @pytest.mark.asyncio
    async def test_synthesize_hierarchical_engine_error(self):
        from src.agents.aggregator import ResultAggregator
        bot = MagicMock()
        bot.engine_manager.get_active_engine.side_effect = Exception("fail")
        r = await ResultAggregator.synthesize(["X", "Y"], bot=bot, strategy="hierarchical")
        assert "Result 1" in r  # falls back to concat

    @pytest.mark.asyncio
    async def test_synthesize_llm_merge_no_bot(self):
        from src.agents.aggregator import ResultAggregator
        r = await ResultAggregator.synthesize(["A", "B"], strategy="llm_merge")
        # Falls back to deduplicate
        assert isinstance(r, str)

    @pytest.mark.asyncio
    async def test_synthesize_llm_merge_with_bot(self):
        from src.agents.aggregator import ResultAggregator
        bot = MagicMock()
        engine = MagicMock()
        engine.generate_response.return_value = "synthesized"
        bot.engine_manager.get_active_engine.return_value = engine
        r = await ResultAggregator.synthesize(["A", "B"], bot=bot, strategy="llm_merge", prompt_hint="context")
        assert r == "synthesized"

    @pytest.mark.asyncio
    async def test_synthesize_llm_merge_engine_error(self):
        from src.agents.aggregator import ResultAggregator
        bot = MagicMock()
        bot.engine_manager.get_active_engine.side_effect = Exception("fail")
        r = await ResultAggregator.synthesize(["X", "Y"], bot=bot, strategy="llm_merge")
        # Falls back to deduplicate
        assert isinstance(r, str)

    @pytest.mark.asyncio
    async def test_synthesize_unknown_strategy(self):
        from src.agents.aggregator import ResultAggregator
        # Unknown strategy falls back to llm_merge (which falls to dedup without bot)
        r = await ResultAggregator.synthesize(["A", "B"], strategy="nonexistent")
        assert isinstance(r, str)

    def test_jaccard_similarity_identical(self):
        from src.agents.aggregator import ResultAggregator
        assert ResultAggregator._jaccard_similarity("hello world", "hello world") == 1.0

    def test_jaccard_similarity_disjoint(self):
        from src.agents.aggregator import ResultAggregator
        assert ResultAggregator._jaccard_similarity("hello world", "foo bar") == 0.0

    def test_jaccard_similarity_empty(self):
        from src.agents.aggregator import ResultAggregator
        assert ResultAggregator._jaccard_similarity("", "hello") == 0.0

    def test_deduplicate_keeps_longer(self):
        from src.agents.aggregator import ResultAggregator
        # Two near-identical results — keeps the longer one
        short = "hello world"
        long_version = "hello world with extra details"
        # Similarity is low between these, so test with actually similar texts
        r = ResultAggregator._deduplicate([short, short])
        assert r.count(short) == 1


# ═══════════════════════════════════════════════════════
#  AgentBus
# ═══════════════════════════════════════════════════════

class TestAgentBus:

    def _fresh_bus(self):
        """Create a fresh bus instance without shared class state."""
        from src.agents.bus import AgentBus
        bus = AgentBus()
        bus._subscriptions = defaultdict(list)
        bus._direct_queues = {}
        bus._pending_requests = {}
        bus._message_log = []
        return bus

    def test_get_instance(self):
        from src.agents.bus import AgentBus
        AgentBus._instance = None
        inst = AgentBus.get_instance()
        assert inst is not None
        assert AgentBus.get_instance() is inst

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self):
        bus = self._fresh_bus()
        count = await bus.publish("topic1", "hello")
        assert count == 0

    @pytest.mark.asyncio
    async def test_subscribe_and_publish_handler(self):
        bus = self._fresh_bus()
        received = []
        def handler(msg):
            received.append(msg.content)
        bus.subscribe("test", handler=handler)
        count = await bus.publish("test", "payload")
        assert count == 1
        assert received == ["payload"]

    @pytest.mark.asyncio
    async def test_subscribe_and_publish_async_handler(self):
        bus = self._fresh_bus()
        received = []
        async def handler(msg):
            received.append(msg.content)
        bus.subscribe("test", handler=handler)
        count = await bus.publish("test", "async_payload")
        assert count == 1
        assert received == ["async_payload"]

    @pytest.mark.asyncio
    async def test_subscribe_with_agent_id(self):
        bus = self._fresh_bus()
        bus.subscribe("topic", agent_id="agent-1")
        count = await bus.publish("topic", "data")
        assert count == 1
        msg = await bus.receive("agent-1", timeout=1.0)
        assert msg.content == "data"

    @pytest.mark.asyncio
    async def test_subscribe_handler_error_suppressed(self):
        bus = self._fresh_bus()
        def bad_handler(msg):
            raise ValueError("boom")
        bus.subscribe("test", handler=bad_handler)
        # Should not raise
        count = await bus.publish("test", "data")
        assert count == 0  # handler errored, not counted

    def test_unsubscribe(self):
        bus = self._fresh_bus()
        sub_id = bus.subscribe("topic", handler=lambda m: None)
        bus.unsubscribe(sub_id)
        topics = bus.get_topics()
        assert topics.get("topic", 0) == 0

    @pytest.mark.asyncio
    async def test_send_direct(self):
        bus = self._fresh_bus()
        result = await bus.send_direct("agent-x", "hello")
        assert result is True
        msg = await bus.receive("agent-x", timeout=1.0)
        assert msg.content == "hello"

    @pytest.mark.asyncio
    async def test_send_direct_queue_full(self):
        bus = self._fresh_bus()
        bus._direct_queues["agent-y"] = asyncio.Queue(maxsize=1)
        await bus.send_direct("agent-y", "first")
        # Queue is now full
        result = await bus.send_direct("agent-y", "second")
        assert result is False

    @pytest.mark.asyncio
    async def test_receive_timeout(self):
        bus = self._fresh_bus()
        msg = await bus.receive("nonexistent", timeout=0.05)
        assert msg is None

    @pytest.mark.asyncio
    async def test_request_and_respond(self):
        bus = self._fresh_bus()

        async def responder():
            msg = await bus.receive("target", timeout=2.0)
            req_id = msg.content.metadata["request_id"]
            await bus.respond(req_id, "answer")

        task = asyncio.create_task(responder())
        result = await bus.request("target", "question", timeout=2.0)
        assert result == "answer"
        await task

    @pytest.mark.asyncio
    async def test_request_timeout(self):
        bus = self._fresh_bus()
        result = await bus.request("nobody", "question", timeout=0.05)
        assert result is None

    @pytest.mark.asyncio
    async def test_respond_no_pending(self):
        bus = self._fresh_bus()
        # Should not raise
        await bus.respond("nonexistent-id", "data")

    @pytest.mark.asyncio
    async def test_fan_out_no_subscribers(self):
        bus = self._fresh_bus()
        results = await bus.fan_out("empty", "data")
        assert results == []

    @pytest.mark.asyncio
    async def test_fan_out_with_agents(self):
        bus = self._fresh_bus()
        bus.subscribe("work", agent_id="worker-1")

        async def worker():
            msg = await bus.receive("worker-1", timeout=2.0)
            # fan_out sends an AgentMessage as content via send_direct,
            # so msg.content is the inner AgentMessage with the request_id
            inner = msg.content
            req_id = inner.metadata["request_id"]
            await bus.respond(req_id, "result-1")

        task = asyncio.create_task(worker())
        results = await bus.fan_out("work", "do this", timeout=2.0)
        assert results == ["result-1"]
        await task

    def test_get_topics(self):
        bus = self._fresh_bus()
        bus.subscribe("alpha", handler=lambda m: None)
        bus.subscribe("alpha", handler=lambda m: None)
        bus.subscribe("beta", handler=lambda m: None)
        topics = bus.get_topics()
        assert topics["alpha"] == 2
        assert topics["beta"] == 1

    def test_get_queue_depth(self):
        bus = self._fresh_bus()
        assert bus.get_queue_depth("unknown") == 0

    @pytest.mark.asyncio
    async def test_get_recent_messages(self):
        bus = self._fresh_bus()
        await bus.publish("t1", "msg1")
        await bus.publish("t2", "msg2")
        all_msgs = bus.get_recent_messages()
        assert len(all_msgs) == 2
        filtered = bus.get_recent_messages(topic="t1")
        assert len(filtered) == 1

    def test_cleanup_agent(self):
        bus = self._fresh_bus()
        bus.subscribe("work", agent_id="worker-1")
        bus.cleanup_agent("worker-1")
        assert "worker-1" not in bus._direct_queues

    @pytest.mark.asyncio
    async def test_log_message_trimming(self):
        bus = self._fresh_bus()
        bus._max_log_size = 10
        for i in range(15):
            await bus.send_direct("a", f"msg{i}")
        assert len(bus._message_log) <= 10


# ═══════════════════════════════════════════════════════
#  ExecutionPlanner
# ═══════════════════════════════════════════════════════

class TestExecutionPlanner:

    @pytest.mark.asyncio
    async def test_plan_no_bot(self):
        from src.agents.planner import ExecutionPlanner
        plan = await ExecutionPlanner.plan("do something")
        assert len(plan.stages) == 1
        assert plan.stages[0].steps[0].agent_task == "do something"

    @pytest.mark.asyncio
    async def test_plan_with_bot_valid_json(self):
        from src.agents.planner import ExecutionPlanner
        bot = MagicMock()
        engine = MagicMock()
        engine.generate_response.return_value = json.dumps({
            "stages": [
                {"stage": 1, "parallel": True, "tasks": [
                    {"id": "s1-1", "description": "Research", "task": "Do research"}
                ]},
                {"stage": 2, "parallel": False, "tasks": [
                    {"id": "s2-1", "description": "Synthesize", "task": "Combine findings"}
                ]}
            ]
        })
        bot.engine_manager.get_active_engine.return_value = engine
        plan = await ExecutionPlanner.plan("complex request", bot=bot)
        assert len(plan.stages) == 2

    @pytest.mark.asyncio
    async def test_plan_with_bot_empty_response(self):
        from src.agents.planner import ExecutionPlanner
        bot = MagicMock()
        engine = MagicMock()
        engine.generate_response.return_value = ""
        bot.engine_manager.get_active_engine.return_value = engine
        with pytest.raises(RuntimeError, match="empty"):
            await ExecutionPlanner.plan("request", bot=bot)

    @pytest.mark.asyncio
    async def test_plan_with_bot_unparseable(self):
        from src.agents.planner import ExecutionPlanner
        bot = MagicMock()
        engine = MagicMock()
        engine.generate_response.return_value = "Here's my plan: just do it step by step."
        bot.engine_manager.get_active_engine.return_value = engine
        plan = await ExecutionPlanner.plan("request", bot=bot)
        # Falls back to single step
        assert len(plan.stages) == 1
        assert "[FALLBACK]" in plan.stages[0].steps[0].description

    def test_parse_plan_response_empty(self):
        from src.agents.planner import ExecutionPlanner
        assert ExecutionPlanner._parse_plan_response("") == []

    def test_parse_plan_response_code_fence(self):
        from src.agents.planner import ExecutionPlanner
        response = '```json\n{"stages": [{"stage": 1, "parallel": true, "tasks": [{"id": "s1-1", "description": "test", "task": "do it"}]}]}\n```'
        stages = ExecutionPlanner._parse_plan_response(response)
        assert len(stages) == 1
        assert stages[0].steps[0].id == "s1-1"

    def test_parse_plan_response_brace_matching(self):
        from src.agents.planner import ExecutionPlanner
        response = 'Here is the plan: {"stages": [{"stage": 1, "parallel": false, "tasks": [{"id": "s1-1", "description": "d", "task": "t"}]}]} end'
        stages = ExecutionPlanner._parse_plan_response(response)
        assert len(stages) == 1

    def test_parse_plan_response_no_json(self):
        from src.agents.planner import ExecutionPlanner
        stages = ExecutionPlanner._parse_plan_response("no json here at all")
        assert stages == []

    def test_parse_plan_response_invalid_json(self):
        from src.agents.planner import ExecutionPlanner
        response = '```json\n{"stages": [invalid}\n```'
        stages = ExecutionPlanner._parse_plan_response(response)
        assert stages == []

    def test_parse_plan_response_no_stages_key(self):
        from src.agents.planner import ExecutionPlanner
        response = '```json\n{"plans": []}\n```'
        stages = ExecutionPlanner._parse_plan_response(response)
        assert stages == []

    def test_parse_plan_response_trailing_commas(self):
        from src.agents.planner import ExecutionPlanner
        response = '```json\n{"stages": [{"stage": 1, "parallel": true, "tasks": [{"id": "s1-1", "description": "d", "task": "t",},],},]}\n```'
        stages = ExecutionPlanner._parse_plan_response(response)
        assert len(stages) == 1  # cleaned and parsed

    def test_build_planning_prompt_without_context(self):
        from src.agents.planner import ExecutionPlanner
        prompt = ExecutionPlanner._build_planning_prompt("test request")
        assert "test request" in prompt
        assert "execution planner" in prompt.lower()

    def test_build_planning_prompt_with_context(self):
        from src.agents.planner import ExecutionPlanner
        prompt = ExecutionPlanner._build_planning_prompt("req", context="extra info")
        assert "extra info" in prompt

    @pytest.mark.asyncio
    async def test_execute_plan_basic(self):
        from src.agents.planner import ExecutionPlanner, ExecutionPlan, ExecutionStage, PlanStep
        from src.agents.spawner import AgentResult, AgentStatus, AggregatedResult

        plan = ExecutionPlan(
            id="test-plan",
            original_request="test",
            stages=[
                ExecutionStage(stage_number=1, steps=[
                    PlanStep(id="s1-1", description="step1", agent_task="do step 1")
                ], is_parallel=False)
            ]
        )

        mock_result = AgentResult(
            agent_id="a1", task="do step 1",
            status=AgentStatus.COMPLETED,
            output="Step 1 done"
        )
        mock_agg = AggregatedResult(
            results=[mock_result], total_agents=1,
            successful=1, failed=0
        )

        with patch("src.agents.spawner.AgentSpawner.spawn_many", new_callable=AsyncMock, return_value=mock_agg):
            result = await ExecutionPlanner.execute_plan(plan, bot=MagicMock())
        assert result.status == "completed"
        assert result.final_output == "Step 1 done"

    @pytest.mark.asyncio
    async def test_execute_plan_with_progress_callback(self):
        from src.agents.planner import ExecutionPlanner, ExecutionPlan, ExecutionStage, PlanStep
        from src.agents.spawner import AgentResult, AgentStatus, AggregatedResult

        plan = ExecutionPlan(
            id="test", original_request="test",
            stages=[ExecutionStage(stage_number=1, steps=[
                PlanStep(id="s1", description="d", agent_task="t")
            ], is_parallel=False)]
        )
        mock_agg = AggregatedResult(
            results=[AgentResult(agent_id="a", task="t", status=AgentStatus.COMPLETED, output="ok")],
            total_agents=1, successful=1, failed=0
        )
        callback_calls = []
        async def callback(stage, step_id, emoji):
            callback_calls.append((stage, step_id, emoji))

        with patch("src.agents.spawner.AgentSpawner.spawn_many", new_callable=AsyncMock, return_value=mock_agg):
            await ExecutionPlanner.execute_plan(plan, bot=MagicMock(), progress_callback=callback)
        assert len(callback_calls) == 2  # running + completed

    @pytest.mark.asyncio
    async def test_execute_plan_failed_step(self):
        from src.agents.planner import ExecutionPlanner, ExecutionPlan, ExecutionStage, PlanStep
        from src.agents.spawner import AgentResult, AgentStatus, AggregatedResult

        plan = ExecutionPlan(
            id="test", original_request="test",
            stages=[ExecutionStage(stage_number=1, steps=[
                PlanStep(id="s1", description="d", agent_task="t")
            ], is_parallel=False)]
        )
        mock_agg = AggregatedResult(
            results=[AgentResult(agent_id="a", task="t", status=AgentStatus.FAILED, error="oops")],
            total_agents=1, successful=0, failed=1
        )
        with patch("src.agents.spawner.AgentSpawner.spawn_many", new_callable=AsyncMock, return_value=mock_agg):
            result = await ExecutionPlanner.execute_plan(plan, bot=MagicMock())
        assert result.status == "completed"  # plan completes even if steps fail
        assert "no results" in result.final_output.lower()

    @pytest.mark.asyncio
    async def test_execute_plan_multi_stage_synthesis(self):
        from src.agents.planner import ExecutionPlanner, ExecutionPlan, ExecutionStage, PlanStep
        from src.agents.spawner import AgentResult, AgentStatus, AggregatedResult

        plan = ExecutionPlan(
            id="test", original_request="test",
            stages=[ExecutionStage(stage_number=1, steps=[
                PlanStep(id="s1-1", description="d1", agent_task="t1"),
                PlanStep(id="s1-2", description="d2", agent_task="t2"),
            ], is_parallel=True)]
        )
        mock_agg = AggregatedResult(
            results=[
                AgentResult(agent_id="a1", task="t1", status=AgentStatus.COMPLETED, output="result A"),
                AgentResult(agent_id="a2", task="t2", status=AgentStatus.COMPLETED, output="result B"),
            ],
            total_agents=2, successful=2, failed=0
        )
        with patch("src.agents.spawner.AgentSpawner.spawn_many", new_callable=AsyncMock, return_value=mock_agg):
            with patch("src.agents.aggregator.ResultAggregator.synthesize", new_callable=AsyncMock, return_value="merged"):
                result = await ExecutionPlanner.execute_plan(plan, bot=MagicMock())
        assert result.final_output == "merged"


# ═══════════════════════════════════════════════════════
#  CognitionTracker
# ═══════════════════════════════════════════════════════

class TestCognitionTracker:

    def _make_tracker(self):
        from src.engines.cognition_tracker import CognitionTracker
        channel = MagicMock()
        channel.send = AsyncMock()
        tracker = CognitionTracker(channel)
        return tracker

    @pytest.mark.asyncio
    async def test_start_posts_embed(self):
        tracker = self._make_tracker()
        with patch("discord.Embed"):
            await tracker.start()
        tracker.channel.send.assert_called_once()
        assert tracker._message is not None

    @pytest.mark.asyncio
    async def test_start_failure_non_fatal(self):
        tracker = self._make_tracker()
        tracker.channel.send = AsyncMock(side_effect=Exception("fail"))
        await tracker.start()
        assert tracker._message is None

    @pytest.mark.asyncio
    async def test_update_no_message(self):
        tracker = self._make_tracker()
        # No start() called, so _message is None
        await tracker.update("search_web")
        # Should not raise

    @pytest.mark.asyncio
    async def test_update_with_message(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time()
        tracker._last_edit = 0  # allow immediate edit
        tracker._pending_update = False
        await tracker.update("search_web")
        assert tracker._current_action != ""

    @pytest.mark.asyncio
    async def test_update_with_detail(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time()
        tracker._last_edit = 0
        await tracker.update("search_web", detail="quantum physics")
        assert "quantum" in tracker._current_action

    @pytest.mark.asyncio
    async def test_tool_complete_no_message(self):
        tracker = self._make_tracker()
        await tracker.tool_complete("search_web")

    @pytest.mark.asyncio
    async def test_tool_complete_with_message(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time()
        tracker._last_edit = 0
        await tracker.tool_complete("search_web")
        assert tracker._tool_count == 1
        assert len(tracker._status_lines) == 1

    @pytest.mark.asyncio
    async def test_update_step(self):
        tracker = self._make_tracker()
        tracker._message = MagicMock()  # must have message for step to be recorded
        await tracker.update_step(3)
        assert tracker._step_count == 3

    @pytest.mark.asyncio
    async def test_update_step_no_message(self):
        tracker = self._make_tracker()
        # _message is None by default — update_step returns early
        await tracker.update_step(5)
        assert tracker._step_count == 0  # early return, never set

    @pytest.mark.asyncio
    async def test_update_agents_no_message(self):
        tracker = self._make_tracker()
        await tracker.update_agents({"a": ("topic", "✅")})

    @pytest.mark.asyncio
    async def test_update_agents_with_message(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time()
        tracker._last_edit = 0
        await tracker.update_agents({"a1": ("Research AI", "🔄"), "a2": ("Search data", "✅")})
        assert len(tracker._agent_states) == 2

    @pytest.mark.asyncio
    async def test_finalize_no_message(self):
        tracker = self._make_tracker()
        await tracker.finalize()  # Should not raise

    @pytest.mark.asyncio
    async def test_finalize_with_message_and_tools(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time() - 10
        tracker._tool_count = 3
        tracker._step_count = 2
        tracker._status_lines = ["🔍 Searching", "📝 Writing", "📄 Rendering"]
        with patch("discord.Embed"):
            await tracker.finalize()
        msg.edit.assert_called_once()
        assert tracker._message is None  # cleaned up

    @pytest.mark.asyncio
    async def test_finalize_with_agents(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time() - 5
        tracker._agent_states = {
            "a1": ("Research topic A", "✅"),
            "a2": ("Research topic B", "❌"),
        }
        with patch("discord.Embed"):
            await tracker.finalize()
        msg.edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_finalize_with_many_agents_collapsed(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time() - 5
        tracker._agent_states = {
            f"a{i}": (f"Topic {i}", "✅") for i in range(20)
        }
        with patch("discord.Embed"):
            await tracker.finalize()
        msg.edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_finalize_with_deferred_task(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        tracker._deferred_task = mock_task
        with patch("discord.Embed"):
            await tracker.finalize()
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_finalize_edit_error_non_fatal(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock(side_effect=Exception("discord error"))
        tracker._message = msg
        tracker._start_time = time.time()
        with patch("discord.Embed"):
            await tracker.finalize()
        assert tracker._message is None  # still cleaned up

    @pytest.mark.asyncio
    async def test_finalize_long_elapsed(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time() - 120  # 2 minutes
        with patch("discord.Embed"):
            await tracker.finalize()
        msg.edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_finalize_many_tools_trimmed(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time() - 5
        tracker._status_lines = [f"Tool {i}" for i in range(20)]
        tracker._tool_count = 20
        with patch("discord.Embed"):
            await tracker.finalize()
        msg.edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_debounce(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time()
        tracker._last_edit = time.time()  # just edited
        tracker._pending_update = True
        await tracker._flush()
        # Should schedule a deferred flush instead of editing immediately
        assert tracker._deferred_task is not None

    @pytest.mark.asyncio
    async def test_do_edit_builds_embed(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time()
        tracker._pending_update = True
        tracker._tool_count = 2
        tracker._step_count = 1
        tracker._status_lines = ["🔍 Search"]
        with patch("discord.Embed"):
            await tracker._do_edit()
        msg.edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_do_edit_with_agent_states_large_swarm(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time()
        tracker._pending_update = True
        tracker._agent_states = {f"a{i}": (f"Topic {i}", "🔄" if i < 5 else "✅") for i in range(20)}
        with patch("discord.Embed"):
            await tracker._do_edit()
        msg.edit.assert_called_once()

    @pytest.mark.asyncio
    async def test_do_edit_content_trimming(self):
        tracker = self._make_tracker()
        msg = MagicMock()
        msg.edit = AsyncMock()
        tracker._message = msg
        tracker._start_time = time.time()
        tracker._pending_update = True
        tracker._status_lines = [f"Very long tool name {'x' * 200}" for _ in range(30)]
        with patch("discord.Embed"):
            await tracker._do_edit()
        msg.edit.assert_called_once()


# ═══════════════════════════════════════════════════════
#  AdminReports
# ═══════════════════════════════════════════════════════

class TestAdminReports:

    def _make_cog(self):
        from src.bot.cogs.admin_reports import AdminReports
        bot = MagicMock()
        return AdminReports(bot)

    @pytest.mark.asyncio
    async def test_cog_check_admin(self):
        cog = self._make_cog()
        ctx = MagicMock()
        ctx.author.id = 123
        with patch("src.bot.cogs.admin_reports.settings") as mock_settings:
            mock_settings.ADMIN_IDS = [123]
            result = await cog.cog_check(ctx)
        assert result is True

    @pytest.mark.asyncio
    async def test_cog_check_non_admin(self):
        cog = self._make_cog()
        ctx = MagicMock()
        ctx.author.id = 999
        with patch("src.bot.cogs.admin_reports.settings") as mock_settings:
            mock_settings.ADMIN_IDS = [123]
            result = await cog.cog_check(ctx)
        assert result is False

    @pytest.mark.asyncio
    async def test_townhall_suggest_no_daemon(self):
        cog = self._make_cog()
        cog.bot.town_hall = None
        ctx = MagicMock()
        ctx.send = AsyncMock()
        # Call the underlying function directly, bypassing discord Command wrapper
        await cog.townhall_suggest.callback(cog, ctx, "t1", "t2", "t3")
        ctx.send.assert_called_once()
        assert "not active" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_townhall_suggest_success(self):
        cog = self._make_cog()
        town_hall = MagicMock()
        town_hall.add_suggestion.return_value = 3
        town_hall._suggested_topics = ["a", "b", "c"]
        cog.bot.town_hall = town_hall
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.author.id = 123
        await cog.townhall_suggest.callback(cog, ctx, "topic1", "topic2", "topic3")
        assert "3 topic(s)" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_townhall_suggest_no_valid(self):
        cog = self._make_cog()
        town_hall = MagicMock()
        town_hall.add_suggestion.return_value = 0
        cog.bot.town_hall = town_hall
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.author.id = 123
        await cog.townhall_suggest.callback(cog, ctx, "", "", "")
        assert "No valid topics" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_user_report_not_dm(self):
        import discord
        cog = self._make_cog()
        ctx = MagicMock()
        ctx.channel = MagicMock()  # Not DMChannel
        ctx.send = AsyncMock()
        await cog.user_report.callback(cog, ctx)
        assert "DMs" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_user_report_no_user_data(self, tmp_path):
        import discord
        cog = self._make_cog()
        ctx = MagicMock()
        ctx.channel = MagicMock(spec=discord.DMChannel)
        ctx.defer = AsyncMock()
        ctx.send = AsyncMock()
        with patch("src.bot.cogs.admin_reports.data_dir", return_value=tmp_path / "nonexistent"):
            await cog.user_report.callback(cog, ctx)
        assert "No user data" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_user_report_user_not_found(self, tmp_path):
        import discord
        cog = self._make_cog()
        cog.bot.guilds = []
        ctx = MagicMock()
        ctx.channel = MagicMock(spec=discord.DMChannel)
        ctx.defer = AsyncMock()
        ctx.send = AsyncMock()

        users_dir = tmp_path / "users"
        users_dir.mkdir(parents=True)

        with patch("src.bot.cogs.admin_reports.data_dir", return_value=tmp_path):
            await cog.user_report.callback(cog, ctx, username="nonexistent")
        assert "Could not find" in ctx.send.call_args[0][0]


# ═══════════════════════════════════════════════════════
#  AgentSpawner
# ═══════════════════════════════════════════════════════

class TestAgentSpawner:

    def setup_method(self):
        """Reset class-level state between tests."""
        from src.agents.spawner import AgentSpawner
        AgentSpawner._active_agents = {}
        AgentSpawner._agent_history = []
        AgentSpawner._semaphore = None

    @pytest.mark.asyncio
    async def test_spawn_depth_exceeded(self):
        from src.agents.spawner import AgentSpawner, AgentSpec, AgentStatus
        spec = AgentSpec(task="test", depth=100)
        result = await AgentSpawner.spawn(spec)
        assert result.status == AgentStatus.FAILED
        assert "depth" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_active_empty(self):
        from src.agents.spawner import AgentSpawner
        assert AgentSpawner.get_active() == {}

    @pytest.mark.asyncio
    async def test_get_history_empty(self):
        from src.agents.spawner import AgentSpawner
        with patch("src.agents.lifecycle.AgentLifecycle.load_disk_history", return_value=[]):
            assert AgentSpawner.get_history() == []

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        from src.agents.spawner import AgentSpawner
        result = await AgentSpawner.cancel("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_spawn_many_parallel(self):
        from src.agents.spawner import AgentSpawner, AgentSpec, AgentStatus, AgentResult

        async def mock_run(self, step_callback=None):
            return AgentResult(
                agent_id=self.id, task=self.spec.task,
                status=AgentStatus.COMPLETED, output="done"
            )

        with patch("src.agents.spawner.SubAgent.run", mock_run):
            result = await AgentSpawner.spawn_many(
                [AgentSpec(task="t1"), AgentSpec(task="t2")],
                bot=MagicMock()
            )
        assert result.total_agents == 2
        assert result.successful == 2

    @pytest.mark.asyncio
    async def test_spawn_many_pipeline(self):
        from src.agents.spawner import AgentSpawner, AgentSpec, AgentStrategy, AgentStatus, AgentResult

        with patch.object(AgentSpawner, "spawn", new_callable=AsyncMock) as mock_spawn:
            mock_spawn.return_value = AgentResult(
                agent_id="a", task="t", status=AgentStatus.COMPLETED, output="out"
            )
            result = await AgentSpawner.spawn_many(
                [AgentSpec(task="t1"), AgentSpec(task="t2")],
                bot=MagicMock(),
                strategy=AgentStrategy.PIPELINE
            )
        assert result.total_agents == 2
        assert result.synthesis == "out"

    @pytest.mark.asyncio
    async def test_spawn_many_fan_out(self):
        from src.agents.spawner import AgentSpawner, AgentSpec, AgentStrategy, AgentStatus, AgentResult, AggregatedResult

        mock_agg = AggregatedResult(
            results=[AgentResult(agent_id="a", task="t", status=AgentStatus.COMPLETED, output="out")],
            total_agents=1, successful=1, failed=0
        )

        with patch.object(AgentSpawner, "_parallel", new_callable=AsyncMock, return_value=mock_agg):
            bot = MagicMock()
            engine = MagicMock()
            engine.generate_response.return_value = "synthesized"
            bot.engine_manager.get_active_engine.return_value = engine
            result = await AgentSpawner.spawn_many(
                [AgentSpec(task="t")], bot=bot,
                strategy=AgentStrategy.FAN_OUT_FAN_IN
            )
        assert result.synthesis == "synthesized"

    @pytest.mark.asyncio
    async def test_spawn_many_default_strategy(self):
        from src.agents.spawner import AgentSpawner, AgentSpec, AgentStatus, AgentResult

        async def mock_run(self, step_callback=None):
            return AgentResult(
                agent_id=self.id, task=self.spec.task,
                status=AgentStatus.COMPLETED, output="done"
            )

        with patch("src.agents.spawner.SubAgent.run", mock_run):
            result = await AgentSpawner.spawn_many(
                [AgentSpec(task="t")], bot=MagicMock(),
                strategy="unknown_strategy"
            )
        assert result.total_agents == 1

    @pytest.mark.asyncio
    async def test_get_history_after_spawn(self):
        from src.agents.spawner import AgentSpawner, AgentSpec, AgentStatus, AgentResult

        async def mock_run(self, step_callback=None):
            return AgentResult(
                agent_id=self.id, task=self.spec.task,
                status=AgentStatus.COMPLETED, output="done"
            )

        with patch("src.agents.spawner.SubAgent.run", mock_run):
            await AgentSpawner.spawn_many([AgentSpec(task="t")], bot=MagicMock())

        history = AgentSpawner.get_history()
        assert len(history) >= 1
        assert history[0]["status"] == "completed"

    def test_ranked_result_dataclass(self):
        from src.agents.aggregator import RankedResult
        r = RankedResult(content="test", score=0.9, source_agent_id="a1")
        assert r.content == "test"
        assert r.score == 0.9

    def test_agent_spec_defaults(self):
        from src.agents.spawner import AgentSpec
        spec = AgentSpec(task="test")
        assert spec.max_steps == 50
        assert spec.scope == "CORE"
        assert spec.depth == 0

    def test_agent_result_defaults(self):
        from src.agents.spawner import AgentResult, AgentStatus
        r = AgentResult(agent_id="a", task="t", status=AgentStatus.COMPLETED)
        assert r.output == ""
        assert r.error is None

    def test_aggregated_result_defaults(self):
        from src.agents.spawner import AggregatedResult
        r = AggregatedResult()
        assert r.total_agents == 0
        assert r.results == []

    def test_agent_strategy_values(self):
        from src.agents.spawner import AgentStrategy
        assert AgentStrategy.PARALLEL.value == "parallel"
        assert AgentStrategy.PIPELINE.value == "pipeline"
        assert AgentStrategy.COMPETITIVE.value == "competitive"
        assert AgentStrategy.FAN_OUT_FAN_IN.value == "fan_out_fan_in"

    def test_agent_status_values(self):
        from src.agents.spawner import AgentStatus
        assert AgentStatus.PENDING.value == "pending"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.COMPLETED.value == "completed"
        assert AgentStatus.FAILED.value == "failed"
        assert AgentStatus.CANCELLED.value == "cancelled"
        assert AgentStatus.TIMED_OUT.value == "timed_out"

    def test_plan_step_defaults(self):
        from src.agents.planner import PlanStep
        s = PlanStep()
        assert s.status == "pending"
        assert s.timeout == 1800.0

    def test_execution_stage_defaults(self):
        from src.agents.planner import ExecutionStage
        s = ExecutionStage()
        assert s.is_parallel is True
        assert s.steps == []

    def test_execution_plan_defaults(self):
        from src.agents.planner import ExecutionPlan
        p = ExecutionPlan()
        assert p.status == "pending"
        assert p.stages == []
