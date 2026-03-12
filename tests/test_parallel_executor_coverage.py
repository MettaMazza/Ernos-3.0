"""
Tests for src/agents/parallel_executor.py — Parallel tool execution.
Covers execute_batch, classify_dependencies, _looks_readonly, _extract_resource_key, _execute_single.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.parallel_executor import ToolCall, ToolResult, ParallelToolExecutor


# ═══════════════════════════════════════════════════════════════════════
# ToolCall & ToolResult dataclass tests
# ═══════════════════════════════════════════════════════════════════════

class TestDataClasses:
    def test_tool_call_defaults(self):
        tc = ToolCall(name="search_web", args_str="query")
        assert tc.name == "search_web"
        assert tc.args_str == "query"
        assert tc.kwargs == {}
        assert tc.depends_on == []
        assert tc.index == 0

    def test_tool_result_defaults(self):
        tr = ToolResult(tool_name="search_web", output="result", success=True)
        assert tr.tool_name == "search_web"
        assert tr.duration_ms == 0
        assert tr.index == 0


# ═══════════════════════════════════════════════════════════════════════
# classify_dependencies tests
# ═══════════════════════════════════════════════════════════════════════

class TestClassifyDependencies:
    def test_readonly_tools_independent(self):
        calls = [
            ToolCall(name="search_web", args_str="q1", index=0),
            ToolCall(name="get_weather", args_str="NYC", index=1),
        ]
        ind, dep = ParallelToolExecutor.classify_dependencies(calls)
        assert len(ind) == 2
        assert len(dep) == 0

    def test_mutating_tools_diff_resources(self):
        calls = [
            ToolCall(name="save_memory", args_str="memory A", index=0),
            ToolCall(name="set_goal", args_str="goal B", index=1),
        ]
        ind, dep = ParallelToolExecutor.classify_dependencies(calls)
        assert len(ind) == 1
        assert len(dep) == 1

    def test_mutating_tools_same_resource(self):
        calls = [
            ToolCall(name="save_memory", args_str="same topic", index=0),
            ToolCall(name="save_memory", args_str="same topic", index=1),
        ]
        ind, dep = ParallelToolExecutor.classify_dependencies(calls)
        assert len(ind) == 1
        assert len(dep) == 1

    def test_unknown_readonly_heuristic(self):
        calls = [ToolCall(name="get_custom_thing", args_str="x", index=0)]
        ind, dep = ParallelToolExecutor.classify_dependencies(calls)
        assert len(ind) == 1
        assert len(dep) == 0

    def test_unknown_not_readonly(self):
        calls = [ToolCall(name="do_something", args_str="x", index=0)]
        ind, dep = ParallelToolExecutor.classify_dependencies(calls)
        assert len(ind) == 0
        assert len(dep) == 1


# ═══════════════════════════════════════════════════════════════════════
# _looks_readonly tests
# ═══════════════════════════════════════════════════════════════════════

class TestLooksReadonly:
    @pytest.mark.parametrize("name", [
        "get_info", "search_docs", "read_file", "list_items",
        "check_status", "consult_expert", "review_code", "recall_memory", "find_pattern",
    ])
    def test_readonly_prefixes(self, name):
        assert ParallelToolExecutor._looks_readonly(name) is True

    @pytest.mark.parametrize("name", [
        "create_file", "update_db", "delete_record", "run_command", "execute_plan",
    ])
    def test_not_readonly(self, name):
        assert ParallelToolExecutor._looks_readonly(name) is False


# ═══════════════════════════════════════════════════════════════════════
# _extract_resource_key tests
# ═══════════════════════════════════════════════════════════════════════

class TestExtractResourceKey:
    def test_basic(self):
        call = ToolCall(name="save_memory", args_str="user context data")
        key = ParallelToolExecutor._extract_resource_key(call)
        assert key == "save_memory:user context data"

    def test_truncation(self):
        call = ToolCall(name="save_memory", args_str="x" * 100)
        key = ParallelToolExecutor._extract_resource_key(call)
        assert len(key.split(":")[1]) == 50


# ═══════════════════════════════════════════════════════════════════════
# _execute_single tests
# ═══════════════════════════════════════════════════════════════════════

class TestExecuteSingle:
    @pytest.mark.asyncio
    async def test_success(self):
        call = ToolCall(name="search_web", args_str="test", index=0)
        execute_fn = AsyncMock(return_value=("result text", 1, True))
        result = await ParallelToolExecutor._execute_single(call, execute_fn)
        assert result.success is True
        assert result.output == "result text"
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_none_result(self):
        call = ToolCall(name="search_web", args_str="test", index=0)
        execute_fn = AsyncMock(return_value=(None, 0, True))
        result = await ParallelToolExecutor._execute_single(call, execute_fn)
        assert result.output == ""

    @pytest.mark.asyncio
    async def test_exception(self):
        call = ToolCall(name="search_web", args_str="test", index=0)
        execute_fn = AsyncMock(side_effect=Exception("tool crash"))
        result = await ParallelToolExecutor._execute_single(call, execute_fn)
        assert result.success is False
        assert "Error" in result.output
        assert result.duration_ms >= 0


# ═══════════════════════════════════════════════════════════════════════
# execute_batch tests
# ═══════════════════════════════════════════════════════════════════════

class TestExecuteBatch:
    @pytest.mark.asyncio
    async def test_empty_batch(self):
        result = await ParallelToolExecutor.execute_batch([], AsyncMock())
        assert result == []

    @pytest.mark.asyncio
    async def test_single_call(self):
        calls = [ToolCall(name="search_web", args_str="q", index=0)]
        execute_fn = AsyncMock(return_value=("result", 1, True))
        results = await ParallelToolExecutor.execute_batch(calls, execute_fn)
        assert len(results) == 1
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_parallel_independent(self):
        calls = [
            ToolCall(name="search_web", args_str="q1", index=0),
            ToolCall(name="get_weather", args_str="NYC", index=1),
        ]
        execute_fn = AsyncMock(return_value=("result", 1, True))
        results = await ParallelToolExecutor.execute_batch(calls, execute_fn)
        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_dependent_sequential(self):
        calls = [
            ToolCall(name="save_memory", args_str="same", index=0),
            ToolCall(name="save_memory", args_str="same", index=1),
        ]
        execute_fn = AsyncMock(return_value=("ok", 1, True))
        results = await ParallelToolExecutor.execute_batch(calls, execute_fn)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_mixed_independent_dependent(self):
        calls = [
            ToolCall(name="search_web", args_str="q1", index=0),
            ToolCall(name="save_memory", args_str="same", index=1),
            ToolCall(name="save_memory", args_str="same", index=2),
        ]
        execute_fn = AsyncMock(return_value=("ok", 1, True))
        results = await ParallelToolExecutor.execute_batch(calls, execute_fn)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_parallel_exception_handling(self):
        """When a parallel tool raises an exception inside asyncio.gather."""
        calls = [
            ToolCall(name="search_web", args_str="q1", index=0),
            ToolCall(name="get_weather", args_str="NYC", index=1),
        ]
        # First call succeeds, second raises
        call_count = 0
        async def flaky_fn(name, args):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("API down")
            return ("ok", 1, True)

        results = await ParallelToolExecutor.execute_batch(calls, flaky_fn)
        assert len(results) == 2
        # One should succeed, one should fail - but gather catches exceptions
        # The exception is wrapped by _execute_single's try/except
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(successes) == 1
        assert len(failures) == 1

    @pytest.mark.asyncio
    async def test_only_dependent(self):
        calls = [
            ToolCall(name="do_something", args_str="a", index=0),
            ToolCall(name="run_mutation", args_str="b", index=1),
        ]
        execute_fn = AsyncMock(return_value=("result", 1, True))
        results = await ParallelToolExecutor.execute_batch(calls, execute_fn)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_gather_returns_exception_object(self):
        """When _execute_single itself raises (not the user fn), gather captures it as Exception."""
        calls = [
            ToolCall(name="search_web", args_str="q1", index=0),
            ToolCall(name="get_weather", args_str="NYC", index=1),
        ]
        execute_fn = AsyncMock(return_value=("ok", 1, True))

        call_count = 0
        original = ParallelToolExecutor._execute_single

        @classmethod
        async def _patched_execute(cls, call, fn):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Unexpected executor crash")
            return await original.__func__(cls, call, fn)

        with patch.object(ParallelToolExecutor, "_execute_single", _patched_execute):
            results = await ParallelToolExecutor.execute_batch(calls, execute_fn)

        assert len(results) == 2
        failures = [r for r in results if not r.success]
        assert len(failures) == 1
        assert "Error" in failures[0].output

