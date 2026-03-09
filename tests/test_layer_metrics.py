"""
Tests for src/memory/layer_metrics.py — Layer Competition Metrics
==================================================================

Covers LayerMetrics: record_query, compute_stats, score_layer,
get_trimming_candidates, merge_layer.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestLayerMetrics:
    """Test the LayerMetrics class."""

    def _make_metrics(self, driver=None):
        from src.memory.layer_metrics import LayerMetrics
        return LayerMetrics(driver=driver)

    # ── record_query ────────────────────────────────────────────

    def test_record_query_increments(self):
        m = self._make_metrics()
        m._query_counts.clear()  # Reset for hermetic test
        m.record_query("semantic")
        m.record_query("semantic")
        m.record_query("temporal")
        assert m._query_counts["semantic"] == 2
        assert m._query_counts["temporal"] == 1

    def test_record_query_new_layer(self):
        m = self._make_metrics()
        m._query_counts.pop("custom_layer", None)  # Reset for hermetic test
        m.record_query("custom_layer")
        assert m._query_counts["custom_layer"] == 1

    # ── compute_stats ───────────────────────────────────────────

    def test_compute_stats_no_driver(self):
        m = self._make_metrics(driver=None)
        result = m.compute_stats()
        assert result == {}

    def test_compute_stats_with_neo4j(self):
        # Set up mock Neo4j session with 3 queries
        mock_session = MagicMock()

        # Query 1: Node counts per layer
        node_records = [
            {"layer": "semantic", "nodes": 50},
            {"layer": "temporal", "nodes": 30},
            {"layer": "custom_test", "nodes": 20},
        ]
        # Query 2: Edge counts per layer
        edge_records = [
            {"layer": "semantic", "edges": 10},
            {"layer": "temporal", "edges": 5},
        ]
        # Query 3: Recency per layer
        recency_records = [
            {"layer": "semantic", "latest": "2026-01-01T00:00:00"},
            {"layer": "temporal", "latest": "2026-01-02T00:00:00"},
        ]

        mock_session.run.side_effect = [node_records, edge_records, recency_records]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        m = self._make_metrics(driver=mock_driver)
        m._query_counts.clear()  # Reset for hermetic test
        m.record_query("semantic")
        m.record_query("semantic")
        m.record_query("semantic")

        stats = m.compute_stats()

        assert "semantic" in stats
        assert "temporal" in stats
        assert "custom_test" in stats
        assert stats["semantic"]["nodes"] == 50
        assert stats["semantic"]["edges"] == 10
        assert stats["semantic"]["last_updated"] == "2026-01-01T00:00:00"
        assert stats["semantic"]["query_freq"] == 3
        assert "score" in stats["semantic"]
        assert "builtin" in stats["semantic"]

    def test_compute_stats_handles_none_layers(self):
        mock_session = MagicMock()
        node_records = [
            {"layer": None, "nodes": 10},
            {"layer": "semantic", "nodes": 5},
        ]
        mock_session.run.side_effect = [node_records, [], []]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        m = self._make_metrics(driver=mock_driver)
        stats = m.compute_stats()

        assert None not in stats
        assert "semantic" in stats

    def test_compute_stats_handles_exception(self):
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j down")
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        m = self._make_metrics(driver=mock_driver)
        result = m.compute_stats()
        assert result == {}

    def test_compute_stats_score_calculation(self):
        """Verify the score formula: density(0.4 + 0.3) + freq(0.3)."""
        mock_session = MagicMock()
        # One layer with ALL nodes and edges
        node_records = [{"layer": "only_layer", "nodes": 100}]
        edge_records = [{"layer": "only_layer", "edges": 50}]
        recency_records = []

        mock_session.run.side_effect = [node_records, edge_records, recency_records]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        m = self._make_metrics(driver=mock_driver)
        m._query_counts.clear()  # Reset for hermetic test
        m.record_query("only_layer")
        stats = m.compute_stats()

        # 100% of nodes(0.4) + 100% of edges(0.3) + 100% of queries(0.3) = 1.0
        assert stats["only_layer"]["score"] == 1.0

    # ── score_layer ─────────────────────────────────────────────

    def test_score_layer_from_cache(self):
        m = self._make_metrics()
        m._cache = {"semantic": {"score": 0.75}}
        assert m.score_layer("semantic") == 0.75

    def test_score_layer_triggers_compute(self):
        mock_session = MagicMock()
        mock_session.run.side_effect = [[], [], []]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        m = self._make_metrics(driver=mock_driver)
        result = m.score_layer("nonexistent")
        assert result == 0.0

    def test_score_layer_unknown_returns_zero(self):
        m = self._make_metrics()
        m._cache = {"semantic": {"score": 0.5}}
        assert m.score_layer("nonexistent") == 0.0  # triggers compute, returns 0

    # ── get_trimming_candidates ─────────────────────────────────

    def test_trimming_candidates_excludes_builtin(self):
        m = self._make_metrics()

        with patch.object(m, "compute_stats", return_value={
            "semantic": {"score": 0.001, "builtin": True},
            "custom_weak": {"score": 0.005, "builtin": False},
        }):
            with patch("src.memory.types.DynamicLayerRegistry") as mock_reg:
                mock_reg.return_value.get_parent.return_value = "semantic"
                candidates = m.get_trimming_candidates(threshold=0.01)

        assert len(candidates) == 1
        assert candidates[0][0] == "custom_weak"
        assert candidates[0][2] == "semantic"  # parent layer

    def test_trimming_candidates_sorted_by_score(self):
        m = self._make_metrics()

        with patch.object(m, "compute_stats", return_value={
            "weak_a": {"score": 0.005, "builtin": False},
            "weak_b": {"score": 0.002, "builtin": False},
            "strong": {"score": 0.5, "builtin": False},
        }):
            with patch("src.memory.types.DynamicLayerRegistry") as mock_reg:
                mock_reg.return_value.get_parent.return_value = "semantic"
                candidates = m.get_trimming_candidates(threshold=0.01)

        assert len(candidates) == 2
        assert candidates[0][0] == "weak_b"  # lowest score first
        assert candidates[1][0] == "weak_a"

    def test_trimming_candidates_empty_if_all_strong(self):
        m = self._make_metrics()

        with patch.object(m, "compute_stats", return_value={
            "custom_a": {"score": 0.5, "builtin": False},
        }):
            candidates = m.get_trimming_candidates(threshold=0.01)
            assert candidates == []

    # ── merge_layer ─────────────────────────────────────────────

    def test_merge_layer_happy_path(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"migrated": 15}
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        m = self._make_metrics(driver=mock_driver)
        result = m.merge_layer("custom_old", "semantic")
        assert result == 15

    def test_merge_builtin_layer_blocked(self):
        m = self._make_metrics(driver=MagicMock())
        result = m.merge_layer("semantic", "temporal")
        assert result == 0  # Built-in layers cannot be merged

    def test_merge_no_driver(self):
        m = self._make_metrics(driver=None)
        result = m.merge_layer("custom", "semantic")
        assert result == 0

    def test_merge_handles_neo4j_error(self):
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j error")
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        m = self._make_metrics(driver=mock_driver)
        result = m.merge_layer("custom_old", "semantic")
        assert result == 0
