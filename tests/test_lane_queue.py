"""
Tests for the Lane Queue System (Synapse Bridge v3.1).
"""
import asyncio
import pytest

from src.concurrency.types import LanePolicy, LanePriority, LaneTask
from src.concurrency.lane import LaneQueue, _Lane


# === LaneTask Tests ===

class TestLaneTask:
    """Tests for the LaneTask dataclass."""

    def test_creation_defaults(self):
        task = LaneTask()
        assert len(task.id) == 8
        assert task.lane_name == ""
        assert task.priority == LanePriority.NORMAL
        assert task.status == "queued"

    def test_unique_ids(self):
        t1 = LaneTask()
        t2 = LaneTask()
        assert t1.id != t2.id


# === LanePolicy Tests ===

class TestLanePolicy:
    """Tests for the LanePolicy configuration."""

    def test_serial_default(self):
        policy = LanePolicy()
        assert policy.max_parallel == 1  # Serial by default

    def test_custom_parallel(self):
        policy = LanePolicy(max_parallel=3)
        assert policy.max_parallel == 3


# === LaneQueue Tests ===

class TestLaneQueue:
    """Tests for the main LaneQueue executor."""

    @pytest.fixture
    async def lane_queue(self):
        lq = LaneQueue()
        await lq.start()
        yield lq
        await lq.stop()

    async def test_start_and_stop(self):
        lq = LaneQueue()
        assert lq._started is False
        await lq.start()
        assert lq._started is True
        await lq.stop()
        assert lq._started is False

    async def test_default_lanes_exist(self, lane_queue):
        stats = lane_queue.get_lane_stats()
        assert "chat" in stats
        assert "autonomy" in stats
        assert "gaming" in stats
        assert "background" in stats

    async def test_serial_execution_order(self, lane_queue):
        """Verify serial lane executes tasks one at a time."""
        results = []

        async def task_fn(value):
            await asyncio.sleep(0.05)
            results.append(value)
            return value

        t1 = await lane_queue.submit("chat", task_fn(1), user_id="u1")
        t2 = await lane_queue.submit("chat", task_fn(2), user_id="u1")
        t3 = await lane_queue.submit("chat", task_fn(3), user_id="u1")

        # Wait for all to complete
        await asyncio.sleep(0.5)

        assert results == [1, 2, 3]

    async def test_parallel_execution(self, lane_queue):
        """Verify background lane runs tasks concurrently."""
        start_times = []

        async def task_fn(index):
            import time
            start_times.append((index, time.time()))
            await asyncio.sleep(0.1)
            return index

        await lane_queue.submit("background", task_fn(1))
        await lane_queue.submit("background", task_fn(2))
        await lane_queue.submit("background", task_fn(3))

        await asyncio.sleep(0.3)

        # All 3 should have started within ~0.05s of each other (parallel)
        if len(start_times) == 3:
            times = [t for _, t in sorted(start_times)]
            # Gap between first and last start should be small
            assert times[-1] - times[0] < 0.1

    async def test_failure_isolation(self, lane_queue):
        """Verify failure in one lane doesn't affect others."""
        chat_result = []
        
        async def failing_task():
            raise RuntimeError("boom")

        async def normal_task():
            await asyncio.sleep(0.05)
            chat_result.append("ok")
            return "ok"

        # Submit failing task to gaming lane
        await lane_queue.submit("gaming", failing_task(), user_id="u1")
        # Submit normal task to chat lane
        await lane_queue.submit("chat", normal_task(), user_id="u1")

        await asyncio.sleep(0.3)

        # Chat should still succeed
        assert chat_result == ["ok"]

    async def test_task_status_tracking(self, lane_queue):
        """Verify task status progresses through lifecycle."""
        async def slow_task():
            await asyncio.sleep(0.1)
            return "done"

        task = await lane_queue.submit("chat", slow_task(), user_id="u1")
        task_ref = lane_queue.get_status(task.id)
        assert task_ref is not None
        
        await asyncio.sleep(0.3)
        assert task_ref.status in ("done", "running")

    async def test_unknown_lane_raises(self, lane_queue):
        """Verify submission to unknown lane raises ValueError."""
        coro = (lambda: None)()  # not a real coroutine

        async def dummy():
            return "test"

        coro = dummy()
        try:
            with pytest.raises(ValueError, match="Unknown lane"):
                await lane_queue.submit("nonexistent", coro, user_id="u1")
        finally:
            coro.close()

    async def test_lane_stats_reporting(self, lane_queue):
        stats = lane_queue.get_lane_stats()
        assert isinstance(stats, dict)
        assert "chat" in stats
        assert "queue_depth" in stats["chat"]
        assert "active" in stats["chat"]
        assert "total_processed" in stats["chat"]

    async def test_backpressure(self):
        """Verify queue rejects when full."""
        lq = LaneQueue()
        # Create a custom lane with tiny queue
        lq.add_lane("tiny", LanePolicy(max_parallel=1, max_queue_depth=2))
        await lq.start()

        hold = asyncio.Event()

        async def blocking_task():
            await hold.wait()
            return "done"

        try:
            # Fill the lane (1 running + 2 queued = at capacity)
            await lq.submit("tiny", blocking_task())
            await asyncio.sleep(0.05)  # Let first task start
            await lq.submit("tiny", blocking_task())
            await lq.submit("tiny", blocking_task())

            # This should be rejected via backpressure
            overflow_coro = blocking_task()
            try:
                overflow = await lq.submit("tiny", overflow_coro)
                assert overflow.status == "failed"
                assert "queue full" in overflow.error.lower()
            except Exception:
                overflow_coro.close()
                raise
        finally:
            hold.set()
            await asyncio.sleep(0.1)
            await lq.stop()

    async def test_timeout(self, lane_queue):
        """Verify tasks that exceed timeout are failed."""
        # Create a lane with very short timeout
        lane_queue.add_lane("fast", LanePolicy(max_parallel=1, timeout_seconds=1))
        # Start the new lane's workers
        await lane_queue._lanes["fast"].start()

        async def slow_task():
            await asyncio.sleep(10)  # Way over timeout
            return "should not reach"

        task = await lane_queue.submit("fast", slow_task())
        await asyncio.sleep(2)

        assert task.status == "failed"
        assert "Timeout" in task.error

    async def test_add_custom_lane(self):
        lq = LaneQueue()
        lq.add_lane("custom", LanePolicy(max_parallel=5, timeout_seconds=30))
        await lq.start()
        
        stats = lq.get_lane_stats()
        assert "custom" in stats
        assert stats["custom"]["max_parallel"] == 5
        
        await lq.stop()

    def test_is_user_processing(self):
        lq = LaneQueue()
        # No tasks — should return False
        assert lq.is_user_processing(123) is False
