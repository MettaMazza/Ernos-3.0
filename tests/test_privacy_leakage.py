
import pytest
from unittest.mock import MagicMock, call
from src.memory.graph import KnowledgeGraph

@pytest.fixture
def mock_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.verify_connectivity.return_value = True
    return driver, session

def test_graph_node_privacy(mock_driver):
    """Verify that add_node includes user_id in properties."""
    driver, session = mock_driver
    
    kg = KnowledgeGraph()
    kg.driver = driver # Inject mock
    
    # Add node for User 123
    kg.add_node("Person", "Alice", user_id=123, properties={"age": 30}, scope="PUBLIC")
    
    # Check the first Cypher call (the main MERGE), not _wire_to_root
    first_call = session.run.call_args_list[0]
    query = first_call[0][0]
    params = first_call[1]
    
    assert "user_id: $user_id" in query
    assert params["name"] == "Alice"
    assert params["user_id"] == 123
    assert params["props"]["user_id"] == 123

def test_graph_query_privacy_leakage(mock_driver):
    """Verify that query_context filters by user_id."""
    driver, session = mock_driver
    kg = KnowledgeGraph()
    kg.driver = driver
    
    # User 123 queries
    kg.query_context("Alice", user_id=123)
    
    args, _ = session.run.call_args
    query = args[0]
    
    # MUST have privacy filter
    assert "WHERE" in query
    assert "(m.user_id = $uid OR m.user_id IS NULL)" in query
    
    # System/Global query (user_id=None)
    # The logic in graph.py says: if user_id: append clause.
    # So if None, it shouldn't filter? Or should it?
    # If user_id is None (System), it presumably sees everything.
    kg.query_context("Alice", user_id=None)
    args_global, _ = session.run.call_args
    
    # Should NOT have the user_id filter if we are System
    # Wait, previous turn implementation:
    # clauses = [] ... if user_id: clauses.append(...)
    # So if user_id is None, clauses is empty -> No WHERE (or only layer)
    assert "(m.user_id = $uid" not in args_global[0]

def test_relationship_privacy(mock_driver):
    driver, session = mock_driver
    kg = KnowledgeGraph()
    kg.driver = driver
    
    kg.add_relationship("Alice", "KNOWS", "Bob", user_id=123, scope="PUBLIC")
    
    args, kwargs = session.run.call_args
    assert kwargs["props"]["user_id"] == 123
