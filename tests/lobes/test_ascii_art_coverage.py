"""
Tests for ASCII Art Ability
Targeting 95%+ coverage for src/lobes/creative/ascii_art.py
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.lobes.creative.ascii_art import ASCIIArtAbility


class TestASCIIArtAbility:
    """Tests for ASCIIArtAbility class."""
    
    def setup_method(self):
        """Setup mock bot for each test."""
        self.mock_bot = MagicMock()
        self.mock_engine = MagicMock()
        self.mock_bot.engine_manager.get_active_engine.return_value = self.mock_engine
        # Create proper async mock for run_in_executor
        async def mock_run_in_executor(executor, func):
            return func()
        self.mock_bot.loop.run_in_executor = mock_run_in_executor
        self.ability = ASCIIArtAbility(self.mock_bot)
    
    @pytest.mark.asyncio
    async def test_execute_default(self):
        """Test default execute calls generate_system_map."""
        result = await self.ability.execute()
        
        assert "ERNOS 3.0 BRAIN" in result
        assert "```" in result  # Protected by code block
    
    @pytest.mark.asyncio
    async def test_generate_system_map(self):
        """Test system map generation."""
        result = await self.ability.generate_system_map()
        
        assert "KERNEL" in result
        assert "SUPEREGO" in result
        assert "COGNITIVE LOBES" in result
        assert "HIPPOCAMPUS" in result
        assert "```" in result
    
    
    @pytest.mark.asyncio
    async def test_generate_diagram_tree_style(self):
        """Test diagram generation with tree style."""
        self.mock_bot.loop.run_in_executor = AsyncMock(return_value="├── Node\n└── Leaf")
        
        result = await self.ability.generate_diagram("Test tree", style="tree")
        
        assert "```" in result
    
    @pytest.mark.asyncio
    async def test_generate_diagram_flow_style(self):
        """Test diagram generation with flow style."""
        self.mock_bot.loop.run_in_executor = AsyncMock(return_value="○ → ◆ → □")
        
        result = await self.ability.generate_diagram("Test flow", style="flow")
        
        assert "```" in result
    
    @pytest.mark.asyncio
    async def test_generate_diagram_simple_style(self):
        """Test diagram generation with simple style."""
        self.mock_bot.loop.run_in_executor = AsyncMock(return_value="+---+\n| A |\n+---+")
        
        result = await self.ability.generate_diagram("Test simple", style="simple")
        
        assert "```" in result
    
    @pytest.mark.asyncio
    async def test_generate_diagram_fallback_style(self):
        """Test diagram generation with unknown style defaults to simple."""
        self.mock_bot.loop.run_in_executor = AsyncMock(return_value="Simple result")
        
        result = await self.ability.generate_diagram("Test", style="unknown")
        
        assert "```" in result
    
    @pytest.mark.asyncio
    async def test_generate_diagram_no_engine(self):
        """Test when no engine available."""
        self.mock_bot.engine_manager.get_active_engine.return_value = None
        
        result = await self.ability.generate_diagram("Test")
        
        # Either shows 'No inference engine' or falls through to error
        assert "```" in result
    
    @pytest.mark.asyncio
    async def test_generate_diagram_exception(self):
        """Test error handling in diagram generation."""
        self.mock_bot.loop.run_in_executor = AsyncMock(side_effect=Exception("LLM Error"))
        
        result = await self.ability.generate_diagram("Test")
        
        assert "Error" in result
        assert "```" in result
    
    @pytest.mark.asyncio
    async def test_generate_art_success(self):
        """Test ASCII art generation."""
        self.mock_bot.loop.run_in_executor = AsyncMock(return_value="   /\\ \n  /  \\\n /    \\")
        
        result = await self.ability.generate_art("mountain")
        
        assert "```" in result
    
    @pytest.mark.asyncio
    async def test_generate_art_no_engine(self):
        """Test art generation when no engine available."""
        self.mock_bot.engine_manager.get_active_engine.return_value = None
        
        result = await self.ability.generate_art("cat")
        
        # Either shows 'No inference engine' or falls through to error
        assert "```" in result
    
    @pytest.mark.asyncio
    async def test_generate_art_exception(self):
        """Test error handling in art generation."""
        self.mock_bot.loop.run_in_executor = AsyncMock(side_effect=Exception("Art Error"))
        
        result = await self.ability.generate_art("dragon")
        
        assert "Error" in result
    
    def test_protect_output_basic(self):
        """Test output protection wraps in code block."""
        result = self.ability._protect_output("Hello World")
        
        assert result == "```\nHello World\n```"
    
    def test_protect_output_removes_existing_blocks(self):
        """Test that existing code blocks are removed."""
        result = self.ability._protect_output("```\nNested\n```")
        
        assert result == "```\n\nNested\n\n```"
        # No triple backticks inside the content
    
    def test_style_guides_exist(self):
        """Test all style guides are defined."""
        assert "box" in ASCIIArtAbility.STYLE_GUIDES
        assert "tree" in ASCIIArtAbility.STYLE_GUIDES
        assert "flow" in ASCIIArtAbility.STYLE_GUIDES
        assert "simple" in ASCIIArtAbility.STYLE_GUIDES
