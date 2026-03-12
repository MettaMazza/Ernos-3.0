"""Tests for Strategy Lobes: Gardener, Goal, Project, Journalist — 18 tests."""
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


# --- Helpers ---
def _make_lobe():
    lobe = MagicMock()
    lobe.bot = MagicMock()
    lobe.bot.engine_manager = MagicMock()
    lobe.bot.loop = MagicMock()
    lobe.hippocampus = MagicMock()
    lobe.hippocampus.graph = MagicMock()
    lobe.hippocampus.timeline = MagicMock()
    return lobe


# ===================== GardenerAbility =====================

class TestGardenerAbility:

    @pytest.fixture
    def gardener(self):
        with patch("src.lobes.strategy.gardener.KnowledgeGraph"):
            from src.lobes.strategy.gardener import GardenerAbility
            lobe = _make_lobe()
            g = GardenerAbility(lobe)
            g.graph = MagicMock()
            return g

    def test_string_similarity_identical(self, gardener):
        assert gardener._string_similarity("hello", "hello") == 1.0

    def test_string_similarity_different(self, gardener):
        assert gardener._string_similarity("hello", "world") < 0.5

    def test_string_similarity_empty(self, gardener):
        assert gardener._string_similarity("", "hello") == 0.0

    def test_string_similarity_similar(self, gardener):
        sim = gardener._string_similarity("Apple Inc", "Apple Ink")
        assert sim > 0.8

    @pytest.mark.asyncio
    async def test_refine_graph_empty(self, gardener):
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []
        gardener.graph.driver.session.return_value = mock_session
        result = await gardener.refine_graph()
        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_execute(self, gardener, tmp_path):
        with patch("os.walk", return_value=[(str(tmp_path), [], ["test.py"])]):
            with patch("builtins.open", MagicMock()):
                result = await gardener.execute("analyze codebase")
                assert "Gardener" in result


# ===================== GoalAbility =====================

class TestGoalAbility:

    @pytest.fixture
    def goal(self):
        with patch("src.lobes.strategy.goal.settings"):
            from src.lobes.strategy.goal import GoalAbility
            lobe = _make_lobe()
            return GoalAbility(lobe)

    @pytest.mark.asyncio
    async def test_execute_no_goals(self, goal):
        with patch("src.tools.memory.manage_goals", return_value="No active goals"):
            with patch("src.bot.globals") as mock_globals:
                mock_globals.active_message.get.return_value = MagicMock(author=MagicMock(id=123))
                result = await goal.execute()
                assert result is None

    @pytest.mark.asyncio
    async def test_execute_with_goals(self, goal):
        with patch("src.tools.memory.manage_goals", return_value="1. Learn Python"):
            with patch("src.bot.globals") as mock_globals:
                mock_globals.active_message.get.return_value = MagicMock(author=MagicMock(id=123))
                result = await goal.execute()
                assert "Learn Python" in result

    @pytest.mark.asyncio
    async def test_audit_no_file(self, goal):
        with patch("src.lobes.strategy.goal.globals") as mock_globals:
            mock_globals.active_message.get.return_value = MagicMock(author=MagicMock(id=123))
            result = await goal._audit_goals(user_id="123")
            assert "No goals" in result or "doesn't exist" in result

    @pytest.mark.asyncio
    async def test_audit_with_stagnant(self, goal, tmp_path):
        goal_file = tmp_path / "goals.json"
        goals = [{"id": 1, "text": "Old goal", "status": "active",
                  "created_at": "2020-01-01T00:00:00", "updated_at": "2020-01-01T00:00:00"}]
        goal_file.write_text(json.dumps(goals))
        with patch("src.lobes.strategy.goal.Path", return_value=goal_file):
            result = await goal._audit_goals(user_id="123")
            assert "Stagnant" in result

    @pytest.mark.asyncio
    async def test_decompose_no_engine(self, goal):
        goal.bot.engine_manager.get_active_engine.return_value = None
        result = await goal._decompose_goal("learn rust")
        assert "error" in result


# ===================== ProjectLeadAbility =====================

class TestProjectLeadAbility:

    @pytest.fixture
    def project(self):
        from src.lobes.strategy.project import ProjectLeadAbility
        lobe = _make_lobe()
        return ProjectLeadAbility(lobe)

    def test_parse_valid_json(self, project):
        response = '{"project_name": "Test", "milestones": [{"id": 1, "title": "Step 1"}]}'
        result = project._parse_project_plan(response)
        assert result["project_name"] == "Test"
        assert len(result["milestones"]) == 1

    def test_parse_invalid_json(self, project):
        response = "This is just plain text without JSON"
        result = project._parse_project_plan(response)
        assert "milestones" in result  # Fallback should still produce milestones

    @pytest.mark.asyncio
    async def test_execute_no_engine(self, project):
        project.bot.engine_manager.get_active_engine.return_value = None
        result = await project.execute("build a website")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_success(self, project):
        engine = MagicMock()
        project.bot.engine_manager.get_active_engine.return_value = engine
        plan_json = json.dumps({"project_name": "Website", "milestones": [{"id": 1, "title": "Setup"}]})
        project.bot.loop.run_in_executor = AsyncMock(return_value=plan_json)
        result = await project.execute("build a website")
        assert result["project_name"] == "Website"


# ===================== JournalistAbility =====================

class TestJournalistAbility:

    @pytest.fixture
    def journalist(self):
        from src.lobes.memory.journalist import JournalistAbility
        lobe = _make_lobe()
        return JournalistAbility(lobe)

    @pytest.mark.asyncio
    async def test_no_events(self, journalist):
        journalist.hippocampus.timeline.get_recent_events.return_value = []
        result = await journalist.execute()
        assert "No recent events" in result

    @pytest.mark.asyncio
    async def test_with_events(self, journalist, tmp_path):
        journalist.hippocampus.timeline.get_recent_events.return_value = [
            {"timestamp": "2025-01-01", "description": "User joined", "type": "system"}
        ]
        with patch("src.lobes.memory.journalist.Path") as mock_path:
            mock_file = MagicMock()
            mock_path.return_value = mock_file
            mock_file.parent = MagicMock()
            with patch("builtins.open", MagicMock()):
                result = await journalist.execute()
                assert "1 events" in result
