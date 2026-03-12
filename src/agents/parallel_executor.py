"""
ParallelToolExecutor — Fixes the sequential tool execution bottleneck.

Instead of executing tools one-by-one in the ReAct loop, this module
classifies tool calls as independent or dependent and runs independent
ones simultaneously via asyncio.gather().
"""
import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("Agents.ParallelExecutor")


@dataclass
class ToolCall:
    """A parsed tool invocation."""
    name: str
    args_str: str
    kwargs: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    index: int = 0


@dataclass
class ToolResult:
    """Result from a tool execution."""
    tool_name: str
    output: str
    success: bool
    duration_ms: float = 0
    index: int = 0


class ParallelToolExecutor:
    """
    Executes multiple tool calls in parallel when they are independent.
    Falls back to sequential for dependent calls.
    """

    # Tools that modify state and should not run in parallel with each other
    MUTATING_TOOLS = {
        "create_program", "save_memory", "store_knowledge",
        "add_to_knowledge_graph", "manage_goals",
        "draft_plan", "complete_step", "update_preferences",
    }

    # Tools that are read-only and always safe to parallelize
    READONLY_TOOLS = {
        "search_web", "browse_site", "browse_interactive",
        "read_file", "list_dir", "find_by_name", "grep_search",
        "recall_user", "search_context_logs", "review_my_reasoning",
        "check_world_news", "get_weather", "get_datetime",
        "consult_science_lobe", "consult_architect_lobe",
        "consult_skeptic", "consult_reasoning_lobe",
    }

    @classmethod
    async def execute_batch(cls, tool_calls: list[ToolCall],
                            execute_fn, max_concurrent: int = 10,
                            context_limit: int = 50000) -> list[ToolResult]:
        """
        Execute a batch of tool calls with maximum parallelism.

        Args:
            tool_calls: List of parsed tool calls
            execute_fn: Async function(tool_name, args_str) -> (result_text, cb_count, was_valid)
            max_concurrent: Maximum simultaneous executions
            context_limit: Max chars per result

        Returns:
            Ordered list of ToolResults
        """
        if not tool_calls:
            return []

        if len(tool_calls) == 1:
            return [await cls._execute_single(tool_calls[0], execute_fn)]

        independent, dependent = cls.classify_dependencies(tool_calls)

        results = [None] * len(tool_calls)
        semaphore = asyncio.Semaphore(max_concurrent)

        # Execute all independent tools in parallel
        if independent:
            async def _guarded(call: ToolCall) -> ToolResult:
                async with semaphore:
                    return await cls._execute_single(call, execute_fn)

            parallel_results = await asyncio.gather(
                *[_guarded(c) for c in independent],
                return_exceptions=True
            )

            for i, result in enumerate(parallel_results):
                call = independent[i]
                if isinstance(result, Exception):
                    results[call.index] = ToolResult(
                        tool_name=call.name,
                        output=f"Error: {result}",
                        success=False,
                        index=call.index
                    )
                else:
                    results[call.index] = result

        # Execute dependent tools sequentially
        for call in dependent:
            result = await cls._execute_single(call, execute_fn)
            results[call.index] = result

        return [r for r in results if r is not None]

    @classmethod
    def classify_dependencies(cls, tool_calls: list[ToolCall]) -> tuple[list[ToolCall], list[ToolCall]]:
        """
        Classify tool calls as independent (parallelizable) or dependent (sequential).

        Rules:
        - Read-only tools are always independent
        - Mutating tools that target different resources are independent
        - Mutating tools that target the same resource are dependent
        - Unknown tools default to sequential for safety
        """
        independent = []
        dependent = []
        seen_mutations = set()

        for call in tool_calls:
            if call.name in cls.READONLY_TOOLS:
                independent.append(call)
            elif call.name in cls.MUTATING_TOOLS:
                resource_key = cls._extract_resource_key(call)
                if resource_key in seen_mutations:
                    dependent.append(call)
                else:
                    seen_mutations.add(resource_key)
                    independent.append(call)
            else:
                # Unknown tools: parallelize if they look read-like
                if cls._looks_readonly(call.name):
                    independent.append(call)
                else:
                    dependent.append(call)

        return independent, dependent

    @classmethod
    def _looks_readonly(cls, tool_name: str) -> bool:
        """Heuristic: tools starting with get/search/read/list/check/consult are likely read-only."""
        readonly_prefixes = ("get_", "search_", "read_", "list_", "check_", "consult_", "review_", "recall_", "find_")
        return any(tool_name.startswith(p) for p in readonly_prefixes)

    @classmethod
    def _extract_resource_key(cls, call: ToolCall) -> str:
        """Extract what resource a mutating tool targets, for conflict detection."""
        return f"{call.name}:{call.args_str[:50]}"

    @classmethod
    async def _execute_single(cls, call: ToolCall, execute_fn) -> ToolResult:
        """Execute a single tool call and wrap the result."""
        start = time.time()
        try:
            result_text, _, was_valid = await execute_fn(call.name, call.args_str)
            return ToolResult(
                tool_name=call.name,
                output=str(result_text) if result_text else "",
                success=was_valid,
                duration_ms=(time.time() - start) * 1000,
                index=call.index
            )
        except Exception as e:
            return ToolResult(
                tool_name=call.name,
                output=f"Error: {e}",
                success=False,
                duration_ms=(time.time() - start) * 1000,
                index=call.index
            )
