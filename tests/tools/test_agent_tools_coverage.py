"""
Coverage tests for src/tools/agent_tools.py.
Targets 165 uncovered lines: delegate_to_agents (auto-subdivide, tracker callbacks,
_build_states, all-fail, single-output, synthesis, flux gate),
execute_agent_plan (tracker, step callbacks, plan progress),
spawn_research_swarm (depth instructions, output paths),
agent_status (active, history, health, dashboard),
spawn_competitive_agents (race states, progress, winner).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from enum import Enum


class MockStatus(Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


@pytest.fixture
def mock_spawner():
    """Provide common mocked agent infrastructure."""
    with patch("src.agents.spawner.AgentSpawner") as SpawnerCls, \
         patch("src.agents.aggregator.ResultAggregator") as AggCls, \
         patch("src.agents.lifecycle.AgentLifecycle") as LCCls:

        lifecycle = MagicMock()
        LCCls.get_instance.return_value = lifecycle

        result_obj = MagicMock()
        result_obj.results = []
        result_obj.synthesis = ""
        result_obj.successful = 0
        result_obj.total_agents = 0
        result_obj.total_duration_ms = 100
        SpawnerCls.spawn_many = AsyncMock(return_value=result_obj)
        AggCls.synthesize = AsyncMock(return_value="synthesized")

        yield {
            "Spawner": SpawnerCls,
            "Aggregator": AggCls,
            "lifecycle": lifecycle,
            "result": result_obj,
        }


# ── delegate_to_agents ───────────────────────────────────
class TestDelegateToAgents:
    @pytest.mark.asyncio
    async def test_no_tasks(self, mock_spawner):
        from src.tools.agent_tools import delegate_to_agents
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]):
            result = await delegate_to_agents("")
        assert "No tasks" in result

    @pytest.mark.asyncio
    async def test_invalid_tasks_type(self, mock_spawner):
        from src.tools.agent_tools import delegate_to_agents
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]):
            result = await delegate_to_agents(123)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_single_task_success(self, mock_spawner):
        from src.tools.agent_tools import delegate_to_agents
        r = MagicMock()
        r.status = MockStatus.COMPLETED
        r.output = "Agent result"
        r.agent_id = "a1"
        r.duration_ms = 100
        r.tokens_used = 50
        r.tools_called = ["tool1"]
        r.error = None
        mock_spawner["result"].results = [r]
        mock_spawner["result"].synthesis = ""

        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.bot.globals.active_tracker") as mock_tracker_var:
            mock_tracker_var.get.return_value = None
            result = await delegate_to_agents("Do task 1")
        assert result == "Agent result"

    @pytest.mark.asyncio
    async def test_all_agents_fail(self, mock_spawner):
        from src.tools.agent_tools import delegate_to_agents
        r = MagicMock()
        r.status = MockStatus.FAILED
        r.output = ""
        r.agent_id = "a1"
        r.duration_ms = 100
        r.error = "timeout"
        r.tokens_used = 0
        r.tools_called = []
        mock_spawner["result"].results = [r]
        mock_spawner["result"].synthesis = ""

        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.bot.globals.active_tracker") as mock_tracker_var:
            mock_tracker_var.get.return_value = None
            result = await delegate_to_agents("Fail task")
        assert "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_synthesis_returned(self, mock_spawner):
        from src.tools.agent_tools import delegate_to_agents
        mock_spawner["result"].synthesis = "Synthesized output"
        mock_spawner["result"].results = []

        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.bot.globals.active_tracker") as mock_tracker_var:
            mock_tracker_var.get.return_value = None
            result = await delegate_to_agents("task1|task2")
        assert result == "Synthesized output"

    @pytest.mark.asyncio
    async def test_auto_subdivide(self, mock_spawner):
        from src.tools.agent_tools import delegate_to_agents
        mock_spawner["result"].synthesis = "done"
        mock_spawner["result"].results = []

        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.bot.globals.active_tracker") as mock_tracker_var:
            mock_tracker_var.get.return_value = None
            result = await delegate_to_agents("topic1", num_agents="3")
        # Should have auto-subdivided into 3 specs
        call_args = mock_spawner["Spawner"].spawn_many.call_args
        specs = call_args[0][0]
        assert len(specs) == 3

    @pytest.mark.asyncio
    async def test_list_tasks_input(self, mock_spawner):
        from src.tools.agent_tools import delegate_to_agents
        mock_spawner["result"].synthesis = "done"
        mock_spawner["result"].results = []

        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.bot.globals.active_tracker") as mock_tracker_var:
            mock_tracker_var.get.return_value = None
            result = await delegate_to_agents(["task1", "task2"])
        assert result == "done"

    @pytest.mark.asyncio
    async def test_flux_gate_blocks(self, mock_spawner):
        from src.tools.agent_tools import delegate_to_agents

        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.bot.globals.active_tracker") as mock_tracker_var, \
             patch("src.core.flux_capacitor.FluxCapacitor") as FluxCls:
            mock_tracker_var.get.return_value = None
            flux = MagicMock()
            flux.consume_agents.return_value = (False, "Rate limited")
            FluxCls.return_value = flux
            result = await delegate_to_agents("task1")
        assert "Rate limited" in result

    @pytest.mark.asyncio
    @patch("src.agents.spawner.AgentSpawner.spawn_many")
    async def test_delegate_swarm_callbacks(self, mock_spawn_many, mock_spawner):
        from src.tools.agent_tools import delegate_to_agents
        
        # Test the tracker callbacks
        tracker = MagicMock()
        tracker.update_agents = AsyncMock()
        
        callbacks = {}
        async def capture_spawn(*args, **kwargs):
            callbacks["progress"] = kwargs.get("progress_callback")
            callbacks["step"] = kwargs.get("step_callback")
            return mock_spawner["result"]
            
        mock_spawn_many.side_effect = capture_spawn
        
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.bot.globals.active_message") as mock_msg_var:
            msg = MagicMock()
            msg._cognition_tracker = tracker
            mock_msg_var.get.return_value = msg
            
            with patch("src.core.flux_capacitor.FluxCapacitor") as FluxCls:
                flux = MagicMock()
                flux.consume_agents.return_value = (True, "")
                FluxCls.return_value = flux
                
                await delegate_to_agents("task1|task2", num_agents="2")
                
                tracker.update_agents.assert_awaited()
                
                prog_cb = callbacks.get("progress")
                step_cb = callbacks.get("step")
                
                if prog_cb:
                    r1 = MagicMock()
                    r1.status.value = "completed"
                    await prog_cb(r1)
                    
                    r2 = MagicMock()
                    r2.status.value = "failed"
                    await prog_cb(r2)
                    
                if step_cb:
                    await step_cb("agent1", 1, "Doing task")


# ── execute_agent_plan ───────────────────────────────────
class TestExecuteAgentPlan:
    @pytest.mark.asyncio
    @patch("src.agents.planner.ExecutionPlanner.plan")
    @patch("src.agents.planner.ExecutionPlanner.execute_plan")
    async def test_execute_plan_success_with_tracker(self, mock_execute, mock_plan):
        from src.tools.agent_tools import execute_agent_plan
        
        # Mock Plan
        plan = MagicMock()
        stage = MagicMock()
        stage.stage_number = 1
        step = MagicMock()
        step.id = "step1"
        step.description = "Test step"
        step.agent_task = "Task 1"
        stage.steps = [step]
        plan.stages = [stage]
        mock_plan.return_value = plan
        
        # Mock Execution Result
        exec_result = MagicMock()
        exec_result.total_agents_spawned = 1
        exec_result.stages = [stage]
        exec_result.total_duration_ms = 100
        exec_result.final_output = "Plan complete"
        mock_execute.return_value = exec_result

        # Mock Tracker
        tracker = MagicMock()
        tracker.update = AsyncMock()
        tracker.update_agents = AsyncMock()
        
        # Capture callbacks to test them
        callbacks = {}
        async def capture_execute(*args, **kwargs):
            callbacks["progress"] = kwargs.get("progress_callback")
            callbacks["step"] = kwargs.get("step_callback")
            return exec_result
            
        mock_execute.side_effect = capture_execute

        with patch("src.bot.globals.active_tracker") as mock_tracker_var, \
             patch("src.bot.globals.active_message") as mock_msg_var, \
             patch("src.core.flux_capacitor.FluxCapacitor") as FluxCls:
            
            # Setup globals to return tracker
            mock_tracker_var.get.return_value = tracker
            flux = MagicMock()
            flux.consume_agents.return_value = (True, "")
            FluxCls.return_value = flux
            
            result = await execute_agent_plan("Complex request")
            
            assert "Plan executed" in result
            assert "Plan complete" in result
            tracker.update.assert_awaited()
            tracker.update_agents.assert_awaited()
            
            # Test inner callbacks
            prog_cb = callbacks.get("progress")
            step_cb = callbacks.get("step")
            
            if prog_cb:
                await prog_cb(1, "step1", "🔄")  # Running
                await prog_cb(1, "step1", "✅")  # Done
                
            if step_cb:
                # Trigger a running state first so step_callback can find it
                if prog_cb: await prog_cb(1, "step1", "🔄")
                await step_cb("agent1", 1, "Using tool X")

    @pytest.mark.asyncio
    @patch("src.agents.planner.ExecutionPlanner.plan")
    async def test_execute_plan_flux_blocked(self, mock_plan):
        from src.tools.agent_tools import execute_agent_plan
        
        plan = MagicMock()
        plan.stages = []
        mock_plan.return_value = plan

        with patch("src.bot.globals.active_tracker") as mock_tracker_var, \
             patch("src.core.flux_capacitor.FluxCapacitor") as FluxCls:
            mock_tracker_var.get.return_value = None
            flux = MagicMock()
            flux.consume_agents.return_value = (False, "Budget exceeded")
            FluxCls.return_value = flux
            
            result = await execute_agent_plan("Request")
        assert "Budget exceeded" in result

    @pytest.mark.asyncio
    @patch("src.agents.planner.ExecutionPlanner.plan")
    @patch("src.agents.planner.ExecutionPlanner.execute_plan")
    async def test_execute_plan_tracker_exceptions(self, mock_execute, mock_plan):
        from src.tools.agent_tools import execute_agent_plan
        
        # Setup mocks
        plan = MagicMock()
        stage = MagicMock()
        step = MagicMock()
        step.description = "Test plan step"
        step.agent_task = "Task"
        step.id = "step1"
        stage.steps = [step]
        stage.stage_number = 1
        plan.stages = [stage]
        mock_plan.return_value = plan
        
        exec_result = MagicMock()
        exec_result.success = True
        exec_result.synthesis = "Plan executed successfully."
        exec_result.total_agents_spawned = 1
        exec_result.stages = [1]
        exec_result.total_duration_ms = 100
        exec_result.final_output = "Done"
        mock_execute.return_value = exec_result

        # Configure tracker with exception
        tracker = MagicMock()
        tracker.update = AsyncMock(side_effect=Exception("UI error"))
        tracker.update_agents = AsyncMock(side_effect=Exception("UI error"))
        
        # Capture callbacks to test them
        callbacks = {}
        async def capture_execute(*args, **kwargs):
            callbacks["progress"] = kwargs.get("progress_callback")
            callbacks["step"] = kwargs.get("step_callback")
            return exec_result
            
        mock_execute.side_effect = capture_execute

        with patch("src.bot.globals.active_tracker") as mock_tracker_var, \
             patch("src.bot.globals.active_message") as mock_msg_var, \
             patch("src.core.flux_capacitor.FluxCapacitor") as FluxCls:
            
            # Setup globals to return tracker
            mock_tracker_var.get.return_value = tracker
            flux = MagicMock()
            flux.consume_agents.return_value = (True, "")
            FluxCls.return_value = flux
            
            await execute_agent_plan("Complex request")
            
            # Test inner callbacks - should catch and suppress the 'UI error' exceptions
            prog_cb = callbacks.get("progress")
            step_cb = callbacks.get("step")
            
            if prog_cb:
                await prog_cb(1, "step1", "🔄")  # Running
                await prog_cb(1, "step1", "✅")  # Done
                
            if step_cb:
                if prog_cb: await prog_cb(1, "step1", "🔄")
                await step_cb("agent1", 1, "Using tool X")


# ── spawn_research_swarm ─────────────────────────────────
class TestSpawnResearchSwarm:
    @pytest.mark.asyncio
    async def test_no_topics(self, mock_spawner):
        from src.tools.agent_tools import spawn_research_swarm
        result = await spawn_research_swarm("")
        assert "No topics" in result

    @pytest.mark.asyncio
    async def test_single_topic_success(self, mock_spawner):
        from src.tools.agent_tools import spawn_research_swarm
        r = MagicMock()
        r.status = MockStatus.COMPLETED
        r.output = "Research findings"
        mock_spawner["result"].results = [r]
        mock_spawner["result"].synthesis = ""

        with patch("src.bot.globals.active_tracker") as mock_tracker_var:
            mock_tracker_var.get.return_value = None
            result = await spawn_research_swarm("AI trends")
        assert result == "Research findings"
        
    @pytest.mark.asyncio
    @patch("src.agents.spawner.AgentSpawner.spawn_many")
    async def test_research_swarm_callbacks(self, mock_spawn_many, mock_spawner):
        from src.tools.agent_tools import spawn_research_swarm
        
        # Test the tracker callbacks
        tracker = MagicMock()
        tracker.update_agents = AsyncMock()
        
        callbacks = {}
        async def capture_spawn(*args, **kwargs):
            callbacks["progress"] = kwargs.get("progress_callback")
            callbacks["step"] = kwargs.get("step_callback")
            return mock_spawner["result"]
            
        mock_spawn_many.side_effect = capture_spawn
        
        with patch("src.bot.globals.active_message") as mock_msg_var:
            msg = MagicMock()
            msg._cognition_tracker = tracker
            mock_msg_var.get.return_value = msg
            
            with patch("src.core.flux_capacitor.FluxCapacitor") as FluxCls:
                flux = MagicMock()
                flux.consume_agents.return_value = (True, "")
                FluxCls.return_value = flux
                
                await spawn_research_swarm("Topic 1|Topic 2")
                
                tracker.update_agents.assert_awaited()
                
                prog_cb = callbacks.get("progress")
                step_cb = callbacks.get("step")
                
                if prog_cb:
                    r1 = MagicMock()
                    r1.status.value = "completed"
                    await prog_cb(r1)
                    
                    r2 = MagicMock()
                    r2.status.value = "failed"
                    await prog_cb(r2)
                    
                if step_cb:
                    await step_cb("agent1", 1, "Reading page")

    @pytest.mark.asyncio
    async def test_no_results(self, mock_spawner):
        from src.tools.agent_tools import spawn_research_swarm
        mock_spawner["result"].results = []
        mock_spawner["result"].synthesis = ""

        with patch("src.bot.globals.active_tracker") as mock_tracker_var:
            mock_tracker_var.get.return_value = None
            result = await spawn_research_swarm("topic1")
        assert "no results" in result.lower()


# ── agent_status ─────────────────────────────────────────
class TestAgentStatus:
    @pytest.mark.asyncio
    async def test_dashboard(self, mock_spawner):
        from src.tools.agent_tools import agent_status
        mock_spawner["lifecycle"].get_dashboard.return_value = "Dashboard content"
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]):
            result = await agent_status("dashboard")
        assert "Dashboard" in result

    @pytest.mark.asyncio
    async def test_active_none(self, mock_spawner):
        from src.tools.agent_tools import agent_status
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.agents.spawner.AgentSpawner.get_active", return_value={}):
            result = await agent_status("active")
        assert "No active" in result

    @pytest.mark.asyncio
    async def test_active_agents(self, mock_spawner):
        from src.tools.agent_tools import agent_status
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.agents.spawner.AgentSpawner.get_active", return_value={
                 "agent1": {"task": "research", "steps": 3, "elapsed_ms": 500}
             }):
            result = await agent_status("active")
        assert "agent1" in result

    @pytest.mark.asyncio
    async def test_history_empty(self, mock_spawner):
        from src.tools.agent_tools import agent_status
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.agents.spawner.AgentSpawner.get_history", return_value=[]):
            result = await agent_status("history")
        assert "No agent history" in result

    @pytest.mark.asyncio
    async def test_history_entries(self, mock_spawner):
        from src.tools.agent_tools import agent_status
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]), \
             patch("src.agents.spawner.AgentSpawner.get_history", return_value=[
                 {"agent_id": "a1", "task": "research", "status": "completed", "duration_ms": 500, "steps": 3}
             ]):
            result = await agent_status("history")
        assert "OK" in result

    @pytest.mark.asyncio
    async def test_health(self, mock_spawner):
        from src.tools.agent_tools import agent_status
        health = MagicMock()
        health.healthy = True
        health.active_agents = 0
        health.avg_response_time_ms = 100
        health.error_rate = 0.05
        health.warnings = []
        mock_spawner["lifecycle"].health_check.return_value = health
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]):
            result = await agent_status("health")
        assert "HEALTHY" in result

    @pytest.mark.asyncio
    async def test_health_with_warnings(self, mock_spawner):
        from src.tools.agent_tools import agent_status
        health = MagicMock()
        health.healthy = False
        health.active_agents = 5
        health.avg_response_time_ms = 5000
        health.error_rate = 0.8
        health.warnings = ["High error rate"]
        mock_spawner["lifecycle"].health_check.return_value = health
        with patch("src.agents.lifecycle.AgentLifecycle.get_instance", return_value=mock_spawner["lifecycle"]):
            result = await agent_status("health")
        assert "DEGRADED" in result
        assert "High error rate" in result


# ── spawn_competitive_agents ─────────────────────────────
class TestSpawnCompetitiveAgents:
    @pytest.mark.asyncio
    async def test_winner(self, mock_spawner):
        from src.tools.agent_tools import spawn_competitive_agents
        mock_spawner["result"].synthesis = "Winner result"
        mock_spawner["result"].total_duration_ms = 250

        with patch("src.bot.globals.active_tracker") as mock_tracker_var:
            mock_tracker_var.get.return_value = None
            result = await spawn_competitive_agents("Do this task", "2")
        assert "Winner" in result

    @pytest.mark.asyncio
    @patch("src.agents.spawner.AgentSpawner.spawn_many")
    async def test_no_winner(self, mock_spawn_many, mock_spawner):
        from src.tools.agent_tools import spawn_competitive_agents
        mock_spawn_many.return_value = mock_spawner["result"]
        mock_spawner["result"].synthesis = ""

        with patch("src.bot.globals.active_tracker") as mock_tracker_var:
            mock_tracker_var.get.return_value = None
            result = await spawn_competitive_agents("Difficult task")
        assert "No agent completed" in result

    @pytest.mark.asyncio
    @patch("src.agents.spawner.AgentSpawner.spawn_many")
    async def test_competitive_race_callbacks(self, mock_spawn_many, mock_spawner):
        from src.tools.agent_tools import spawn_competitive_agents
        
        # Test the tracker callbacks and flux gate
        tracker = MagicMock()
        tracker.update_agents = AsyncMock()
        
        callbacks = {}
        async def capture_spawn(*args, **kwargs):
            callbacks["progress"] = kwargs.get("progress_callback")
            callbacks["step"] = kwargs.get("step_callback")
            return mock_spawner["result"]
            
        mock_spawn_many.side_effect = capture_spawn
        
        with patch("src.bot.globals.active_message") as mock_msg_var:
            msg = MagicMock()
            msg._cognition_tracker = tracker
            mock_msg_var.get.return_value = msg
            
            with patch("src.core.flux_capacitor.FluxCapacitor") as FluxCls:
                flux = MagicMock()
                flux.consume_agents.return_value = (True, "")
                FluxCls.return_value = flux
                
                mock_spawner["result"].synthesis = "Winner won!"
                await spawn_competitive_agents("Race task", "3")
                
                tracker.update_agents.assert_awaited()
                
                prog_cb = callbacks.get("progress")
                step_cb = callbacks.get("step")
                
                if prog_cb:
                    # First agent fails
                    r_fail = MagicMock()
                    r_fail.status.value = "failed"
                    await prog_cb(r_fail)
                    
                    # Second agent forms the winner
                    r_win = MagicMock()
                    r_win.status.value = "completed"
                    await prog_cb(r_win)
                    
                if step_cb:
                    await step_cb("agent1", 1, "Racing")
                    
    @pytest.mark.asyncio
    @patch("src.agents.spawner.AgentSpawner.spawn_many")
    async def test_competitive_flux_blocked(self, mock_spawn_many, mock_spawner):
        from src.tools.agent_tools import spawn_competitive_agents
        mock_spawn_many.return_value = mock_spawner["result"]
        with patch("src.bot.globals.active_tracker") as mock_tracker_var, \
             patch("src.core.flux_capacitor.FluxCapacitor") as FluxCls:
            mock_tracker_var.get.return_value = None
            flux = MagicMock()
            flux.consume_agents.return_value = (False, "Budget exceeded")
            FluxCls.return_value = flux
            
            result = await spawn_competitive_agents("Race task", "2")
        assert "Budget exceeded" in result

    @pytest.mark.asyncio
    @patch("src.agents.spawner.AgentSpawner.spawn_many")
    async def test_competitive_tracker_exceptions(self, mock_spawn_many, mock_spawner):
        from src.tools.agent_tools import spawn_competitive_agents
        
        tracker = MagicMock()
        tracker.update_agents = AsyncMock(side_effect=Exception("UI error"))
        
        callbacks = {}
        async def capture_spawn(*args, **kwargs):
            callbacks["progress"] = kwargs.get("progress_callback")
            callbacks["step"] = kwargs.get("step_callback")
            return mock_spawner["result"]
            
        mock_spawn_many.side_effect = capture_spawn
        
        with patch("src.bot.globals.active_message") as mock_msg_var, \
             patch("src.core.flux_capacitor.FluxCapacitor") as FluxCls:
            msg = MagicMock()
            msg._cognition_tracker = tracker
            mock_msg_var.get.return_value = msg
            
            flux = MagicMock()
            flux.consume_agents.return_value = (True, "")
            FluxCls.return_value = flux
            
            mock_spawner["result"].synthesis = "Winner won!"
            await spawn_competitive_agents("Race task", "3")
            
            prog_cb = callbacks.get("progress")
            step_cb = callbacks.get("step")
            
            # The exceptions should be gracefully caught and suppressed
            if prog_cb:
                r_win = MagicMock()
                r_win.status.value = "completed"
                await prog_cb(r_win)
                
            if step_cb:
                await step_cb("agent1", 1, "Racing")
