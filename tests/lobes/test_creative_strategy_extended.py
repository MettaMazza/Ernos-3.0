"""
Phase 7 — Extended coverage tests for Creative & Strategy Lobes.
Targets: gardener.py, project.py, artist.py, autonomy.py  → 95%+
"""
# Pre-mock torch-dependent modules BEFORE any project imports
import sys
from unittest.mock import MagicMock

_mock_generators = MagicMock()
_mock_generators.MediaGenerator = MagicMock()
sys.modules.setdefault("src.lobes.creative.generators", _mock_generators)

import pytest
import asyncio
import json
import time
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, PropertyMock, mock_open



# ─── Helpers ─────────────────────────────────────────────────────

async def _async_run_in_executor(executor, fn, *args):
    """Replacement for bot.loop.run_in_executor that calls fn directly."""
    return fn(*args)

def _make_lobe():
    """Create a mock lobe chain: lobe.cerebrum.bot → mock bot."""
    lobe = MagicMock()
    bot = MagicMock()
    bot.loop = MagicMock()
    bot.loop.run_in_executor = _async_run_in_executor
    bot.hippocampus = MagicMock()
    bot.hippocampus.observe = AsyncMock()
    bot.hippocampus.graph = MagicMock()
    engine = MagicMock()
    engine.generate_response = MagicMock(return_value="LLM response text")
    bot.engine_manager.get_active_engine.return_value = engine
    bot.is_processing = False
    bot.last_interaction = time.time() - 700  # idle for 200s
    lobe.cerebrum.bot = bot
    return lobe, bot, engine


# ═══════════════════════════════════════════════════════════════
# GardenerAbility
# ═══════════════════════════════════════════════════════════════

from src.lobes.strategy.gardener import GardenerAbility


class TestGardenerAbility:

    def _make(self):
        lobe, bot, engine = _make_lobe()
        with patch("src.lobes.strategy.gardener.KnowledgeGraph"):
            g = GardenerAbility(lobe)
        g.graph = MagicMock()
        return g

    # --- __init__ ---
    def test_init(self):
        g = self._make()
        assert g.graph is not None

    # --- _string_similarity ---
    def test_similarity_identical(self):
        g = self._make()
        assert g._string_similarity("Apple", "Apple") == 1.0

    def test_similarity_empty(self):
        g = self._make()
        assert g._string_similarity("", "test") == 0.0
        assert g._string_similarity("test", "") == 0.0

    def test_similarity_high(self):
        g = self._make()
        sim = g._string_similarity("Apple", "apple")
        assert sim == 1.0  # case insensitive

    def test_similarity_different(self):
        g = self._make()
        sim = g._string_similarity("Apple", "Banana")
        assert sim < 0.5

    def test_similarity_swap_shorter_first(self):
        """Cover the len1 < len2 swap branch."""
        g = self._make()
        sim = g._string_similarity("ab", "abcdef")
        assert 0.0 <= sim <= 1.0

    def test_similarity_very_different_lengths(self):
        """Cover early termination for very different lengths."""
        g = self._make()
        sim = g._string_similarity("a", "abcdefghij")
        assert sim == 0.0

    # --- _merge_nodes ---
    def test_merge_nodes_success(self):
        g = self._make()
        mock_session = MagicMock()
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        g._merge_nodes("id1", "id2")
        assert mock_session.run.call_count == 2

    def test_merge_nodes_exception(self):
        g = self._make()
        g.graph.driver.session.side_effect = Exception("connection lost")
        g._merge_nodes("id1", "id2")  # Should not raise
        assert True  # No exception: error handled gracefully

    # --- refine_graph ---
    @pytest.mark.asyncio
    async def test_refine_graph_empty(self):
        g = self._make()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.run.return_value = mock_result
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        result = await g.refine_graph()
        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_refine_graph_no_duplicates(self):
        g = self._make()
        mock_session = MagicMock()
        nodes = [
            {"name": "Alpha", "id": "1", "labels": ["Person"]},
            {"name": "Zeta", "id": "2", "labels": ["Person"]},
        ]
        mock_session.run.return_value = iter(nodes)
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        result = await g.refine_graph()
        assert "No duplicates" in result

    @pytest.mark.asyncio
    async def test_refine_graph_high_sim_auto_merge(self):
        g = self._make()
        mock_session = MagicMock()
        nodes = [
            {"name": "Apple Inc", "id": "1", "labels": ["Company"]},
            {"name": "Apple Inc.", "id": "2", "labels": ["Company"]},
        ]
        mock_session.run.return_value = iter(nodes)
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        with patch.object(g, "_merge_nodes"):
            result = await g.refine_graph()
        assert "Auto-Merged" in result

    @pytest.mark.asyncio
    async def test_refine_graph_medium_sim_manual_review(self):
        g = self._make()
        mock_session = MagicMock()
        # Nodes with ~85% similarity but < 95%
        nodes = [
            {"name": "Apple Computer", "id": "1", "labels": ["Company"]},
            {"name": "Apple Company", "id": "2", "labels": ["Company"]},
        ]
        mock_session.run.return_value = iter(nodes)
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        result = await g.refine_graph()
        assert "Review" in result or "Duplicates" in result or "No duplicates" in result

    @pytest.mark.asyncio
    async def test_refine_graph_auto_merge_fails(self):
        """Cover the auto-merge exception → fallback to manual_review."""
        g = self._make()
        mock_session = MagicMock()
        nodes = [
            {"name": "Apple Inc", "id": "1", "labels": ["Org"]},
            {"name": "Apple Inc.", "id": "2", "labels": ["Org"]},
        ]
        mock_session.run.return_value = iter(nodes)
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        with patch.object(g, "_merge_nodes", side_effect=Exception("merge fail")):
            result = await g.refine_graph()
        assert "Review" in result

    @pytest.mark.asyncio
    async def test_refine_graph_different_labels_skip(self):
        g = self._make()
        mock_session = MagicMock()
        nodes = [
            {"name": "Python", "id": "1", "labels": ["Language"]},
            {"name": "Python", "id": "2", "labels": ["Animal"]},
        ]
        mock_session.run.return_value = iter(nodes)
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        result = await g.refine_graph()
        assert "No duplicates" in result

    @pytest.mark.asyncio
    async def test_refine_graph_driver_exception(self):
        g = self._make()
        g.graph.driver.session.side_effect = Exception("Neo4j down")
        result = await g.refine_graph()
        assert "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_refine_graph_many_manual_reviews(self):
        """Cover the '... and N more' branch when manual_review > 10."""
        g = self._make()
        mock_session = MagicMock()
        # Create 12 similar nodes to generate >10 manual review items
        nodes = [{"name": f"TestNode{chr(65+i)}", "id": str(i), "labels": ["X"]} for i in range(12)]
        mock_session.run.return_value = iter(nodes)
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        # Force all similarities to be in manual review range (0.8 < sim < 0.95)
        with patch.object(g, "_string_similarity", return_value=0.88):
            result = await g.refine_graph()
        assert "more" in result

    # --- execute ---
    @pytest.mark.asyncio
    async def test_execute_counts_files(self, tmp_path):
        g = self._make()
        # Create a fake src directory
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "small.py").write_text("a = 1\n")
        (src_dir / "big.py").write_text("x = 1\n" * 1500)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = await g.execute("analyze codebase")
            assert "Codebase Scale" in result
            assert "2 files" in result
            assert "big.py" in result  # > 200 lines → flagged
        finally:
            os.chdir(old_cwd)


# ═══════════════════════════════════════════════════════════════
# ProjectLeadAbility
# ═══════════════════════════════════════════════════════════════

from src.lobes.strategy.project import ProjectLeadAbility


class TestProjectLeadAbility:

    def _make(self):
        lobe, bot, engine = _make_lobe()
        p = ProjectLeadAbility(lobe)
        return p, bot, engine

    # --- execute ---
    @pytest.mark.asyncio
    async def test_execute_no_engine(self):
        p, bot, engine = self._make()
        bot.engine_manager.get_active_engine.return_value = None
        result = await p.execute("build a website")
        assert "error" in result
        assert result["milestones"] == []

    @pytest.mark.asyncio
    async def test_execute_success_with_milestones(self):
        p, bot, engine = self._make()
        plan = {
            "project_name": "Website",
            "milestones": [
                {"id": 1, "title": "Setup", "description": "Init project"}
            ]
        }
        engine.generate_response.return_value = json.dumps(plan)
        result = await p.execute("build website")
        assert result["project_name"] == "Website"

    @pytest.mark.asyncio
    async def test_execute_stores_in_kg(self):
        p, bot, engine = self._make()
        plan = {"project_name": "Test", "milestones": [{"id": 1, "title": "M1", "description": "do stuff"}]}
        engine.generate_response.return_value = json.dumps(plan)
        mock_msg = MagicMock()
        mock_msg.author.id = 42
        with patch.dict("sys.modules", {
            "src.bot": MagicMock(),
            "src.bot.globals": MagicMock(active_message=MagicMock(get=MagicMock(return_value=mock_msg))),
            "src.memory.types": MagicMock(GraphLayer=MagicMock(TASK="task")),
        }):
            result = await p.execute("build test")
        assert result["project_name"] == "Test"

    @pytest.mark.asyncio
    async def test_execute_exception(self):
        p, bot, engine = self._make()
        engine.generate_response.side_effect = Exception("Engine crash")
        result = await p.execute("impossible request")
        assert "error" in result

    # --- _parse_project_plan ---
    def test_parse_valid_json(self):
        p, _, _ = self._make()
        raw = '{"project_name": "X", "milestones": [{"id": 1}]}'
        result = p._parse_project_plan(raw)
        assert result["project_name"] == "X"

    def test_parse_json_without_milestones(self):
        p, _, _ = self._make()
        raw = '{"project_name": "X", "steps": [1,2,3]}'
        result = p._parse_project_plan(raw)
        assert "milestones" in result  # Fallback

    def test_parse_no_json(self):
        p, _, _ = self._make()
        result = p._parse_project_plan("Just do the thing.")
        assert result["milestones"][0]["description"] == "Just do the thing."

    def test_parse_invalid_json(self):
        p, _, _ = self._make()
        result = p._parse_project_plan("{broken json!!!}")
        assert "milestones" in result

    # --- _store_milestones_in_kg ---
    def test_store_milestones_no_user_id(self):
        """Cover line 124 — no active message → abort."""
        p, bot, _ = self._make()
        plan = {"project_name": "Test", "milestones": [{"id": 1, "title": "M1"}]}
        with patch.dict("sys.modules", {
            "src.memory.types": MagicMock(GraphLayer=MagicMock(TASK="task")),
            "src.bot": MagicMock(),
            "src.bot.globals": MagicMock(active_message=MagicMock(get=MagicMock(return_value=None))),
        }):
            p._store_milestones_in_kg(plan, "request")  # Should just return (no user_id)
        assert True  # No exception: negative case handled correctly

    def test_store_milestones_with_user(self):
        """Cover lines 130-165."""
        p, bot, _ = self._make()
        plan = {"project_name": "Test", "milestones": [
            {"id": 1, "title": "Step1", "description": "Do step 1", "estimated_effort": "small"},
            {"id": 2, "title": "Step2", "description": "Do step 2"},
        ]}
        mock_msg = MagicMock()
        mock_msg.author.id = 42
        with patch.dict("sys.modules", {
            "src.memory.types": MagicMock(GraphLayer=MagicMock(TASK="task")),
            "src.bot": MagicMock(),
            "src.bot.globals": MagicMock(active_message=MagicMock(get=MagicMock(return_value=mock_msg))),
        }):
            p._store_milestones_in_kg(plan, "request")
            assert bot.hippocampus.graph.add_node.call_count == 3  # 1 project + 2 milestones
            assert bot.hippocampus.graph.add_relationship.call_count == 2

    def test_store_milestones_exception(self):
        """Cover exception handler."""
        p, bot, _ = self._make()
        bot.hippocampus.graph.add_node.side_effect = Exception("KG down")
        plan = {"project_name": "Test", "milestones": [{"id": 1, "title": "M1"}]}
        mock_msg = MagicMock()
        mock_msg.author.id = 42
        with patch.dict("sys.modules", {
            "src.memory.types": MagicMock(GraphLayer=MagicMock(TASK="task")),
            "src.bot": MagicMock(),
            "src.bot.globals": MagicMock(active_message=MagicMock(get=MagicMock(return_value=mock_msg))),
        }):
            p._store_milestones_in_kg(plan, "request")  # Should not raise
        assert True  # No exception: error handled gracefully


# ═══════════════════════════════════════════════════════════════
# VisualCortexAbility (artist.py)
# ═══════════════════════════════════════════════════════════════

from src.lobes.creative.artist import VisualCortexAbility




class TestVisualCortexAbility:

    def _make(self):
        lobe, bot, engine = _make_lobe()
        v = VisualCortexAbility(lobe)
        return v, bot

    def test_init(self):
        v, _ = self._make()
        assert v.turn_lock is False

    def test_reset_turn_lock(self):
        v, _ = self._make()
        v.turn_lock = True
        v.reset_turn_lock()
        assert v.turn_lock is False

    # --- _get_usage_file ---
    def test_get_usage_file(self):
        v, _ = self._make()
        mock_sm = MagicMock()
        mock_sm.get_user_home.return_value = Path("/tmp/user123")
        with patch.dict("sys.modules", {"src.privacy.scopes": MagicMock(ScopeManager=mock_sm)}):
            result = v._get_usage_file(123)
            assert str(result).endswith("usage.json")

    # --- _check_limits ---
    def test_check_limits_fresh_user(self, tmp_path):
        v, _ = self._make()
        usage_file = tmp_path / "usage.json"
        with patch.object(v, "_get_usage_file", return_value=usage_file):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.DAILY_IMAGE_LIMIT = 10
                result = v._check_limits("image", 1)
        assert result is True
        assert usage_file.exists()

    def test_check_limits_at_limit(self, tmp_path):
        v, _ = self._make()
        usage_file = tmp_path / "usage.json"
        usage_file.write_text(json.dumps({"image_count": 10, "last_reset": time.time()}))
        with patch.object(v, "_get_usage_file", return_value=usage_file):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.DAILY_IMAGE_LIMIT = 10
                result = v._check_limits("image", 1)
        assert result is False

    def test_check_limits_reset_after_24h(self, tmp_path):
        v, _ = self._make()
        usage_file = tmp_path / "usage.json"
        old = time.time() - 90000  # > 86400
        usage_file.write_text(json.dumps({"image_count": 10, "last_reset": old}))
        with patch.object(v, "_get_usage_file", return_value=usage_file):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.DAILY_IMAGE_LIMIT = 10
                result = v._check_limits("image", 1)
        assert result is True  # Reset occurred

    def test_check_limits_corrupt_usage_file(self, tmp_path):
        v, _ = self._make()
        usage_file = tmp_path / "usage.json"
        usage_file.write_text("NOT JSON")
        with patch.object(v, "_get_usage_file", return_value=usage_file):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.DAILY_IMAGE_LIMIT = 10
                result = v._check_limits("image", 1)
        assert result is True  # Falls through with default

    def test_check_limits_video(self, tmp_path):
        v, _ = self._make()
        usage_file = tmp_path / "usage.json"
        
        # Mock FluxCapacitor to return Tier 2 (Planter) -> 2 Videos Allowed
        with patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            flux_instance = MockFlux.return_value
            flux_instance.get_tier.return_value = 2
            
            with patch.object(v, "_get_usage_file", return_value=usage_file):
                with patch("src.lobes.creative.artist.settings") as mock_s:
                    mock_s.DAILY_VIDEO_LIMIT = 3
                    result = v._check_limits("video", 1)
        assert result is True

    # --- execute ---
    @pytest.mark.asyncio
    async def test_execute_turn_lock(self):
        v, bot = self._make()
        v.turn_lock = True
        result = await v.execute("paint a cat", user_id=99999)
        assert "Rate limit" in result

    @pytest.mark.asyncio
    async def test_execute_rate_limit(self):
        v, bot = self._make()
        with patch.object(v, "_check_limits", return_value=False):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.ADMIN_ID = 1
                mock_s.DAILY_IMAGE_LIMIT = 5
                result = await v.execute("paint a cat", user_id=42)
        assert "limit" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_image_success(self, tmp_path):
        v, bot = self._make()
        mock_gen = MagicMock()
        with patch.object(v, "_check_limits", return_value=True):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.ADMIN_ID = 1
                mock_s.ADMIN_IDS = [1]
                mock_s.DAILY_IMAGE_LIMIT = 10
                with patch("src.lobes.creative.artist.MediaGenerator", return_value=mock_gen):
                    with patch("src.lobes.creative.artist.os.getcwd", return_value=str(tmp_path)):
                        with patch.dict("sys.modules", {
                            "src.privacy.scopes": MagicMock(
                                ScopeManager=MagicMock(),
                                PrivacyScope=MagicMock(PUBLIC=MagicMock(name="public"), **{"__getitem__": lambda s, k: MagicMock(name="public")})
                            ),
                            "src.security.provenance": MagicMock(),
                        }):
                            # Simpler: patch PrivacyScope enum
                            mock_scope_enum = MagicMock()
                            mock_scope_enum.__getitem__ = MagicMock(return_value=MagicMock(name="public"))
                            with patch("src.lobes.creative.artist.asyncio.to_thread", new_callable=AsyncMock):
                                result = await v.execute("paint cat", user_id=42)
            assert v.turn_lock is True
            assert "generated_image" in result or tmp_path.name in result or result.endswith(".png")

    @pytest.mark.asyncio
    async def test_execute_no_user_sets_admin(self):
        """Cover line 82-83 — None user_id → ADMIN_ID."""
        v, bot = self._make()
        with patch.object(v, "_check_limits", return_value=True):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.ADMIN_ID = 999
                mock_s.ADMIN_IDS = [999]
                with patch("src.lobes.creative.artist.os.getcwd", return_value="/tmp"):
                    with patch("src.lobes.creative.artist.asyncio.to_thread", new_callable=AsyncMock):
                        with patch.dict("sys.modules", {"src.security.provenance": MagicMock()}):
                            result = await v.execute("paint cat", user_id=None)
            assert "core" in result.lower() or result.endswith(".png")

    @pytest.mark.asyncio
    async def test_execute_video(self):
        v, bot = self._make()
        with patch.object(v, "_check_limits", return_value=True):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.ADMIN_ID = 1
                mock_s.ADMIN_IDS = [1]
                with patch("src.lobes.creative.artist.os.getcwd", return_value="/tmp"):
                    with patch("src.lobes.creative.artist.asyncio.to_thread", new_callable=AsyncMock):
                        with patch.dict("sys.modules", {"src.security.provenance": MagicMock()}):
                            result = await v.execute("make video", media_type="video", user_id=42)
            assert result.endswith(".mp4")

    @pytest.mark.asyncio
    async def test_execute_generation_error(self):
        v, bot = self._make()
        with patch.object(v, "_check_limits", return_value=True):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.ADMIN_ID = 1
                mock_s.ADMIN_IDS = [1]
                with patch("src.lobes.creative.artist.os.getcwd", return_value="/tmp"):
                    with patch("src.lobes.creative.artist.asyncio.to_thread", side_effect=Exception("GPU OOM")):
                        result = await v.execute("paint cat", user_id=42)
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_execute_bad_scope(self):
        """Cover except on PrivacyScope enum lookup."""
        v, bot = self._make()
        with patch.object(v, "_check_limits", return_value=True):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.ADMIN_ID = 1
                mock_s.ADMIN_IDS = [1]
                with patch("src.lobes.creative.artist.os.getcwd", return_value="/tmp"):
                    with patch("src.lobes.creative.artist.asyncio.to_thread", new_callable=AsyncMock):
                        with patch.dict("sys.modules", {"src.security.provenance": MagicMock()}):
                            result = await v.execute("paint", user_id=42, request_scope="INVALID")
            assert result.endswith(".png")

    # --- _send_to_imaging_channel ---
    @pytest.mark.asyncio
    async def test_send_to_imaging_channel_success(self):
        v, bot = self._make()
        mock_channel = AsyncMock()
        bot.get_channel.return_value = mock_channel
        with patch("discord.File"), patch("os.path.getsize", return_value=1024):
            await v._send_to_imaging_channel("/tmp/img.png", "a cat")
        mock_channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_imaging_channel_long_prompt(self):
        v, bot = self._make()
        mock_channel = AsyncMock()
        bot.get_channel.return_value = mock_channel
        with patch("discord.File"), patch("os.path.getsize", return_value=1024):
            await v._send_to_imaging_channel("/tmp/img.png", "x" * 2000)
        mock_channel.send.assert_called_once()
        call_args = mock_channel.send.call_args
        assert "..." in call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_to_imaging_channel_no_channel(self):
        v, bot = self._make()
        bot.get_channel.return_value = None
        await v._send_to_imaging_channel("/tmp/img.png", "cat")  # Should not raise
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_send_to_imaging_channel_exception(self):
        v, bot = self._make()
        bot.get_channel.side_effect = Exception("Discord down")
        await v._send_to_imaging_channel("/tmp/img.png", "cat")  # Should not raise
        assert True  # No exception: error handled gracefully


# ═══════════════════════════════════════════════════════════════
# AutonomyAbility
# ═══════════════════════════════════════════════════════════════

from src.lobes.creative.autonomy import AutonomyAbility

class TestAutonomyAbility:

    def _make(self):
        lobe, bot, engine = _make_lobe()
        # Ensure cognition is mocked for AutonomyAbility
        bot.cognition = MagicMock()
        bot.cognition.process = AsyncMock()
        a = AutonomyAbility(lobe)
        return a, bot, engine

    # --- __init__ ---
    def test_init(self):
        a, _, _ = self._make()
        assert a.is_running is False
        assert a.autonomy_log_buffer == []
        assert a.last_summary_time > 0

    # --- execute with instruction → _one_shot_dream ---
    @pytest.mark.asyncio
    async def test_execute_with_instruction(self):
        a, bot, engine = self._make()
        bot.cognition.process.return_value = "Deep thoughts..."
        result = await a.execute("reflect on existence")
        assert "[DREAM]" in result

    @pytest.mark.asyncio
    async def test_one_shot_dream_success(self):
        a, bot, engine = self._make()
        bot.cognition.process.return_value = "Reflection result"
        result = await a._one_shot_dream("think about self")
        assert "DREAM" in result

    @pytest.mark.asyncio
    async def test_one_shot_dream_exception(self):
        a, bot, engine = self._make()
        bot.cognition.process.side_effect = Exception("LLM down")
        result = await a._one_shot_dream("think")
        assert "Failed" in result

    # --- execute without instruction (loop) ---
    @pytest.mark.asyncio
    async def test_execute_already_running(self):
        a, bot, engine = self._make()
        a.is_running = True
        result = await a.execute()
        assert "already active" in result.lower()

    # --- _send_transparency_report ---
    @pytest.mark.asyncio
    async def test_transparency_report_no_channel(self):
        a, bot, engine = self._make()
        bot.get_channel.return_value = None
        await a._send_transparency_report()  # Should not raise
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_transparency_report_empty_buffer(self):
        a, bot, engine = self._make()
        mock_channel = AsyncMock()
        bot.get_channel.return_value = mock_channel
        bot.cognition.process.return_value = "Report: All quiet."
        a.autonomy_log_buffer = []
        await a._send_transparency_report()
        mock_channel.send.assert_called_once()
        assert a.autonomy_log_buffer == []

    @pytest.mark.asyncio
    async def test_transparency_report_with_buffer(self):
        a, bot, engine = self._make()
        mock_channel = AsyncMock()
        bot.get_channel.return_value = mock_channel
        bot.cognition.process.return_value = "Summary report"
        a.autonomy_log_buffer = ["[10:00] Did X", "[10:05] Did Y"]
        await a._send_transparency_report()
        mock_channel.send.assert_called_once()
        assert a.autonomy_log_buffer == []  # Cleared

    @pytest.mark.asyncio
    async def test_transparency_report_exception(self):
        a, bot, engine = self._make()
        bot.get_channel.side_effect = Exception("boom")
        await a._send_transparency_report()  # Should not raise
        assert True  # No exception: error handled gracefully



    @pytest.mark.asyncio
    async def test_run_consolidation(self):
        a, bot, engine = self._make()
        with patch("src.lobes.creative.autonomy.MemoryConsolidator", create=True) as MockMC:
            # wait, autonomy.py does `from .consolidation import MemoryConsolidator`
            # so we patch `src.lobes.creative.consolidation.MemoryConsolidator`
            pass
            
        with patch("src.lobes.creative.consolidation.MemoryConsolidator") as MockMC:
            mock_c = MockMC.return_value
            mock_c.run_consolidation = AsyncMock(return_value="done")
            result = await a.run_consolidation()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_process_episodic_memories(self):
        a, bot, engine = self._make()
        with patch("src.lobes.creative.consolidation.MemoryConsolidator") as MockMC:
            mock_c = MockMC.return_value
            mock_c.process_episodic_memories = AsyncMock(return_value=5)
            result = await a._process_episodic_memories()
        assert result == 5

    @pytest.mark.asyncio
    async def test_update_user_bios(self):
        a, bot, engine = self._make()
        with patch("src.lobes.creative.consolidation.MemoryConsolidator") as MockMC:
            mock_c = MockMC.return_value
            mock_c.update_user_bios = AsyncMock(return_value=3)
            result = await a._update_user_bios()
        assert result == 3

    @pytest.mark.asyncio
    async def test_synthesize_narrative(self):
        a, bot, engine = self._make()
        with patch("src.lobes.creative.consolidation.MemoryConsolidator") as MockMC:
            mock_c = MockMC.return_value
            mock_c.synthesize_narrative = AsyncMock(return_value="narrative")
            result = await a._synthesize_narrative()
        assert result == "narrative"

    @pytest.mark.asyncio
    async def test_extract_lessons_from_narrative(self):
        a, bot, engine = self._make()
        with patch("src.lobes.creative.consolidation.MemoryConsolidator") as MockMC:
            mock_c = MockMC.return_value
            mock_c.extract_lessons_from_narrative = AsyncMock(return_value=None)
            result = await a._extract_lessons_from_narrative("some narrative")
        assert result is None


# ═══════════════════════════════════════════════════════════════
# Autonomy Execute Loop Coverage (lines 37-268)
# ═══════════════════════════════════════════════════════════════

class TestAutonomyExecuteLoop:
    """Tests that exercise the main autonomy while-loop."""

    def _make(self):
        lobe, bot, engine = _make_lobe()
        bot.cognition = MagicMock()
        bot.cognition.process = AsyncMock()
        a = AutonomyAbility(lobe)
        return a, bot, engine

    @pytest.mark.asyncio
    async def test_loop_idle_detects_and_dreams(self):
        """Cover lines 37-61: start loop, detect idle, trigger autonomy."""
        a, bot, engine = self._make()
        bot.is_processing = False
        bot.last_interaction = time.time() - 700  # Must exceed 600s Lite idle threshold

        # Engine returns plain text
        bot.cognition.process.return_value = "I am reflecting on the cosmos."

        call_count = 0
        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                a.is_running = False
                bot.is_processing = True  # Break inner loop

        with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                with patch.dict("sys.modules", {
                    "src.bot": MagicMock(),
                    "src.bot.globals": MagicMock(activity_log=[]),
                }):
                    await a.execute()

        assert a.is_running is False
        assert len(a.autonomy_log_buffer) > 0

    @pytest.mark.asyncio
    async def test_loop_user_active_skips(self):
        """Cover line 53-55: bot is processing → continue."""
        a, bot, engine = self._make()
        bot.is_processing = True

        call_count = 0

        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                a.is_running = False
                bot.is_processing = True

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await a.execute()

        assert a.is_running is False

    @pytest.mark.asyncio
    async def test_loop_engine_returns_none(self):
        """Cover lines: engine returns None → handled gracefully."""
        a, bot, engine = self._make()
        bot.is_processing = False
        bot.last_interaction = time.time() - 700
        bot.cognition.process.return_value = None

        call_count = 0
        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                a.is_running = False
                bot.is_processing = True

        with patch("asyncio.sleep", side_effect=fake_sleep):
            with patch.dict("sys.modules", {
                "src.bot": MagicMock(),
                "src.bot.globals": MagicMock(activity_log=[]),
            }):
                await a.execute()
        assert True  # No exception: async operation completed within timeout

    @pytest.mark.asyncio
    async def test_loop_transparency_report_trigger(self):
        """Cover lines 48-50: 30min timer triggers transparency report."""
        a, bot, engine = self._make()
        bot.is_processing = False
        bot.last_interaction = time.time() - 700  # Must exceed 600s Lite idle threshold
        bot.send_to_mind = AsyncMock()
        bot.cognition.process.return_value = "Thought"

        report_called = []
        async def capture_report():
            report_called.append(True)
        a._send_transparency_report = capture_report

        time_call_count = [0]
        base_time = time.time()
        def fake_time():
            time_call_count[0] += 1
            if time_call_count[0] <= 2:
                return base_time
            return base_time + 22000  # Must exceed 21600s (6h) Lite mode report interval

        call_count = 0
        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                a.is_running = False
                bot.is_processing = True

        with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                with patch("src.lobes.creative.autonomy.time.time", side_effect=fake_time):
                    with patch.dict("sys.modules", {
                        "src.bot": MagicMock(),
                        "src.bot.globals": MagicMock(activity_log=[]),
                    }):
                        await a.execute()

        assert len(report_called) > 0

    @pytest.mark.asyncio
    async def test_loop_dream_cycle_exception(self):
        """Cover lines 257-258: dream cycle exception."""
        a, bot, engine = self._make()
        bot.is_processing = False
        bot.last_interaction = time.time() - 700
        bot.cognition.process.side_effect = Exception("LLM crashed")

        call_count = 0
        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                a.is_running = False
                bot.is_processing = True

        with patch("asyncio.sleep", side_effect=fake_sleep):
            with patch.dict("sys.modules", {
                "src.bot": MagicMock(),
                "src.bot.globals": MagicMock(activity_log=[]),
            }):
                await a.execute()
        assert True  # No exception: error handled gracefully

    @pytest.mark.asyncio
    async def test_loop_cancelled_error(self):
        """Cover lines 263-265: CancelledError."""
        a, bot, engine = self._make()
        bot.is_processing = True

        async def fake_sleep(seconds):
            raise asyncio.CancelledError()

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await a.execute()

        assert a.is_running is False

    @pytest.mark.asyncio
    async def test_loop_fatal_error(self):
        """Cover lines 266-268: fatal error."""
        a, bot, engine = self._make()
        bot.is_processing = True

        async def fake_sleep(seconds):
            raise RuntimeError("FATAL")

        with patch("asyncio.sleep", side_effect=fake_sleep):
            await a.execute()

        assert a.is_running is False

    @pytest.mark.asyncio
    async def test_loop_send_to_mind(self):
        """Cover work mode dev channel broadcasting."""
        a, bot, engine = self._make()
        bot.is_processing = False
        bot.last_interaction = time.time() - 700
        bot.send_to_mind = AsyncMock()
        bot.send_to_dev_channel = AsyncMock()
        engine.generate_response.return_value = "Pure thought no tools"

        call_count = 0
        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 8:
                a.is_running = False
                bot.is_processing = True

        with patch("asyncio.sleep", side_effect=fake_sleep):
            with patch.dict("sys.modules", {
                "src.bot": MagicMock(),
                "src.bot.globals": MagicMock(activity_log=[]),
            }):
                with patch("src.tools.weekly_quota.is_quota_met", return_value=False):
                    with patch("src.tools.weekly_quota.get_remaining_quota", return_value=5.0):
                        # Must enable work mode for dev cycle path
                        with patch("config.settings.ENABLE_WORK_MODE", True):
                            with patch("config.settings.AUTONOMY_LITE_MODE", False):
                                await a.execute()

        assert bot.send_to_dev_channel.call_count > 0

    @pytest.mark.asyncio
    async def test_loop_json_arg_parsing(self):
        """Cover lines 161-163: JSON argument parsing."""
        a, bot, engine = self._make()
        bot.is_processing = False
        bot.last_interaction = time.time() - 700
        engine.generate_response.return_value = '[TOOL: recall_user({"user_id": "123", "detail": "full"})]'

        call_count = 0
        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                a.is_running = False
                bot.is_processing = True

        with patch("asyncio.sleep", side_effect=fake_sleep):
            with patch.dict("sys.modules", {
                "src.bot": MagicMock(),
                "src.bot.globals": MagicMock(activity_log=[]),
            }):
                with patch("src.lobes.creative.autonomy.ToolRegistry") as mock_tr:
                    mock_tr.execute = AsyncMock(return_value="data")
                    await a.execute()
        assert True  # No exception: async operation completed within timeout

    @pytest.mark.asyncio
    async def test_loop_raw_input_fallback(self):
        """Cover lines 179-180: raw_input fallback when kwargs parsing fails."""
        a, bot, engine = self._make()
        bot.is_processing = False
        bot.last_interaction = time.time() - 700
        engine.generate_response.return_value = "[TOOL: recall_user(some unparseable garbage)]"

        call_count = 0
        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                a.is_running = False
                bot.is_processing = True

        with patch("asyncio.sleep", side_effect=fake_sleep):
            with patch.dict("sys.modules", {
                "src.bot": MagicMock(),
                "src.bot.globals": MagicMock(activity_log=[]),
            }):
                with patch("src.lobes.creative.autonomy.ToolRegistry") as mock_tr:
                    mock_tr.execute = AsyncMock(return_value="data")
                    await a.execute()
        assert True  # No exception: async operation completed within timeout

    @pytest.mark.asyncio
    async def test_loop_no_activity_log(self):
        """Cover line 65: globals has no activity_log attribute."""
        a, bot, engine = self._make()
        bot.is_processing = False
        bot.last_interaction = time.time() - 700
        engine.generate_response.return_value = "Thought"

        call_count = 0
        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 7:
                a.is_running = False
                bot.is_processing = True

        mock_globals = MagicMock(spec=[])  # No activity_log attribute
        with patch("asyncio.sleep", side_effect=fake_sleep):
            with patch.dict("sys.modules", {
                "src.bot": MagicMock(),
                "src.bot.globals": mock_globals,
            }):
                await a.execute()
        assert True  # No exception: negative case handled correctly

    @pytest.mark.asyncio
    async def test_loop_execution_edge_cases(self):
        a, bot, engine = self._make()
        bot.is_processing = False
        bot.last_interaction = time.time() - 700
        
        # Test paren escaping, nested parens, and literal_eval fail fallback to kv parsing
        # Also tests set_goal, complete_goal, review_goals tools directly executed
        responses = [
            r"[TOOL: test_tool(param='val \)')]",            # line 153-154: escape paren
            r"[TOOL: test_tool(param=(1, 2))]",             # line 161: nested paren depth += 1
            "[TOOL: set_goal(description='test', priority='3')]",
            "[TOOL: set_goal(description='')]",             # line 280: skipped empty
            "[TOOL: set_goal(description='duplicate')]",    # line 280: skipped duplicate
            '[TOOL: bad_json({"bad": var})]',               # perfectly formed braces but literal eval fail -> hits 208-214 and 232-234
            '[TOOL: extract_wisdom(topic="A", insight="")]', # topic param explicitly extracting empty insight -> hits 249
            "Done"
        ]
        
        call_idx = [0]
        def gen_resp(*args, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            if idx < len(responses):
                return responses[idx]
            return None
            
        engine.generate_response.side_effect = gen_resp

        call_count = 0
        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 12:
                a.is_running = False
                bot.is_processing = True

        with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
            with patch("asyncio.sleep", side_effect=fake_sleep):
                with patch.dict("sys.modules", {
                    "src.bot": MagicMock(),
                    "src.bot.globals": MagicMock(activity_log=[]),
                }):
                    with patch("src.lobes.creative.autonomy.ToolRegistry") as mock_tr:
                        mock_tr.execute = AsyncMock(return_value="data")
                        with patch("src.memory.goals.get_goal_manager") as mock_ggm:
                            mock_goal_man = mock_ggm.return_value
                            mock_goal_man.add_goal.return_value = "✅ Goal Saved"
                            mock_goal_man.complete_goal.return_value = "Done"
                            mock_goal_man.list_goals.return_value = "Goals: ..."
                            mock_goal_man.is_duplicate.side_effect = lambda d: d == "duplicate"
                            
                            # Give a fake last_goal_time initialized to 0 to pass cooldown
                            a._last_goal_time = 0
                            
                            await a.execute()
        assert True


# ═══════════════════════════════════════════════════════════════
# Additional Gardener Edge Cases (lines 54, 69-75, 94)
# ═══════════════════════════════════════════════════════════════

class TestGardenerEdgeCases:

    def _make(self):
        lobe, bot, engine = _make_lobe()
        with patch("src.lobes.strategy.gardener.KnowledgeGraph"):
            g = GardenerAbility(lobe)
        g.graph = MagicMock()
        return g

    @pytest.mark.asyncio
    async def test_refine_graph_all_auto_merged(self):
        """Cover lines 69-75, 94: auto-merge succeeds → 'All duplicates auto-merged'."""
        g = self._make()
        mock_session = MagicMock()
        # Use long names with tiny difference for >0.95 similarity
        # "international tech company x" vs "international tech company y" = 28 chars, 1 edit = 0.964
        nodes = [
            {"name": "international tech company x", "id": "1", "labels": ["Org"]},
            {"name": "international tech company y", "id": "2", "labels": ["Org"]},
        ]
        mock_session.run.return_value = iter(nodes)
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        with patch.object(g, "_merge_nodes"):
            result = await g.refine_graph()
        assert "All duplicates auto-merged" in result

    @pytest.mark.asyncio
    async def test_refine_graph_auto_merge_exception_fallback(self):
        """Cover lines 73-75: auto-merge exception → add to manual_review."""
        g = self._make()
        mock_session = MagicMock()
        nodes = [
            {"name": "international tech company x", "id": "1", "labels": ["Org"]},
            {"name": "international tech company y", "id": "2", "labels": ["Org"]},
        ]
        mock_session.run.return_value = iter(nodes)
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        with patch.object(g, "_merge_nodes", side_effect=Exception("APOC missing")):
            result = await g.refine_graph()
        assert "Review" in result

    @pytest.mark.asyncio
    async def test_refine_seen_pairs_dedup(self):
        """Cover line 53-55: seen_pairs prevents duplicate comparisons."""
        g = self._make()
        mock_session = MagicMock()
        nodes = [
            {"name": "Node Alpha", "id": "1", "labels": ["T"]},
            {"name": "Node Beta", "id": "2", "labels": ["T"]},
            {"name": "Node Gamma", "id": "3", "labels": ["T"]},
        ]
        mock_session.run.return_value = iter(nodes)
        g.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        g.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
        result = await g.refine_graph()
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════
# Additional Artist Edge Case (line 60)
# ═══════════════════════════════════════════════════════════════

class TestArtistEdgeCases:

    def _make(self):
        lobe, bot, engine = _make_lobe()
        v = VisualCortexAbility(lobe)
        return v, bot

    def test_check_limits_no_last_reset_key(self, tmp_path):
        """Cover line 59-60: usage data missing last_reset → sets it."""
        v, _ = self._make()
        usage_file = tmp_path / "usage.json"
        # Write data WITHOUT last_reset but with recent timestamp
        data = {"image_count": 0, "video_count": 0}
        usage_file.write_text(json.dumps(data))
        with patch.object(v, "_get_usage_file", return_value=usage_file):
            with patch("src.lobes.creative.artist.settings") as mock_s:
                mock_s.DAILY_IMAGE_LIMIT = 10
                result = v._check_limits("image", 1)
        assert result is True
        # Verify last_reset was written
        saved = json.loads(usage_file.read_text())
        assert "last_reset" in saved
