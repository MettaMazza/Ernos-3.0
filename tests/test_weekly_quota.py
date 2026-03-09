"""Tests for Weekly Quota and Review Pipeline tools."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestWeeklyQuota(unittest.TestCase):
    """Tests for src/tools/weekly_quota.py."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.quota_dir = Path(self.tmp) / "quota"
        # Patch QUOTA_DIR and FEEDBACK_PATH
        self.patcher_dir = patch("src.tools.weekly_quota.QUOTA_DIR", self.quota_dir)
        self.patcher_fb = patch("src.tools.weekly_quota.FEEDBACK_PATH", self.quota_dir / "feedback_history.json")
        self.patcher_dir.start()
        self.patcher_fb.start()

    def tearDown(self):
        self.patcher_dir.stop()
        self.patcher_fb.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── _load_week / _save_week ──

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    def test_load_fresh_week(self, mock_iso):
        from src.tools.weekly_quota import _load_week
        state = _load_week()
        self.assertEqual(state["week"], "2026-W07")
        self.assertIn("monday", state["days"])
        self.assertIn("friday", state["days"])
        self.assertEqual(state["days"]["friday"]["status"], "REVIEW_DAY")
        self.assertEqual(state["review_status"], "PENDING")

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    def test_save_and_reload(self, mock_iso):
        from src.tools.weekly_quota import _load_week, _save_week
        state = _load_week()
        state["days"]["monday"]["hours_logged"] = 2.5
        _save_week(state)
        reloaded = _load_week()
        self.assertEqual(reloaded["days"]["monday"]["hours_logged"], 2.5)

    # ── get_quota_status ──

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="tuesday")
    def test_get_quota_status_shows_week(self, mock_day, mock_iso):
        from src.tools.weekly_quota import get_quota_status
        result = get_quota_status()
        self.assertIn("2026-W07", result)
        self.assertIn("TODAY", result)
        self.assertIn("3h", result)

    # ── assign_dev_task ──

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="wednesday")
    @patch("src.tools.weekly_quota._now_uk")
    def test_assign_task_on_work_day(self, mock_now, mock_day, mock_iso):
        mock_now.return_value = datetime(2026, 2, 11, 10, 0, 0)
        from src.tools.weekly_quota import assign_dev_task, _load_week
        result = assign_dev_task(description="Build new module", estimated_hours=1.5)
        self.assertIn("Task #0", result)
        self.assertIn("Build new module", result)
        state = _load_week()
        self.assertEqual(len(state["days"]["wednesday"]["tasks"]), 1)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="friday")
    @patch("src.tools.weekly_quota._now_uk")
    def test_assign_task_on_friday_blocked(self, mock_now, mock_day, mock_iso):
        mock_now.return_value = datetime(2026, 2, 13, 10, 0, 0)
        from src.tools.weekly_quota import assign_dev_task
        result = assign_dev_task(description="Anything")
        self.assertIn("Review day", result)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="saturday")
    @patch("src.tools.weekly_quota._now_uk")
    def test_assign_task_on_saturday(self, mock_now, mock_day, mock_iso):
        mock_now.return_value = datetime(2026, 2, 14, 10, 0, 0)
        from src.tools.weekly_quota import assign_dev_task
        result = assign_dev_task(description="Saturday work")
        self.assertIn("Task #0", result)  # Saturday is a work day

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="monday")
    @patch("src.tools.weekly_quota._now_uk")
    def test_assign_task_quota_full(self, mock_now, mock_day, mock_iso):
        mock_now.return_value = datetime(2026, 2, 9, 10, 0, 0)
        from src.tools.weekly_quota import assign_dev_task, _load_week, _save_week
        # Pre-fill quota
        state = _load_week()
        state["days"]["monday"]["hours_logged"] = 3.0
        _save_week(state)
        result = assign_dev_task(description="One more task")
        self.assertIn("quota is met", result)

    # ── complete_dev_task ──

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="tuesday")
    @patch("src.tools.weekly_quota._now_uk")
    def test_complete_task(self, mock_now, mock_day, mock_iso):
        # Assign at 14:00, complete at 15:30 → 1.5h measured
        from src.tools.weekly_quota import assign_dev_task, complete_dev_task, _load_week
        mock_now.return_value = datetime(2026, 2, 10, 14, 0, 0)
        assign_dev_task(description="Test task", estimated_hours=1.0)
        mock_now.return_value = datetime(2026, 2, 10, 15, 30, 0)  # 1.5h later
        result = complete_dev_task(output_files="test.py", summary="Built test")
        self.assertIn("Task #0 completed", result)
        self.assertIn("1.50h measured", result)
        state = _load_week()
        self.assertEqual(len(state["staged_changes"]), 1)
        self.assertEqual(state["days"]["tuesday"]["tasks"][0]["hours_logged"], 1.5)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="saturday")
    @patch("src.tools.weekly_quota._now_uk")
    def test_complete_task_on_saturday(self, mock_now, mock_day, mock_iso):
        from src.tools.weekly_quota import assign_dev_task, complete_dev_task
        mock_now.return_value = datetime(2026, 2, 14, 10, 0, 0)
        assign_dev_task(description="Saturday task")
        mock_now.return_value = datetime(2026, 2, 14, 12, 0, 0)
        result = complete_dev_task(summary="Done")
        self.assertIn("Task #0 completed", result)  # Saturday is a work day now

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="monday")
    def test_complete_task_none_assigned(self, mock_day, mock_iso):
        from src.tools.weekly_quota import complete_dev_task
        result = complete_dev_task()
        self.assertIn("No tasks assigned", result)

    # ── stage_for_review ──

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="wednesday")
    @patch("src.tools.weekly_quota._now_uk")
    def test_stage_for_review(self, mock_now, mock_day, mock_iso):
        mock_now.return_value = datetime(2026, 2, 11, 10, 0, 0)
        from src.tools.weekly_quota import stage_for_review, _load_week
        result = stage_for_review(path="memory/core/staging/test.py", description="New test")
        self.assertIn("Staged", result)
        state = _load_week()
        self.assertEqual(len(state["staged_changes"]), 1)

    # ── is_merge_allowed ──

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="wednesday")
    def test_merge_blocked_on_wednesday(self, mock_day, mock_iso):
        from src.tools.weekly_quota import is_merge_allowed
        self.assertFalse(is_merge_allowed())

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="friday")
    def test_merge_allowed_on_friday(self, mock_day, mock_iso):
        from src.tools.weekly_quota import is_merge_allowed
        self.assertTrue(is_merge_allowed())

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="tuesday")
    def test_merge_allowed_after_approval(self, mock_day, mock_iso):
        from src.tools.weekly_quota import is_merge_allowed, _load_week, _save_week
        state = _load_week()
        state["review_status"] = "APPROVED"
        _save_week(state)
        self.assertTrue(is_merge_allowed())

    # ── get_remaining_quota ──

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="monday")
    def test_remaining_quota_full_day(self, mock_day, mock_iso):
        from src.tools.weekly_quota import get_remaining_quota
        self.assertEqual(get_remaining_quota(), 3.0)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="saturday")
    def test_remaining_quota_saturday(self, mock_day, mock_iso):
        from src.tools.weekly_quota import get_remaining_quota
        self.assertEqual(get_remaining_quota(), 3.0)  # Saturday is a work day

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="sunday")
    def test_remaining_quota_sunday(self, mock_day, mock_iso):
        from src.tools.weekly_quota import get_remaining_quota
        self.assertEqual(get_remaining_quota(), 3.0)  # Sunday is a work day

    # ── get_feedback_report ──

    def test_feedback_report_empty(self):
        from src.tools.weekly_quota import get_feedback_report
        result = get_feedback_report()
        self.assertIn("No review history yet", result)

    # ── is_quota_met ──

    @patch("src.tools.weekly_quota._is_work_mode_off", return_value=False)
    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="monday")
    def test_quota_not_met_on_fresh_day(self, mock_day, mock_iso, mock_override):
        from src.tools.weekly_quota import is_quota_met
        self.assertFalse(is_quota_met())

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="monday")
    def test_quota_met_after_3h(self, mock_day, mock_iso):
        from src.tools.weekly_quota import is_quota_met, _load_week, _save_week
        state = _load_week()
        state["days"]["monday"]["hours_logged"] = 3.0
        _save_week(state)
        self.assertTrue(is_quota_met())

    @patch("src.tools.weekly_quota._day_name", return_value="friday")
    def test_quota_met_on_friday(self, mock_day):
        from src.tools.weekly_quota import is_quota_met
        self.assertTrue(is_quota_met())  # Friday is off — quota auto-met

    @patch("src.tools.weekly_quota._is_work_mode_off", return_value=False)
    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="saturday")
    def test_quota_not_met_on_saturday(self, mock_day, mock_iso, mock_override):
        from src.tools.weekly_quota import is_quota_met
        self.assertFalse(is_quota_met())  # Saturday IS a work day now

    @patch("src.tools.weekly_quota._is_work_mode_off", return_value=False)
    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="sunday")
    def test_quota_not_met_on_sunday(self, mock_day, mock_iso, mock_override):
        from src.tools.weekly_quota import is_quota_met
        self.assertFalse(is_quota_met())  # Sunday is a work day

class TestReviewPipeline(unittest.TestCase):
    """Tests for src/tools/review_pipeline.py."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.quota_dir = Path(self.tmp) / "quota"
        self.staging_dir = Path(self.tmp) / "staging"
        self.projects_dir = Path(self.tmp) / "projects"
        
        self.patcher_quota = patch("src.tools.weekly_quota.QUOTA_DIR", self.quota_dir)
        self.patcher_fb = patch("src.tools.weekly_quota.FEEDBACK_PATH", self.quota_dir / "feedback_history.json")
        self.patcher_staging = patch("src.tools.review_pipeline.STAGING_DIR", self.staging_dir)
        self.patcher_projects = patch("src.tools.review_pipeline.PROJECTS_DIR", self.projects_dir)
        
        self.patcher_quota.start()
        self.patcher_fb.start()
        self.patcher_staging.start()
        self.patcher_projects.start()

    def tearDown(self):
        self.patcher_quota.stop()
        self.patcher_fb.stop()
        self.patcher_staging.stop()
        self.patcher_projects.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="wednesday")
    @patch("src.tools.weekly_quota._now_uk")
    def test_get_review_queue_empty(self, mock_now, mock_day, mock_iso):
        mock_now.return_value = datetime(2026, 2, 11, 10, 0, 0)
        from src.tools.review_pipeline import get_review_queue
        result = get_review_queue()
        self.assertIn("No staged changes", result)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="wednesday")
    @patch("src.tools.weekly_quota._now_uk")
    @patch("src.tools.review_pipeline._now_uk")
    def test_get_review_queue_with_staged(self, mock_review_now, mock_quota_now, mock_day, mock_iso):
        mock_quota_now.return_value = datetime(2026, 2, 11, 10, 0, 0)
        mock_review_now.return_value = datetime(2026, 2, 11, 10, 0, 0)
        from src.tools.weekly_quota import stage_for_review
        from src.tools.review_pipeline import get_review_queue
        stage_for_review(path="test.py", description="New feature")
        result = get_review_queue()
        self.assertIn("New feature", result)
        self.assertIn("1 change(s)", result)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="friday")
    @patch("src.tools.weekly_quota._now_uk")
    @patch("src.tools.review_pipeline._now_uk")
    def test_approve_all(self, mock_review_now, mock_quota_now, mock_day, mock_iso):
        mock_quota_now.return_value = datetime(2026, 2, 13, 10, 0, 0)
        mock_review_now.return_value = datetime(2026, 2, 13, 10, 0, 0)
        from src.tools.weekly_quota import stage_for_review
        from src.tools.review_pipeline import approve_review
        stage_for_review(path="test.py", description="New feature")
        result = approve_review(feedback="Great work!")
        self.assertIn("1 approved", result)
        self.assertIn("Great work!", result)
        self.assertIn("adoption rate", result)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="friday")
    @patch("src.tools.weekly_quota._now_uk")
    @patch("src.tools.review_pipeline._now_uk")
    def test_reject_all(self, mock_review_now, mock_quota_now, mock_day, mock_iso):
        mock_quota_now.return_value = datetime(2026, 2, 13, 10, 0, 0)
        mock_review_now.return_value = datetime(2026, 2, 13, 10, 0, 0)
        from src.tools.weekly_quota import stage_for_review
        from src.tools.review_pipeline import reject_review
        stage_for_review(path="bad.py", description="Bad approach")
        result = reject_review(feedback="Not what we need", reasons="Wrong pattern|Too complex")
        self.assertIn("1 change(s)", result)
        self.assertIn("Not what we need", result)
        self.assertIn("Wrong pattern", result)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="friday")
    @patch("src.tools.weekly_quota._now_uk")
    @patch("src.tools.review_pipeline._now_uk")
    def test_approve_partial(self, mock_review_now, mock_quota_now, mock_day, mock_iso):
        mock_quota_now.return_value = datetime(2026, 2, 13, 10, 0, 0)
        mock_review_now.return_value = datetime(2026, 2, 13, 10, 0, 0)
        from src.tools.weekly_quota import stage_for_review
        from src.tools.review_pipeline import approve_review
        stage_for_review(path="good.py", description="Good feature")
        stage_for_review(path="bad.py", description="Bad feature")
        result = approve_review(approved_indices="0")
        self.assertIn("1 approved", result)
        self.assertIn("1 not approved", result)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="friday")
    @patch("src.tools.weekly_quota._now_uk")
    @patch("src.tools.review_pipeline._now_uk")
    def test_feedback_accumulates(self, mock_review_now, mock_quota_now, mock_day, mock_iso):
        mock_quota_now.return_value = datetime(2026, 2, 13, 10, 0, 0)
        mock_review_now.return_value = datetime(2026, 2, 13, 10, 0, 0)
        from src.tools.weekly_quota import stage_for_review, get_feedback_report
        from src.tools.review_pipeline import approve_review
        stage_for_review(path="test.py", description="Feature A")
        approve_review(feedback="Nice")
        result = get_feedback_report()
        self.assertIn("Weeks tracked: 1", result)
        self.assertIn("Adoption rate", result)

    @patch("src.tools.weekly_quota._iso_week", return_value="2026-W07")
    @patch("src.tools.weekly_quota._day_name", return_value="wednesday")
    def test_approve_nothing_staged(self, mock_day, mock_iso):
        from src.tools.review_pipeline import approve_review
        result = approve_review()
        self.assertIn("Nothing staged", result)


if __name__ == "__main__":
    unittest.main()
