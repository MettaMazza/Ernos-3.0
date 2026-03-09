"""
Tests for Gaming Tools
Targeting 95%+ coverage for src/tools/gaming_tools.py
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.tools.gaming_tools import start_game, stop_game, game_command, game_status


class TestStartGame:
    """Tests for start_game tool."""
    
    @pytest.mark.asyncio
    async def test_admin_only_rejection(self):
        """Test non-admin users are rejected."""
        # Patch config.settings directly
        with patch('config.settings.ADMIN_IDS', {12345}):
            
            result = await start_game(
                game="minecraft",
                user_id=99999,  # Not admin
                bot=MagicMock()
            )
            
            assert "admin-only" in result.lower()
            assert "🔒" in result
    
    @pytest.mark.asyncio
    async def test_admin_only_string_user_id(self):
        """Test string user_id handling."""
        with patch('config.settings.ADMIN_IDS', {12345}):
            
            result = await start_game(
                game="minecraft",
                user_id="not_a_number",
                bot=MagicMock()
            )
            
            assert "admin-only" in result.lower()
    
    @pytest.mark.asyncio
    async def test_no_bot_context(self):
        """Test error when no bot provided."""
        with patch('config.settings.ADMIN_IDS', {12345}):
            
            result = await start_game(
                game="minecraft",
                user_id=12345,
                bot=None
            )
            
            assert "No bot context" in result
    
    @pytest.mark.asyncio
    async def test_start_game_success(self):
        """Test successful game start."""
        with patch('config.settings.ADMIN_IDS', {12345}):
            
            mock_bot = MagicMock()
            mock_agent = MagicMock()
            mock_agent.start = AsyncMock(return_value=True)
            mock_agent.is_running = False  # Not running yet
            mock_bot.gaming_agent = mock_agent
            
            result = await start_game(
                game="minecraft",
                user_id=12345,
                bot=mock_bot,
                channel=MagicMock()
            )
            
            assert "🎮" in result
            assert "Started minecraft" in result
    
    @pytest.mark.asyncio
    async def test_start_game_failure(self):
        """Test game start failure."""
        with patch('config.settings.ADMIN_IDS', {12345}):
            
            mock_bot = MagicMock()
            mock_agent = MagicMock()
            mock_agent.start = AsyncMock(return_value=False)
            mock_agent.is_running = False  # Not running yet
            mock_bot.gaming_agent = mock_agent
            
            result = await start_game(
                game="minecraft",
                user_id=12345,
                bot=mock_bot,
                channel=MagicMock()
            )
            
            assert "❌" in result
            assert "Failed" in result
    
    @pytest.mark.asyncio
    async def test_start_game_already_running(self):
        """Test start_game rejected when game already running (duplicate launch prevention)."""
        with patch('config.settings.ADMIN_IDS', {12345}):
            
            mock_bot = MagicMock()
            mock_agent = MagicMock()
            mock_agent.is_running = True  # Already running!
            mock_bot.gaming_agent = mock_agent
            
            result = await start_game(
                game="minecraft",
                user_id=12345,
                bot=mock_bot,
                channel=MagicMock()
            )
            
            assert "already running" in result.lower()
            assert "🎮" in result
            # Verify start was NOT called
            mock_agent.start.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_creates_gaming_agent(self):
        """Test gaming agent creation when not exists."""
        with patch('config.settings.ADMIN_IDS', {12345}):
            # Patch where GamingAgent is IMPORTED FROM, not where the function is
            with patch('src.gaming.GamingAgent') as mock_ga:
                
                mock_bot = MagicMock(spec=[])  # No gaming_agent attribute
                mock_agent = MagicMock()
                mock_agent.start = AsyncMock(return_value=True)
                mock_agent.is_running = False  # Must be False for start to proceed
                mock_ga.return_value = mock_agent
                
                result = await start_game(
                    game="minecraft",
                    user_id=12345,
                    bot=mock_bot,
                    channel=MagicMock()
                )
                
                assert "Started" in result


class TestStopGame:
    """Tests for stop_game tool."""
    
    @pytest.mark.asyncio
    async def test_no_active_session(self):
        """Test when no gaming session is active."""
        result = await stop_game(bot=None)
        assert "No active gaming session" in result
    
    @pytest.mark.asyncio
    async def test_no_gaming_agent(self):
        """Test when bot has no gaming_agent."""
        mock_bot = MagicMock(spec=[])  # No gaming_agent
        result = await stop_game(bot=mock_bot)
        assert "No active gaming session" in result
    
    @pytest.mark.asyncio
    async def test_stop_success(self):
        """Test successful game stop."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent = MagicMock()
        mock_bot.gaming_agent.stop = AsyncMock()
        
        result = await stop_game(bot=mock_bot)
        
        assert "stopped" in result.lower()
        mock_bot.gaming_agent.stop.assert_called_once()


class TestGameCommand:
    """Tests for game_command tool."""
    
    @pytest.mark.asyncio
    async def test_no_bot(self):
        """Test with no bot context."""
        result = await game_command(command="goto 0 64 0", bot=None)
        assert "No active gaming session" in result
    
    @pytest.mark.asyncio
    async def test_no_gaming_agent(self):
        """Test when bot has no gaming_agent."""
        mock_bot = MagicMock(spec=[])
        result = await game_command(command="goto 0 64 0", bot=mock_bot)
        assert "No active gaming session" in result
    
    @pytest.mark.asyncio
    async def test_game_not_running(self):
        """Test when game is not running."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent = MagicMock()
        mock_bot.gaming_agent.is_running = False
        
        result = await game_command(command="goto 0 64 0", bot=mock_bot)
        assert "Not currently playing" in result
    
    @pytest.mark.asyncio
    async def test_goto_command(self):
        """Test goto command."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={"success": True, "data": "Arrived"})
        
        result = await game_command(command="goto 100 64 200", bot=mock_bot)
        
        assert "✅" in result
        mock_bot.gaming_agent.execute.assert_called_once_with("goto", x=100.0, y=64.0, z=200.0)
    
    @pytest.mark.asyncio
    async def test_goto_invalid_args(self):
        """Test goto with insufficient args."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        
        result = await game_command(command="goto 100", bot=mock_bot)
        assert "Usage:" in result
    
    @pytest.mark.asyncio
    async def test_collect_command(self):
        """Test collect command."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={"success": True, "data": "Collected 5"})
        
        result = await game_command(command="collect oak_log 5", bot=mock_bot)
        
        assert "✅" in result
        mock_bot.gaming_agent.execute.assert_called_once_with("collect", block_type="oak_log", count=5)
    
    @pytest.mark.asyncio
    async def test_collect_default_args(self):
        """Test collect with default args."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={"success": True, "data": "Collected"})
        
        result = await game_command(command="collect", bot=mock_bot)
        
        mock_bot.gaming_agent.execute.assert_called_once_with("collect", block_type="oak_log", count=1)
    
    @pytest.mark.asyncio
    async def test_attack_command(self):
        """Test attack command."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={"success": True, "data": "Attacked"})
        
        result = await game_command(command="attack zombie", bot=mock_bot)
        
        mock_bot.gaming_agent.execute.assert_called_once_with("attack", entity_type="zombie")
    
    @pytest.mark.asyncio
    async def test_craft_command(self):
        """Test craft command."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={"success": True, "data": "Crafted"})
        
        result = await game_command(command="craft wooden_pickaxe 2", bot=mock_bot)
        
        mock_bot.gaming_agent.execute.assert_called_once_with("craft", item="wooden_pickaxe", count=2)
    
    @pytest.mark.asyncio
    async def test_chat_command(self):
        """Test chat command."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={"success": True, "data": "Sent"})
        
        result = await game_command(command="chat Hello world!", bot=mock_bot)
        
        mock_bot.gaming_agent.execute.assert_called_once_with("chat", message="Hello world!")
    
    @pytest.mark.asyncio
    async def test_status_command(self):
        """Test status command."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={"success": True, "data": "Status data"})
        
        result = await game_command(command="status", bot=mock_bot)
        
        mock_bot.gaming_agent.execute.assert_called_once_with("status")
    
    @pytest.mark.asyncio
    async def test_follow_command(self):
        """Test follow command."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={"success": True, "data": "Following"})
        
        result = await game_command(command="follow PlayerName", bot=mock_bot)
        
        mock_bot.gaming_agent.execute.assert_called_once_with("follow", username="PlayerName")
    
    @pytest.mark.asyncio
    async def test_unknown_command(self):
        """Test unknown command."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        
        result = await game_command(command="dance", bot=mock_bot)
        
        assert "Unknown command" in result
    
    @pytest.mark.asyncio
    async def test_command_failure(self):
        """Test command failure response."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={"success": False, "error": "Path blocked"})
        
        result = await game_command(command="goto 100 64 200", bot=mock_bot)
        
        assert "❌" in result
        assert "failed" in result.lower()


class TestGameStatus:
    """Tests for game_status tool."""
    
    @pytest.mark.asyncio
    async def test_not_playing_no_bot(self):
        """Test when no bot."""
        result = await game_status(bot=None)
        assert "Not playing" in result
    
    @pytest.mark.asyncio
    async def test_not_playing_no_agent(self):
        """Test when no gaming agent."""
        mock_bot = MagicMock(spec=[])
        result = await game_status(bot=mock_bot)
        assert "Not playing" in result
    
    @pytest.mark.asyncio
    async def test_game_not_running(self):
        """Test when game not running."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = False
        
        result = await game_status(bot=mock_bot)
        assert "Not currently playing" in result
    
    @pytest.mark.asyncio
    async def test_status_success(self):
        """Test successful status retrieval."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={
            "success": True,
            "data": {
                "health": 20,
                "food": 18,
                "position": {"x": 100, "y": 64, "z": 200},
                "inventory": ["stick", "pickaxe", "stone"]
            }
        })
        
        result = await game_status(bot=mock_bot)
        
        assert "Health: 20/20" in result
        assert "Food: 18/20" in result
        assert "100" in result  # x position
        assert "3 items" in result  # inventory count
    
    @pytest.mark.asyncio
    async def test_status_error(self):
        """Test status error."""
        mock_bot = MagicMock()
        mock_bot.gaming_agent.is_running = True
        mock_bot.gaming_agent.execute = AsyncMock(return_value={
            "success": False,
            "error": "Connection lost"
        })
        
        result = await game_status(bot=mock_bot)
        
        assert "Error" in result
        assert "Connection lost" in result
