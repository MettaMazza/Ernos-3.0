"""
Regression tests for Gaming Agent cognition handling.
Tests the fix for "too many values to unpack" error that caused bot freeze/rejoin loops.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


class TestGamingAgentCognition:
    """Regression tests for _think() cognition result handling."""
    
    def setup_method(self):
        """Setup mock bot and agent."""
        self.mock_bot = MagicMock()
        self.mock_bot.cognition = AsyncMock()
        self.mock_bot.engine_manager.get_active_engine.return_value = MagicMock()
        
    @pytest.mark.asyncio
    async def test_cognition_returns_tuple_of_two(self):
        """Test normal case: cognition returns (response, files)."""
        from src.gaming.agent import GamingAgent
        
        agent = GamingAgent(self.mock_bot)
        agent.bridge = MagicMock()
        
        # Simulate normal return: (response_text, files_list)
        self.mock_bot.cognition.process.return_value = ("ACTION: explore", [], [])
        
        state = {
            'health': 20, 'food': 20,
            'position': {'x': 0, 'y': 64, 'z': 0},
            'is_day': True, 'nearby_entities': [],
            'hostiles_nearby': False, 'inventory': [],
            'pending_chats': [], 'screenshot': None
        }
        
        result = await agent._think(state)
        
        assert result == "explore"
    
    @pytest.mark.asyncio
    async def test_cognition_returns_tuple_of_three_regression(self):
        """
        REGRESSION TEST: Handle case where cognition returns 3+ values.
        This was causing "too many values to unpack (expected 2)" error.
        """
        from src.gaming.agent import GamingAgent
        
        agent = GamingAgent(self.mock_bot)
        agent.bridge = MagicMock()
        
        # Simulate edge case: 3 values returned (the bug trigger)
        self.mock_bot.cognition.process.return_value = ("ACTION: scan", [], {"extra": "data"})
        
        state = {
            'health': 20, 'food': 20,
            'position': {'x': 0, 'y': 64, 'z': 0},
            'is_day': True, 'nearby_entities': [],
            'hostiles_nearby': False, 'inventory': [],
            'pending_chats': [], 'screenshot': None
        }
        
        # Should NOT raise "too many values to unpack"
        result = await agent._think(state)
        
        assert result == "scan"
    
    @pytest.mark.asyncio
    async def test_cognition_returns_string_directly(self):
        """Test case where cognition returns just a string (not tuple)."""
        from src.gaming.agent import GamingAgent
        
        agent = GamingAgent(self.mock_bot)
        agent.bridge = MagicMock()
        
        # Simulate direct string return
        self.mock_bot.cognition.process.return_value = "ACTION: wander"
        
        state = {
            'health': 20, 'food': 20,
            'position': {'x': 0, 'y': 64, 'z': 0},
            'is_day': True, 'nearby_entities': [],
            'hostiles_nearby': False, 'inventory': [],
            'pending_chats': [], 'screenshot': None
        }
        
        result = await agent._think(state)
        
        assert result == "wander"
    
    @pytest.mark.asyncio
    async def test_cognition_returns_empty_tuple(self):
        """Test edge case: empty tuple returned."""
        from src.gaming.agent import GamingAgent
        
        agent = GamingAgent(self.mock_bot)
        agent.bridge = MagicMock()
        
        # Simulate empty tuple
        self.mock_bot.cognition.process.return_value = ()
        
        state = {
            'health': 20, 'food': 20,
            'position': {'x': 0, 'y': 64, 'z': 0},
            'is_day': True, 'nearby_entities': [],
            'hostiles_nearby': False, 'inventory': [],
            'pending_chats': [], 'screenshot': None
        }
        
        # Should fallback to explore, not crash
        result = await agent._think(state)
        
        assert result == "explore"
    
    @pytest.mark.asyncio
    async def test_cognition_returns_none(self):
        """Test edge case: None returned."""
        from src.gaming.agent import GamingAgent
        
        agent = GamingAgent(self.mock_bot)
        agent.bridge = MagicMock()
        
        self.mock_bot.cognition.process.return_value = None
        
        state = {
            'health': 20, 'food': 20,
            'position': {'x': 0, 'y': 64, 'z': 0},
            'is_day': True, 'nearby_entities': [],
            'hostiles_nearby': False, 'inventory': [],
            'pending_chats': [], 'screenshot': None
        }
        
        # Should fallback to explore
        result = await agent._think(state)
        
        assert result == "explore"
    
    @pytest.mark.asyncio
    async def test_no_action_in_response_fallback(self):
        """Test fallback when ACTION: not in response."""
        from src.gaming.agent import GamingAgent
        
        agent = GamingAgent(self.mock_bot)
        agent.bridge = MagicMock()
        
        # Response without ACTION:
        self.mock_bot.cognition.process.return_value = ("I should explore the area", [], [])
        
        state = {
            'health': 20, 'food': 20,
            'position': {'x': 0, 'y': 64, 'z': 0},
            'is_day': True, 'nearby_entities': [],
            'hostiles_nearby': False, 'inventory': [],
            'pending_chats': [], 'screenshot': None
        }
        
        result = await agent._think(state)
        
        # Should fallback to explore
        assert result == "explore"


class TestStuckDetection:
    """Tests for stuck detection and recovery."""
    
    def test_stuck_counter_increments(self):
        """Test stuck counter increments when not moving."""
        from src.gaming.agent import GamingAgent
        
        mock_bot = MagicMock()
        agent = GamingAgent(mock_bot)
        agent._last_position = {'x': 100, 'y': 64, 'z': 100}
        agent._stuck_counter = 0
        
        # Same position (not moving)
        result = agent._check_stuck({'x': 100, 'y': 64, 'z': 100})
        
        assert agent._stuck_counter == 1
        assert result is False  # Not stuck yet (need 3)
    
    def test_stuck_detected_after_three_cycles(self):
        """Test stuck is detected after 3 cycles."""
        from src.gaming.agent import GamingAgent
        
        mock_bot = MagicMock()
        agent = GamingAgent(mock_bot)
        agent._last_position = {'x': 100, 'y': 64, 'z': 100}
        agent._stuck_counter = 2  # Already 2 cycles
        
        # Same position again
        result = agent._check_stuck({'x': 100, 'y': 64, 'z': 100})
        
        assert agent._stuck_counter == 3
        assert result is True  # NOW stuck
    
    def test_stuck_counter_resets_on_movement(self):
        """Test stuck counter resets when bot moves."""
        from src.gaming.agent import GamingAgent
        
        mock_bot = MagicMock()
        agent = GamingAgent(mock_bot)
        agent._last_position = {'x': 100, 'y': 64, 'z': 100}
        agent._stuck_counter = 2
        
        # Moved more than 1 block
        result = agent._check_stuck({'x': 105, 'y': 64, 'z': 100})
        
        assert agent._stuck_counter == 0  # Reset
        assert result is False
