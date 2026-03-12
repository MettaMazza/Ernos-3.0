import pytest
from unittest.mock import MagicMock, patch, ANY
import subprocess

# Add src to path if needed (though conftest usually handles it)
from src.tools import weekly_quota

@pytest.fixture
def mock_week_state():
    return {
        "week": "2026-W08",
        "daily_hours": 3,
        "days": {
            "monday": {
                "tasks": [],
                "hours_logged": 0,
                "status": "PENDING",
                "session": None,
                "verifications": {}
            },
            "sunday": {
                "tasks": [],
                "hours_logged": 0,
                "status": "PENDING",
            }
        },
        "staged_changes": [],
        "review_status": "PENDING",
    }

@patch("src.tools.weekly_quota._load_week")
@patch("src.tools.weekly_quota._save_week")
@patch("src.tools.weekly_quota._day_name")
@patch("src.tools.weekly_quota._now_uk")
def test_start_work_session(mock_now, mock_day, mock_save, mock_load, mock_week_state):
    mock_load.return_value = mock_week_state
    mock_day.return_value = "monday"
    mock_now.return_value.isoformat.return_value = "2026-02-16T10:00:00"

    result = weekly_quota.start_work_session(plan="Fix bugs", predicted_tasks=3)

    assert "Work Session Started" in result or "Rocket" in result
    if "days" in mock_week_state and "monday" in mock_week_state["days"]:
         assert mock_week_state["days"]["monday"]["session"]["status"] == "ACTIVE"

@patch("src.tools.weekly_quota.subprocess.run")
@patch("src.tools.weekly_quota._load_week")
@patch("src.tools.weekly_quota._save_week")
@patch("src.tools.weekly_quota._day_name")
@patch("src.tools.weekly_quota._now_uk")
def test_verify_staging_item_success(mock_now, mock_day, mock_save, mock_load, mock_subprocess, mock_week_state):
    # Setup
    mock_load.return_value = mock_week_state
    mock_day.return_value = "monday"
    mock_now.return_value.isoformat.return_value = "2026-02-16T10:00:00"
    
    # Mock successful subprocess result
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "Test passed"
    mock_res.stderr = ""
    mock_subprocess.return_value = mock_res
    
    # Execute
    result = weekly_quota.verify_staging_item(path="test.py", test_command="pytest test.py")
    
    # Verify
    assert "Verification PASSED" in result
    assert mock_week_state["days"]["monday"]["verifications"]["test.py"]["status"] == "PASSED"

@patch("src.tools.weekly_quota.subprocess.run")
@patch("src.tools.weekly_quota._load_week")
@patch("src.tools.weekly_quota._save_week")
@patch("src.tools.weekly_quota._day_name")
@patch("src.tools.weekly_quota._now_uk")
def test_verify_staging_item_failure(mock_now, mock_day, mock_save, mock_load, mock_subprocess, mock_week_state):
    # Setup
    mock_load.return_value = mock_week_state
    mock_day.return_value = "monday"
    mock_now.return_value.isoformat.return_value = "2026-02-16T10:00:00"
    
    # Mock failed subprocess result
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stdout = ""
    mock_res.stderr = "SyntaxError"
    mock_subprocess.return_value = mock_res
    
    # Execute
    result = weekly_quota.verify_staging_item(path="broken.py", test_command="pytest broken.py")
    
    # Verify — syntax check runs first for .py files
    assert "SYNTAX ERROR" in result or "FAILED" in result
    assert mock_week_state["days"]["monday"]["verifications"]["broken.py"]["status"] == "FAILED"

@patch("src.tools.weekly_quota._load_week")
@patch("src.tools.weekly_quota._save_week")
@patch("src.tools.weekly_quota._day_name")
@patch("src.tools.weekly_quota._now_uk")
def test_complete_task_rejected_without_verification(mock_now, mock_day, mock_save, mock_load, mock_week_state):
    # Setup
    mock_load.return_value = mock_week_state
    mock_day.return_value = "monday"
    mock_now.return_value.isoformat.return_value = "2026-02-16T11:00:00"
    
    # Active task exists
    mock_week_state["days"]["monday"]["tasks"] = [
        {"id": 0, "started_at": "2026-02-16T10:00:00", "completed_at": None, "description": "Test Task"}
    ]
    # No verifications
    mock_week_state["days"]["monday"]["verifications"] = {}
    
    # Execute
    result = weekly_quota.complete_dev_task(task_id=0, output_files="test.py")
    
    # Verify
    assert "QA GATE: Verification missing" in result
    # Task should remain incomplete
    assert mock_week_state["days"]["monday"]["tasks"][0].get("completed_at") is None

@patch("src.tools.weekly_quota._load_week")
@patch("src.tools.weekly_quota._save_week")
@patch("src.tools.weekly_quota._day_name")
@patch("src.tools.weekly_quota._now_uk")
def test_complete_task_success_with_verification(mock_now, mock_day, mock_save, mock_load, mock_week_state):
    # Setup
    mock_load.return_value = mock_week_state
    mock_day.return_value = "monday"
    mock_now.return_value.isoformat.return_value = "2026-02-16T11:00:00"
    
    # Active task exists
    mock_week_state["days"]["monday"]["tasks"] = [
        {"id": 0, "started_at": "2026-02-16T10:00:00", "completed_at": None, "description": "Test Task"}
    ]
    # Verification passed
    mock_week_state["days"]["monday"]["verifications"] = {
        "test.py": {"status": "PASSED"}
    }
    
    # Execute
    result = weekly_quota.complete_dev_task(task_id=0, output_files="test.py")
    
    # Verify
    assert "Task #0 completed" in result
    assert mock_week_state["days"]["monday"]["tasks"][0].get("completed_at") is not None
    # Check verification recorded in staging
    staged = mock_week_state["staged_changes"][0]
    assert staged["path"] == "test.py"
    # Depending on implementation detail, it might store the full record or just "PASSED"
    # In weekly_quota.py: "verification": verifications.get(f, "DOC_ONLY")
    assert staged["verification"]["status"] == "PASSED"

@patch("src.tools.weekly_quota._day_name")
def test_schedule_sunday_is_workday(mock_day):
    mock_day.return_value = "sunday"
    # If sunday is a workday, get_remaining_quota should likely return > 0 or at least check state
    with patch("src.tools.weekly_quota._load_week") as mock_load:
        mock_load.return_value = {"days": {"sunday": {"hours_logged": 0}}}
        remaining = weekly_quota.get_remaining_quota()
        # Should be 3.0
        assert remaining == 3.0

@patch("src.tools.weekly_quota._day_name")
def test_schedule_friday_is_review_day(mock_day):
    mock_day.return_value = "friday"
    # Friday is off (0 quota)
    remaining = weekly_quota.get_remaining_quota()
    assert remaining == 0.0
