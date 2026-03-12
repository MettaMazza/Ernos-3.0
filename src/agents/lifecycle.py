"""
AgentLifecycle — Manages agent creation, monitoring, timeout,
cancellation, recovery, and observability.

Provides a centralized view of all agent activity across
the system with metrics and health monitoring.
"""
import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("Agents.Lifecycle")

HISTORY_PATH = "memory/core/agent_history.jsonl"


@dataclass
class AgentMetrics:
    """Cumulative metrics for agent system."""
    total_spawned: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_timed_out: int = 0
    total_cancelled: int = 0
    total_tokens_used: int = 0
    total_tool_calls: int = 0
    avg_duration_ms: float = 0
    peak_concurrent: int = 0
    current_concurrent: int = 0
    agents_by_depth: dict = field(default_factory=lambda: defaultdict(int))
    agents_by_strategy: dict = field(default_factory=lambda: defaultdict(int))
    errors_by_type: dict = field(default_factory=lambda: defaultdict(int))


@dataclass
class AgentHealthCheck:
    """Health status of the agent system."""
    healthy: bool = True
    active_agents: int = 0
    queue_depth: int = 0
    avg_response_time_ms: float = 0
    error_rate: float = 0.0
    warnings: list[str] = field(default_factory=list)


class AgentLifecycle:
    """
    Centralized lifecycle management for all agents.
    Singleton pattern - one instance manages the entire agent ecosystem.
    """

    _instance = None
    _metrics = AgentMetrics()
    _recent_durations: list[float] = []
    _max_duration_history = 500
    _error_window: list[float] = []
    _error_window_seconds = 300  # 5 minute error rate window

    @classmethod
    def get_instance(cls) -> "AgentLifecycle":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record_spawn(self, agent_id: str, depth: int = 0, strategy: str = "single"):
        """Record that an agent was spawned."""
        self._metrics.total_spawned += 1
        self._metrics.current_concurrent += 1
        self._metrics.agents_by_depth[depth] = self._metrics.agents_by_depth.get(depth, 0) + 1
        self._metrics.agents_by_strategy[strategy] = self._metrics.agents_by_strategy.get(strategy, 0) + 1

        if self._metrics.current_concurrent > self._metrics.peak_concurrent:
            self._metrics.peak_concurrent = self._metrics.current_concurrent

    def record_completion(self, agent_id: str, duration_ms: float,
                          tokens_used: int = 0, tool_calls: int = 0,
                          task: str = "", user_id: str = ""):
        """Record that an agent completed successfully."""
        self._metrics.total_completed += 1
        self._metrics.current_concurrent = max(0, self._metrics.current_concurrent - 1)
        self._metrics.total_tokens_used += tokens_used
        self._metrics.total_tool_calls += tool_calls
        self._update_duration(duration_ms)
        self._persist_event(agent_id, "completed", duration_ms, task, user_id)

    def record_failure(self, agent_id: str, error_type: str, duration_ms: float = 0,
                       task: str = "", user_id: str = ""):
        """Record that an agent failed."""
        self._metrics.total_failed += 1
        self._metrics.current_concurrent = max(0, self._metrics.current_concurrent - 1)
        self._metrics.errors_by_type[error_type] = self._metrics.errors_by_type.get(error_type, 0) + 1
        self._error_window.append(time.time())
        self._update_duration(duration_ms)
        self._persist_event(agent_id, f"failed:{error_type}", duration_ms, task, user_id)

    def record_timeout(self, agent_id: str, duration_ms: float = 0,
                       task: str = "", user_id: str = ""):
        """Record that an agent timed out."""
        self._metrics.total_timed_out += 1
        self._metrics.current_concurrent = max(0, self._metrics.current_concurrent - 1)
        self._error_window.append(time.time())
        self._update_duration(duration_ms)
        self._persist_event(agent_id, "timeout", duration_ms, task, user_id)

    def record_cancellation(self, agent_id: str):
        """Record that an agent was cancelled."""
        self._metrics.total_cancelled += 1
        self._metrics.current_concurrent = max(0, self._metrics.current_concurrent - 1)

    def health_check(self) -> AgentHealthCheck:
        """Perform a health check on the agent system."""
        from src.agents.spawner import AgentSpawner

        check = AgentHealthCheck()
        check.active_agents = self._metrics.current_concurrent
        check.avg_response_time_ms = self._metrics.avg_duration_ms

        # Calculate error rate in the last 5 minutes
        now = time.time()
        self._error_window = [t for t in self._error_window
                              if now - t < self._error_window_seconds]
        total_recent = self._metrics.total_spawned  # simplified
        if total_recent > 0:
            check.error_rate = len(self._error_window) / max(total_recent, 1)

        # Warnings
        if check.active_agents > 30:
            check.warnings.append(f"High concurrent agents: {check.active_agents}")
        if check.error_rate > 0.3:
            check.warnings.append(f"High error rate: {check.error_rate:.1%}")
        if check.avg_response_time_ms > 60000:
            check.warnings.append(f"Slow avg response: {check.avg_response_time_ms:.0f}ms")

        check.healthy = len(check.warnings) == 0
        return check

    def get_metrics(self) -> dict:
        """Get all metrics as a dictionary."""
        return {
            "total_spawned": self._metrics.total_spawned,
            "total_completed": self._metrics.total_completed,
            "total_failed": self._metrics.total_failed,
            "total_timed_out": self._metrics.total_timed_out,
            "total_cancelled": self._metrics.total_cancelled,
            "total_tokens_used": self._metrics.total_tokens_used,
            "total_tool_calls": self._metrics.total_tool_calls,
            "avg_duration_ms": round(self._metrics.avg_duration_ms, 1),
            "peak_concurrent": self._metrics.peak_concurrent,
            "current_concurrent": self._metrics.current_concurrent,
            "success_rate": (
                self._metrics.total_completed / max(self._metrics.total_spawned, 1)
            ),
            "agents_by_depth": dict(self._metrics.agents_by_depth),
            "agents_by_strategy": dict(self._metrics.agents_by_strategy),
            "top_errors": dict(
                sorted(self._metrics.errors_by_type.items(),
                       key=lambda x: x[1], reverse=True)[:10]
            ),
        }

    def get_dashboard(self) -> str:
        """Get a formatted dashboard string for display."""
        m = self._metrics
        health = self.health_check()

        status = "HEALTHY" if health.healthy else "DEGRADED"
        lines = [
            f"=== Agent System Dashboard ===",
            f"Status: {status}",
            f"Active: {m.current_concurrent} | Peak: {m.peak_concurrent}",
            f"Total: {m.total_spawned} spawned | {m.total_completed} completed | {m.total_failed} failed",
            f"Timeouts: {m.total_timed_out} | Cancelled: {m.total_cancelled}",
            f"Avg Duration: {m.avg_duration_ms:.0f}ms",
            f"Tokens Used: {m.total_tokens_used:,}",
            f"Tool Calls: {m.total_tool_calls:,}",
            f"Success Rate: {m.total_completed / max(m.total_spawned, 1):.1%}",
        ]

        if health.warnings:
            lines.append(f"Warnings: {', '.join(health.warnings)}")

        return "\n".join(lines)

    def reset_metrics(self):
        """Reset all metrics (for testing or new session)."""
        self._metrics = AgentMetrics()
        self._recent_durations = []
        self._error_window = []

    def _update_duration(self, duration_ms: float):
        if duration_ms > 0:
            self._recent_durations.append(duration_ms)
            if len(self._recent_durations) > self._max_duration_history:
                self._recent_durations = self._recent_durations[-self._max_duration_history:]
            self._metrics.avg_duration_ms = (
                sum(self._recent_durations) / len(self._recent_durations)
            )

    @staticmethod
    def _persist_event(agent_id: str, status: str, duration_ms: float,
                       task: str = "", user_id: str = ""):
        """Append a completion/failure record to disk so it survives reboots."""
        try:
            os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
            entry = {
                "agent_id": agent_id,
                "status": status,
                "task": task[:200] if task else "",
                "duration_ms": round(duration_ms, 1),
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }
            with open(HISTORY_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist agent event: {e}")

    @staticmethod
    def load_disk_history(limit: int = 50) -> list[dict]:
        """Load recent agent history from disk. Used after reboots."""
        if not os.path.exists(HISTORY_PATH):
            return []
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
            entries = []
            for line in lines[-(limit):]:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return entries
        except Exception as e:
            logger.warning(f"Failed to load agent history: {e}")
            return []
