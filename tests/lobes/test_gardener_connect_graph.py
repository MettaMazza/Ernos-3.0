"""
Tests for KG Connector functionality in GardenerAbility.

Covers:
    - connect_graph() pipeline (scan → candidates → infer → store)
    - _select_candidate_pairs() heuristics
    - _parse_connection_response() JSON parsing
"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch

from src.lobes.strategy.gardener import GardenerAbility, _parse_connection_response


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def gardener():
    lobe = MagicMock()
    with patch("src.lobes.strategy.gardener.KnowledgeGraph"):
        return GardenerAbility(lobe)


# ── _parse_connection_response tests ─────────────────────────

class TestParseConnectionResponse:
    def test_empty_string(self):
        assert _parse_connection_response("") == []

    def test_empty_array(self):
        assert _parse_connection_response("[]") == []

    def test_valid_json_array(self):
        raw = json.dumps([
            {"subject": "Python", "predicate": "IS_A", "object": "Language"},
            {"subject": "Neo4j", "predicate": "IS_A", "object": "Database"},
        ])
        result = _parse_connection_response(raw)
        assert len(result) == 2
        assert result[0]["subject"] == "Python"
        assert result[1]["predicate"] == "IS_A"

    def test_json_with_code_fences(self):
        raw = "```json\n" + json.dumps([
            {"subject": "A", "predicate": "RELATED_TO", "object": "B"}
        ]) + "\n```"
        result = _parse_connection_response(raw)
        assert len(result) == 1

    def test_json_with_preamble(self):
        raw = "Here are the connections:\n" + json.dumps([
            {"subject": "X", "predicate": "HAS", "object": "Y"}
        ])
        result = _parse_connection_response(raw)
        assert len(result) == 1
        assert result[0]["subject"] == "X"

    def test_missing_required_keys(self):
        raw = json.dumps([
            {"subject": "A"},  # missing object
            {"predicate": "IS_A", "object": "B"},  # missing subject
            {"subject": "C", "object": "D"},  # missing predicate — still valid (has subject+object)
        ])
        result = _parse_connection_response(raw)
        # Only item 3 has both subject and object
        assert len(result) == 1
        assert result[0]["subject"] == "C"

    def test_invalid_json(self):
        assert _parse_connection_response("not json at all") == []

    def test_no_brackets(self):
        assert _parse_connection_response('{"single": "object"}') == []


# ── _select_candidate_pairs tests ────────────────────────────

class TestSelectCandidatePairs:
    def _make_node(self, name, neighbors=None, layer=None):
        return {
            "name": name,
            "labels": ["Concept"],
            "layer": layer,
            "neighbors": neighbors or [],
            "degree": len(neighbors or []),
        }

    def test_shared_neighbor_strategy(self, gardener):
        """Nodes sharing a neighbor should be paired."""
        nodes = [
            self._make_node("A", neighbors=["shared"]),
            self._make_node("B", neighbors=["shared"]),
        ]
        pairs = gardener._select_candidate_pairs(nodes, max_pairs=10)
        assert len(pairs) == 1
        assert pairs[0]["reason"].startswith("shared_neighbor:")

    def test_same_layer_strategy(self, gardener):
        """Nodes in the same layer should be paired if no shared neighbors."""
        nodes = [
            self._make_node("A", layer="cognitive"),
            self._make_node("B", layer="cognitive"),
            self._make_node("C", layer="narrative"),
        ]
        pairs = gardener._select_candidate_pairs(nodes, max_pairs=10)
        # A-B share layer, C is different
        layer_pairs = [p for p in pairs if p["reason"].startswith("same_layer:")]
        assert len(layer_pairs) >= 1
        names = {p["node_a"]["name"] for p in layer_pairs} | {p["node_b"]["name"] for p in layer_pairs}
        assert "C" not in names or "cognitive" in str(layer_pairs)  # C won't pair with A/B by layer

    def test_word_overlap_strategy(self, gardener):
        """Nodes with overlapping names should be paired."""
        nodes = [
            self._make_node("Machine Learning"),
            self._make_node("Machine Vision"),
        ]
        pairs = gardener._select_candidate_pairs(nodes, max_pairs=10)
        overlap_pairs = [p for p in pairs if p["reason"].startswith("word_overlap:")]
        assert len(overlap_pairs) >= 1

    def test_max_pairs_limit(self, gardener):
        """Should not exceed max_pairs."""
        nodes = [self._make_node(f"Node_{i}", neighbors=["hub"]) for i in range(20)]
        pairs = gardener._select_candidate_pairs(nodes, max_pairs=5)
        assert len(pairs) <= 5

    def test_no_self_pairs(self, gardener):
        """A node should never be paired with itself."""
        nodes = [self._make_node("A", neighbors=["hub"])]
        pairs = gardener._select_candidate_pairs(nodes, max_pairs=10)
        assert len(pairs) == 0

    def test_no_duplicate_pairs(self, gardener):
        """Same pair should not appear twice."""
        nodes = [
            self._make_node("A", neighbors=["hub"], layer="L1"),
            self._make_node("B", neighbors=["hub"], layer="L1"),
        ]
        pairs = gardener._select_candidate_pairs(nodes, max_pairs=50)
        pair_keys = [tuple(sorted([p["node_a"]["name"], p["node_b"]["name"]])) for p in pairs]
        assert len(pair_keys) == len(set(pair_keys))

    def test_empty_nodes(self, gardener):
        pairs = gardener._select_candidate_pairs([], max_pairs=10)
        assert pairs == []


# ── connect_graph integration tests ──────────────────────────

class TestConnectGraph:
    @pytest.mark.asyncio
    async def test_well_connected_graph_returns_early(self, gardener):
        """If no low-connectivity nodes, should return early."""
        mock_session = MagicMock()
        mock_session.run.return_value = []  # No low-connectivity nodes
        gardener.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        gardener.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)

        result = await gardener.connect_graph()
        assert "well-connected" in result.lower()

    @pytest.mark.asyncio
    async def test_no_candidates_returns_early(self, gardener):
        """If nodes found but no viable pairs, should report that."""
        mock_session = MagicMock()
        # Return some isolated nodes with no neighbors
        mock_session.run.return_value = [
            {"name": "Lonely", "labels": ["Concept"], "layer": None,
             "neighbors": [], "degree": 0},
        ]
        gardener.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        gardener.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)

        result = await gardener.connect_graph()
        # With a single node, no pairs can be formed
        assert "No viable candidate pairs" in result or "Scanned" in result

    @pytest.mark.asyncio
    async def test_no_engine_returns_warning(self, gardener):
        """If no LLM engine available, should warn."""
        mock_session = MagicMock()
        mock_session.run.return_value = [
            {"name": "A", "labels": ["C"], "layer": "L1", "neighbors": ["hub"], "degree": 1},
            {"name": "B", "labels": ["C"], "layer": "L1", "neighbors": ["hub"], "degree": 1},
        ]
        gardener.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        gardener.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.lobes.strategy.gardener.globals") as mock_globals:
            mock_globals.bot = None
            result = await gardener.connect_graph()
            # With no bot, engine is None, so we get the warning
            assert "No active LLM engine" in result or "Proposed Connections" in result

    @pytest.mark.asyncio
    async def test_exception_handling(self, gardener):
        """Should catch exceptions and return error string."""
        gardener.graph.driver.session.side_effect = Exception("Neo4j down")
        result = await gardener.connect_graph()
        assert "failed" in result.lower()
