import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from pathlib import Path
from src.tools.skill_admin_tools import _save_schedules, restore_schedules, schedule_skill, cancel_schedule

# Sample schedule data
SAMPLE_SCHEDULES = {
    "skill_user1_test_skill_10_30": {
        "skill_name": "test_skill",
        "user_id": "user1",
        "hour": 10,
        "minute": 30
    }
}

@pytest.mark.asyncio
async def test_save_schedules():
    with patch("src.scheduler.get_scheduler") as mock_get_scheduler, \
         patch("src.tools.skill_admin_tools.SCHEDULES_FILE") as mock_file:
        
        # Setup mock scheduler with one task
        mock_scheduler = MagicMock()
        mock_scheduler._tasks = {
            "skill_user1_test_skill_10_30": {"hour": 10, "minute": 30},
            "daily_backup": {"hour": 14, "minute": 0} # Should be ignored
        }
        mock_get_scheduler.return_value = mock_scheduler
        
        # Setup mock file write
        mock_file.parent.mkdir = MagicMock()
        mock_file.write_text = MagicMock()
        
        # Execute
        _save_schedules()
        
        # Verify
        mock_file.parent.mkdir.assert_called_with(parents=True, exist_ok=True)
        # Check that write_text was called with JSON containing ONLY the skill task
        args, _ = mock_file.write_text.call_args
        saved_data = json.loads(args[0])
        
        assert "skill_user1_test_skill_10_30" in saved_data
        assert "daily_backup" not in saved_data
        assert saved_data["skill_user1_test_skill_10_30"]["skill_name"] == "test_skill"

@pytest.mark.asyncio
async def test_restore_schedules():
    # Mock file content
    mock_content = json.dumps(SAMPLE_SCHEDULES)
    
    with patch("src.tools.skill_admin_tools.SCHEDULES_FILE") as mock_file, \
         patch("src.tools.skill_admin_tools.schedule_skill", new_callable=AsyncMock) as mock_schedule, \
         patch("src.bot.globals.bot") as mock_bot:
        
        # restore_schedules checks bot.skill_registry.get_skill before calling schedule_skill
        mock_bot.skill_registry.get_skill.return_value = {"name": "test_skill"}
        
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = mock_content
        
        # Execute
        await restore_schedules()
        
        # Verify schedule_skill was called with correct params
        mock_schedule.assert_called_once_with(
            skill_name="test_skill",
            hour=10,
            minute=30,
            user_id="user1",
            channel_id=None
        )

@pytest.mark.asyncio
async def test_integration_save_on_schedule():
    # Verify schedule_skill writes directly to SCHEDULES_FILE
    with patch("src.tools.skill_admin_tools.SCHEDULES_FILE") as mock_file, \
         patch("src.scheduler.get_scheduler"), \
         patch("src.bot.globals.bot") as mock_bot:
         
         # Mock bot registry to allow skill lookup
         mock_bot.skill_registry.get_skill.return_value = {"name": "test"}
         
         # Setup mock file for direct write
         mock_file.exists.return_value = False
         mock_file.parent.mkdir = MagicMock()
         mock_file.write_text = MagicMock()
         mock_file.resolve.return_value = "/fake/path/schedules.json"
         
         await schedule_skill("test", 12, 0, "user1")
         
         mock_file.write_text.assert_called_once()
         # Verify the written JSON contains the schedule
         written = json.loads(mock_file.write_text.call_args[0][0])
         assert any("test" in v.get("skill_name", "") for v in written.values())

@pytest.mark.asyncio
async def test_integration_save_on_cancel():
    # Verify cancel_schedule removes entry from SCHEDULES_FILE
    existing_data = json.dumps({"skill_user1_test_12_0": {"skill_name": "test", "user_id": "user1", "hour": 12, "minute": 0}})
    
    with patch("src.tools.skill_admin_tools.SCHEDULES_FILE") as mock_file, \
         patch("src.scheduler.get_scheduler") as mock_get_scheduler:
         
         mock_scheduler = MagicMock()
         mock_scheduler._tasks = {"skill_user1_test_12_0": {}}
         mock_get_scheduler.return_value = mock_scheduler
         
         mock_file.exists.return_value = True
         mock_file.read_text.return_value = existing_data
         mock_file.write_text = MagicMock()
         mock_file.resolve.return_value = "/fake/path/schedules.json"
         
         await cancel_schedule("test", 12, 0, "user1")
         
         mock_file.write_text.assert_called_once()
         # Verify the written JSON no longer contains the cancelled schedule
         written = json.loads(mock_file.write_text.call_args[0][0])
         assert "skill_user1_test_12_0" not in written

@pytest.mark.asyncio
async def test_schedule_case_insensitivity():
    # Verify we can schedule "TestSkill" even if registry has "testskill"
    with patch("src.scheduler.get_scheduler"), \
         patch("src.bot.globals.bot") as mock_bot:
         
         # Registry has lowercase "testskill"
         # The mock get_skill needs to simulate being case-sensitive if we didn't normalize
         # But since we normalize in the tool, the tool should ask for "testskill"
         
         mock_bot.skill_registry.get_skill.side_effect = lambda name, user_id: {"name": "testskill"} if name == "testskill" else None
         
         # Call with MixedCase
         result = await schedule_skill("TestSkill", 12, 0, "user1")
         
         # Verify we asked registry for "testskill"
         mock_bot.skill_registry.get_skill.assert_called_with("testskill", user_id="user1")
         assert "Scheduled skill" in result


@pytest.mark.asyncio
async def test_schedule_channel_persistence():
    """Verify that channel_id is correctly saved and restored."""
    from src.tools.skill_admin_tools import _save_schedules, restore_schedules

    # Test saving with channel_id
    with patch("src.scheduler.get_scheduler") as mock_get_scheduler, \
         patch("src.tools.skill_admin_tools.SCHEDULES_FILE") as mock_file:

        mock_scheduler = MagicMock()
        # Task with channel_id encoded (Use long ID > 10 chars)
        mock_scheduler._tasks = {
            "skill_user1_123456789012345678_test_skill_10_30": {
                "hour": 10, 
                "minute": 30,
            }
        }
        mock_get_scheduler.return_value = mock_scheduler
        
        mock_file.parent.mkdir = MagicMock()
        mock_file.write_text = MagicMock()

        _save_schedules()

        # Check JSON content
        args, _ = mock_file.write_text.call_args
        saved_json = json.loads(args[0])
        assert "skill_user1_123456789012345678_test_skill_10_30" in saved_json
        item = saved_json["skill_user1_123456789012345678_test_skill_10_30"]
        assert item["channel_id"] == "123456789012345678"
        assert item["skill_name"] == "test_skill"

    # Test restoring with channel_id
    mock_content = json.dumps({
        "skill_user1_123456789012345678_test_skill_10_30": {
            "skill_name": "test_skill",
            "hour": 10,
            "minute": 30,
            "user_id": "user1",
            "channel_id": "123456789012345678"
        }
    })

    with patch("src.tools.skill_admin_tools.SCHEDULES_FILE") as mock_file, \
         patch("src.tools.skill_admin_tools.schedule_skill", new_callable=AsyncMock) as mock_schedule, \
         patch("src.bot.globals.bot") as mock_bot:
         
        mock_bot.skill_registry.get_skill.return_value = {"name": "test_skill"}
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = mock_content

        await restore_schedules()

        mock_schedule.assert_called_once_with(
            skill_name="test_skill",
            hour=10,
            minute=30,
            user_id="user1",
            channel_id="123456789012345678"
        )
