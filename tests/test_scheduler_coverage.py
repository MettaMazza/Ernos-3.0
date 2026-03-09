"""
Tests for TaskScheduler
Targeting 95%+ coverage for src/scheduler.py
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import src.scheduler as scheduler_module
from src.scheduler import TaskScheduler, get_scheduler, setup_backup_scheduler


class TestTaskSchedulerInit:
    """Tests for TaskScheduler initialization."""
    
    def test_init(self):
        """Test basic initialization."""
        ts = TaskScheduler()
        assert ts._tasks == {}
        assert ts._running is False
        assert ts._loop_task is None


class TestAddDailyTask:
    """Tests for add_daily_task method."""
    
    def test_add_daily_task(self):
        """Test adding a daily task."""
        ts = TaskScheduler()
        
        async def dummy():
            pass
        
        ts.add_daily_task("test_task", 14, 30, dummy)
        
        assert "test_task" in ts._tasks
        assert ts._tasks["test_task"]["hour"] == 14
        assert ts._tasks["test_task"]["minute"] == 30
        assert ts._tasks["test_task"]["func"] == dummy
        assert ts._tasks["test_task"]["last_run"] is None
    
    def test_add_multiple_tasks(self):
        """Test adding multiple tasks."""
        ts = TaskScheduler()
        
        async def task1():
            pass
        
        async def task2():
            pass
        
        ts.add_daily_task("task1", 10, 0, task1)
        ts.add_daily_task("task2", 22, 30, task2)
        
        assert len(ts._tasks) == 2


class TestRemoveTask:
    """Tests for remove_task method."""
    
    def test_remove_existing_task(self):
        """Test removing an existing task."""
        ts = TaskScheduler()
        
        async def dummy():
            pass
        
        ts.add_daily_task("test_task", 14, 30, dummy)
        assert "test_task" in ts._tasks
        
        ts.remove_task("test_task")
        assert "test_task" not in ts._tasks
    
    def test_remove_nonexistent_task(self):
        """Test removing a task that doesn't exist."""
        ts = TaskScheduler()
        
        # Should not raise
        ts.remove_task("nonexistent")
        assert True  # No exception: error handled gracefully


class TestCheckAndRun:
    """Tests for _check_and_run method."""
    
    @pytest.mark.asyncio
    async def test_check_and_run_executes_task(self):
        """Test task execution when time matches."""
        ts = TaskScheduler()
        
        executed = []
        
        async def task():
            executed.append(True)
        
        now = datetime.now()
        ts.add_daily_task("test", now.hour, now.minute, task)
        
        await ts._check_and_run()
        
        assert len(executed) == 1
        assert ts._tasks["test"]["last_run"] is not None
    
    @pytest.mark.asyncio
    async def test_check_and_run_skips_wrong_time(self):
        """Test that tasks don't run at wrong time."""
        ts = TaskScheduler()
        
        executed = []
        
        async def task():
            executed.append(True)
        
        # Schedule for a different hour
        now = datetime.now()
        ts.add_daily_task("test", (now.hour + 2) % 24, now.minute, task)
        
        await ts._check_and_run()
        
        assert len(executed) == 0
    
    @pytest.mark.asyncio
    async def test_check_and_run_skips_already_run_today(self):
        """Test that tasks only run once per day."""
        ts = TaskScheduler()
        
        executed = []
        
        async def task():
            executed.append(True)
        
        now = datetime.now()
        ts.add_daily_task("test", now.hour, now.minute, task)
        
        # Run once
        await ts._check_and_run()
        assert len(executed) == 1
        
        # Run again - should not execute
        await ts._check_and_run()
        assert len(executed) == 1  # Still 1
    
    @pytest.mark.asyncio
    async def test_check_and_run_handles_exception(self):
        """Test exception handling in task execution."""
        ts = TaskScheduler()
        
        async def failing_task():
            raise ValueError("Task failed!")
        
        now = datetime.now()
        ts.add_daily_task("test", now.hour, now.minute, failing_task)
        
        # Should not raise
        await ts._check_and_run()
        assert True  # No exception: error handled gracefully
        
        # Task should still be marked as run to prevent retry loops
        # (Actually looking at code, it doesn't mark on failure - that's expected)


class TestSchedulerLoop:
    """Tests for _scheduler_loop method."""
    
    @pytest.mark.asyncio
    async def test_scheduler_loop_runs(self):
        """Test that scheduler loop runs and can be stopped."""
        ts = TaskScheduler()
        ts._running = True
        
        # Mock sleep to return immediately and then stop
        call_count = [0]
        original_sleep = asyncio.sleep
        
        async def mock_sleep(seconds):
            call_count[0] += 1
            if call_count[0] >= 2:
                ts._running = False
            await original_sleep(0.01)
        
        with patch('asyncio.sleep', mock_sleep):
            await ts._scheduler_loop()
        
        assert call_count[0] >= 1


class TestStartStop:
    """Tests for start and stop methods."""
    
    def test_start(self):
        """Test starting the scheduler."""
        ts = TaskScheduler()
        
        # Mock asyncio.create_task
        with patch('asyncio.create_task') as mock_create_task:
            mock_create_task.return_value = MagicMock()
            ts.start()
        
        assert ts._running is True
        mock_create_task.assert_called_once()
    
    def test_start_idempotent(self):
        """Test that starting twice doesn't create multiple loops."""
        ts = TaskScheduler()
        
        with patch('asyncio.create_task') as mock_create_task:
            mock_create_task.return_value = MagicMock()
            ts.start()
            ts.start()  # Second call
        
        # Should only be called once
        assert mock_create_task.call_count == 1
    
    def test_stop(self):
        """Test stopping the scheduler."""
        ts = TaskScheduler()
        ts._running = True
        ts._loop_task = MagicMock()
        
        ts.stop()
        
        assert ts._running is False
        ts._loop_task.cancel.assert_called_once()
    
    def test_stop_no_task(self):
        """Test stopping when no loop task exists."""
        ts = TaskScheduler()
        ts._running = True
        
        # Should not raise
        ts.stop()
        
        assert ts._running is False


class TestGetScheduler:
    """Tests for get_scheduler function."""
    
    def test_get_scheduler_creates_instance(self):
        """Test that get_scheduler creates an instance."""
        # Reset global
        scheduler_module._scheduler = None
        
        s = get_scheduler()
        
        assert isinstance(s, TaskScheduler)
    
    def test_get_scheduler_returns_same_instance(self):
        """Test that get_scheduler returns the same instance."""
        scheduler_module._scheduler = None
        
        s1 = get_scheduler()
        s2 = get_scheduler()
        
        assert s1 is s2


class TestSetupBackupScheduler:
    """Tests for setup_backup_scheduler function."""
    
    @pytest.mark.asyncio
    async def test_setup_backup_scheduler(self):
        """Test setting up the backup scheduler."""
        scheduler_module._scheduler = None
        
        with patch('src.scheduler.get_scheduler') as mock_get_scheduler, \
             patch('src.backup.manager.BackupManager') as mock_backup_mgr:
            
            mock_scheduler = MagicMock()
            mock_get_scheduler.return_value = mock_scheduler
            
            mock_backup_instance = MagicMock()
            mock_backup_mgr.return_value = mock_backup_instance
            
            await setup_backup_scheduler(bot=MagicMock())
            
            mock_scheduler.add_daily_task.assert_called_once()
            call_args = mock_scheduler.add_daily_task.call_args
            assert call_args[1]["name"] == "daily_backup"
            assert call_args[1]["hour"] == 14
            assert call_args[1]["minute"] == 0
            
            mock_scheduler.start.assert_called_once()
