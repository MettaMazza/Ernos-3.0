"""
REGRESSION TESTS: Neo4j Graph Relationship Sanitization

These tests ensure relationship types are properly sanitized before being
sent to Neo4j, which only allows alphanumeric characters and underscores.

DO NOT REMOVE THESE TESTS.
See conversation: 8d84b082-52b2-4ade-8bf4-336b5c893f4f (2026-02-05)
"""
import pytest
from unittest.mock import MagicMock, patch


class TestGraphRelTypeSanitization:
    """Regression tests for Neo4j relationship type sanitization."""
    
    @pytest.fixture
    def mock_graph(self):
        """Create a KnowledgeGraph with mocked Neo4j driver."""
        with patch('src.memory.graph.GraphDatabase') as mock_driver:
            # Mock the driver and session
            mock_driver.driver.return_value = MagicMock()
            mock_driver.driver.return_value.verify_connectivity.return_value = None
            mock_driver.driver.return_value.session.return_value.__enter__ = MagicMock()
            mock_driver.driver.return_value.session.return_value.__exit__ = MagicMock()
            
            from src.memory.graph import KnowledgeGraph
            
            # Patch the entire init to avoid Neo4j connection
            with patch.object(KnowledgeGraph, '__init__', lambda self: None):
                graph = KnowledgeGraph()
                graph.driver = MagicMock()
                graph.quarantine = MagicMock()
                yield graph
    
    def test_sanitize_colon_in_rel_type(self, mock_graph):
        """Colons in relationship types must be converted to underscores."""
        # This was the bug: "NODE:_DIAGNOSTICTEST_WITH_PROPERTY" caused syntax error
        mock_graph.add_relationship("A", "NODE:TEST", "B", user_id=-1, scope="CORE")
        
        # Get the query that was executed
        call_args = mock_graph.driver.session.return_value.__enter__.return_value.run.call_args
        query = call_args[0][0]
        
        # Must NOT contain colons in the relationship type
        assert "NODE_TEST" in query
        assert "NODE:TEST" not in query
    
    def test_sanitize_spaces_in_rel_type(self, mock_graph):
        """Spaces in relationship types must be converted to underscores."""
        mock_graph.add_relationship("A", "HAS RELATIONSHIP", "B", user_id=-1, scope="CORE")
        call_args = mock_graph.driver.session.return_value.__enter__.return_value.run.call_args
        query = call_args[0][0]
        
        assert "HAS_RELATIONSHIP" in query
    
    def test_sanitize_dashes_in_rel_type(self, mock_graph):
        """Dashes in relationship types must be converted to underscores."""
        mock_graph.add_relationship("A", "RELATED-TO", "B", user_id=-1, scope="CORE")
        call_args = mock_graph.driver.session.return_value.__enter__.return_value.run.call_args
        query = call_args[0][0]
        
        assert "RELATED_TO" in query
    
    def test_sanitize_dots_in_rel_type(self, mock_graph):
        """Dots in relationship types must be converted to underscores."""
        mock_graph.add_relationship("A", "HAS.PROPERTY", "B", user_id=-1, scope="CORE")
        call_args = mock_graph.driver.session.return_value.__enter__.return_value.run.call_args
        query = call_args[0][0]
        
        assert "HAS_PROPERTY" in query
    
    def test_sanitize_special_chars_removed(self, mock_graph):
        """Special characters must be removed from relationship types."""
        mock_graph.add_relationship("A", "HAS (PROPERTY)", "B", user_id=-1, scope="CORE")
        call_args = mock_graph.driver.session.return_value.__enter__.return_value.run.call_args
        query = call_args[0][0]
        
        # Relationship type portion should not have parentheses
        assert "[r:HAS_PROPERTY" in query
    
    def test_empty_rel_type_gets_default(self, mock_graph):
        """Empty relationship type after sanitization gets default."""
        mock_graph.add_relationship("A", ":::...", "B", user_id=-1, scope="CORE")
        call_args = mock_graph.driver.session.return_value.__enter__.return_value.run.call_args
        query = call_args[0][0]
        
        # Should default to RELATED_TO
        assert "RELATED_TO" in query
    
    def test_uppercases_rel_type(self, mock_graph):
        """Relationship types must be uppercased."""
        mock_graph.add_relationship("A", "likes", "B", user_id=-1, scope="CORE")
        call_args = mock_graph.driver.session.return_value.__enter__.return_value.run.call_args
        query = call_args[0][0]
        
        assert "LIKES" in query
        assert "likes" not in query
