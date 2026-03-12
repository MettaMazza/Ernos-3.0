"""
ExecutionPlanner — Decomposes complex requests into DAGs of
parallel and sequential agent tasks.

Uses LLM to analyze a request and create an execution plan,
then runs it through the AgentSpawner with proper dependency tracking.
"""
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("Agents.Planner")


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    id: str = ""
    description: str = ""
    agent_task: str = ""
    depends_on: list[str] = field(default_factory=list)
    tools_hint: list[str] = field(default_factory=list)
    model_hint: Optional[str] = None
    timeout: float = 1800.0  # 30 minutes — agents need real time for complex tasks
    result: Optional[str] = None
    status: str = "pending"


@dataclass
class ExecutionStage:
    """A group of steps that can run in parallel."""
    stage_number: int = 0
    steps: list[PlanStep] = field(default_factory=list)
    is_parallel: bool = True


@dataclass
class ExecutionPlan:
    """A DAG of execution stages."""
    id: str = ""
    original_request: str = ""
    stages: list[ExecutionStage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "pending"
    final_output: str = ""
    total_agents_spawned: int = 0
    total_duration_ms: float = 0


class ExecutionPlanner:
    """
    Analyzes complex requests and creates execution plans
    with parallel/sequential stages, then executes them.
    """

    @classmethod
    async def plan(cls, request: str, bot=None,
                   context: str = "") -> ExecutionPlan:
        """
        Use LLM to decompose a request into an execution plan.
        """
        plan = ExecutionPlan(
            id=f"plan-{int(time.time())}",
            original_request=request
        )

        if not bot:
            logger.warning("No bot passed to planner — cannot decompose, using single step")
            plan.stages = [ExecutionStage(
                stage_number=1,
                steps=[PlanStep(id="s1-1", description="Execute directly",
                                agent_task=request)],
                is_parallel=False
            )]
            return plan

        engine = bot.engine_manager.get_active_engine()
        planning_prompt = cls._build_planning_prompt(request, context)

        logger.info(f"Planner: decomposing request ({len(request)} chars): {request[:120]}")

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, engine.generate_response, planning_prompt, []
        )

        if not response or len(response.strip()) < 10:
            logger.error(f"Planner got empty/tiny LLM response: '{response}'")
            raise RuntimeError(f"Planner LLM returned empty response")

        logger.debug(f"Planner raw LLM response ({len(response)} chars):\n{response[:600]}")

        plan.stages = cls._parse_plan_response(response)

        if not plan.stages:
            # Parsing failed — log the FULL response so we can debug
            logger.error(
                f"Planner could not parse any stages from LLM response. "
                f"Full response ({len(response)} chars):\n{response}"
            )
            # Still fall back, but now it's LOUD — you'll see this in logs
            plan.stages = [ExecutionStage(
                stage_number=1,
                steps=[PlanStep(id="s1-1",
                                description=f"[FALLBACK] {request[:60]}",
                                agent_task=request)],
                is_parallel=False
            )]
        else:
            total_steps = sum(len(s.steps) for s in plan.stages)
            logger.info(f"Planner decomposed into {len(plan.stages)} stages, {total_steps} total steps")
            for stage in plan.stages:
                for step in stage.steps:
                    logger.info(f"  Stage {stage.stage_number} | {step.id}: {step.description}")

        return plan

    @classmethod
    async def execute_plan(cls, plan: ExecutionPlan, bot=None,
                           user_id: str = "CORE",
                           scope: str = "CORE",
                           progress_callback=None,
                           step_callback=None) -> ExecutionPlan:
        """
        Execute an execution plan through the AgentSpawner.
        Runs stages sequentially, steps within stages in parallel.

        Args:
            progress_callback: Optional async callable(stage_num, step_id, status_emoji)
                               called as steps change status.
            step_callback: Optional async callable(agent_id, step, detail)
                           called each inner agent step for live tool visibility.
        """
        from src.agents.spawner import AgentSpawner, AgentSpec, AgentStrategy
        from src.agents.aggregator import ResultAggregator

        start = time.time()
        plan.status = "running"
        previous_stage_output = ""

        for stage in plan.stages:
            stage_start = time.time()
            logger.info(f"Executing stage {stage.stage_number} "
                       f"({len(stage.steps)} steps, parallel={stage.is_parallel})")

            specs = []
            for step in stage.steps:
                step.status = "running"
                # Fire progress callback — step is now running
                if progress_callback:
                    try:
                        await progress_callback(stage.stage_number, step.id, "🔄")
                    except Exception as e:
                        logger.debug(f"Progress callback failed: {e}")

                task_with_context = step.agent_task
                if previous_stage_output:
                    task_with_context = (
                        f"Previous stage findings:\n{previous_stage_output}\n\n"
                        f"Your task: {step.agent_task}"
                    )

                specs.append(AgentSpec(
                    task=task_with_context,
                    context={"plan_id": plan.id, "step_id": step.id},
                    max_steps=50,
                    timeout=step.timeout,
                    model_hint=step.model_hint,
                    scope=scope,
                    user_id=user_id,
                ))

            if stage.is_parallel and len(specs) > 1:
                strategy = AgentStrategy.PARALLEL
            else:
                strategy = AgentStrategy.PIPELINE

            agg_result = await AgentSpawner.spawn_many(specs, bot, strategy, step_callback=step_callback)
            plan.total_agents_spawned += agg_result.total_agents

            for i, step in enumerate(stage.steps):
                if i < len(agg_result.results):
                    agent_result = agg_result.results[i]
                    step.result = agent_result.output
                    step.status = "completed" if agent_result.status.value == "completed" else "failed"
                    if step.status == "failed":
                        logger.warning(f"Step {step.id} failed: {agent_result.error}")
                else:
                    step.status = "failed"
                    logger.warning(f"Step {step.id} has no matching result (index {i} >= {len(agg_result.results)})")

                # Fire progress callback — step completed or failed
                if progress_callback:
                    try:
                        emoji = "✅" if step.status == "completed" else "❌"
                        await progress_callback(stage.stage_number, step.id, emoji)
                    except Exception as e:
                        logger.debug(f"Progress callback failed: {e}")

            successful_outputs = [
                s.result for s in stage.steps
                if s.status == "completed" and s.result
            ]

            if len(successful_outputs) > 1:
                previous_stage_output = await ResultAggregator.synthesize(
                    successful_outputs, bot, strategy="llm_merge",
                    prompt_hint=plan.original_request
                )
            elif successful_outputs:
                previous_stage_output = successful_outputs[0]
            else:
                logger.error(f"Stage {stage.stage_number} produced NO successful outputs")
                previous_stage_output = "[Stage produced no results]"

        plan.final_output = previous_stage_output or ""
        plan.status = "completed"
        plan.total_duration_ms = (time.time() - start) * 1000
        return plan

    @classmethod
    def _build_planning_prompt(cls, request: str, context: str = "") -> str:
        # Build as a list to avoid the broken ternary-concatenation bug
        parts = [
            "You are an execution planner for a multi-agent AI system.",
            "Decompose the following request into MULTIPLE stages with sub-tasks.",
            "",
            "CRITICAL RULES:",
            "- You MUST create at least 2 stages",
            "- Stage 1 should gather/research (parallel tasks for different aspects)",
            "- Final stage should synthesize/combine all findings",
            "- Each stage contains tasks that run IN PARALLEL (independent of each other)",
            "- Stages run SEQUENTIALLY (stage 2 waits for stage 1 to finish)",
            "- Each task must be self-contained with clear, specific instructions",
            "- NEVER create just 1 stage with 1 task — that defeats the purpose of planning",
            "- Split research across MULTIPLE parallel agents (one per topic/subtopic)",
            "- Be specific: tell each agent exactly what to search, analyze, or produce",
            "",
            "Output format (strict JSON only, no other text):",
            "```json",
            "{",
            '  "stages": [',
            '    {',
            '      "stage": 1,',
            '      "parallel": true,',
            '      "tasks": [',
            '        {"id": "s1-1", "description": "Research aspect X", "task": "Search for and thoroughly analyze X. Focus on key findings, data, and relevant details."},',
            '        {"id": "s1-2", "description": "Research aspect Y", "task": "Search for and thoroughly analyze Y. Focus on key findings, data, and relevant details."}',
            '      ]',
            '    },',
            '    {',
            '      "stage": 2,',
            '      "parallel": false,',
            '      "tasks": [',
            '        {"id": "s2-1", "description": "Synthesize comprehensive report", "task": "Using all findings from stage 1, create a comprehensive and well-structured report that addresses the original request."}',
            '      ]',
            '    }',
            '  ]',
            "}",
            "```",
            "",
        ]

        if context:
            parts.append(f"Additional context:\n{context}")
            parts.append("")

        parts.append(f"Request to decompose:\n{request}")
        parts.append("")
        parts.append("Your execution plan (JSON only, minimum 2 stages with multiple tasks in stage 1):")

        return "\n".join(parts)

    @classmethod
    def _parse_plan_response(cls, response: str) -> list[ExecutionStage]:
        """Parse LLM response into execution stages."""
        stages = []

        if not response:
            logger.error("_parse_plan_response called with empty response")
            return stages

        # Strategy 1: Extract from code fence
        json_match = re.search(r'```(?:json)?\s*(\{.+\})\s*```', response, re.DOTALL)

        if not json_match:
            # Strategy 2: Find JSON object with "stages" key using balanced braces
            start_idx = response.find('"stages"')
            if start_idx == -1:
                start_idx = response.find("'stages'")
            if start_idx >= 0:
                # Walk backwards to find opening brace
                brace_start = response.rfind('{', 0, start_idx)
                if brace_start >= 0:
                    # Walk forward with balanced brace counting
                    depth = 0
                    end_idx = brace_start
                    for i in range(brace_start, len(response)):
                        if response[i] == '{':
                            depth += 1
                        elif response[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end_idx = i + 1
                                break
                    if end_idx > brace_start:
                        raw_json = response[brace_start:end_idx]
                        logger.debug(f"Extracted JSON via brace matching: {raw_json[:200]}")
                        json_match = type('Match', (), {'group': lambda self, n=1: raw_json})()

        if not json_match:
            logger.error(f"No JSON found in planner response ({len(response)} chars): {response[:400]}")
            return stages

        raw_json = json_match.group(1)

        try:
            plan_data = json.loads(raw_json)
        except json.JSONDecodeError as e1:
            logger.warning(f"JSON parse attempt 1 failed: {e1}")
            try:
                # Clean trailing commas and retry
                cleaned = re.sub(r',\s*([}\]])', r'\1', raw_json)
                plan_data = json.loads(cleaned)
            except json.JSONDecodeError as e2:
                logger.error(f"JSON parse failed even after cleanup: {e2}\nRaw JSON: {raw_json[:500]}")
                return stages

        if "stages" not in plan_data:
            logger.error(f"Parsed JSON has no 'stages' key. Keys: {list(plan_data.keys())}")
            return stages

        for stage_data in plan_data["stages"]:
            steps = []
            for task_data in stage_data.get("tasks", []):
                steps.append(PlanStep(
                    id=task_data.get("id", f"auto-{len(steps)}"),
                    description=task_data.get("description", ""),
                    agent_task=task_data.get("task", task_data.get("description", "")),
                    timeout=task_data.get("timeout", 1800.0),
                ))

            if steps:
                stages.append(ExecutionStage(
                    stage_number=stage_data.get("stage", len(stages) + 1),
                    steps=steps,
                    is_parallel=stage_data.get("parallel", True),
                ))

        if not stages:
            logger.error(f"Parsed JSON but got 0 stages. plan_data: {json.dumps(plan_data)[:500]}")

        logger.info(f"Parsed {len(stages)} stages with {sum(len(s.steps) for s in stages)} total steps")
        return stages
