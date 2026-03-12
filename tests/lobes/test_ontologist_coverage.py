"""
Tests for OntologistAbility — covering real failure paths that were crashing in production.

These tests exercise the contradiction/mediator routing and None-safety paths
that the original over-mocked tests never touched.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture
def ontologist():
    """Create OntologistAbility with minimal real wiring."""
    from src.lobes.memory.ontologist import OntologistAbility
    mock_lobe = MagicMock()
    # cerebrum with lobes dict — the real structure
    mock_lobe.cerebrum = MagicMock()
    mock_lobe.cerebrum.lobes = {}
    onto = OntologistAbility(mock_lobe)
    return onto


@pytest.fixture
def mock_graph():
    """A mock graph that behaves like the real KnowledgeGraph."""
    g = MagicMock()
    g.check_contradiction = MagicMock(return_value=None)
    g.query_core_knowledge = MagicMock(return_value=[])
    g.add_relationship = MagicMock()
    g.driver = None  # No Neo4j in tests
    g.quarantine = None
    return g


@pytest.fixture
def mock_globals(mock_graph):
    """Patch src.bot.globals with working hippocampus and graph."""
    mg = MagicMock()
    mg.bot.hippocampus.graph = mock_graph
    mg.active_message.get.return_value = None
    return mg


# ─── Route to Mediator with None cerebrum ───

@pytest.mark.asyncio
async def test_route_to_mediator_cerebrum_none(ontologist):
    """The actual crash: cerebrum.lobes was None → .get() blew up."""
    ontologist.lobe.cerebrum = None
    result = await ontologist._route_to_mediator(
        "Earth", "CAPITAL_IS", "Moon",
        contradiction={"object": "Sun"},
        user_id="123", source_url=None
    )
    assert "Conflict" in result or "⚠️" in result


@pytest.mark.asyncio
async def test_route_to_mediator_lobes_none(ontologist):
    """cerebrum exists but lobes is None."""
    ontologist.lobe.cerebrum.lobes = None
    result = await ontologist._route_to_mediator(
        "Earth", "CAPITAL_IS", "Moon",
        contradiction={"object": "Sun"},
        user_id="123", source_url=None
    )
    assert "Conflict" in result or "⚠️" in result


@pytest.mark.asyncio
async def test_route_to_mediator_contradiction_none(ontologist):
    """contradiction param is None — should not crash."""
    result = await ontologist._route_to_mediator(
        "Earth", "CAPITAL_IS", "Moon",
        contradiction=None,
        user_id="123", source_url=None
    )
    assert "Conflict" in result or "⚠️" in result


@pytest.mark.asyncio
async def test_route_to_mediator_no_superego(ontologist):
    """SuperegoLobe not registered — fallback path."""
    ontologist.lobe.cerebrum.lobes = {}  # Empty lobes dict
    result = await ontologist._route_to_mediator(
        "Earth", "CAPITAL_IS", "Moon",
        contradiction={"object": "Sun", "provenance": None},
        user_id="123", source_url=None
    )
    assert "⚠️" in result
    assert "Sun" in result


@pytest.mark.asyncio
async def test_route_to_mediator_mediator_returns_none(ontologist):
    """Mediator.arbitrate() returns None — the isinstance check must catch it."""
    mock_superego = MagicMock()
    mock_mediator = MagicMock()
    mock_mediator.arbitrate = AsyncMock(return_value=None)
    mock_superego.get_ability.return_value = mock_mediator
    ontologist.lobe.cerebrum.lobes = {"SuperegoLobe": mock_superego}

    result = await ontologist._route_to_mediator(
        "Earth", "CAPITAL_IS", "Moon",
        contradiction={"object": "Sun"},
        user_id="123", source_url=None
    )
    assert "queued" in result.lower() or "defer" in result.lower()


@pytest.mark.asyncio
async def test_route_to_mediator_reject_with_none_provenance(ontologist):
    """Mediator returns REJECT but contradiction has None provenance."""
    mock_superego = MagicMock()
    mock_mediator = MagicMock()
    mock_mediator.arbitrate = AsyncMock(return_value={
        "verdict": "REJECT",
        "reasoning": "Core knowledge says otherwise",
        "action_taken": "rejected"
    })
    mock_superego.get_ability.return_value = mock_mediator
    ontologist.lobe.cerebrum.lobes = {"SuperegoLobe": mock_superego}

    # provenance is None — this was the other crash path
    result = await ontologist._route_to_mediator(
        "Earth", "CAPITAL_IS", "Moon",
        contradiction={"object": "Sun", "provenance": None},
        user_id="123", source_url=None
    )
    assert "🛡️" in result
    assert "Sun" in result


@pytest.mark.asyncio
async def test_mediator_arbitrate_handles_none_provenance(mock_globals):
    """Verify mediator.arbitrate does not crash when provenance is strictly None."""
    from src.lobes.superego.mediator import MediatorAbility
    
    mock_lobe = MagicMock()
    mock_lobe.bot = mock_globals.bot
    
    # Mock engine to return a VERDICT: ACCEPT so we don't need real API calls
    mock_engine = MagicMock()
    mock_engine.generate_response.return_value = "VERDICT: DEFER\nREASONING: Not enough context."
    mock_globals.bot.engine_manager.get_active_engine.return_value = mock_engine
    
    mediator = MediatorAbility(mock_lobe)
    
    # Execute arbitrate where core_fact explicitly returns {"provenance": None}
    verdict = await mediator.arbitrate(
        user_claim={"subject": "Sky", "predicate": "IS", "object": "Green"},
        core_fact={"subject": "Sky", "predicate": "IS", "object": "Blue", "provenance": None},
        user_evidence="I have a green filter",
        user_id="123"
    )
    
    # It should not crash, and should return a dict containing the verdict
    assert isinstance(verdict, dict)
    assert "verdict" in verdict
    assert verdict["verdict"] == "DEFER"


@pytest.mark.asyncio
async def test_route_to_mediator_accept(ontologist):
    """Mediator accepts the claim."""
    mock_superego = MagicMock()
    mock_mediator = MagicMock()
    mock_mediator.arbitrate = AsyncMock(return_value={
        "verdict": "ACCEPT",
        "reasoning": "User provided valid evidence",
        "action_taken": "updated"
    })
    mock_superego.get_ability.return_value = mock_mediator
    ontologist.lobe.cerebrum.lobes = {"SuperegoLobe": mock_superego}

    result = await ontologist._route_to_mediator(
        "Earth", "SHAPE", "Sphere",
        contradiction={"object": "Flat"},
        user_id="123", source_url="https://nasa.gov"
    )
    assert "✅" in result or "accepted" in result.lower()


@pytest.mark.asyncio
async def test_route_to_mediator_annotate(ontologist):
    """Mediator annotates both perspectives."""
    mock_superego = MagicMock()
    mock_mediator = MagicMock()
    mock_mediator.arbitrate = AsyncMock(return_value={
        "verdict": "ANNOTATE",
        "reasoning": "Both valid perspectives",
        "action_taken": "annotated"
    })
    mock_superego.get_ability.return_value = mock_mediator
    ontologist.lobe.cerebrum.lobes = {"SuperegoLobe": mock_superego}

    result = await ontologist._route_to_mediator(
        "Pizza", "BEST_TOPPING", "Pineapple",
        contradiction={"object": "Pepperoni"},
        user_id="123", source_url=None
    )
    assert "📝" in result or "perspectives" in result.lower()


# ─── Execute paths with contradiction ───

@pytest.mark.asyncio
async def test_execute_with_contradiction(ontologist, mock_graph, mock_globals):
    """Full execute path hitting contradiction → mediator routing."""
    mock_graph.check_contradiction.return_value = {"object": "Sun", "provenance": None}
    # No SuperegoLobe → fallback
    ontologist.lobe.cerebrum.lobes = {}

    with patch("src.lobes.memory.ontologist.OntologistAbility._score_confidence"):
        with patch("src.bot.globals", mock_globals):
            result = await ontologist.execute(
                "Earth", "ORBITS", "Moon", user_id="123"
            )
    assert "⚠️" in result


@pytest.mark.asyncio
async def test_execute_question_detection(ontologist):
    """Questions should be rejected, not stored."""
    result = await ontologist.execute(
        "How does gravity work", "IS", "complicated?", user_id="123"
    )
    assert "question" in result.lower()


@pytest.mark.asyncio
async def test_execute_empty_subject(ontologist):
    """Empty subject should return error."""
    result = await ontologist.execute("", "IS", "something", user_id="123")
    assert "Error" in result


@pytest.mark.asyncio
async def test_execute_quarantine(ontologist, mock_graph, mock_globals):
    """Low confidence facts should be quarantined."""
    mock_graph.check_contradiction.return_value = None
    mock_graph.query_core_knowledge.return_value = []
    ontologist.lobe.cerebrum.lobes = {}

    with patch("src.bot.globals", mock_globals):
        # Patch confidence to return quarantine range
        with patch.object(ontologist, "_score_confidence", return_value=0.3):
            result = await ontologist.execute(
                "Unicorn", "IS", "Real", user_id="123"
            )
    assert "noted" in result.lower() or "queued" in result.lower() or "Learned" in result


# ─── Score confidence ───

def test_score_confidence_with_source(ontologist, mock_graph):
    """Source URL should boost confidence."""
    score_no_src = ontologist._score_confidence(
        "Earth", "IS", "Planet", mock_graph, "123", None
    )
    score_with_src = ontologist._score_confidence(
        "Earth", "IS", "Planet", mock_graph, "123", "https://wikipedia.org/Earth"
    )
    assert score_with_src > score_no_src


def test_score_confidence_known_subject(ontologist, mock_graph):
    """Known subjects should get higher confidence."""
    mock_graph.query_core_knowledge.return_value = []
    score_unknown = ontologist._score_confidence(
        "Zxqwv", "IS", "Nothing", mock_graph, "123", None
    )
    mock_graph.query_core_knowledge.return_value = [{"predicate": "IS"}]
    score_known = ontologist._score_confidence(
        "Earth", "IS", "Planet", mock_graph, "123", None
    )
    assert score_known >= score_unknown


def test_score_confidence_reasonable_predicate(ontologist, mock_graph):
    """Standard predicates should score higher than weird ones."""
    score_standard = ontologist._score_confidence(
        "A", "IS_A", "B", mock_graph, "123", None
    )
    score_weird = ontologist._score_confidence(
        "A", "XYZZY_PLUGH", "B", mock_graph, "123", None
    )
    assert score_standard >= score_weird
