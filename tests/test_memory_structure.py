import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.memory.hippocampus import Hippocampus, ContextObject
from src.privacy.scopes import PrivacyScope, ScopeManager

@pytest.fixture
def mock_settings(mocker):
    mocker.patch("src.memory.hippocampus.settings.OLLAMA_EMBED_MODEL", "mock_embed_model")
    mocker.patch("src.memory.hippocampus.settings.OLLAMA_BASE_URL", "http://mock-url")
    mocker.patch("src.memory.graph.settings.NEO4J_URI", "bolt://mock:7687")
    mocker.patch("src.memory.graph.settings.NEO4J_USER", "mock")
    mocker.patch("src.memory.graph.settings.NEO4J_PASSWORD", "mock")

@pytest.fixture
def mock_neo4j(mocker):
    mock_driver = MagicMock()
    mocker.patch("src.memory.graph.GraphDatabase.driver", return_value=mock_driver)
    return mock_driver

@pytest.fixture
def mock_ollama(mocker):
    return mocker.patch("src.memory.vector.ollama.Client")

def test_hippocampus_initialization(mock_settings, mock_neo4j, mock_ollama):
    """Test that Hippocampus initializes all tiers."""
    h = Hippocampus()
    assert h.working is not None
    assert h.vector_store is not None
    assert h.graph is not None
    assert h.timeline is not None
    
    # Verify Neo4j connection attempted
    mock_neo4j.verify_connectivity.assert_called_once()

@pytest.mark.asyncio
async def test_hippocampus_recall_observe(mock_settings, mock_neo4j, mock_ollama, mocker):
    """Test recall and observe flow."""
    h = Hippocampus()
    
    # Mock PrivacyManager -> ScopeManager
    mocker.patch("src.memory.hippocampus.ScopeManager.get_scope", return_value=PrivacyScope.PUBLIC)
    
    # Mock Embedder
    h.embedder.get_embedding = MagicMock(return_value=[0.1, 0.2])
    
    # Call Recall
    ctx = h.recall("Hello", 123, 456)
    assert isinstance(ctx, ContextObject)
    assert ctx.scope == "PUBLIC"
    
    # Call Observe
    h.timeline.add_event = MagicMock()
    # Use AsyncMock because observe calls asyncio.create_task(stream.add_turn(...))
    from unittest.mock import AsyncMock
    h.stream.add_turn = AsyncMock() 
    # Update alias too if needed, though observe uses self.stream
    h.working.add_turn = h.stream.add_turn
    
    # Needs to be a numeric string
    await h.observe("123", "Hi", "Hello", 999)
    
    # Check calling
    # Since ContextStream.add_turn is also async and created as a task, 
    # we might need to verify differently or ensuring proper mocking.
    # However, for this test structure, checking call args on the mock is enough if properly mocked.
    # But h.working is self.stream. If we mock h.working.add_turn, we are mocking the method on the real object.
    
    h.working.add_turn.assert_called_once()
    h.timeline.add_event.assert_called_once()

def test_strict_neo4j_failure(mock_settings, mocker):
    """Test that Hippocampus FAILS if Neo4j is down."""
    # Mock driver to raise exception
    mocker.patch("src.memory.graph.GraphDatabase.driver", side_effect=Exception("Connection Refused"))
    
    with pytest.raises(Exception, match="Connection Refused"):
        Hippocampus()
