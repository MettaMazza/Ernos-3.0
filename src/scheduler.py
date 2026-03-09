"""
Scheduler - Handles scheduled tasks like daily backups.
Uses APScheduler for background task scheduling.
"""
import logging
import asyncio
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger("Scheduler")


class TaskScheduler:
    """
    Simple scheduler for background tasks.
    Uses asyncio for scheduling rather than external dependencies.
    """
    
    def __init__(self):
        self._tasks = {}
        self._adhoc_tasks = []  # List of {"time": datetime, "func": coro, "name": str}
        self._running = False
        self._loop_task = None
        
    def add_daily_task(self, name: str, hour: int, minute: int, coro_func: Callable):
        """
        Schedule a task to run daily at a specific time.
        
        Args:
            name: Unique task name
            hour: Hour (0-23) to run
            minute: Minute (0-59) to run
            coro_func: Async function to run
        """
        self._tasks[name] = {
            "hour": hour,
            "minute": minute,
            "func": coro_func,
            "last_run": None
        }
        logger.info(f"Scheduled daily task '{name}' at {hour:02d}:{minute:02d}")

    def add_one_time_task(self, name: str, run_at: datetime, coro_func: Callable):
        """Schedule a task to run once at a specific datetime."""
        self._adhoc_tasks.append({
            "name": name,
            "time": run_at,
            "func": coro_func
        })
        self._adhoc_tasks.sort(key=lambda x: x["time"])
        logger.info(f"Scheduled ad-hoc task '{name}' at {run_at}")
        
    def remove_task(self, name: str):
        """Remove a scheduled task."""
        if name in self._tasks:
            del self._tasks[name]
            logger.info(f"Removed daily task '{name}'")
        
        # Also remove from ad-hoc
        self._adhoc_tasks = [t for t in self._adhoc_tasks if t["name"] != name]
            
    async def _check_and_run(self):
        """Check if any tasks should run now."""
        now = datetime.now()
        
        # 1. Check Daily Tasks
        for name, task in self._tasks.items():
            # Check if current time matches schedule
            if now.hour == task["hour"] and now.minute == task["minute"]:
                # Check if already run today
                if task["last_run"] and task["last_run"].date() == now.date():
                    continue
                    
                try:
                    logger.info(f"Running scheduled task: {name}")
                    await task["func"]()
                    task["last_run"] = now
                except Exception as e:
                    logger.error(f"Scheduled task '{name}' failed: {e}")

        # 2. Check Ad-hoc Tasks
        # Iterate copy since we might modify list
        remaining = []
        for task in self._adhoc_tasks:
            if now >= task["time"]:
                try:
                    logger.info(f"Running ad-hoc task: {task['name']}")
                    await task["func"]()
                except Exception as e:
                    logger.error(f"Ad-hoc task '{task['name']}' failed: {e}")
            else:
                remaining.append(task)
        self._adhoc_tasks = remaining
                    
    async def _scheduler_loop(self):
        """Main scheduler loop, checks every minute."""
        while self._running:
            await self._check_and_run()
            await asyncio.sleep(60)  # Check every minute
            
    def start(self):
        """Start the scheduler."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started")
        
    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
        logger.info("Scheduler stopped")


# Global scheduler instance
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


async def setup_backup_scheduler(bot=None):
    """
    Setup the daily 2pm backup task.
    Call this during bot startup.
    """
    from src.backup.manager import BackupManager
    
    backup_mgr = BackupManager(bot)
    scheduler = get_scheduler()
    
    scheduler.add_daily_task(
        name="daily_backup",
        hour=14,  # 2pm
        minute=0,
        coro_func=backup_mgr.daily_backup
    )
    
    scheduler.start()
    logger.info("Backup scheduler initialized for 2pm daily")
