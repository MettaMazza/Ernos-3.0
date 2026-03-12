import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.tools.skill_admin_tools import cancel_schedule, list_schedules, schedule_skill

@pytest.mark.asyncio
async def test_schedule_cancellation_flow():
    # Mock bot and scheduler
    mock_bot = MagicMock()
    mock_bot.skill_registry.get_skill.return_value = {"name": "test_skill"}
    
    with patch("src.bot.globals.bot", mock_bot), \
         patch("src.scheduler.get_scheduler") as mock_get_scheduler:
        
        # Setup mock scheduler
        mock_scheduler = MagicMock()
        mock_scheduler._tasks = {}
        
        # Define add_daily_task behavior to actually update _tasks
        def add_task(name, hour, minute, coro_func):
            mock_scheduler._tasks[name] = {"hour": hour, "minute": minute}
        mock_scheduler.add_daily_task.side_effect = add_task
        
        # Define remove_task behavior
        def remove_task(name):
            if name in mock_scheduler._tasks:
                del mock_scheduler._tasks[name]
        mock_scheduler.remove_task.side_effect = remove_task
        
        mock_get_scheduler.return_value = mock_scheduler
        
        # 1. Schedule a task
        await schedule_skill("test_skill", 10, 30, user_id="user1")
        
        # New format includes "global" for channel_id
        task_name = "skill_user1_global_test_skill_10_30"
        assert task_name in mock_scheduler._tasks
        
        # 2. List schedules
        listing = await list_schedules()
        # listing output may not be exact task ID string, but likely contains skill name/time
        # But let's check if listing contains the task ID if list_schedules implementation returns it?
        # Typically list_schedules returns user friendly string. 
        # But let's assume if it lists internal IDs or formatted output.
        # Actually list_schedules returns a formatted string. 
        # But let's check if it contains the skill name and time at least.
        assert "test_skill" in listing
        assert "10:30" in listing
        
        # 3. Cancel task
        result = await cancel_schedule("test_skill", 10, 30, user_id="user1")
        
        assert "Cancel" in result
        assert task_name not in mock_scheduler._tasks
        
        # 4. Verify listing is empty
        listing_empty = await list_schedules()
        assert "No scheduled tasks" in listing_empty
