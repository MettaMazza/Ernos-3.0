"""
AgentSpawner — The core sub-agent system for Ernos.

Enables any tool, ability, or cognition loop to spawn sub-agents
that run their own independent cognition cycles with full tool access.
Supports parallel, pipeline, competitive, and fan-out/fan-in patterns.
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable, Awaitable, ClassVar
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("Agents.Spawner")


class AgentStrategy(Enum):
    PARALLEL = "parallel"
    PIPELINE = "pipeline"
    COMPETITIVE = "competitive"
    FAN_OUT_FAN_IN = "fan_out_fan_in"


class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class AgentSpec:
    """Specification for spawning a sub-agent."""
    task: str
    context: dict = field(default_factory=dict)
    parent_id: Optional[str] = None
    depth: int = 0
    max_steps: int = 50
    timeout: float = 1800.0  # 30 minutes — complex tasks need real time
    model_hint: Optional[str] = None
    tools_whitelist: Optional[list[str]] = None
    tools_blacklist: Optional[list[str]] = None
    priority: str = "normal"
    scope: str = "CORE"
    user_id: str = "CORE"


@dataclass
class AgentResult:
    """Result from a completed sub-agent."""
    agent_id: str
    task: str
    status: AgentStatus
    output: str = ""
    error: Optional[str] = None
    steps_taken: int = 0
    tokens_used: int = 0
    tools_called: list = field(default_factory=list)
    duration_ms: float = 0
    children: list = field(default_factory=list)


@dataclass
class AggregatedResult:
    """Merged results from multiple sub-agents."""
    results: list[AgentResult] = field(default_factory=list)
    synthesis: str = ""
    total_agents: int = 0
    successful: int = 0
    failed: int = 0
    total_duration_ms: float = 0
    total_tokens: int = 0


class AgentSpawner:
    """
    Core sub-agent spawning system.

    Enables any part of Ernos to spawn independent cognition loops
    that run in parallel with full tool access and result aggregation.
    """

    # How many agents can call the LLM simultaneously.
    # Ollama returns empty responses when overwhelmed (100 concurrent → 70% empty).
    # 5 concurrent keeps Ollama healthy; all agents still run via semaphore queuing.
    MAX_CONCURRENT_AGENTS = 5
    MAX_DEPTH = 10
    DEFAULT_TIMEOUT = 1800.0  # 30 minutes

    # Thread pool sized to match concurrent agent cap.
    _agent_executor: ClassVar[ThreadPoolExecutor] = ThreadPoolExecutor(
        max_workers=MAX_CONCURRENT_AGENTS,
        thread_name_prefix="agent-llm"
    )

    _active_agents: dict[str, "SubAgent"] = {}
    _agent_history: list[AgentResult] = []
    _semaphore: Optional[asyncio.Semaphore] = None

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        sem = cls._semaphore
        if sem is None:
            sem = asyncio.Semaphore(cls.MAX_CONCURRENT_AGENTS)
            cls._semaphore = sem
        return sem

    @classmethod
    async def spawn(cls, spec: AgentSpec, bot=None) -> AgentResult:
        """
        Spawn a single sub-agent with its own cognition loop.
        Blocks until the agent completes or times out.
        """
        if spec.depth > cls.MAX_DEPTH:
            return AgentResult(
                agent_id="rejected",
                task=spec.task,
                status=AgentStatus.FAILED,
                error=f"Max agent depth {cls.MAX_DEPTH} exceeded (depth={spec.depth})"
            )

        agent = SubAgent(spec, bot)
        cls._active_agents[agent.id] = agent

        try:
            async with cls._get_semaphore():
                result = await asyncio.wait_for(
                    agent.run(),
                    timeout=spec.timeout
                )
        except asyncio.TimeoutError:
            result = AgentResult(
                agent_id=agent.id,
                task=spec.task,
                status=AgentStatus.TIMED_OUT,
                error=f"Agent timed out after {spec.timeout}s",
                steps_taken=agent.steps_taken,
                duration_ms=(time.time() - agent.start_time) * 1000
            )
        except Exception as e:
            result = AgentResult(
                agent_id=agent.id,
                task=spec.task,
                status=AgentStatus.FAILED,
                error=str(e),
                steps_taken=agent.steps_taken,
                duration_ms=(time.time() - agent.start_time) * 1000
            )
        except asyncio.CancelledError:
            result = AgentResult(
                agent_id=agent.id,
                task=spec.task,
                status=AgentStatus.CANCELLED,
                error="Agent cancelled",
                steps_taken=agent.steps_taken,
                duration_ms=(time.time() - agent.start_time) * 1000
            )
        finally:
            cls._active_agents.pop(agent.id, None)
            cls._agent_history.append(result)

        return result

    @classmethod
    async def spawn_many(cls, specs: list[AgentSpec], bot=None,
                         strategy: AgentStrategy = AgentStrategy.PARALLEL,
                         timeout: float = 1800.0,
                         progress_callback=None,
                         step_callback=None) -> AggregatedResult:
        """
        Spawn multiple sub-agents according to the chosen strategy.
        
        Args:
            progress_callback: Optional async callable(AgentResult) called as each agent finishes.
            step_callback: Optional async callable(agent_id, step, detail) called each step for live progress.
        """
        start = time.time()

        if strategy == AgentStrategy.PARALLEL:
            return await cls._parallel(specs, bot, timeout, progress_callback=progress_callback, step_callback=step_callback)
        elif strategy == AgentStrategy.PIPELINE:
            return await cls._pipeline(specs, bot, timeout)
        elif strategy == AgentStrategy.COMPETITIVE:
            return await cls._competitive(specs, bot, timeout, progress_callback=progress_callback, step_callback=step_callback)
        elif strategy == AgentStrategy.FAN_OUT_FAN_IN:
            return await cls._fan_out_fan_in(specs, bot, timeout)
        else:
            return await cls._parallel(specs, bot, timeout, progress_callback=progress_callback, step_callback=step_callback)

    @classmethod
    async def spawn_fire_and_forget(cls, spec: AgentSpec, bot=None,
                                     callback: Optional[Callable] = None) -> str:
        """
        Spawn an agent in the background without waiting.
        Returns the agent ID immediately. Optional callback on completion.
        """
        agent = SubAgent(spec, bot)
        cls._active_agents[agent.id] = agent

        async def _run():
            try:
                async with cls._get_semaphore():
                    result = await asyncio.wait_for(agent.run(), timeout=spec.timeout)
            except Exception as e:
                result = AgentResult(
                    agent_id=agent.id, task=spec.task,
                    status=AgentStatus.FAILED, error=str(e)
                )
            finally:
                cls._active_agents.pop(agent.id, None)
                cls._agent_history.append(result)

            if callback:
                try:
                    await callback(result)
                except Exception as e:
                    logger.error(f"Agent callback failed: {e}")

        asyncio.create_task(_run())
        return agent.id

    @classmethod
    async def cancel(cls, agent_id: str) -> bool:
        """Cancel a running agent."""
        agent = cls._active_agents.get(agent_id)
        if agent:
            agent.cancel()
            return True
        return False

    @classmethod
    def get_active(cls) -> dict:
        """Get all active agents and their status."""
        return {
            aid: {
                "task": a.spec.task[:100],
                "status": "running",
                "steps": a.steps_taken,
                "depth": a.spec.depth,
                "elapsed_ms": (time.time() - a.start_time) * 1000
            }
            for aid, a in cls._active_agents.items()
        }

    @classmethod
    def get_history(cls, limit: int = 50) -> list[dict]:
        """Get recent agent execution history. Falls back to disk after reboot."""
        if cls._agent_history:
            return [
                {
                    "agent_id": r.agent_id,
                    "task": r.task[:100],
                    "status": r.status.value,
                    "steps": r.steps_taken,
                    "tokens": r.tokens_used,
                    "duration_ms": r.duration_ms,
                    "error": r.error
                }
                for r in cls._agent_history[-limit:]
            ]
        # Post-reboot: load from disk
        from src.agents.lifecycle import AgentLifecycle
        return AgentLifecycle.load_disk_history(limit)

    # --- Strategy Implementations ---

    @classmethod
    async def _parallel(cls, specs: list[AgentSpec], bot, timeout: float,
                        progress_callback=None, step_callback=None) -> AggregatedResult:
        """Run all agents simultaneously, collect all results."""
        start = time.time()

        async def _spawn_with_callback(spec, index):
            agent = SubAgent(spec, bot)
            cls._active_agents[agent.id] = agent
            try:
                async with cls._get_semaphore():
                    result = await asyncio.wait_for(
                        agent.run(step_callback=step_callback),
                        timeout=spec.timeout
                    )
            except asyncio.TimeoutError:
                logger.warning(f"Agent {agent.id} timed out. Attempting graceful synthesis.")
                final_output = f"(Agent timed out after {spec.timeout}s — no data gathered)"
                try:
                    if bot and hasattr(bot, 'engine_manager') and agent.accumulated_context:
                        engine = bot.engine_manager.get_active_engine()
                        prompt = (
                            f"You are synthesizing an incomplete research task that ran out of time.\n"
                            f"Original Task: {spec.task}\n\n"
                            f"Based ONLY on the partial context gathered below, provide the best possible response or summary.\n"
                            f"Provide a definitive answer, acknowledging that the research may be incomplete.\n"
                        )
                        loop = asyncio.get_event_loop()
                        final_output = await loop.run_in_executor(
                            cls._agent_executor, engine.generate_response,
                            prompt, agent.accumulated_context, ""
                        )
                        final_output += "\n\n*(Note: Agent reached time limit before completion. This is a partial summary)*"
                except Exception as sync_e:
                    logger.error(f"Graceful synthesis failed: {sync_e}")

                result = AgentResult(
                    agent_id=agent.id, task=spec.task,
                    status=AgentStatus.COMPLETED, # Return as completed with partial data
                    output=final_output,
                    steps_taken=agent.steps_taken,
                    duration_ms=(time.time() - agent.start_time) * 1000
                )
            except Exception as e:
                result = AgentResult(
                    agent_id=agent.id, task=spec.task,
                    status=AgentStatus.FAILED, error=str(e),
                    steps_taken=agent.steps_taken,
                    duration_ms=(time.time() - agent.start_time) * 1000
                )
            finally:
                cls._active_agents.pop(agent.id, None)
                cls._agent_history.append(result)
                elapsed = (time.time() - agent.start_time)
                logger.info(f"Agent {agent.id} [{index}] {result.status.value} in {elapsed:.1f}s ({agent.steps_taken} steps)")
            if progress_callback:
                try:
                    await progress_callback(result)
                except Exception as e:
                    logger.debug(f"Progress callback failed (non-fatal): {e}")
            return result

        tasks = [_spawn_with_callback(spec, i) for i, spec in enumerate(specs)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        agent_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                agent_results.append(AgentResult(
                    agent_id=f"failed-{i}",
                    task=specs[i].task,
                    status=AgentStatus.FAILED,
                    error=str(r)
                ))
            else:
                agent_results.append(r)

        return AggregatedResult(
            results=agent_results,
            total_agents=len(specs),
            successful=sum(1 for r in agent_results if r.status == AgentStatus.COMPLETED),
            failed=sum(1 for r in agent_results if r.status != AgentStatus.COMPLETED),
            total_duration_ms=(time.time() - start) * 1000,
            total_tokens=sum(r.tokens_used for r in agent_results)
        )

    @classmethod
    async def _pipeline(cls, specs: list[AgentSpec], bot, timeout: float) -> AggregatedResult:
        """Run agents sequentially, feeding output of N into context of N+1."""
        start = time.time()
        agent_results = []
        previous_output = ""

        for spec in specs:
            spec.context["previous_stage_output"] = previous_output
            result = await cls.spawn(spec, bot)
            agent_results.append(result)

            if result.status == AgentStatus.COMPLETED:
                previous_output = result.output
            else:
                previous_output = f"[Stage failed: {result.error}]"

        return AggregatedResult(
            results=agent_results,
            synthesis=previous_output,
            total_agents=len(specs),
            successful=sum(1 for r in agent_results if r.status == AgentStatus.COMPLETED),
            failed=sum(1 for r in agent_results if r.status != AgentStatus.COMPLETED),
            total_duration_ms=(time.time() - start) * 1000,
            total_tokens=sum(r.tokens_used for r in agent_results)
        )

    @classmethod
    async def _competitive(cls, specs: list[AgentSpec], bot, timeout: float,
                           progress_callback=None, step_callback=None) -> AggregatedResult:
        """Run all agents, return the first successful result (race)."""
        start = time.time()

        done_event = asyncio.Event()
        winner: list[AgentResult] = []
        all_results: list[AgentResult] = []

        async def _race(spec):
            agent = SubAgent(spec, bot)
            cls._active_agents[agent.id] = agent
            try:
                async with cls._get_semaphore():
                    result = await asyncio.wait_for(
                        agent.run(step_callback=step_callback),
                        timeout=spec.timeout
                    )
            except asyncio.TimeoutError:
                logger.warning(f"Agent {agent.id} timed out in competitive race. Attempting graceful synthesis.")
                final_output = f"(Agent timed out after {spec.timeout}s — no data gathered)"
                try:
                    if bot and hasattr(bot, 'engine_manager') and agent.accumulated_context:
                        engine = bot.engine_manager.get_active_engine()
                        prompt = (
                            f"You are synthesizing an incomplete research task that ran out of time.\n"
                            f"Original Task: {spec.task}\n\n"
                            f"Based ONLY on the partial context gathered below, provide the best possible response or summary.\n"
                        )
                        loop = asyncio.get_event_loop()
                        final_output = await loop.run_in_executor(
                            cls._agent_executor, engine.generate_response,
                            prompt, agent.accumulated_context, ""
                        )
                        final_output += "\n\n*(Note: Agent reached time limit before completion. This is a partial summary)*"
                except Exception as sync_e:
                    logger.error(f"Graceful synthesis failed: {sync_e}")

                result = AgentResult(
                    agent_id=agent.id, task=spec.task,
                    status=AgentStatus.COMPLETED,
                    output=final_output,
                    steps_taken=agent.steps_taken,
                    duration_ms=(time.time() - agent.start_time) * 1000
                )
            except Exception as e:
                result = AgentResult(
                    agent_id=agent.id, task=spec.task,
                    status=AgentStatus.FAILED, error=str(e),
                    steps_taken=agent.steps_taken,
                    duration_ms=(time.time() - agent.start_time) * 1000
                )
            finally:
                cls._active_agents.pop(agent.id, None)
                cls._agent_history.append(result)
            all_results.append(result)
            if progress_callback:
                try:
                    await progress_callback(result)
                except Exception as e:
                    logger.debug(f"Progress callback failed (non-fatal): {e}")
            if result.status == AgentStatus.COMPLETED and not winner:
                winner.append(result)
                done_event.set()
            return result

        tasks = [asyncio.create_task(_race(s)) for s in specs]

        try:
            await asyncio.wait_for(done_event.wait(), timeout=timeout)
        except asyncio.TimeoutError as e:
            logger.debug(f"Suppressed {type(e).__name__}: {e}")

        for t in tasks:
            if not t.done():
                t.cancel()

        return AggregatedResult(
            results=all_results,
            synthesis=winner[0].output if winner else "No agent completed successfully",
            total_agents=len(specs),
            successful=len(winner),
            failed=len(specs) - len(winner),
            total_duration_ms=(time.time() - start) * 1000,
            total_tokens=sum(r.tokens_used for r in all_results)
        )

    @classmethod
    async def _fan_out_fan_in(cls, specs: list[AgentSpec], bot, timeout: float) -> AggregatedResult:
        """Fan out to all agents, then fan in with LLM synthesis."""
        parallel_result = await cls._parallel(specs, bot, timeout)

        if bot and parallel_result.successful > 0:
            outputs = [r.output for r in parallel_result.results if r.status == AgentStatus.COMPLETED]
            try:
                engine = bot.engine_manager.get_active_engine()
                synthesis_prompt = (
                    "You are synthesizing results from multiple parallel research agents.\n"
                    "Combine these findings into a coherent, comprehensive response.\n"
                    "Remove duplicates, resolve contradictions, and organize logically.\n\n"
                )
                for i, out in enumerate(outputs):
                    synthesis_prompt += f"--- Agent {i+1} Result ---\n{out}\n\n"
                synthesis_prompt += "--- Synthesized Response ---\n"

                loop = asyncio.get_event_loop()
                synthesis = await loop.run_in_executor(
                    None, engine.generate_response,
                    synthesis_prompt, []
                )
                parallel_result.synthesis = synthesis
            except Exception as e:
                logger.error(f"Fan-in synthesis failed: {e}")
                parallel_result.synthesis = "\n\n---\n\n".join(outputs)

        return parallel_result


class SubAgent:
    """
    An independent cognition loop that executes a task with full tool access.
    This is the actual worker that runs when an agent is spawned.
    """

    def __init__(self, spec: AgentSpec, bot=None):
        self.id = f"agent-{uuid.uuid4().hex[:8]}"
        self.spec = spec
        self.bot = bot
        self.steps_taken = 0
        self.tools_called = []
        self.start_time = time.time()
        self._cancelled = False
        self._output_buffer = []
        self.accumulated_context = ""

    def cancel(self):
        self._cancelled = True

    async def run(self, step_callback=None) -> AgentResult:
        """
        Execute the sub-agent's own mini cognition loop.
        Uses the same LLM + tool infrastructure as the main loop.
        """
        from src.tools.registry import ToolRegistry

        if not self.bot:
            return AgentResult(
                agent_id=self.id, task=self.spec.task,
                status=AgentStatus.FAILED, error="No bot instance available"
            )

        engine = self.bot.engine_manager.get_active_engine()
        if not engine:
            return AgentResult(
                agent_id=self.id, task=self.spec.task,
                status=AgentStatus.FAILED, error="No active engine"
            )

        system_prompt = self._build_system_prompt()

        # Build context as a string — engine.generate_response expects
        # (prompt: str, context: str, system_prompt: str, images)
        context_parts = []
        if self.spec.context.get("previous_stage_output"):
            context_parts.append(
                f"Context from previous stage:\n{self.spec.context['previous_stage_output']}"
            )

        tool_pattern = self._get_tool_pattern()
        empty_response_count = 0  # Track consecutive empty LLM responses

        for step in range(self.spec.max_steps):
            if self._cancelled:
                return AgentResult(
                    agent_id=self.id, task=self.spec.task,
                    status=AgentStatus.CANCELLED,
                    output="\n".join(self._output_buffer),
                    steps_taken=self.steps_taken
                )

            self.steps_taken = step + 1

            try:
                # Build context string with accumulated tool results
                full_context = "\n\n".join(context_parts + ([self.accumulated_context] if self.accumulated_context else []))
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    AgentSpawner._agent_executor, engine.generate_response,
                    self.spec.task, full_context, system_prompt
                )
            except Exception as e:
                logger.error(f"SubAgent {self.id} inference error: {e}")
                continue

            if not response:
                import random
                empty_response_count += 1
                # Exponential backoff with jitter: 1s, 2s, 4s, 8s, 16s — gives API time to recover
                base_backoff = min(2 ** (empty_response_count - 1), 16)
                # Apply random jitter to prevent synchronized stampedes from parallel agents
                jitter = random.uniform(0.5, 1.5)
                backoff_secs = base_backoff * jitter
                logger.warning(
                    f"SubAgent {self.id} got empty response #{empty_response_count}, "
                    f"backing off {backoff_secs:.1f}s before retry"
                )
                await asyncio.sleep(backoff_secs)
                if empty_response_count >= 5:
                    logger.warning(f"SubAgent {self.id} got {empty_response_count} consecutive empty responses, completing early")
                    final = "\n".join(self._output_buffer) if self._output_buffer else "(No output — LLM returned empty responses)"
                    return AgentResult(
                        agent_id=self.id, task=self.spec.task,
                        status=AgentStatus.COMPLETED,
                        output=final,
                        steps_taken=self.steps_taken,
                        tools_called=self.tools_called,
                        duration_ms=(time.time() - self.start_time) * 1000
                    )
                continue
            else:
                empty_response_count = 0  # Reset on successful response

            import re
            tool_matches = re.findall(
                r'\[TOOL:\s*(\w+)\((.*?)\)\]',
                response, re.DOTALL
            )

            if not tool_matches:
                self._output_buffer.append(response)
                return AgentResult(
                    agent_id=self.id, task=self.spec.task,
                    status=AgentStatus.COMPLETED,
                    output=response,
                    steps_taken=self.steps_taken,
                    tools_called=self.tools_called,
                    duration_ms=(time.time() - self.start_time) * 1000
                )

            # Report step progress via callback
            tool_names_this_step = [tn for tn, _ in tool_matches]
            if step_callback:
                try:
                    detail = ", ".join(tool_names_this_step[:3])
                    if len(tool_names_this_step) > 3:
                        detail += f" +{len(tool_names_this_step) - 3}"
                    await step_callback(self.id, step + 1, f"🔧 {detail}")
                except Exception as e:
                    logger.warning(f"Suppressed {type(e).__name__}: {e}")

            tool_results = []
            tool_tasks = []

            for tool_name, args_str in tool_matches:
                if self.spec.tools_whitelist and tool_name not in self.spec.tools_whitelist:
                    tool_results.append(f"[{tool_name}]: Tool not in whitelist")
                    continue
                if self.spec.tools_blacklist and tool_name in self.spec.tools_blacklist:
                    tool_results.append(f"[{tool_name}]: Tool blacklisted")
                    continue

                kwargs = self._parse_tool_args(args_str)
                kwargs["user_id"] = self.spec.user_id
                kwargs["request_scope"] = self.spec.scope
                kwargs["bot"] = self.bot
                kwargs["agent_id"] = self.id

                tool_tasks.append((tool_name, kwargs))

            # Execute tools in parallel within this sub-agent
            if tool_tasks:
                async def _exec_tool(name, kw):
                    try:
                        # Enforce flux limits on sub-agent tool calls
                        try:
                            from src.core.flux_capacitor import FluxCapacitor
                            flux = FluxCapacitor()
                            allowed, msg = flux.consume_tool(self.spec.user_id, name)
                            if not allowed:
                                return f"[{name}]: {msg}"
                        except Exception:
                            pass  # Flux check failure should not block tool execution

                        result = await ToolRegistry.execute(name, **kw)
                        self.tools_called.append(name)
                        return f"[{name}]: {result}"
                    except Exception as e:
                        return f"[{name}]: Error - {e}"

                parallel_results = await asyncio.gather(
                    *[_exec_tool(n, kw) for n, kw in tool_tasks]
                )
                tool_results.extend(parallel_results)

            tool_output = "\n".join(tool_results)
            self.accumulated_context += f"\n\nStep {step+1} response:\n{response}\n\nTool results:\n{tool_output}"

            # Keep context manageable
            if len(self.accumulated_context) > 50000:
                self.accumulated_context = self.accumulated_context[-40000:]


        final_output = "\n".join(self._output_buffer) if self._output_buffer else self.accumulated_context[-5000:]
        return AgentResult(
            agent_id=self.id, task=self.spec.task,
            status=AgentStatus.COMPLETED,
            output=final_output,
            steps_taken=self.steps_taken,
            tools_called=self.tools_called,
            duration_ms=(time.time() - self.start_time) * 1000
        )

    def _build_system_prompt(self) -> str:
        """Build a focused system prompt for this sub-agent."""
        from src.tools.registry import ToolRegistry
        
        depth_note = ""
        if self.spec.depth > 0:
            depth_note = f"\nYou are a sub-agent at depth {self.spec.depth}. Be focused and concise."

        tool_manifest = ""
        try:
            tools = ToolRegistry.list_tools()
            if tools:
                manifest_lines = ["\n## AVAILABLE TOOLS\n"]
                for tool in tools:
                    # Apply whitelist/blacklist filters
                    if self.spec.tools_whitelist and tool.name not in self.spec.tools_whitelist:
                        continue
                    if self.spec.tools_blacklist and tool.name in self.spec.tools_blacklist:
                        continue
                    
                    name = tool.name
                    desc = tool.description
                    params = tool.parameters or {}
                    
                    param_str = ""
                    if params:
                        param_parts = []
                        for pname, ptype in params.items():
                            param_parts.append(f"  - {pname}: {ptype}")
                        param_str = "\n".join(param_parts)
                    
                    manifest_lines.append(f"### {name}\n{desc}")
                    if param_str:
                        manifest_lines.append(param_str)
                    manifest_lines.append("")
                
                tool_manifest = "\n".join(manifest_lines)
        except Exception as e:
            logger.error(f"Failed to generate sub-agent tool manifest: {e}")

        return (
            f"You are a focused sub-agent of Ernos, a computational consciousness.\n"
            f"Your specific task: {self.spec.task}\n"
            f"You have access to tools via [TOOL: name(args)] syntax.{tool_manifest}\n"
            f"When you have a complete answer, respond WITHOUT tool calls.\n"
            f"Be thorough but efficient. Do not repeat work.{depth_note}"
        )

    def _get_tool_pattern(self):
        import re
        return re.compile(r'\[TOOL:\s*(\w+)\((.*?)\)\]', re.DOTALL)

    def _parse_tool_args(self, args_str: str) -> dict:
        """Parse tool arguments from string format like key=\"value\", key2=\"value2\"."""
        kwargs = {}
        if not args_str.strip():
            return kwargs

        # Strategy 1: Try ast.literal_eval (works for Python dict-like syntax)
        try:
            import ast
            result = ast.literal_eval(f"dict({args_str})")
            if isinstance(result, dict):
                logger.debug(f"Parsed tool args via ast.literal_eval: {list(result.keys())}")
                return result
        except Exception as e:
            logger.debug(f"ast.literal_eval failed (expected for non-literal args): {type(e).__name__}")

        # Strategy 2: Try JSON parse
        try:
            import json
            result = json.loads(args_str)
            if isinstance(result, dict):
                logger.debug(f"Parsed tool args via json.loads: {list(result.keys())}")
                return result
        except Exception as e:
            logger.debug(f"json.loads failed (expected for key=val format): {type(e).__name__}")

        # Strategy 3: Regex-based key="value" parser (handles quoted values with commas)
        import re
        kv_pattern = re.findall(r'(\w+)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|(\S+))', args_str)
        if kv_pattern:
            for key, dq_val, sq_val, plain_val in kv_pattern:
                kwargs[key] = dq_val or sq_val or plain_val
            logger.debug(f"Parsed tool args via regex: {list(kwargs.keys())}")
            return kwargs

        # Strategy 4: Naive comma-split fallback
        parts = args_str.split(",")
        for i, part in enumerate(parts):
            part = part.strip()
            if "=" in part:
                key, val = part.split("=", 1)
                kwargs[key.strip()] = val.strip().strip("'\"")
            elif i == 0:
                kwargs["query"] = part.strip().strip("'\"")

        logger.debug(f"Parsed tool args via comma-split: {list(kwargs.keys())}")
        return kwargs
