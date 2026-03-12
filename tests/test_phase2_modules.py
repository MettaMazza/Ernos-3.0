"""
Tests for Phase 2 memory/lobe/viz modules — epistemic, graph_advanced,
mediator, visualization/server.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock


# ═══════════════════════════════════════════════════
# epistemic.py  (28% → 100%)
# ═══════════════════════════════════════════════════

class TestSourceTier:
    def test_enum_values(self):
        from src.memory.epistemic import SourceTier
        assert SourceTier.KNOWLEDGE_GRAPH.value == "KG"
        assert SourceTier.TOOL_RESULT.value == "TL"


class TestSourceTag:
    def test_tag_property(self):
        from src.memory.epistemic import SourceTag, SourceTier
        st = SourceTag(tier=SourceTier.KNOWLEDGE_GRAPH, source_id="User_likes_cats", content_preview="User likes cats")
        assert st.tag == "[SRC:KG:User_likes_cats]"
        assert str(st) == "[SRC:KG:User_likes_cats]"


class TestEpistemicContext:

    def test_tag_short_id(self):
        from src.memory.epistemic import EpistemicContext, SourceTier
        ec = EpistemicContext()
        result = ec.tag(SourceTier.VECTOR_STORE, "emb_42", "Some retrieved content")
        assert result.startswith("[SRC:VS:emb_42]")
        assert len(ec.sources) == 1

    def test_tag_truncates_long_id(self):
        from src.memory.epistemic import EpistemicContext, SourceTier
        ec = EpistemicContext()
        long_id = "A" * 100
        result = ec.tag(SourceTier.KNOWLEDGE_GRAPH, long_id, "content")
        assert len(ec.sources[0].source_id) < 100

    def test_tag_list(self):
        from src.memory.epistemic import EpistemicContext, SourceTier
        ec = EpistemicContext()
        items = ["fact1", "fact2", "fact3"]
        tagged = ec.tag_list(SourceTier.LESSONS, items, id_prefix="lesson_")
        assert len(tagged) == 3
        assert all("[SRC:LS:" in t for t in tagged)
        assert len(ec.sources) == 3

    def test_get_source_summary_empty(self):
        from src.memory.epistemic import EpistemicContext
        ec = EpistemicContext()
        assert "No memory sources" in ec.get_source_summary()

    def test_get_source_summary_with_sources(self):
        from src.memory.epistemic import EpistemicContext, SourceTier
        ec = EpistemicContext()
        ec.tag(SourceTier.KNOWLEDGE_GRAPH, "id1", "content1")
        ec.tag(SourceTier.KNOWLEDGE_GRAPH, "id2", "content2")
        ec.tag(SourceTier.VECTOR_STORE, "vec1", "vector content")

        summary = ec.get_source_summary()
        assert "Knowledge Graph" in summary
        assert "2 item(s)" in summary
        assert "Semantic Memory" in summary

    def test_get_source_summary_truncates_above_3(self):
        from src.memory.epistemic import EpistemicContext, SourceTier
        ec = EpistemicContext()
        for i in range(5):
            ec.tag(SourceTier.KNOWLEDGE_GRAPH, f"id_{i}", f"content_{i}")

        summary = ec.get_source_summary()
        assert "and 2 more" in summary

    def test_extract_id_kg_triple(self):
        from src.memory.epistemic import EpistemicContext
        result = EpistemicContext._extract_id("Alice -[knows]-> Bob (layer: social)", "fallback")
        assert "Alice" in result
        assert "knows" in result
        assert "Bob" in result

    def test_extract_id_short_content(self):
        from src.memory.epistemic import EpistemicContext
        result = EpistemicContext._extract_id("Hello world", "fb_0")
        assert result == "Hello_world"

    def test_extract_id_empty(self):
        from src.memory.epistemic import EpistemicContext
        result = EpistemicContext._extract_id("", "fallback_99")
        assert result == "fallback_99"


class TestIntrospectClaim:

    @pytest.mark.asyncio
    async def test_no_hippocampus(self):
        from src.memory.epistemic import introspect_claim
        bot = MagicMock(spec=[])  # no hippocampus attr
        result = await introspect_claim(bot, "cats are mammals")
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_kg_search(self):
        from src.memory.epistemic import introspect_claim

        mock_kg = MagicMock()
        mock_kg.query_core_knowledge.return_value = [
            {"subject": "Cat", "predicate": "is_a", "object": "Mammal", "layer": "taxonomic"}
        ]

        mock_hippo = MagicMock()
        mock_hippo.graph = mock_kg
        mock_hippo.embedder = None
        mock_hippo.working = None
        mock_hippo.lessons = MagicMock()
        mock_hippo.lessons.get_all_lessons.return_value = []

        bot = MagicMock()
        bot.hippocampus = mock_hippo

        result = await introspect_claim(bot, "Cats are mammals")
        assert "Knowledge Graph" in result
        assert "Cat" in result

    @pytest.mark.asyncio
    async def test_no_evidence_found(self):
        from src.memory.epistemic import introspect_claim

        mock_kg = MagicMock()
        mock_kg.query_core_knowledge.return_value = []

        mock_hippo = MagicMock()
        mock_hippo.graph = mock_kg
        mock_hippo.embedder = MagicMock()
        mock_hippo.embedder.get_embedding.return_value = None
        mock_hippo.working = None
        mock_hippo.lessons = MagicMock()
        mock_hippo.lessons.get_all_lessons.return_value = []

        bot = MagicMock()
        bot.hippocampus = mock_hippo

        result = await introspect_claim(bot, "XYZ unknown fact")
        assert "No stored evidence" in result

    @pytest.mark.asyncio
    async def test_vector_store_search(self):
        from src.memory.epistemic import introspect_claim

        mock_hippo = MagicMock()
        mock_hippo.graph = None
        mock_hippo.working = None
        mock_hippo.lessons = MagicMock()
        mock_hippo.lessons.get_all_lessons.return_value = []

        mock_hippo.embedder.get_embedding.return_value = [0.1] * 768
        mock_hippo.vector_store.retrieve.return_value = [
            {"text": "Cats purr when happy", "score": 0.95, "metadata": {"id": "doc_42"}}
        ]

        bot = MagicMock()
        bot.hippocampus = mock_hippo

        result = await introspect_claim(bot, "cats purring behavior", user_id="123")
        assert "Semantic Memory" in result

    @pytest.mark.asyncio
    async def test_lessons_search(self):
        from src.memory.epistemic import introspect_claim

        mock_hippo = MagicMock()
        mock_hippo.graph = None
        mock_hippo.embedder.get_embedding.return_value = None
        mock_hippo.working = None
        mock_hippo.lessons.get_all_lessons.return_value = [
            "User prefers dark mode for comfort"
        ]

        bot = MagicMock()
        bot.hippocampus = mock_hippo

        result = await introspect_claim(bot, "User prefers dark mode", user_id="42")
        assert "Lessons" in result

    @pytest.mark.asyncio
    async def test_persona_user_id(self):
        """Persona-prefixed IDs should not crash int() conversion."""
        from src.memory.epistemic import introspect_claim

        mock_hippo = MagicMock()
        mock_hippo.graph = None
        mock_hippo.embedder.get_embedding.return_value = None
        mock_hippo.working = None
        mock_hippo.lessons.get_all_lessons.return_value = []

        bot = MagicMock()
        bot.hippocampus = mock_hippo

        result = await introspect_claim(bot, "test claim", user_id="persona:ernos")
        assert "INTROSPECTION REPORT" in result


# ═══════════════════════════════════════════════════
# graph_advanced.py  (23% → 100%)
# ═══════════════════════════════════════════════════

def _make_session():
    """Create a mock Neo4j session that supports `with` context."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    return mock_session


def _make_driver(session=None):
    """Create a mock Neo4j driver that returns a session."""
    if session is None:
        session = _make_session()
    mock_driver = MagicMock()
    mock_driver.session.return_value = session
    return mock_driver, session


class TestStrengthenSynapse:
    def test_creates_synapse(self):
        from src.memory.graph_advanced import strengthen_synapse
        driver, session = _make_driver()
        strengthen_synapse(driver, "semantic", "temporal")
        session.run.assert_called_once()

    def test_no_driver(self):
        from src.memory.graph_advanced import strengthen_synapse
        # None driver → exception caught
        strengthen_synapse(None, "a", "b")  # Should not raise


class TestGetSynapseMap:
    def test_returns_synapses(self):
        from src.memory.graph_advanced import get_synapse_map
        session = _make_session()
        driver, _ = _make_driver(session)

        # session.run returns an iterable of records
        mock_record = {"source": "Root:Semantic", "target": "Root:Temporal", "strength": 5, "last_fired": 12345}
        session.run.return_value = [mock_record]

        result = get_synapse_map(driver)
        assert len(result) == 1
        assert result[0]["strength"] == 5

    def test_no_driver(self):
        from src.memory.graph_advanced import get_synapse_map
        assert get_synapse_map(None) == []


class TestDecaySynapses:
    def test_decay_and_prune(self):
        from src.memory.graph_advanced import decay_synapses
        session = _make_session()
        driver, _ = _make_driver(session)

        mock_result = MagicMock()
        mock_result.single.return_value = {"pruned": 2}
        # First call = decay (no return needed), second = prune
        session.run.side_effect = [None, mock_result]

        decay_synapses(driver, decay_rate=0.1, prune_threshold=0)
        assert session.run.call_count == 2

    def test_no_driver(self):
        from src.memory.graph_advanced import decay_synapses
        decay_synapses(None)  # Should not raise


class TestBulkSeed:
    def test_seeds_facts(self):
        from src.memory.graph_advanced import bulk_seed
        session = _make_session()
        driver, _ = _make_driver(session)

        mock_tx = MagicMock()
        mock_tx.__enter__ = MagicMock(return_value=mock_tx)
        mock_tx.__exit__ = MagicMock(return_value=False)
        session.begin_transaction.return_value = mock_tx

        facts = [
            {"subject": "Cat", "predicate": "is_a", "object": "Mammal", "layer": "taxonomic"},
            {"subject": "Dog", "predicate": "is_a", "object": "Mammal", "layer": "taxonomic"},
        ]
        result = bulk_seed(driver, facts, batch_size=10)
        assert result["seeded"] == 2
        assert result["errors"] == 0

    def test_empty_facts(self):
        from src.memory.graph_advanced import bulk_seed
        result = bulk_seed(MagicMock(), [])
        assert result["seeded"] == 0

    def test_skips_empty_subject(self):
        from src.memory.graph_advanced import bulk_seed
        session = _make_session()
        driver, _ = _make_driver(session)

        mock_tx = MagicMock()
        mock_tx.__enter__ = MagicMock(return_value=mock_tx)
        mock_tx.__exit__ = MagicMock(return_value=False)
        session.begin_transaction.return_value = mock_tx

        facts = [{"subject": "", "predicate": "is", "object": "X", "layer": "semantic"}]
        result = bulk_seed(driver, facts)
        assert result["skipped"] == 1
        assert result["seeded"] == 0


class TestQueryCoreKnowledge:
    def test_returns_facts(self):
        from src.memory.graph_advanced import query_core_knowledge
        session = _make_session()
        driver, _ = _make_driver(session)

        mock_record = {
            "subject": "Cat", "predicate": "IS_A", "object": "Mammal",
            "layer": "taxonomic", "provenance": "{}", "scope": "CORE"
        }

        class FakeRecord:
            def __getitem__(self, key):
                return mock_record[key]
            def get(self, key, default=None):
                return mock_record.get(key, default)

        session.run.return_value = [FakeRecord()]

        result = query_core_knowledge(driver, "Cat")
        assert len(result) == 1
        assert result[0]["subject"] == "Cat"

    def test_no_driver(self):
        from src.memory.graph_advanced import query_core_knowledge
        assert query_core_knowledge(None, "Cat") == []


class TestCheckContradiction:
    def test_finds_contradiction(self):
        from src.memory.graph_advanced import check_contradiction
        session = _make_session()
        driver, _ = _make_driver(session)

        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: {
            "subject": "Cat", "predicate": "IS_A", "object": "Mammal",
            "layer": "taxonomic", "provenance": "{}"
        }[key]
        mock_record.get = lambda key, default=None: {
            "subject": "Cat", "predicate": "IS_A", "object": "Mammal",
            "layer": "taxonomic", "provenance": "{}"
        }.get(key, default)

        mock_result = MagicMock()
        mock_result.single.return_value = mock_record
        session.run.return_value = mock_result

        result = check_contradiction(driver, "Cat", "is_a", "Reptile")
        assert result is not None
        assert result["conflict_type"] == "direct_contradiction"

    def test_no_contradiction(self):
        from src.memory.graph_advanced import check_contradiction
        session = _make_session()
        driver, _ = _make_driver(session)

        mock_result = MagicMock()
        mock_result.single.return_value = None
        session.run.return_value = mock_result

        result = check_contradiction(driver, "Cat", "is_a", "Mammal")
        assert result is None

    def test_no_driver(self):
        from src.memory.graph_advanced import check_contradiction
        assert check_contradiction(None, "a", "b", "c") is None


class TestBackfillMissingScopes:
    def test_backfill(self):
        from src.memory.graph_advanced import backfill_missing_scopes
        session = _make_session()
        driver, _ = _make_driver(session)

        # 4 queries: core nodes, public nodes, core rels, public rels
        mock_results = []
        for val in [5, 10, 3, 7]:
            mr = MagicMock()
            mr.single.return_value = {"cnt": val}
            mock_results.append(mr)
        session.run.side_effect = mock_results

        result = backfill_missing_scopes(driver)
        assert result["core"] == 5 + 3
        assert result["public"] == 10 + 7


# ═══════════════════════════════════════════════════
# mediator.py  (29% → 100%)
# ═══════════════════════════════════════════════════

class TestMediatorAbility:

    def _make_mediator(self):
        from src.lobes.superego.mediator import MediatorAbility
        mock_lobe = MagicMock()
        return MediatorAbility(mock_lobe)

    @pytest.mark.asyncio
    async def test_arbitrate_accept_verdict(self):
        mediator = self._make_mediator()

        # Mock the bot's engine to return ACCEPT
        mediator.bot.engine_manager.get_active_engine.return_value.generate_response = MagicMock(
            return_value="ACCEPT: User evidence is strong"
        )
        mediator.bot.loop.run_in_executor = AsyncMock(return_value="ACCEPT: User evidence is strong")

        with patch.object(mediator, "_execute_verdict", new_callable=AsyncMock, return_value="foundation_updated"), \
             patch("builtins.open", side_effect=FileNotFoundError):
            result = await mediator.arbitrate(
                user_claim={"subject": "Cat", "predicate": "is_a", "object": "Fish"},
                core_fact={"subject": "Cat", "predicate": "is_a", "object": "Mammal"},
                user_evidence="scientific paper",
                user_id=42,
            )

        assert result["verdict"] == "ACCEPT"

    @pytest.mark.asyncio
    async def test_arbitrate_exception_falls_to_defer(self):
        mediator = self._make_mediator()

        mediator.bot.engine_manager.get_active_engine.side_effect = Exception("Engine down")

        with patch("builtins.open", side_effect=FileNotFoundError):
            result = await mediator.arbitrate(
                user_claim={"subject": "X", "predicate": "is", "object": "Y"},
                core_fact={"subject": "X", "predicate": "is", "object": "Z"},
            )

        assert result["verdict"] == "DEFER"

    def test_parse_verdict_accept(self):
        mediator = self._make_mediator()
        result = mediator._parse_verdict("ACCEPT: good evidence supports this")
        assert result["verdict"] == "ACCEPT"

    def test_parse_verdict_reject(self):
        mediator = self._make_mediator()
        result = mediator._parse_verdict("REJECT - Foundation is authoritative")
        assert result["verdict"] == "REJECT"

    def test_parse_verdict_unknown_defaults_defer(self):
        mediator = self._make_mediator()
        result = mediator._parse_verdict("I'm not sure what to say")
        assert result["verdict"] == "DEFER"

    def test_fallback_prompt(self):
        mediator = self._make_mediator()
        prompt = mediator._fallback_prompt()
        assert "ACCEPT" in prompt
        assert "REJECT" in prompt
        assert "DEFER" in prompt

    @pytest.mark.asyncio
    async def test_check_and_arbitrate_no_contradiction(self):
        mediator = self._make_mediator()
        mediator.bot.hippocampus.graph.check_contradiction.return_value = None

        result = await mediator.check_and_arbitrate("Cat", "is_a", "Mammal")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_and_arbitrate_with_contradiction(self):
        mediator = self._make_mediator()
        mediator.bot.hippocampus.graph.check_contradiction.return_value = {
            "subject": "Cat", "predicate": "IS_A", "object": "Mammal"
        }
        mediator.arbitrate = AsyncMock(return_value={"verdict": "REJECT", "reasoning": "wrong"})

        result = await mediator.check_and_arbitrate("Cat", "is_a", "Fish")
        assert result["verdict"] == "REJECT"

    @pytest.mark.asyncio
    async def test_execute_verdict_no_kg(self):
        from src.lobes.superego.mediator import MediatorAbility
        mock_lobe = MagicMock()
        mock_lobe.cerebrum.bot = MagicMock(spec=["engine_manager"])
        mediator = MediatorAbility(mock_lobe)

        result = await mediator._execute_verdict(
            {"verdict": "ACCEPT"}, {"subject": "A"}, {"subject": "B"}, 42
        )
        assert result == "no_kg_available"

    @pytest.mark.asyncio
    async def test_execute_verdict_reject(self):
        mediator = self._make_mediator()
        result = await mediator._execute_verdict(
            {"verdict": "REJECT"}, {"subject": "A"}, {}, 42
        )
        assert result == "claim_rejected"

    @pytest.mark.asyncio
    async def test_execute_verdict_defer(self):
        mediator = self._make_mediator()
        result = await mediator._execute_verdict(
            {"verdict": "DEFER", "reasoning": "not enough info"}, {"subject": "A"}, {}, 42
        )
        assert result == "quarantined"


# ═══════════════════════════════════════════════════
# visualization/server.py  (19% → 100%)
# ═══════════════════════════════════════════════════

class TestKGVisualizationServer:

    def _make_server(self):
        from src.visualization.server import KGVisualizationServer
        bot = MagicMock(spec=["get_channel"])
        return KGVisualizationServer(bot)

    def test_init(self):
        server = self._make_server()
        assert server.host == "127.0.0.1"
        assert server.port == 8742

    @pytest.mark.asyncio
    async def test_start_without_aiohttp(self):
        with patch("src.visualization.server.HAS_AIOHTTP", False):
            server = self._make_server()
            await server.start()  # Should warn and return

    @pytest.mark.asyncio
    async def test_stop(self):
        server = self._make_server()
        mock_runner = AsyncMock()
        server._runner = mock_runner
        await server.stop()
        mock_runner.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_no_runner(self):
        server = self._make_server()
        server._runner = None
        await server.stop()  # Should not raise

    def test_get_graph_returns_none_when_no_attrs(self):
        server = self._make_server()
        result = server._get_graph()
        assert result is None

    def test_get_graph_from_hippocampus(self):
        from src.visualization.server import KGVisualizationServer
        bot = MagicMock()
        bot.hippocampus.graph = MagicMock()
        server = KGVisualizationServer(bot)
        result = server._get_graph()
        assert result is not None

    def test_empty_stats(self):
        server = self._make_server()
        stats = server._empty_stats()
        assert stats["total_nodes"] == 0
        assert stats["health_score"] is None

    def test_extract_graph_data_no_driver(self):
        server = self._make_server()
        mock_graph = MagicMock(spec=[])  # No driver attribute
        nodes, links = server._extract_graph_data(mock_graph)
        assert nodes == []
        assert links == []

    def test_compute_stats_no_driver(self):
        server = self._make_server()
        mock_graph = MagicMock(spec=[])  # No driver attribute
        stats = server._compute_stats(mock_graph)
        assert isinstance(stats, dict)
        assert stats["total_nodes"] == 0

    @pytest.mark.asyncio
    async def test_handle_graph_no_graph(self):
        server = self._make_server()
        server._get_graph = MagicMock(return_value=None)

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web:
            mock_web.Response = MagicMock(return_value="response")
            request = MagicMock()
            request.query = {}
            result = await server._handle_graph(request)

    @pytest.mark.asyncio
    async def test_handle_stats_no_graph(self):
        server = self._make_server()
        server._get_graph = MagicMock(return_value=None)

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web:
            mock_web.Response = MagicMock(return_value="response")
            request = MagicMock()
            await server._handle_stats(request)

    @pytest.mark.asyncio
    async def test_handle_quarantine_empty(self):
        server = self._make_server()
        server._get_graph = MagicMock(return_value=None)

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web, \
             patch("src.visualization.server.Path") as mock_path:
            mock_web.Response = MagicMock(return_value="response")
            mock_path.return_value.exists.return_value = False
            request = MagicMock()
            await server._handle_quarantine(request)
