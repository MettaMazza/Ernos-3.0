"""
Regression Tests for Critical Integration Points

These tests exist to catch regressions in core integration points
that have historically broken due to API mismatches.

CRITICAL: Do not remove or skip these tests.
"""

import pytest
import inspect
from unittest.mock import MagicMock, patch


class TestToolSignatureCompatibility:
    """
    Ensure all tools can accept is_autonomy parameter.
    This prevents the Dreamer autonomy loop from breaking.
    Issue: TypeError when tool doesn't accept is_autonomy
    """
    
    def test_search_web_accepts_is_autonomy(self):
        """search_web must accept is_autonomy parameter."""
        from src.tools.web import search_web
        sig = inspect.signature(search_web)
        
        # Must have is_autonomy or **kwargs
        params = sig.parameters
        assert 'is_autonomy' in params or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        ), "search_web MUST accept is_autonomy parameter for Dreamer autonomy loop"
    
    def test_check_world_news_accepts_is_autonomy(self):
        """check_world_news must accept is_autonomy parameter."""
        from src.tools.web import check_world_news
        sig = inspect.signature(check_world_news)
        
        params = sig.parameters
        assert 'is_autonomy' in params or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        ), "check_world_news MUST accept is_autonomy parameter for Dreamer autonomy loop"
    
    def test_start_deep_research_accepts_is_autonomy(self):
        """start_deep_research must accept is_autonomy parameter."""
        from src.tools.web import start_deep_research
        sig = inspect.signature(start_deep_research)
        
        params = sig.parameters
        assert 'is_autonomy' in params, "start_deep_research MUST accept is_autonomy parameter"


class TestLobeManagerAPIConsistency:
    """
    Ensure LobeManager (Cerebrum) provides expected methods.
    Issue: AttributeError when calling get_lobe_by_name()
    """
    
    def test_cerebrum_has_get_lobe(self):
        """Cerebrum must have get_lobe method."""
        from src.lobes.manager import Cerebrum
        assert hasattr(Cerebrum, 'get_lobe'), "Cerebrum MUST have get_lobe method"
    
    def test_cerebrum_has_get_lobe_by_name_alias(self):
        """Cerebrum must have get_lobe_by_name alias for compatibility."""
        from src.lobes.manager import Cerebrum
        assert hasattr(Cerebrum, 'get_lobe_by_name'), (
            "Cerebrum MUST have get_lobe_by_name alias - "
            "components call this method and will get AttributeError otherwise"
        )
    
    def test_get_lobe_by_name_returns_same_as_get_lobe(self):
        """get_lobe_by_name must be equivalent to get_lobe."""
        from src.lobes.manager import Cerebrum
        
        mock_bot = MagicMock()
        cerebrum = Cerebrum(mock_bot)
        
        # They should return the same result
        assert cerebrum.get_lobe("TestLobe") == cerebrum.get_lobe_by_name("TestLobe")


class TestNeo4jQueryPatterns:
    """
    Ensure Neo4j queries don't create Cartesian products.
    Issue: PERFORMANCE warning GQL 03N90 - disconnected patterns
    """
    
    def test_add_relationship_no_cartesian_product(self):
        """add_relationship must not use MATCH (a), (b) pattern."""
        from src.memory.graph import KnowledgeGraph
        import inspect
        
        source = inspect.getsource(KnowledgeGraph.add_relationship)
        
        # Check for the bad pattern: MATCH (a ...), (b ...)
        # This creates a Cartesian product
        assert 'MATCH (a' not in source or 'WITH a' in source, (
            "add_relationship uses MATCH (a), (b) Cartesian product pattern - "
            "must use MERGE...WITH...MERGE instead"
        )


class TestContextObjectConsistency:
    """
    Ensure ContextObject has all required fields.
    Issue: TypeError when fields are missing from dataclass
    """
    
    def test_context_object_has_lessons(self):
        """ContextObject must have lessons field."""
        from src.memory.hippocampus import ContextObject
        import dataclasses
        
        fields = [f.name for f in dataclasses.fields(ContextObject)]
        assert 'lessons' in fields, (
            "ContextObject MUST have 'lessons' field - "
            "LessonManager integration requires this"
        )
    
    def test_context_object_has_required_fields(self):
        """ContextObject must have all core fields."""
        from src.memory.hippocampus import ContextObject
        import dataclasses
        
        fields = [f.name for f in dataclasses.fields(ContextObject)]
        required = ['working_memory', 'related_memories', 'knowledge_graph', 'scope']
        
        for field in required:
            assert field in fields, f"ContextObject MUST have '{field}' field"


class TestHippocampusIntegration:
    """
    Ensure Hippocampus properly initializes subsystems.
    Issue: Missing manager initializations
    """
    
    def test_hippocampus_has_lessons_manager(self):
        """Hippocampus must initialize LessonManager."""
        from src.memory.hippocampus import Hippocampus
        
        # Check the __init__ method initializes lessons
        import inspect
        source = inspect.getsource(Hippocampus.__init__)
        assert 'LessonManager' in source or 'lessons' in source, (
            "Hippocampus MUST initialize LessonManager in __init__"
        )


class TestPrivacyScopeConsistency:
    """
    Ensure privacy scope handling is consistent.
    """
    
    def test_privacy_scope_enum_values(self):
        """PrivacyScope must have CORE, PRIVATE, PUBLIC."""
        from src.privacy.scopes import PrivacyScope
        
        assert hasattr(PrivacyScope, 'CORE'), "PrivacyScope must have CORE"
        assert hasattr(PrivacyScope, 'PRIVATE'), "PrivacyScope must have PRIVATE"
        assert hasattr(PrivacyScope, 'PUBLIC'), "PrivacyScope must have PUBLIC"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
