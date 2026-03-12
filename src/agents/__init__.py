"""
Agents subsystem — Multi-agent orchestration for Ernos.

Provides sub-agent spawning, parallel tool execution, inter-agent
communication, result aggregation, execution planning, model routing,
and lifecycle management.
"""
from src.agents.spawner import AgentSpawner, AgentSpec, AgentResult, AgentStrategy, AgentStatus
from src.agents.parallel_executor import ParallelToolExecutor, ToolCall, ToolResult
from src.agents.bus import AgentBus, AgentMessage
from src.agents.aggregator import ResultAggregator
from src.agents.planner import ExecutionPlanner, ExecutionPlan
from src.agents.router import ModelRouter, ModelProfile
from src.agents.lifecycle import AgentLifecycle

__all__ = [
    "AgentSpawner", "AgentSpec", "AgentResult", "AgentStrategy", "AgentStatus",
    "ParallelToolExecutor", "ToolCall", "ToolResult",
    "AgentBus", "AgentMessage",
    "ResultAggregator",
    "ExecutionPlanner", "ExecutionPlan",
    "ModelRouter", "ModelProfile",
    "AgentLifecycle",
]
