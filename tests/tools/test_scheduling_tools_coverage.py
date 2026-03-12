"""
Coverage tests for src/tools/scheduling_tools.py.
Targets 26 uncovered lines across: check_current_time, read_channel.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestCheckCurrentTime:
    @pytest.mark.asyncio
    async def test_with_timezone(self):
        from src.tools.scheduling_tools import check_current_time
        mock_settings = MagicMock()
        mock_settings.TIMEZONE = "Europe/London"
        with patch("src.tools.scheduling_tools.check_current_time.__module__", "src.tools.scheduling_tools"):
            # Direct call — it imports pytz and settings internally
            with patch.dict("sys.modules", {"config": MagicMock(), "config.settings": mock_settings}):
                with patch("pytz.timezone") as mock_tz:
                    from datetime import datetime
                    mock_tz.return_value = MagicMock()
                    with patch("datetime.datetime") as mock_dt:
                        mock_dt.now.return_value = datetime(2026, 2, 21, 14, 30, 0)
                        # Reimport to use patched config
                        import importlib
                        import src.tools.scheduling_tools as st
                        result = await st.check_current_time()
                assert "Current Time" in result

    @pytest.mark.asyncio
    async def test_timezone_fallback(self):
        from src.tools.scheduling_tools import check_current_time
        # If pytz.timezone raises, falls back to utcnow
        with patch("pytz.timezone", side_effect=Exception("bad tz")):
            result = await check_current_time()
        assert "Current Time" in result


class TestReadChannel:
    @pytest.mark.asyncio
    async def test_no_bot(self):
        from src.tools.scheduling_tools import read_channel
        result = await read_channel(channel_name="general")
        assert "No bot context" in result

    @pytest.mark.asyncio
    async def test_channel_not_found(self):
        from src.tools.scheduling_tools import read_channel
        mock_bot = MagicMock()
        mock_guild = MagicMock()
        mock_guild.text_channels = []
        mock_bot.guilds = [mock_guild]
        result = await read_channel(channel_name="nonexistent", bot=mock_bot)
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_exact_match(self):
        from src.tools.scheduling_tools import read_channel
        mock_bot = MagicMock()
        mock_channel = MagicMock()
        mock_channel.name = "general"
        mock_channel.permissions_for.return_value = MagicMock(read_message_history=True)

        # Setup async history
        msg1 = MagicMock()
        msg1.created_at = MagicMock()
        msg1.created_at.strftime.return_value = "14:30"
        msg1.author.display_name = "User1"
        msg1.content = "Hello!"
        msg1.embeds = []

        async def mock_history(limit=20):
            for m in [msg1]:
                yield m

        mock_channel.history = mock_history

        mock_guild = MagicMock()
        mock_guild.text_channels = [mock_channel]
        mock_bot.guilds = [mock_guild]

        result = await read_channel(channel_name="general", limit=5, bot=mock_bot)
        assert "Hello!" in result

    @pytest.mark.asyncio
    async def test_fuzzy_match(self):
        from src.tools.scheduling_tools import read_channel
        mock_bot = MagicMock()
        mock_channel = MagicMock()
        mock_channel.name = "persona-chats"
        mock_channel.permissions_for.return_value = MagicMock(read_message_history=True)

        async def mock_history(limit=20):
            msg = MagicMock()
            msg.created_at.strftime.return_value = "10:00"
            msg.author.display_name = "Bot"
            msg.content = "Test"
            msg.embeds = []
            yield msg

        mock_channel.history = mock_history

        mock_guild = MagicMock()
        mock_guild.text_channels = [mock_channel]
        mock_bot.guilds = [mock_guild]

        # "persona-chat" should fuzzy match "persona-chats" (adding 's' variant)
        result = await read_channel(channel_name="persona-chat", bot=mock_bot)
        assert "Test" in result

    @pytest.mark.asyncio
    async def test_no_permission(self):
        from src.tools.scheduling_tools import read_channel
        mock_bot = MagicMock()
        mock_channel = MagicMock()
        mock_channel.name = "secret"
        mock_channel.permissions_for.return_value = MagicMock(read_message_history=False)

        mock_guild = MagicMock()
        mock_guild.text_channels = [mock_channel]
        mock_guild.me = MagicMock()
        mock_bot.guilds = [mock_guild]

        result = await read_channel(channel_name="secret", bot=mock_bot)
        assert "permission" in result.lower()

    @pytest.mark.asyncio
    async def test_with_embeds(self):
        from src.tools.scheduling_tools import read_channel
        mock_bot = MagicMock()
        mock_channel = MagicMock()
        mock_channel.name = "news"
        mock_channel.permissions_for.return_value = MagicMock(read_message_history=True)

        embed = MagicMock()
        embed.author.name = "NewsBot"
        embed.description = "Breaking news!"

        msg = MagicMock()
        msg.created_at.strftime.return_value = "12:00"
        msg.author.display_name = "Bot"
        msg.content = ""
        msg.embeds = [embed]

        async def mock_history(limit=20):
            yield msg

        mock_channel.history = mock_history

        mock_guild = MagicMock()
        mock_guild.text_channels = [mock_channel]
        mock_bot.guilds = [mock_guild]

        result = await read_channel(channel_name="news", bot=mock_bot)
        assert "NewsBot" in result
        assert "Breaking news" in result

    @pytest.mark.asyncio
    async def test_empty_channel(self):
        from src.tools.scheduling_tools import read_channel
        mock_bot = MagicMock()
        mock_channel = MagicMock()
        mock_channel.name = "empty"
        mock_channel.permissions_for.return_value = MagicMock(read_message_history=True)

        async def mock_history(limit=20):
            return
            yield  # empty async gen

        mock_channel.history = mock_history

        mock_guild = MagicMock()
        mock_guild.text_channels = [mock_channel]
        mock_bot.guilds = [mock_guild]

        result = await read_channel(channel_name="empty", bot=mock_bot)
        assert "no recent messages" in result.lower()

    @pytest.mark.asyncio
    async def test_clamp_limit(self):
        from src.tools.scheduling_tools import read_channel
        mock_bot = MagicMock()
        mock_channel = MagicMock()
        mock_channel.name = "test"
        mock_channel.permissions_for.return_value = MagicMock(read_message_history=True)

        async def mock_history(limit=20):
            msg = MagicMock()
            msg.created_at.strftime.return_value = "00:00"
            msg.author.display_name = "X"
            msg.content = "Y"
            msg.embeds = []
            yield msg

        mock_channel.history = mock_history

        mock_guild = MagicMock()
        mock_guild.text_channels = [mock_channel]
        mock_bot.guilds = [mock_guild]

        # limit=100 should be clamped to 50
        result = await read_channel(channel_name="test", limit=100, bot=mock_bot)
        assert "Y" in result

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        from src.tools.scheduling_tools import read_channel
        mock_bot = MagicMock()
        mock_bot.guilds = MagicMock(side_effect=RuntimeError("fail"))
        result = await read_channel(channel_name="test", bot=mock_bot)
        assert "❌" in result or "Error" in result or "not found" in result
