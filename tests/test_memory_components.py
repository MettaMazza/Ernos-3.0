import pytest
from unittest.mock import MagicMock, call, mock_open
from datetime import datetime
from src.memory.working import WorkingMemory, Turn
from src.memory.vector import InMemoryVectorStore, OllamaEmbedder, BaseEmbedder
from src.memory.graph import KnowledgeGraph
from src.memory.timeline import Timeline
from src.privacy.scopes import PrivacyScope, ScopeManager

# --- Tier 1: Working Memory Tests ---

def test_working_memory_add_turn(mocker):
    # Mock persistence to prevent disk I/O in tests
    mocker.patch.object(WorkingMemory, '_load_from_disk')
    mocker.patch.object(WorkingMemory, '_save_to_disk')
    
    wm = WorkingMemory(max_turns=2)
    wm.add_turn("u1", "msg1", "bot1")
    assert len(wm.turns) == 1
    
    # Check consolidation trigger
    wm._consolidate = MagicMock()
    wm.add_turn("u2", "msg2", "bot2")
    wm.add_turn("u3", "msg3", "bot3") # Should trigger
    
    # Logic is: append then check > max_turns
    # 3 items > 2 max -> consolidate
    wm._consolidate.assert_called()

def test_working_memory_format(mocker):
    mocker.patch.object(WorkingMemory, '_load_from_disk')
    mocker.patch.object(WorkingMemory, '_save_to_disk')
    
    wm = WorkingMemory()
    wm.add_turn("u1", "M1", "B1", user_name="TestUser")
    assert "TestUser [ID:u1]: M1" in wm.get_context_string()
    assert "Ernos: B1" in wm.get_context_string()

def test_working_memory_consolidation_logic(mocker):
    mocker.patch.object(WorkingMemory, '_load_from_disk')
    mocker.patch.object(WorkingMemory, '_save_to_disk')
    
    # Test real consolidation method (stub logic)
    wm = WorkingMemory(max_turns=1)
    wm.turns = [
        Turn("u1", "OldUser", "old", "old_bot", 1.0, {}),
        Turn("u1", "NewUser", "new", "new_bot", 2.0, {})
    ]
    # Manually trigger
    wm._consolidate()
    # Should remove old, keep new
    assert len(wm.turns) == 1
    assert wm.turns[0].user_message == "new"

# --- Tier 2: Vector Store Tests ---

@pytest.fixture(autouse=True)
def enable_privacy(mocker):
    """Enable privacy scopes for all tests in this execution."""
    mocker.patch("config.settings.ENABLE_PRIVACY_SCOPES", True)

def test_vector_store_add_element():
    store = InMemoryVectorStore()
    store.add_element("doc1", [1.0, 0.0], {"scope": "PUBLIC"})
    assert len(store.documents) == 1

def test_vector_store_abstract_add_memory():
    store = InMemoryVectorStore()
    with pytest.raises(NotImplementedError):
        store.add_memory("fail")

def test_vector_store_retrieve_privacy():
    store = InMemoryVectorStore()
    # Doc A: PRIVATE (Scope 2)
    store.add_element("Private", [1.0, 0.0], {"scope": PrivacyScope.PRIVATE})
    # Doc B: PUBLIC (Scope 3)
    store.add_element("Public", [0.0, 1.0], {"scope": PrivacyScope.PUBLIC})
    
    # 1. Query as PUBLIC user
    # Should only see Public
    # Query vector matches both equally? No, [1,0] matches Private. 
    # But [1,0] query with PUBLIC scope should return NOTHING for Private doc.
    
    results = store.retrieve([1.0, 0.0], PrivacyScope.PUBLIC)
    # Blocked Private, but finds Public (even if low score) because it's the only one allowed
    assert len(results) == 1 
    assert results[0]['text'] == "Public"
    
    results = store.retrieve([0.0, 1.0], PrivacyScope.PUBLIC)
    assert len(results) == 1
    assert results[0]['text'] == "Public"

    # 2. Query as PRIVATE user
    results = store.retrieve([1.0, 0.0], PrivacyScope.PRIVATE)
    # Should see BOTH Private and Public
    assert len(results) == 2
    assert results[0]['text'] == "Private" # Best match first
    assert results[0]['text'] == "Private"

def test_ollama_embedder_error(mocker):
    mock_client = MagicMock()
    mock_client.embeddings.side_effect = Exception("Ollama Down")
    
    mocker.patch("src.memory.vector.ollama.Client", return_value=mock_client)
    if True:
        embedder = OllamaEmbedder("model")
        res = embedder.get_embedding("test")
        assert res == []

# --- Tier 3: Graph Tests ---

@pytest.fixture
def mock_neo4j(mocker):
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__.return_value = mock_session
    mocker.patch("src.memory.graph.GraphDatabase.driver", return_value=mock_driver)
    
    mocker.patch("src.memory.graph.settings.NEO4J_URI", "bolt://mock")
    mocker.patch("src.memory.graph.settings.NEO4J_USER", "user")
    mocker.patch("src.memory.graph.settings.NEO4J_PASSWORD", "pass")
    
    return mock_driver, mock_session

def test_graph_operations(mock_neo4j):
    driver, session = mock_neo4j
    kg = KnowledgeGraph()
    session.run.reset_mock()  # Clear index-creation calls from __init__
    
    kg.add_node("User", "Alice", layer="social", user_id=-1, scope="CORE")
    session.run.assert_called()
    # Check the first session.run call (the main MERGE), not the last (_wire_to_root)
    first_call = session.run.call_args_list[0]
    assert "MERGE (n:User" in first_call[0][0]
    
    session.run.reset_mock()
    kg.add_relationship("Alice", "KNOWS", "Bob", user_id=-1, scope="CORE")
    session.run.assert_called()
    assert "-[r:KNOWS" in session.run.call_args[0][0]
    
    kg.close()
    driver.close.assert_called()

def test_graph_query_context(mock_neo4j):
    driver, session = mock_neo4j
    kg = KnowledgeGraph()
    
    # Mock result
    mock_record = {"rel": "KNOWS", "target": "Bob", "target_layer": "social"}
    session.run.return_value = [mock_record]
    
    results = kg.query_context("Alice")
    assert len(results) == 1
    assert "Alice" in results[0]
    assert "Bob" in results[0]

# --- Tier 4: Timeline Tests ---

def test_timeline_add_event(mocker):
    mocker.patch("builtins.open", mock_open())
    mocker.patch("os.makedirs") # Mock directory creation
    tl = Timeline()
    tl.add_event("type", "desc")
    # Verified write called with new default path
    open.assert_called_with("memory/public/timeline.jsonl", "a", encoding="utf-8")

def test_timeline_read_filtered(mocker):
    # Mock file content
    log_content = '{"scope": "PUBLIC", "desc": "pub"}\n{"scope": "PRIVATE", "desc": "priv"}'
    mocker.patch("src.memory.timeline.os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data=log_content))
    
    tl = Timeline()
    
    # Public User -> 1 event
    events = tl.get_recent_events(scope=PrivacyScope.PUBLIC)
    assert len(events) == 1
    assert events[0]['desc'] == 'pub'
    
    # Private User -> 2 events
    events = tl.get_recent_events(scope=PrivacyScope.PRIVATE)
    assert len(events) == 2


# --- Edge Cases & Failure Modes ---

def test_vector_store_zero_norm():
    store = InMemoryVectorStore()
    # Zero vector document
    store.add_element("Zero", [0.0, 0.0], {"scope": PrivacyScope.PUBLIC})
    
    # Query with normal vector
    results = store.retrieve([1.0, 0.0], PrivacyScope.PUBLIC)
    assert len(results) == 0 # Should exclude zero norm docs to prevent div by zero
    
    # Normal doc, Zero query
    store.add_element("Normal", [1.0, 0.0], {"scope": PrivacyScope.PUBLIC})
    results = store.retrieve([0.0, 0.0], PrivacyScope.PUBLIC)
    assert len(results) == 0

def test_vector_store_empty_inputs():
    store = InMemoryVectorStore()
    store.add_element("", [1.0]) # Empty text
    assert len(store.documents) == 0
    
    store.add_element("Text", []) # Empty embedding
    assert len(store.documents) == 0
    
    with pytest.raises(NotImplementedError):
        store.add_memory("Text") # Stub raises NotImplementedError

def test_timeline_corrupt_data(mocker):
    # Mixed content: 1 valid, 1 corrupt JSON, 1 valid but invalid Scope
    content = '{"scope": "PUBLIC", "desc": "valid"}\nCORRUPT JSON\n{"scope": "INVALID_SCOPE", "desc": "fallback"}\n'
    
    mocker.patch("src.memory.timeline.os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data=content))
    
    tl = Timeline()
    events = tl.get_recent_events(limit=10, scope=PrivacyScope.PUBLIC)
    
    # Should get 'valid' and 'fallback' (defaulted to PUBLIC)
    assert len(events) == 2
    assert events[0]['desc'] == 'fallback'
    assert events[1]['desc'] == 'valid'

def test_timeline_write_error(mocker):
    mocker.patch("builtins.open", side_effect=Exception("Write Fail"))
    tl = Timeline()
    # Should log error but not crash
    tl.add_event("type", "desc")
    assert True  # No exception: error handled gracefully

def test_graph_error(mock_neo4j):
    driver, session = mock_neo4j
    session.run.side_effect = Exception("Neo4j Error")
    
    kg = KnowledgeGraph()
    # Should catch exception and log
    kg.add_node("U", "N", user_id=-1, scope="CORE")
    kg.add_relationship("A", "REL", "B", user_id=-1, scope="CORE")
    assert True  # No exception: error handled gracefully

