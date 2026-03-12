"""
Agent Tools — Exposes the multi-agent orchestration system to the LLM.

These tools allow Ernos to spawn sub-agents, run parallel research,
execute multi-stage plans, and monitor agent activity — all from
within the main cognition loop.
"""
import asyncio
import json
import logging
from src.tools.registry import ToolRegistry

logger = logging.getLogger("Tools.Agent")


# ============================================================
# TOOL: delegate_to_agents
# The primary sub-agent spawning tool
# ============================================================

@ToolRegistry.register(
    name="delegate_to_agents",
    description=(
        "Spawn multiple sub-agents to work on tasks in parallel. "
        "Each agent gets its own independent cognition loop with full tool access. "
        "Use this when you need to research multiple topics, verify multiple claims, "
        "or perform any work that can be parallelized. "
        "Strategies: 'parallel' (all at once), 'pipeline' (sequential chain), "
        "'competitive' (race, first good result wins), 'fan_out_fan_in' (parallel + LLM synthesis). "
        "If the user requests a specific number of agents, set num_agents to that number — "
        "the system will auto-subdivide tasks to fill the requested count. "
        "Returns aggregated results from all agents."
    ),
    parameters={
        "tasks": "List of task descriptions for sub-agents (pipe-separated: 'task1|task2|task3')",
        "strategy": "Execution strategy: parallel, pipeline, competitive, fan_out_fan_in (default: parallel)",
        "timeout": "Max seconds to wait for all agents (default: 3600)",
        "num_agents": "Exact number of agents to spawn. If larger than tasks provided, tasks are auto-subdivided into sub-angles (default: match task count)",
    }
)
async def delegate_to_agents(tasks: str, strategy: str = "parallel",
                              timeout: str = "3600", num_agents: str = "0",
                              bot=None, user_id: str = "CORE",
                              request_scope: str = "CORE") -> str:
    from src.agents.spawner import AgentSpawner, AgentSpec, AgentStrategy
    from src.agents.aggregator import ResultAggregator
    from src.agents.lifecycle import AgentLifecycle

    lifecycle = AgentLifecycle.get_instance()

    # Parse tasks
    if isinstance(tasks, str):
        task_list = [t.strip() for t in tasks.split("|") if t.strip()]
    elif isinstance(tasks, list):
        task_list = tasks
    else:
        return "Error: tasks must be a pipe-separated string or list"

    if not task_list:
        return "Error: No tasks provided"

    requested_count = int(num_agents) if isinstance(num_agents, str) else num_agents

    # Auto-subdivide: if user wants more agents than tasks, expand each task
    if requested_count > len(task_list):
        expanded = []
        agents_per_task = requested_count // len(task_list)
        remainder = requested_count % len(task_list)
        for i, task in enumerate(task_list):
            count = agents_per_task + (1 if i < remainder else 0)
            if count == 1:
                expanded.append(task)
            else:
                for j in range(count):
                    expanded.append(
                        f"{task}\n\n[Sub-agent {j+1}/{count}: Focus on a DIFFERENT angle, "
                        f"aspect, or approach than the other sub-agents working on this same topic. "
                        f"Bring unique findings.]"
                    )
        task_list = expanded
        logger.info(f"Auto-subdivided {len(task_list)} tasks from {requested_count} requested agents")

    timeout_val = float(timeout) if isinstance(timeout, str) else timeout

    # Map strategy string to enum
    strategy_map = {
        "parallel": AgentStrategy.PARALLEL,
        "pipeline": AgentStrategy.PIPELINE,
        "competitive": AgentStrategy.COMPETITIVE,
        "fan_out_fan_in": AgentStrategy.FAN_OUT_FAN_IN,
    }
    agent_strategy = strategy_map.get(strategy, AgentStrategy.PARALLEL)

    # Create agent specs — agents run in PARALLEL, so each gets the full timeout
    # (not divided by count — that was the old broken formula)
    per_agent_timeout = max(timeout_val, 120.0)  # At least 2 minutes each
    specs = [
        AgentSpec(
            task=task,
            context={},
            max_steps=50,
            timeout=per_agent_timeout,
            scope=request_scope,
            user_id=user_id,
        )
        for task in task_list
    ]

    logger.info(f"Delegating {len(specs)} tasks with strategy={strategy}")

    # ── Flux Gate: check agent spawn budget ──
    try:
        from src.core.flux_capacitor import FluxCapacitor
        flux = FluxCapacitor(bot)
        allowed, msg = flux.consume_agents(user_id, len(specs))
        if not allowed:
            return msg
    except Exception as e:
        logger.debug(f"Flux agent check skipped: {e}")

    lifecycle.record_spawn("batch", strategy=strategy)

    # ── Progress Callback for CognitionTracker ──
    progress_callback = None
    step_callback = None
    try:
        from src.bot import globals as bot_globals
        tracker = bot_globals.active_tracker.get()
        if tracker is None:
            active_msg = bot_globals.active_message.get()
            if active_msg and hasattr(active_msg, '_cognition_tracker'):
                tracker = active_msg._cognition_tracker
    except Exception:
        tracker = None

    if tracker:
        _labels = [spec.task[:80].replace('\n', ' ') for spec in specs]
        _done = 0
        _failed = 0
        _active_detail = ""

        def _build_states():
            """Rebuild tracker states from atomic counters."""
            states = {}
            for i, label in enumerate(_labels):
                key = f"agent-{i}"
                if i < _done:
                    states[key] = (label, "✅")
                elif i < _done + _failed:
                    states[key] = (label, "❌")
                elif _active_detail and i == _done + _failed:
                    states[key] = (f"{label} — {_active_detail}", "🔄")
                else:
                    states[key] = (label, "⏳")
            return states

        await tracker.update_agents(_build_states())

        async def progress_callback(result):
            nonlocal _done, _failed
            try:
                if result.status.value == "completed":
                    _done += 1
                else:
                    _failed += 1
                await tracker.update_agents(_build_states())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

        async def step_callback(agent_id, step_num, detail):
            nonlocal _active_detail
            try:
                _active_detail = f"Step {step_num}: {detail}"
                await tracker.update_agents(_build_states())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

    result = await AgentSpawner.spawn_many(specs, bot, agent_strategy, timeout_val,
                                            progress_callback=progress_callback,
                                            step_callback=step_callback)

    # Record metrics
    for r in result.results:
        if r.status.value == "completed":
            lifecycle.record_completion(r.agent_id, r.duration_ms, r.tokens_used, len(r.tools_called))
        else:
            lifecycle.record_failure(r.agent_id, r.status.value, r.duration_ms)

    # Synthesize if fan_out_fan_in or multiple results
    if result.synthesis:
        return result.synthesis

    outputs = [r.output for r in result.results if r.output and r.status.value == "completed"]
    if not outputs:
        errors = [f"Agent {r.agent_id}: {r.error}" for r in result.results if r.error]
        return f"All {len(task_list)} agents failed.\nErrors:\n" + "\n".join(errors)

    if len(outputs) == 1:
        return outputs[0]

    return await ResultAggregator.synthesize(outputs, bot, strategy="llm_merge")


# ============================================================
# TOOL: execute_agent_plan
# LLM-guided multi-stage execution planning
# ============================================================

@ToolRegistry.register(
    name="execute_agent_plan",
    description=(
        "Decompose a complex request into a multi-stage execution plan and run it. "
        "The system uses AI to create a DAG of parallel and sequential stages, "
        "then spawns agents for each stage. Use this for complex, multi-step tasks "
        "like comprehensive research reports, multi-file code changes, or any task "
        "that benefits from structured decomposition."
    ),
    parameters={
        "request": "The complex request to decompose and execute",
        "context": "Optional additional context for the planner",
    }
)
async def execute_agent_plan(request: str, context: str = "",
                              bot=None, user_id: str = "CORE",
                              request_scope: str = "CORE") -> str:
    from src.agents.planner import ExecutionPlanner

    logger.info(f"Creating execution plan for: {request[:100]}")

    # ── Retrieve CognitionTracker ──
    tracker = None
    try:
        from src.bot import globals as bot_globals
        tracker = bot_globals.active_tracker.get()
        if tracker is None:
            active_msg = bot_globals.active_message.get()
            if active_msg and hasattr(active_msg, '_cognition_tracker'):
                tracker = active_msg._cognition_tracker
    except Exception as e:
        logger.warning(f"Suppressed {type(e).__name__}: {e}")

    if tracker:
        try:
            await tracker.update("📋 Building execution plan...")
        except Exception as e:
            logger.warning(f"Suppressed {type(e).__name__}: {e}")

    plan = await ExecutionPlanner.plan(request, bot, context)
    total_steps = sum(len(s.steps) for s in plan.stages)

    logger.info(f"Plan created with {len(plan.stages)} stages, {total_steps} total steps")

    # ── Flux Gate: check agent spawn budget ──
    try:
        from src.core.flux_capacitor import FluxCapacitor
        flux = FluxCapacitor(bot)
        allowed, msg = flux.consume_agents(user_id, total_steps)
        if not allowed:
            return msg
    except Exception as e:
        logger.debug(f"Flux agent check skipped: {e}")

    if tracker:
        try:
            _plan_states = {}
            for stage in plan.stages:
                for step in stage.steps:
                    desc = step.description or step.agent_task[:80]
                    _plan_states[step.id] = (f"[S{stage.stage_number}] {desc[:80]}", "⏳")
            await tracker.update_agents(_plan_states)
        except Exception as e:
            logger.warning(f"Suppressed {type(e).__name__}: {e}")

    # ── Step-level progress callback ──
    async def _plan_progress(stage_num, step_id, status_emoji):
        if tracker:
            try:
                old_label = _plan_states.get(step_id, (step_id, ""))[0]
                if status_emoji == "🔄":
                    # Running — show it
                    _plan_states[step_id] = (old_label, "🔄")
                else:
                    _plan_states[step_id] = (old_label, status_emoji)
                await tracker.update_agents(_plan_states)
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

    # ── Step callback: inner tool visibility ──
    async def _step_callback(agent_id, step_num, detail):
        """Show which tools each inner agent is using right now."""
        if tracker:
            try:
                # Find which plan step this agent belongs to by matching running states
                for sid, (label, st) in list(_plan_states.items()):
                    if st == "🔄":
                        base_label = label.split(' — ')[0]
                        _plan_states[sid] = (f"{base_label} — {detail}", "🔄")
                        break
                await tracker.update_agents(_plan_states)
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

    executed_plan = await ExecutionPlanner.execute_plan(
        plan, bot, user_id=user_id, scope=request_scope,
        progress_callback=_plan_progress,
        step_callback=_step_callback
    )

    summary = (
        f"Plan executed: {executed_plan.total_agents_spawned} agents across "
        f"{len(executed_plan.stages)} stages in {executed_plan.total_duration_ms:.0f}ms\n\n"
        f"{executed_plan.final_output}"
    )

    return summary


# ============================================================
# TOOL: spawn_research_swarm
# Quick parallel research across multiple topics
# ============================================================

@ToolRegistry.register(
    name="spawn_research_swarm",
    description=(
        "Spawn a swarm of research agents to investigate multiple topics simultaneously. "
        "Each agent independently searches the web, browses sites, and synthesizes findings. "
        "Results are merged into a comprehensive report. "
        "Use this when you need to research multiple topics, compare alternatives, "
        "or gather broad information quickly. "
        "If the user requests a specific number of agents, set num_agents to that exact number."
    ),
    parameters={
        "topics": "Pipe-separated list of research topics: 'topic1|topic2|topic3'",
        "depth": "Research depth: 'shallow' (1 search each), 'medium' (3 searches each), 'deep' (full deep research each)",
        "num_agents": "Exact number of research agents to spawn. If larger than topics provided, each topic gets multiple agents with different research angles (default: match topic count)",
    }
)
async def spawn_research_swarm(topics: str, depth: str = "medium",
                                num_agents: str = "0",
                                bot=None, user_id: str = "CORE",
                                request_scope: str = "CORE") -> str:
    from src.agents.spawner import AgentSpawner, AgentSpec, AgentStrategy
    from src.agents.aggregator import ResultAggregator

    topic_list = [t.strip() for t in topics.split("|") if t.strip()]
    if not topic_list:
        return "Error: No topics provided"

    requested_count = int(num_agents) if isinstance(num_agents, str) else num_agents

    # Disable auto-splitting per user request. 
    # If they want 4 topics, they get 4 agents.
    # We will just cap the agent count to exactly the number of topics to avoid completely duplicate identical agents.
    if requested_count > len(topic_list):
        logger.info(f"Requested {requested_count} agents but only provided {len(topic_list)} topics. Executing 1:1 topic mapping.")

    depth_instructions = {
        "shallow": "Do a single web search and summarize the top results concisely.",
        "medium": "Do 3 web searches with different angles, browse the most relevant pages, and write a thorough summary.",
        "deep": "Conduct comprehensive research: multiple searches, browse key sources, cross-reference findings, and produce a detailed report with sources.",
    }

    instruction = depth_instructions.get(depth, depth_instructions["medium"])

    specs = [
        AgentSpec(
            task=f"Research the following topic thoroughly:\n\n{topic}\n\n{instruction}",
            max_steps=30 if depth == "shallow" else 50,
            timeout=1200 if depth == "shallow" else 3600, # 20 mins for shallow, 60 mins for deep
            scope=request_scope,
            user_id=user_id,
        )
        for topic in topic_list
    ]

    logger.info(f"Spawning research swarm: {len(specs)} agents, depth={depth}")

    # ── Flux Gate: check agent spawn budget ──
    try:
        from src.core.flux_capacitor import FluxCapacitor
        flux = FluxCapacitor(bot)
        allowed, msg = flux.consume_agents(user_id, len(specs))
        if not allowed:
            return msg
    except Exception as e:
        logger.debug(f"Flux agent check skipped: {e}")

    # ── Progress Callback for CognitionTracker ──
    progress_callback = None
    try:
        from src.bot import globals as bot_globals
        tracker = bot_globals.active_tracker.get()
        if tracker is None:
            active_msg = bot_globals.active_message.get()
            if active_msg and hasattr(active_msg, '_cognition_tracker'):
                tracker = active_msg._cognition_tracker
    except Exception:
        tracker = None

    if tracker:
        _total = len(topic_list)
        _done = 0
        _failed = 0
        _active_detail = ""  # Latest step detail from any agent

        def _build_states():
            """Rebuild tracker states from atomic counters — no race possible."""
            states = {}
            for i, topic in enumerate(topic_list):
                key = f"agent-{i}"
                label = topic[:80]
                if i < _done:
                    states[key] = (label, "✅")
                elif i < _done + _failed:
                    states[key] = (label, "❌")
                elif _active_detail and i == _done + _failed:
                    states[key] = (f"{label} — {_active_detail}", "🔄")
                else:
                    states[key] = (label, "⏳")
            return states

        await tracker.update_agents(_build_states())

        async def progress_callback(result):
            nonlocal _done, _failed
            try:
                if result.status.value == "completed":
                    _done += 1
                else:
                    _failed += 1
                await tracker.update_agents(_build_states())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

        async def step_callback(agent_id, step_num, detail):
            nonlocal _active_detail
            try:
                _active_detail = f"Step {step_num}: {detail}"
                await tracker.update_agents(_build_states())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

    else:
        step_callback = None

    result = await AgentSpawner.spawn_many(specs, bot, AgentStrategy.PARALLEL, progress_callback=progress_callback, step_callback=step_callback)

    outputs = [r.output for r in result.results if r.output and r.status.value == "completed"]

    if not outputs:
        return "Research swarm returned no results."

    if len(outputs) == 1:
        return outputs[0]

    synthesis = await ResultAggregator.synthesize(
        outputs, bot, strategy="llm_merge",
        prompt_hint=f"Research topics: {', '.join(topic_list)}"
    )

    return (
        f"Research swarm completed: {result.successful}/{result.total_agents} agents succeeded "
        f"in {result.total_duration_ms:.0f}ms\n\n{synthesis}"
    )


# ============================================================
# TOOL: agent_status
# Monitor and manage active agents
# ============================================================

@ToolRegistry.register(
    name="agent_status",
    description=(
        "View the status of the agent system: active agents, metrics, "
        "health check, and recent history. Use this to monitor agent activity."
    ),
    parameters={
        "action": "What to show: 'dashboard', 'active', 'history', 'health' (default: dashboard)",
    }
)
async def agent_status(action: str = "dashboard", bot=None) -> str:
    from src.agents.spawner import AgentSpawner
    from src.agents.lifecycle import AgentLifecycle

    lifecycle = AgentLifecycle.get_instance()

    if action == "active":
        active = AgentSpawner.get_active()
        if not active:
            return "No active agents."
        lines = ["Active Agents:"]
        for aid, info in active.items():
            lines.append(f"  {aid}: {info['task']} (steps={info['steps']}, {info['elapsed_ms']:.0f}ms)")
        return "\n".join(lines)

    elif action == "history":
        history = AgentSpawner.get_history(limit=20)
        if not history:
            return "No agent history."
        lines = ["Recent Agent History:"]
        for h in history:
            status_icon = "OK" if h["status"] == "completed" else "FAIL"
            lines.append(f"  [{status_icon}] {h['agent_id']}: {h['task']} ({h['duration_ms']:.0f}ms, {h['steps']} steps)")
        return "\n".join(lines)

    elif action == "health":
        health = lifecycle.health_check()
        status = "HEALTHY" if health.healthy else "DEGRADED"
        lines = [
            f"Health: {status}",
            f"Active Agents: {health.active_agents}",
            f"Avg Response: {health.avg_response_time_ms:.0f}ms",
            f"Error Rate: {health.error_rate:.1%}",
        ]
        if health.warnings:
            lines.append(f"Warnings: {', '.join(health.warnings)}")
        return "\n".join(lines)

    else:  # dashboard
        return lifecycle.get_dashboard()


# ============================================================
# TOOL: spawn_competitive_agents
# Race multiple agents on the same task
# ============================================================

@ToolRegistry.register(
    name="spawn_competitive_agents",
    description=(
        "Spawn multiple agents working on the SAME task and return the first "
        "successful result. Useful for getting the fastest response or for "
        "tasks where different approaches might yield different quality results. "
        "The winning result is returned immediately; other agents are cancelled."
    ),
    parameters={
        "task": "The task for all agents to work on",
        "num_agents": "How many competing agents to spawn (default: 3)",
    }
)
async def spawn_competitive_agents(task: str, num_agents: str = "3",
                                    bot=None, user_id: str = "CORE",
                                    request_scope: str = "CORE") -> str:
    from src.agents.spawner import AgentSpawner, AgentSpec, AgentStrategy

    n = int(num_agents) if isinstance(num_agents, str) else num_agents

    # ── Flux Gate: check agent spawn budget ──
    try:
        from src.core.flux_capacitor import FluxCapacitor
        flux = FluxCapacitor(bot)
        allowed, msg = flux.consume_agents(user_id, n)
        if not allowed:
            return msg
    except Exception as e:
        logger.debug(f"Flux agent check skipped: {e}")

    # ── Retrieve CognitionTracker ──
    tracker = None
    try:
        from src.bot import globals as bot_globals
        tracker = bot_globals.active_tracker.get()
        if tracker is None:
            active_msg = bot_globals.active_message.get()
            if active_msg and hasattr(active_msg, '_cognition_tracker'):
                tracker = active_msg._cognition_tracker
    except Exception as e:
        logger.warning(f"Suppressed {type(e).__name__}: {e}")

    _race_states = {}
    progress_callback = None
    step_callback = None

    if tracker:
        task_preview = task[:60].replace('\n', ' ')
        _done_count = 0
        _fail_count = 0
        _race_active_detail = ""
        _winner = False

        def _build_race_states():
            """Rebuild race tracker states from counters."""
            states = {}
            for i in range(n):
                key = f"racer-{i}"
                label = f"Racer {i+1}: {task_preview}"
                if _winner and i == 0:
                    states[key] = (label, "🏆")
                elif i < _done_count:
                    states[key] = (label, "✅")
                elif i < _done_count + _fail_count:
                    states[key] = (label, "❌")
                elif _winner:
                    states[key] = (label, "⏹")
                elif _race_active_detail and i == _done_count + _fail_count:
                    states[key] = (f"{label} — {_race_active_detail}", "🔄")
                else:
                    states[key] = (label, "⏳")
            return states

        try:
            await tracker.update_agents(_build_race_states())
        except Exception as e:
            logger.warning(f"Suppressed {type(e).__name__}: {e}")

        async def progress_callback(result):
            nonlocal _done_count, _fail_count, _winner
            try:
                if result.status.value == "completed":
                    if not _winner:
                        _winner = True
                    _done_count += 1
                else:
                    _fail_count += 1
                await tracker.update_agents(_build_race_states())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

        async def step_callback(agent_id, step_num, detail):
            nonlocal _race_active_detail
            try:
                _race_active_detail = f"Step {step_num}: {detail}"
                await tracker.update_agents(_build_race_states())
            except Exception as e:
                logger.warning(f"Suppressed {type(e).__name__}: {e}")

    specs = [
        AgentSpec(
            task=task,
            max_steps=50,
            timeout=180,
            scope=request_scope,
            user_id=user_id,
        )
        for _ in range(n)
    ]

    result = await AgentSpawner.spawn_many(
        specs, bot, AgentStrategy.COMPETITIVE,
        progress_callback=progress_callback,
        step_callback=step_callback
    )

    if result.synthesis:
        return f"Competitive race ({n} agents): Winner returned in {result.total_duration_ms:.0f}ms\n\n{result.synthesis}"
    else:
        return "No agent completed successfully in the competitive race."
