import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.silo_manager import SiloManager

@pytest.mark.asyncio
async def test_propose_silo_success():
    mock_bot = MagicMock()
    mock_bot_user = MagicMock()
    mock_bot_user.id = 1
    mock_bot.user = mock_bot_user
    mock_bot.loop.create_task = MagicMock()
    def close_coro(coro):
        coro.close()
        return MagicMock()
    mock_bot.loop.create_task.side_effect = close_coro
    
    silo = SiloManager(mock_bot)
    
    user2 = MagicMock()
    user2.id = 2
    
    msg = MagicMock()
    msg.mentions = [mock_bot_user, user2]
    msg.reply = AsyncMock()
    msg.reply.return_value.id = 100
    msg.reply.return_value.add_reaction = AsyncMock()
    msg.author.id = 123
    
    await silo.propose_silo(msg)
    
    assert 100 in silo.pending_silos
    # pending[100] should have user ids. 
    # we need to mock user objects better if we rely on u.id
    # but the test checks existence.

@pytest.mark.asyncio
async def test_propose_silo_ignore():
    mock_bot = MagicMock()
    mock_bot.user = "BotUser"
    silo = SiloManager(mock_bot)
    
    msg = MagicMock()
    msg.mentions = ["User2"] # Bot not mentioned
    
    await silo.propose_silo(msg)
    assert len(silo.pending_silos) == 0

@pytest.mark.asyncio
async def test_quorum_activation(mocker):
    mock_bot = MagicMock()
    silo = SiloManager(mock_bot)
    
    # Setup pending
    silo.pending_silos[100] = {1, 2}
    
    # Mock retrieval of message
    mock_msg = MagicMock()
    mock_msg.reactions = []
    
    # Reaction object
    # Reaction object with async iterator for users()
    react = MagicMock()
    react.emoji = "✅"
    react.count = 2 
    
    # Create an async iterator mock
    async def async_iter():
        yield MagicMock(id=1)
        yield MagicMock(id=2)
    
    react.users.return_value = async_iter()
    mock_msg.reactions = [react]
    
    mock_channel = MagicMock()
    mock_channel.fetch_message = AsyncMock(return_value=mock_msg)
    mock_bot.get_channel.return_value = mock_channel
    
    # Mock Activate
    silo.activate_silo = AsyncMock()
    
    # Payload
    payload = MagicMock()
    payload.message_id = 100
    payload.emoji = "✅"
    
    await silo.check_quorum(payload)
    
    silo.activate_silo.assert_called()
    assert 100 not in silo.pending_silos

@pytest.mark.asyncio
async def test_activate_logic():
    mock_bot = MagicMock()
    silo = SiloManager(mock_bot)
    
    origin = MagicMock()
    origin.id = 999
    origin.channel.create_thread = AsyncMock()
    origin.reference.message_id = 888
    
    # Mock fetching original message for mentions
    mock_orig_msg = MagicMock()
    mock_orig_msg.mentions = [MagicMock(id=1), MagicMock(id=2)]
    mock_orig_msg.author = MagicMock(id=3)
    
    origin.channel.fetch_message = AsyncMock(return_value=mock_orig_msg)
    
    await silo.activate_silo(origin, {1,2})
    
    origin.channel.create_thread.assert_called()
    # Confirm users added
    thread = origin.channel.create_thread.return_value
    assert thread.add_user.call_count >= 2
    assert thread.id in silo.active_silos

@pytest.mark.asyncio
async def test_silo_exceptions():
    # Test Propose Exception
    mock_bot = MagicMock()
    mock_bot.user = MagicMock()
    silo = SiloManager(mock_bot)
    
    msg = MagicMock()
    # mentions length ok, bot mentioned
    msg.mentions = [mock_bot.user, MagicMock()] 
    msg.reply.side_effect = Exception("Boom")
    
    # Should not crash
    await silo.propose_silo(msg)
    
    # Test Activate Exception
    origin = MagicMock()
    origin.create_thread.side_effect = Exception("Thread Fail")
    await silo.activate_silo(origin, set())

    # Test Check Quorum Edge Cases
    # 1. Payload not in pending
    payload = MagicMock(message_id=999)
    await silo.check_quorum(payload) # Should return
    
    # 2. Wrong emoji
    silo.pending_silos[100] = {1}
    payload = MagicMock(message_id=100, emoji="❌")
    await silo.check_quorum(payload)
    assert 100 in silo.pending_silos # Still pending

@pytest.mark.asyncio
async def test_propose_silo_only_bot():
    mock_bot = MagicMock()
    mock_bot.user = MagicMock()
    silo = SiloManager(mock_bot)
    
    msg = MagicMock()
    # mentions length 1 (Only bot)
    msg.mentions = [mock_bot.user]
    
    await silo.propose_silo(msg)
    assert len(silo.pending_silos) == 0
