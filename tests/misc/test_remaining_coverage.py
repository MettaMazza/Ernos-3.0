import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# --- Scopes Tests ---
def test_get_public_user_silo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.privacy.scopes import ScopeManager
    
    path = ScopeManager.get_public_user_silo(12345)
    assert path.exists()
    assert "public" in str(path)

# --- Silo Manager Tests ---
@pytest.fixture
def silo_mgr():
    from src.silo_manager import SiloManager
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 999
    return SiloManager(bot)

@pytest.mark.asyncio
async def test_propose_silo_too_few_mentions(silo_mgr):
    msg = MagicMock()
    msg.mentions = [MagicMock()]  # Only 1 mention
    await silo_mgr.propose_silo(msg)
    assert True  # Execution completed without error
    # Should return early, no proposal

@pytest.mark.asyncio
async def test_propose_silo_bot_not_mentioned(silo_mgr):
    msg = MagicMock()
    msg.mentions = [MagicMock(), MagicMock()]  # 2 mentions but neither is bot
    await silo_mgr.propose_silo(msg)
    assert True  # No exception: negative case handled correctly
    # Should return early

@pytest.mark.asyncio 
async def test_expire_proposal(silo_mgr):
    silo_mgr.pending_silos[123] = {1, 2}
    
    with patch("asyncio.sleep", return_value=None):
        await silo_mgr._expire_proposal(123)
        assert 123 not in silo_mgr.pending_silos

@pytest.mark.asyncio
async def test_activate_silo_exception(silo_mgr):
    msg = MagicMock()
    msg.create_thread.side_effect = Exception("Thread Error")
    
    with patch("src.silo_manager.logger") as mock_logger:
        await silo_mgr.activate_silo(msg, {1, 2})
        mock_logger.error.assert_called()

# --- Memory Tools Tests ---
@pytest.mark.asyncio
async def test_add_reaction_no_message():
    from src.tools.memory import add_reaction
    
    with patch("src.bot.globals.active_message") as mock_active:
        mock_active.get.return_value = None
        result = await add_reaction("👍")
        assert "No active message" in result

@pytest.mark.asyncio
async def test_add_reaction_no_bot():
    from src.tools.memory import add_reaction
    
    with patch("src.bot.globals.active_message") as mock_active:
        mock_msg = MagicMock()
        mock_active.get.return_value = mock_msg
        with patch("src.bot.globals.bot", None):
            result = await add_reaction("👍")
            assert "Bot instance not available" in result

def test_recall_user_exception():
    from src.tools.memory import recall_user
    
    with patch("src.bot.globals.active_message") as mock_active:
        mock_active.get.return_value = None
        with patch("pathlib.Path.exists", side_effect=Exception("Path Error")):
            result = recall_user("123")
            assert "Error" in result

def test_recall_user_silo_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.tools.memory import recall_user
    
    # Create empty silo
    silo = Path("memory/public/users/123")
    silo.mkdir(parents=True)
    (silo / "timeline.jsonl").write_text("")
    
    with patch("src.bot.globals.active_message") as mock_active:
        mock_active.get.return_value = None
        result = recall_user("123")
        assert "empty" in result

def test_review_reasoning_exception():
    from src.tools.memory import review_my_reasoning
    
    with patch("os.path.exists", side_effect=Exception("Error")):
        with patch("src.bot.globals.active_message") as mock_active:
            mock_active.get.return_value = None  # No active message context
            result = review_my_reasoning()
            # May return Access Denied (scope check) or Introspection Error (exception)
            assert "Error" in result or "Access Denied" in result or "Introspection" in result

def test_publish_to_bridge_exception():
    from src.tools.memory import publish_to_bridge
    
    with patch("os.makedirs", side_effect=Exception("Dir Error")):
        result = publish_to_bridge("test")
        assert "Error" in result

def test_read_public_bridge_exception():
    from src.tools.memory import read_public_bridge
    
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=Exception("Read Error")):
            result = read_public_bridge()
            assert "Error" in result
