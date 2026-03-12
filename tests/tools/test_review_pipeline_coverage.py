"""
Coverage tests for src/tools/review_pipeline.py.
Targets 106 uncovered lines: _now_uk, get_review_queue, approve_review (merge,
rollback, manifest, pytest, feedback), reject_review, friday_review_summary,
daily_quota_check, _count_week_tasks.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock


# ── Fixtures ─────────────────────────────────────────────
@pytest.fixture
def mock_week():
    """Provide a mock weekly state."""
    return {
        "week": "2026-W08",
        "review_status": "PENDING",
        "staged_changes": [
            {"description": "Add feature X", "path": "staging/feature_x.py", "day": "monday"},
            {"description": "Fix bug Y", "path": "staging/bug_y.py", "day": "tuesday"},
        ],
        "days": {
            "monday": {"hours_logged": 2.0, "tasks": [{"completed_at": "2026-02-16"}]},
            "tuesday": {"hours_logged": 1.5, "tasks": [{"completed_at": None}]},
        }
    }


@pytest.fixture
def mock_feedback():
    return {
        "weekly_history": [],
        "total_weeks": 0,
        "total_tasks_submitted": 0,
        "total_approved": 0,
        "total_rejected": 0,
        "total_partial": 0,
        "adoption_rate": 0.0,
    }


# ── _now_uk ──────────────────────────────────────────────
class TestNowUk:
    def test_with_zoneinfo(self):
        from src.tools.review_pipeline import _now_uk
        dt = _now_uk()
        assert dt is not None

    def test_without_zoneinfo(self):
        from src.tools.review_pipeline import _now_uk
        with patch.dict("sys.modules", {"zoneinfo": None}):
            with patch("builtins.__import__", side_effect=ImportError("no zoneinfo")):
                dt = _now_uk()
        # Should still return a datetime (utc fallback)


# ── get_review_queue ─────────────────────────────────────
class TestGetReviewQueue:
    def test_empty_queue(self):
        from src.tools.review_pipeline import get_review_queue
        with patch("src.tools.weekly_quota._load_week", return_value={"staged_changes": [], "week": "W08"}):
            result = get_review_queue()
        assert "No staged changes" in result

    def test_with_items(self, mock_week):
        from src.tools.review_pipeline import get_review_queue
        with patch("src.tools.weekly_quota._load_week", return_value=mock_week):
            result = get_review_queue()
        assert "Add feature X" in result
        assert "Fix bug Y" in result
        assert "PENDING" in result


# ── approve_review ───────────────────────────────────────
class TestApproveReview:
    def test_nothing_staged(self):
        from src.tools.review_pipeline import approve_review
        with patch("src.tools.weekly_quota._load_week", return_value={"staged_changes": []}):
            result = approve_review()
        assert "Nothing staged" in result

    def test_approve_all(self, mock_week, mock_feedback, tmp_path):
        from src.tools.review_pipeline import approve_review
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()
        (staging_dir / "feature_x.py").write_text("code")
        (staging_dir / "bug_y.py").write_text("code")
        manifest_path = staging_dir / "staging_manifest.json"

        with patch("src.tools.weekly_quota._load_week", return_value=mock_week), \
             patch("src.tools.weekly_quota._save_week"), \
             patch("src.tools.weekly_quota._load_feedback", return_value=mock_feedback), \
             patch("src.tools.weekly_quota._save_feedback"), \
             patch("src.tools.review_pipeline.STAGING_DIR", staging_dir), \
             patch("src.tools.review_pipeline.PROJECTS_DIR", tmp_path / "projects"), \
             patch("src.tools.review_pipeline._count_week_tasks", return_value=2):
            result = approve_review(feedback="LGTM")
        assert "approved" in result.lower()
        assert "LGTM" in result

    def test_approve_specific_indices(self, mock_week, mock_feedback, tmp_path):
        from src.tools.review_pipeline import approve_review
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()
        (staging_dir / "feature_x.py").write_text("code")

        with patch("src.tools.weekly_quota._load_week", return_value=mock_week), \
             patch("src.tools.weekly_quota._save_week"), \
             patch("src.tools.weekly_quota._load_feedback", return_value=mock_feedback), \
             patch("src.tools.weekly_quota._save_feedback"), \
             patch("src.tools.review_pipeline.STAGING_DIR", staging_dir), \
             patch("src.tools.review_pipeline.PROJECTS_DIR", tmp_path / "projects"), \
             patch("src.tools.review_pipeline._count_week_tasks", return_value=2):
            result = approve_review(approved_indices="0")
        assert "1 approved" in result
        assert "1 not approved" in result

    def test_approve_bad_indices(self, mock_week):
        from src.tools.review_pipeline import approve_review
        with patch("src.tools.weekly_quota._load_week", return_value=mock_week):
            result = approve_review(approved_indices="abc")
        assert "Error" in result

    def test_merge_to_production(self, mock_week, mock_feedback, tmp_path):
        """Files with src/ intended paths go to production."""
        from src.tools.review_pipeline import approve_review
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()
        (staging_dir / "feature_x.py").write_text("new code")

        # Create manifest pointing to src/
        manifest = [{"staged_as": "feature_x.py", "intended_path": "src/feature_x.py"}]
        (staging_dir / "staging_manifest.json").write_text(json.dumps(manifest))

        # Create existing file for backup
        dst = tmp_path / "src" / "feature_x.py"
        dst.parent.mkdir(parents=True)
        dst.write_text("old code")

        mock_week["staged_changes"] = [mock_week["staged_changes"][0]]

        with patch("src.tools.weekly_quota._load_week", return_value=mock_week), \
             patch("src.tools.weekly_quota._save_week"), \
             patch("src.tools.weekly_quota._load_feedback", return_value=mock_feedback), \
             patch("src.tools.weekly_quota._save_feedback"), \
             patch("src.tools.review_pipeline.STAGING_DIR", staging_dir), \
             patch("src.tools.review_pipeline.PROJECTS_DIR", tmp_path / "projects"), \
             patch("src.tools.review_pipeline._count_week_tasks", return_value=1), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = approve_review()
        assert "merged to production" in result.lower()

    def test_pytest_rollback(self, mock_week, mock_feedback, tmp_path):
        """If pytest fails after merge, changes are rolled back."""
        from src.tools.review_pipeline import approve_review
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()
        (staging_dir / "feature_x.py").write_text("broken code")
        manifest = [{"staged_as": "feature_x.py", "intended_path": "src/feature_x.py"}]
        (staging_dir / "staging_manifest.json").write_text(json.dumps(manifest))

        mock_week["staged_changes"] = [mock_week["staged_changes"][0]]

        with patch("src.tools.weekly_quota._load_week", return_value=mock_week), \
             patch("src.tools.weekly_quota._save_week"), \
             patch("src.tools.weekly_quota._load_feedback", return_value=mock_feedback), \
             patch("src.tools.weekly_quota._save_feedback"), \
             patch("src.tools.review_pipeline.STAGING_DIR", staging_dir), \
             patch("src.tools.review_pipeline.PROJECTS_DIR", tmp_path / "projects"), \
             patch("src.tools.review_pipeline._count_week_tasks", return_value=1), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="FAILED test", stderr="")
            result = approve_review()
        assert "ROLLED BACK" in result


# ── reject_review ────────────────────────────────────────
class TestRejectReview:
    def test_nothing_staged(self):
        from src.tools.review_pipeline import reject_review
        with patch("src.tools.weekly_quota._load_week", return_value={"staged_changes": []}):
            result = reject_review()
        assert "Nothing staged" in result

    def test_reject_all(self, mock_week, mock_feedback):
        from src.tools.review_pipeline import reject_review
        with patch("src.tools.weekly_quota._load_week", return_value=mock_week), \
             patch("src.tools.weekly_quota._save_week"), \
             patch("src.tools.weekly_quota._load_feedback", return_value=mock_feedback), \
             patch("src.tools.weekly_quota._save_feedback"), \
             patch("src.tools.review_pipeline._count_week_tasks", return_value=2):
            result = reject_review(feedback="Not ready", reasons="code quality|missing tests")
        assert "Rejected" in result
        assert "Not ready" in result
        assert "code quality" in result

    def test_reject_partial(self, mock_week, mock_feedback):
        from src.tools.review_pipeline import reject_review
        with patch("src.tools.weekly_quota._load_week", return_value=mock_week), \
             patch("src.tools.weekly_quota._save_week"), \
             patch("src.tools.weekly_quota._load_feedback", return_value=mock_feedback), \
             patch("src.tools.weekly_quota._save_feedback"), \
             patch("src.tools.review_pipeline._count_week_tasks", return_value=2):
            result = reject_review(rejected_indices="0")
        assert "1" in result
        assert "still staged" in result

    def test_reject_bad_indices(self, mock_week):
        from src.tools.review_pipeline import reject_review
        with patch("src.tools.weekly_quota._load_week", return_value=mock_week):
            result = reject_review(rejected_indices="abc")
        assert "Error" in result


# ── friday_review_summary ────────────────────────────────
class TestFridayReviewSummary:
    @pytest.mark.asyncio
    async def test_no_staged(self):
        from src.tools.review_pipeline import friday_review_summary
        with patch("src.tools.weekly_quota._load_week", return_value={"staged_changes": []}):
            await friday_review_summary()

    @pytest.mark.asyncio
    async def test_with_staged_and_bot(self, mock_week):
        from src.tools.review_pipeline import friday_review_summary
        bot = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock()
        bot.get_channel.return_value = channel
        admin = MagicMock()
        admin.send = AsyncMock()
        bot.fetch_user = AsyncMock(return_value=admin)

        with patch("src.tools.weekly_quota._load_week", return_value=mock_week), \
             patch("config.settings.ERNOS_CODE_CHANNEL_ID", 123), \
             patch("config.settings.ADMIN_USER_ID", 456):
            await friday_review_summary(bot)

        channel.send.assert_called_once()
        admin.send.assert_called_once()


# ── daily_quota_check ────────────────────────────────────
class TestDailyQuotaCheck:
    @pytest.mark.asyncio
    async def test_runs(self):
        from src.tools.review_pipeline import daily_quota_check
        with patch("src.tools.weekly_quota._day_name", return_value="monday"), \
             patch("src.tools.weekly_quota.get_remaining_quota", return_value=6.0):
            await daily_quota_check()


# ── _count_week_tasks ────────────────────────────────────
class TestCountWeekTasks:
    def test_counts(self):
        from src.tools.review_pipeline import _count_week_tasks
        state = {"days": {
            "monday": {"tasks": [1, 2]},
            "tuesday": {"tasks": [3]},
        }}
        assert _count_week_tasks(state) == 3

    def test_empty(self):
        from src.tools.review_pipeline import _count_week_tasks
        assert _count_week_tasks({"days": {}}) == 0

    def test_non_dict_day(self):
        from src.tools.review_pipeline import _count_week_tasks
        assert _count_week_tasks({"days": {"monday": "invalid"}}) == 0
