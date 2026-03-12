"""
Tests for skill_graph.py — Skill dependency graph for non-crafting goals.
"""

import pytest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestSkillGraph:
    """Tests for SkillGraph class."""

    @pytest.fixture
    def graph(self, tmp_path, monkeypatch):
        """Create a skill graph with temp file."""
        from src.gaming.skill_graph import SkillGraph

        monkeypatch.setattr(SkillGraph, "GRAPH_FILE", str(tmp_path / "skill_graph.json"))
        return SkillGraph()

    def test_default_goals_loaded(self, graph):
        """Should have default seeded goals."""
        assert graph.has_goal("build shelter")
        assert graph.has_goal("go mining")
        assert graph.has_goal("start farm")
        assert graph.has_goal("prepare for night")

    def test_get_plan_leaf_action(self, graph):
        """Unknown goal should return itself as single step."""
        plan = graph.get_plan("collect oak_log 5")
        assert plan == ["collect oak_log 5"]

    def test_get_plan_known_goal(self, graph):
        """Known goal should return expanded steps."""
        plan = graph.get_plan("start farm")
        assert len(plan) >= 2
        # Should include wooden hoe and seeds at minimum
        assert any("hoe" in step or "seeds" in step or "water" in step for step in plan)

    def test_get_plan_skips_completed(self, graph):
        """Planning should skip completed steps."""
        plan_full = graph.get_plan("start farm")
        plan_partial = graph.get_plan("start farm", completed={"craft wooden_hoe"})
        assert len(plan_partial) <= len(plan_full)

    def test_add_goal(self, graph):
        """Should add new goal to graph."""
        graph.add_goal("build bridge", ["collect oak_log 30", "craft oak_planks 120"])
        assert graph.has_goal("build bridge")
        plan = graph.get_plan("build bridge")
        assert "collect oak_log 30" in plan

    def test_add_goal_persists(self, tmp_path, monkeypatch):
        """Added goals should persist across instances."""
        from src.gaming.skill_graph import SkillGraph

        graph_file = str(tmp_path / "persist_test.json")
        monkeypatch.setattr(SkillGraph, "GRAPH_FILE", graph_file)

        g1 = SkillGraph()
        g1.add_goal("test_goal", ["step1", "step2"])

        g2 = SkillGraph()
        assert g2.has_goal("test_goal")

    def test_has_goal_false(self, graph):
        """has_goal should return False for unknown goals."""
        assert graph.has_goal("fly to the moon") is False

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        """Should handle corrupt graph file gracefully."""
        from src.gaming.skill_graph import SkillGraph

        graph_file = tmp_path / "corrupt.json"
        graph_file.write_text("not json")
        monkeypatch.setattr(SkillGraph, "GRAPH_FILE", str(graph_file))

        g = SkillGraph()
        # Should still have defaults
        assert g.has_goal("build shelter")

    def test_nested_dependencies(self, graph):
        """Goals with nested dependencies should expand recursively."""
        # "build house" depends on "build shelter" which depends on collect/craft
        plan = graph.get_plan("build house")
        assert len(plan) >= 3
        # Should have leaf actions, not just references to other goals
        assert all(not graph.has_goal(step) for step in plan)


class TestSkillGraphAsync:
    """Tests for async LLM goal generation."""

    @pytest.fixture
    def graph(self, tmp_path, monkeypatch):
        from src.gaming.skill_graph import SkillGraph
        monkeypatch.setattr(SkillGraph, "GRAPH_FILE", str(tmp_path / "async_graph.json"))
        return SkillGraph()

    @pytest.mark.asyncio
    async def test_add_goal_via_llm(self, graph):
        """Should add goal via LLM engine."""
        from unittest.mock import AsyncMock

        mock_engine = AsyncMock()
        mock_engine.process.return_value = (
            '{"prerequisites": ["collect sand 8", "craft glass 8", "place blocks"]}',
        )

        prereqs = await graph.add_goal_via_llm("build greenhouse", engine=mock_engine)
        assert len(prereqs) == 3
        assert graph.has_goal("build greenhouse")

    @pytest.mark.asyncio
    async def test_add_goal_via_llm_error(self, graph):
        """Should handle LLM errors gracefully."""
        from unittest.mock import AsyncMock

        mock_engine = AsyncMock()
        mock_engine.process.side_effect = Exception("API error")

        prereqs = await graph.add_goal_via_llm("impossible_goal", engine=mock_engine)
        assert prereqs == []
        assert not graph.has_goal("impossible_goal")

    @pytest.mark.asyncio
    async def test_add_goal_via_llm_invalid_response(self, graph):
        """Should handle invalid LLM response."""
        from unittest.mock import AsyncMock

        mock_engine = AsyncMock()
        mock_engine.process.return_value = ("not json at all",)

        prereqs = await graph.add_goal_via_llm("weird_goal", engine=mock_engine)
        assert prereqs == []


class TestGetSkillGraph:
    """Tests for singleton getter."""

    def test_singleton(self):
        """get_skill_graph should return same instance."""
        import src.gaming.skill_graph as mod
        mod._skill_graph = None

        g1 = mod.get_skill_graph()
        g2 = mod.get_skill_graph()
        assert g1 is g2

        mod._skill_graph = None
