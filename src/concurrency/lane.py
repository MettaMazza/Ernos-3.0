"""
Lane Queue — Serial-default concurrent task execution with failure isolation.

Each lane has its own asyncio queue and worker loop. An exception in one lane
does NOT affect other lanes. Tasks are serial by default with opt-in parallelism.
"""
import asyncio
import logging
import time
from typing import Callable, Coroutine, Dict, Optional

from src.concurrency.types import LanePolicy, LanePriority, LaneTask

logger = logging.getLogger("Concurrency.LaneQueue")


class _Lane:
    """
    Internal lane implementation.
    
    Each lane has its own asyncio.Queue and one or more worker tasks.
    Serial lanes (max_parallel=1) guarantee one-at-a-time execution.
    """

    def __init__(self, name: str, policy: LanePolicy):
        self.name = name
        self.policy = policy
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: list = []
        self._active_count = 0
        self._total_processed = 0
        self._total_failed = 0

    async def start(self):
        """Start worker tasks for this lane."""
        for i in range(self.policy.max_parallel):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        logger.info(
            f"Lane '{self.name}' started with {self.policy.max_parallel} worker(s)"
        )

    async def stop(self):
        """Gracefully stop all workers."""
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()
        logger.info(f"Lane '{self.name}' stopped")

    async def submit(self, task: LaneTask, coro: Coroutine) -> LaneTask:
        """
        Submit a task to this lane.
        
        Enforces backpressure: rejects if queue exceeds max depth.
        """
        if self._queue.qsize() >= self.policy.max_queue_depth:
            task.status = "failed"
            task.error = (
                f"Lane '{self.name}' queue full "
                f"({self._queue.qsize()}/{self.policy.max_queue_depth})"
            )
            logger.warning(f"Backpressure: {task.error}")
            coro.close()  # Prevent RuntimeWarning: coroutine never awaited
            return task

        task.lane_name = self.name
        await self._queue.put((task, coro))
        logger.debug(f"Task {task.id} queued in lane '{self.name}'")
        return task

    async def _worker_loop(self, worker_id: int):
        """Main worker loop — pulls tasks from queue and executes them."""
        while True:
            try:
                task, coro = await self._queue.get()
            except asyncio.CancelledError:
                return

            task.status = "running"
            self._active_count += 1

            try:
                # Execute with timeout
                task.result = await asyncio.wait_for(
                    coro, timeout=self.policy.timeout_seconds
                )
                task.status = "done"
                self._total_processed += 1
            except asyncio.TimeoutError:
                task.status = "failed"
                task.error = f"Timeout after {self.policy.timeout_seconds}s"
                self._total_failed += 1
                logger.error(
                    f"Task {task.id} timed out in lane '{self.name}' "
                    f"after {self.policy.timeout_seconds}s"
                )
            except asyncio.CancelledError:
                task.status = "cancelled"
                return
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                self._total_failed += 1
                logger.error(
                    f"Task {task.id} failed in lane '{self.name}': {e}"
                )

                # Retry if policy allows
                if self.policy.retry_on_failure:
                    logger.info(f"Retrying task {task.id}...")
                    task.status = "queued"
                    # We can't retry the same coroutine since it's been consumed.
                    # In practice, retries need a factory. For now, just log.
                    logger.warning(
                        f"Retry not supported yet for task {task.id} "
                        f"(coroutine already consumed)"
                    )
            finally:
                self._active_count -= 1
                self._queue.task_done()

    @property
    def stats(self) -> dict:
        """Return current lane statistics."""
        return {
            "name": self.name,
            "queue_depth": self._queue.qsize(),
            "active": self._active_count,
            "total_processed": self._total_processed,
            "total_failed": self._total_failed,
            "max_parallel": self.policy.max_parallel,
            "max_queue_depth": self.policy.max_queue_depth,
        }


class LaneQueue:
    """
    Lane-based concurrent task executor.
    
    Pre-configured lanes:
    - chat: serial (1), for user message processing
    - autonomy: serial (1), for autonomy loop
    - gaming: serial (1), for gaming actions
    - background: parallel (3), for maintenance tasks
    
    Usage:
        lane_queue = LaneQueue()
        await lane_queue.start()
        task = await lane_queue.submit("chat", some_coroutine(), user_id="123")
    """

    # Default lane configurations — expanded for multi-agent architecture
    DEFAULT_LANES = {
        "chat": LanePolicy(max_parallel=1, timeout_seconds=300, max_queue_depth=20),
        "autonomy": LanePolicy(max_parallel=1, timeout_seconds=600, max_queue_depth=10),
        "gaming": LanePolicy(max_parallel=1, timeout_seconds=180, max_queue_depth=20),
        "background": LanePolicy(max_parallel=5, timeout_seconds=600, max_queue_depth=30),
        # New agent-specific lanes
        "agents": LanePolicy(max_parallel=10, timeout_seconds=300, max_queue_depth=50),
        "research": LanePolicy(max_parallel=5, timeout_seconds=600, max_queue_depth=20),
        "coding": LanePolicy(max_parallel=3, timeout_seconds=600, max_queue_depth=10),
        "verification": LanePolicy(max_parallel=5, timeout_seconds=120, max_queue_depth=30),
    }

    def __init__(self):
        self._lanes: Dict[str, _Lane] = {}
        self._tasks: Dict[str, LaneTask] = {}  # task_id -> task
        self._started = False

        # Pre-create default lanes
        for name, policy in self.DEFAULT_LANES.items():
            self._lanes[name] = _Lane(name, policy)

    async def start(self):
        """Start all lane workers."""
        if self._started:
            return
        for lane in self._lanes.values():
            await lane.start()
        self._started = True
        logger.info(f"LaneQueue started with {len(self._lanes)} lanes")

    async def stop(self):
        """Stop all lane workers."""
        for lane in self._lanes.values():
            await lane.stop()
        self._started = False
        logger.info("LaneQueue stopped")

    def add_lane(self, name: str, policy: LanePolicy) -> None:
        """Add a custom lane (must be done before start)."""
        self._lanes[name] = _Lane(name, policy)
        logger.info(f"Added custom lane '{name}' with policy {policy}")

    async def submit(
        self,
        lane_name: str,
        coro: Coroutine,
        user_id: str = "",
        channel_id: str = "",
        priority: LanePriority = LanePriority.NORMAL,
    ) -> LaneTask:
        """
        Submit a coroutine to a named lane for execution.
        
        Args:
            lane_name: Which lane to submit to
            coro: The async callable to execute
            user_id: Originating user ID
            channel_id: Originating channel ID
            priority: Task priority level
            
        Returns:
            LaneTask with status tracking
            
        Raises:
            ValueError: If lane_name is not registered or user exceeds rate limit
        """
        if lane_name not in self._lanes:
            coro.close()  # Prevent RuntimeWarning: coroutine never awaited
            raise ValueError(
                f"Unknown lane '{lane_name}'. "
                f"Available lanes: {list(self._lanes.keys())}"
            )

        # Per-user rate limiting: max 3 queued tasks per user per lane
        MAX_USER_TASKS_PER_LANE = 15
        if user_id:
            user_queued = sum(
                1 for tid, t in self._tasks.items()
                if t.user_id == user_id
                and t.lane_name == lane_name
                and t.status == "queued"
            )
            if user_queued >= MAX_USER_TASKS_PER_LANE:
                coro.close()
                raise ValueError(
                    f"User {user_id} has {user_queued} queued tasks in lane "
                    f"'{lane_name}' (max {MAX_USER_TASKS_PER_LANE}). "
                    f"Wait for existing tasks to complete."
                )

        task = LaneTask(
            lane_name=lane_name,
            priority=priority,
            user_id=user_id,
            channel_id=channel_id,
        )

        self._tasks[task.id] = task
        await self._lanes[lane_name].submit(task, coro)
        return task

    def cancel(self, task_id: str) -> bool:
        """
        Cancel a queued task (running tasks cannot be cancelled this way).
        
        Returns:
            True if task was found and marked cancelled
        """
        task = self._tasks.get(task_id)
        if task and task.status == "queued":
            task.status = "cancelled"
            return True
        return False

    def get_status(self, task_id: str) -> Optional[LaneTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_lane_stats(self) -> Dict[str, dict]:
        """Return statistics for all lanes."""
        return {name: lane.stats for name, lane in self._lanes.items()}

    # === Compatibility Wrappers (preserve existing processing_users API) ===

    def is_user_processing(self, user_id: int, channel_id: int = None) -> bool:
        """Check if a user has an active task in the chat lane."""
        for task in self._tasks.values():
            if (
                task.user_id == str(user_id)
                and task.status == "running"
                and task.lane_name == "chat"
            ):
                if channel_id is None or task.channel_id == str(channel_id):
                    return True
        return False
