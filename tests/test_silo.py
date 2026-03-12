import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
import discord
from src.silo_manager import SiloManager

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 1
    bot.loop = asyncio.new_event_loop()
    return bot

@pytest.mark.asyncio
async def test_propose_silo_logic(mock_bot):
    silo = SiloManager(mock_bot)
    user2 = MagicMock(spec=discord.Member); user2.id = 2
    msg = MagicMock(spec=discord.Message)
    msg.mentions = [mock_bot.user, user2]
    msg.reply = AsyncMock()
    msg.reply.return_value.id = 100
    msg.reply.return_value.add_reaction = AsyncMock()
    msg.author.id = 123
    await silo.propose_silo(msg)
    assert 100 in silo.pending_silos
    assert silo.pending_silos[100] == {2, 123}

@pytest.mark.asyncio
async def test_quorum_activation(mock_bot):
    silo = SiloManager(mock_bot)
    silo.pending_silos[100] = {1, 2}
    mock_msg = MagicMock(spec=discord.Message)
    react = MagicMock(spec=discord.Reaction); react.emoji = '✅'
    async def async_iter():
        yield MagicMock(id=1); yield MagicMock(id=2)
    react.users.return_value = async_iter()
    mock_msg.reactions = [react]
    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.fetch_message = AsyncMock(return_value=mock_msg)
    mock_bot.get_channel.return_value = mock_channel
    silo.activate_silo = AsyncMock()
    payload = MagicMock(spec=discord.RawReactionActionEvent, message_id=100, emoji='✅', channel_id=456)
    await silo.check_quorum(payload)
    silo.activate_silo.assert_called()
    assert 100 not in silo.pending_silos

@pytest.mark.asyncio
async def test_turn_taking(mock_bot):
    silo = SiloManager(mock_bot)
    silo.active_silos.add(555)
    thread = MagicMock(spec=discord.Thread); thread.id = 555
    m2 = MagicMock(spec=discord.Member); m2.id = 2
    thread.fetch_members = AsyncMock(return_value=[mock_bot.user, m2])
    msg_bot = MagicMock(spec=discord.Message); msg_bot.author.id = 1
    async def hist_bot(): yield msg_bot
    thread.history.return_value = hist_bot()
    msg = MagicMock(spec=discord.Message, channel=thread, mentions=[])
    assert await silo.should_bot_reply(msg) is False
    msg_human = MagicMock(spec=discord.Message); msg_human.author.id = 2
    async def hist_human(): yield msg_human; yield msg_bot
    thread.history.return_value = hist_human()
    assert await silo.should_bot_reply(msg) is True

@pytest.mark.asyncio
async def test_cleanup_and_discard_logic(mock_bot):
    silo = SiloManager(mock_bot)
    silo.active_silos.add(123)
    mock_thread = MagicMock(spec=discord.Thread)
    mock_thread.id = 123
    mock_thread.member_count = 1
    mock_thread.delete = AsyncMock()
    await silo.check_empty_silo(mock_thread)
    assert 123 not in silo.active_silos
    # Second call should not raise KeyError
    await silo.check_empty_silo(mock_thread)
