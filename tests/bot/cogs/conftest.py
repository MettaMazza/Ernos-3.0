"""Shared fixtures for cog tests — mock discord.Interaction and bot."""
import pytest
from unittest.mock import MagicMock, AsyncMock
import discord


def _make_interaction(*, is_dm=True, user_id=12345, guild_id=None, channel_id=100):
    """Build a mock discord.Interaction for cog testing."""
    interaction = MagicMock(spec=discord.Interaction)

    user = MagicMock(spec=discord.User)
    user.id = user_id
    user.display_name = "TestUser"
    user.mention = f"<@{user_id}>"
    interaction.user = user

    if is_dm:
        channel = MagicMock(spec=discord.DMChannel)
        channel.id = channel_id
        interaction.guild = None
        interaction.guild_id = None
    else:
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = channel_id
        channel.threads = []
        interaction.guild = MagicMock(spec=discord.Guild)
        interaction.guild.id = guild_id or 999
        interaction.guild_id = guild_id or 999

    interaction.channel = channel
    interaction.channel_id = channel_id

    response = MagicMock()
    response.send_message = AsyncMock()
    response.defer = AsyncMock()
    interaction.response = response

    followup = MagicMock()
    followup.send = AsyncMock()
    interaction.followup = followup

    return interaction


def _make_bot(**extras):
    """Build a minimal mock bot for cog testing."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "ErnosTest"
    bot.add_cog = AsyncMock()
    bot.town_hall = None
    bot.cerebrum = MagicMock()
    bot.silo_manager = MagicMock()
    bot.silo_manager.active_silos = {}
    bot.silo_manager.check_empty_silo = AsyncMock()
    for k, v in extras.items():
        setattr(bot, k, v)
    return bot


@pytest.fixture
def make_interaction():
    return _make_interaction


@pytest.fixture
def make_bot_fixture():
    return _make_bot


@pytest.fixture
def bot():
    return _make_bot()


@pytest.fixture
def dm_interaction():
    return _make_interaction(is_dm=True)


@pytest.fixture
def guild_interaction():
    return _make_interaction(is_dm=False, channel_id=987654321)
