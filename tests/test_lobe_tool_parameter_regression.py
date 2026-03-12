"""
REGRESSION TESTS: Lobe Tool Parameter Defaults

These tests ensure ALL lobe tools can be called WITHOUT positional arguments.
This prevents "missing required positional argument" errors at runtime.

DO NOT REMOVE THESE TESTS. They exist to prevent regression.
See conversation: 8d84b082-52b2-4ade-8bf4-336b5c893f4f (2026-02-05)
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestLobeToolParameterDefaults:
    """
    All lobe tools MUST be callable with NO positional arguments.
    If any of these tests fail, it means a tool has a required parameter
    without a default value, which will break LLM tool calls.
    """
    
    @pytest.fixture
    def mock_bot(self):
        """Mock bot with cerebrum."""
        with patch("src.bot.globals.bot") as mock:
            mock.cerebrum = MagicMock()
            lobe = MagicMock()
            ability = MagicMock()
            ability.execute = AsyncMock(return_value="OK")
            lobe.get_ability.return_value = ability
            mock.cerebrum.get_lobe.return_value = lobe
            yield mock
    
    # === STRATEGY TOOLS ===
    
    @pytest.mark.asyncio
    async def test_consult_gardener_no_args(self, mock_bot):
        """consult_gardener_lobe must work without args."""
        from src.tools.lobe_tools import consult_gardener_lobe
        result = await consult_gardener_lobe()
        assert "Error" not in result or "Cerebrum" in result  # Only system errors allowed
    
    @pytest.mark.asyncio
    async def test_consult_architect_no_args(self, mock_bot):
        """consult_architect_lobe must work without args."""
        from src.tools.lobe_tools import consult_architect_lobe
        result = await consult_architect_lobe()
        assert "Error" not in result or "Cerebrum" in result
    
    @pytest.mark.asyncio
    async def test_consult_project_lead_no_args(self, mock_bot):
        """consult_project_lead must work without args."""
        from src.tools.lobe_tools import consult_project_lead
        result = await consult_project_lead()
        assert "Error" not in result or "Cerebrum" in result
    
    @pytest.mark.asyncio
    async def test_consult_predictor_no_args(self, mock_bot):
        """consult_predictor must work without args."""
        from src.tools.lobe_tools import consult_predictor
        result = await consult_predictor()
        assert "Error" not in result or "Cerebrum" in result
    
    @pytest.mark.asyncio
    async def test_consult_performance_no_args(self, mock_bot):
        """consult_performance_lobe must work without args."""
        from src.tools.lobe_tools import consult_performance_lobe
        result = await consult_performance_lobe()
        assert "Error" not in result or "Cerebrum" in result
    
    # === SUPEREGO TOOLS ===
    
    @pytest.mark.asyncio
    async def test_consult_superego_no_args(self, mock_bot):
        """consult_superego must work without args."""
        from src.tools.lobe_tools import consult_superego
        result = await consult_superego()
        assert "missing" not in result.lower()
    
    @pytest.mark.asyncio
    async def test_consult_skeptic_no_args(self, mock_bot):
        """consult_skeptic must work without args."""
        from src.tools.lobe_tools import consult_skeptic
        result = await consult_skeptic()
        assert "missing" not in result.lower()
    
    # === INTERACTION TOOLS ===
    
    @pytest.mark.asyncio
    async def test_consult_science_no_args(self, mock_bot):
        """consult_science_lobe must work without args."""
        from src.tools.lobe_tools import consult_science_lobe
        result = await consult_science_lobe()
        assert "Error" in result  # Should give helpful error, not crash
    
    @pytest.mark.asyncio
    async def test_consult_bridge_no_args(self, mock_bot):
        """consult_bridge_lobe must work without args."""
        from src.tools.lobe_tools import consult_bridge_lobe
        result = await consult_bridge_lobe()
        assert "Error" not in result or "Cerebrum" in result or "instruction" in result.lower()
    
    @pytest.mark.asyncio
    async def test_consult_social_no_args(self, mock_bot):
        """consult_social_lobe must work without args."""
        from src.tools.lobe_tools import consult_social_lobe
        result = await consult_social_lobe()
        assert "Error" not in result or "Cerebrum" in result
    
    @pytest.mark.asyncio
    async def test_consult_world_lobe_no_args(self, mock_bot):
        """consult_world_lobe must work without args."""
        from src.tools.lobe_tools import consult_world_lobe
        result = await consult_world_lobe()
        assert "Error" in result  # Should give helpful error, not crash
    
    # === CREATIVE TOOLS ===
    
    @pytest.mark.asyncio
    async def test_consult_autonomy_no_args(self, mock_bot):
        """consult_autonomy must work without args."""
        from src.tools.lobe_tools import consult_autonomy
        result = await consult_autonomy()
        assert "Error" not in result or "Cerebrum" in result
    
    @pytest.mark.asyncio
    async def test_consult_subconscious_no_args(self, mock_bot):
        """consult_subconscious must work without args."""
        from src.tools.lobe_tools import consult_subconscious
        result = await consult_subconscious()
        assert "missing" not in result.lower()
    
    @pytest.mark.asyncio
    async def test_consult_curiosity_no_args(self, mock_bot):
        """consult_curiosity must work without args."""
        from src.tools.lobe_tools import consult_curiosity
        result = await consult_curiosity()
        assert "Error" not in result or "Cerebrum" in result
    
    # === MEMORY TOOLS ===
    
    @pytest.mark.asyncio
    async def test_consult_curator_no_args(self, mock_bot):
        """consult_curator must work without args."""
        from src.tools.lobe_tools import consult_curator
        result = await consult_curator()
        assert "missing" not in result.lower()  # Should work or give helpful error
    
    @pytest.mark.asyncio
    async def test_search_memory_no_args(self, mock_bot):
        """search_memory must work without args."""
        from src.tools.lobe_tools import search_memory
        result = await search_memory()
        assert "Error" in result  # Should give helpful error, not crash
    
    @pytest.mark.asyncio
    async def test_deep_think_no_args(self, mock_bot):
        """deep_think must work without args."""
        from src.tools.lobe_tools import deep_think
        result = await deep_think()
        assert "Error" not in result or "Cerebrum" in result


class TestLobeToolKwargsAliases:
    """
    Lobe tools must accept common kwarg aliases.
    LLMs sometimes use 'query' instead of 'instruction', etc.
    """
    
    @pytest.fixture
    def mock_bot(self):
        with patch("src.bot.globals.bot") as mock:
            mock.cerebrum = MagicMock()
            lobe = MagicMock()
            ability = MagicMock()
            ability.execute = AsyncMock(return_value="OK")
            lobe.get_ability.return_value = ability
            mock.cerebrum.get_lobe.return_value = lobe
            yield mock
    
    @pytest.mark.asyncio
    async def test_superego_accepts_content_kwarg(self, mock_bot):
        """consult_superego must accept 'content' kwarg."""
        from src.tools.lobe_tools import consult_superego
        result = await consult_superego(content="Test content")
        assert "missing" not in result.lower()
    
    @pytest.mark.asyncio
    async def test_skeptic_accepts_statement_kwarg(self, mock_bot):
        """consult_skeptic must accept 'statement' kwarg."""
        from src.tools.lobe_tools import consult_skeptic
        result = await consult_skeptic(statement="The sky is blue")
        assert "missing" not in result.lower()
    
    @pytest.mark.asyncio
    async def test_subconscious_accepts_query_kwarg(self, mock_bot):
        """consult_subconscious must accept 'query' kwarg."""
        from src.tools.lobe_tools import consult_subconscious
        result = await consult_subconscious(query="Reflect on self")
        assert "missing" not in result.lower()
    
    @pytest.mark.asyncio
    async def test_review_reasoning_no_args(self, mock_bot):
        """review_reasoning must work without args."""
        from src.tools.lobe_tools import review_reasoning
        result = await review_reasoning()
        assert "missing" not in result.lower()
    
    @pytest.mark.asyncio
    async def test_manage_projects_no_args(self, mock_bot):
        """manage_projects must work without args."""
        from src.tools.lobe_tools import manage_projects
        result = await manage_projects()
        assert "missing" not in result.lower()
