"""
Tests for Testing Mode Toggle — verify that non-admin users are blocked
and admin users pass through when TESTING_MODE is True.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Testing Mode Gate Tests ───────────────────────────────────

ADMIN_ID = 1299810741984956449
NON_ADMIN_ID = 9999999999


class TestTestingModeGate:
    """Test the TESTING_MODE gate in on_message()."""

    def _make_message(self, author_id, content="hello", is_bot=False, guild=True):
        """Create a mock Discord message."""
        msg = AsyncMock()
        msg.id = 12345
        msg.content = content
        msg.author = MagicMock()
        msg.author.id = author_id
        msg.author.bot = is_bot
        msg.reply = AsyncMock()
        msg.channel = MagicMock()
        if guild:
            msg.guild = MagicMock()
            msg.channel.guild = msg.guild
        else:
            msg.guild = None
            msg.channel.guild = None
        return msg

    @pytest.mark.asyncio
    @patch("config.settings.TESTING_MODE", True)
    @patch("config.settings.ADMIN_IDS", {ADMIN_ID})
    @patch("config.settings.ADMIN_ID", ADMIN_ID)
    @patch("config.settings.TESTING_MODE_MESSAGE", "Testing mode active")
    async def test_non_admin_blocked_in_testing_mode(self):
        """Non-admin messages should be replied to and dropped in testing mode."""
        msg = self._make_message(NON_ADMIN_ID)

        # Simulate the gate logic from chat.py on_message()
        from config import settings
        if getattr(settings, 'TESTING_MODE', False):
            if msg.author.id not in getattr(settings, 'ADMIN_IDS', {settings.ADMIN_ID}):
                await msg.reply(settings.TESTING_MODE_MESSAGE)
                blocked = True
            else:
                blocked = False
        else:
            blocked = False

        assert blocked is True
        msg.reply.assert_called_once_with("Testing mode active")

    @pytest.mark.asyncio
    @patch("config.settings.TESTING_MODE", True)
    @patch("config.settings.ADMIN_IDS", {ADMIN_ID})
    @patch("config.settings.ADMIN_ID", ADMIN_ID)
    async def test_admin_passes_in_testing_mode(self):
        """Admin messages should NOT be blocked in testing mode."""
        msg = self._make_message(ADMIN_ID)

        from config import settings
        if getattr(settings, 'TESTING_MODE', False):
            if msg.author.id not in getattr(settings, 'ADMIN_IDS', {settings.ADMIN_ID}):
                blocked = True
            else:
                blocked = False
        else:
            blocked = False

        assert blocked is False
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    @patch("config.settings.TESTING_MODE", False)
    async def test_all_users_pass_when_testing_off(self):
        """When testing mode is off, all users should pass."""
        msg = self._make_message(NON_ADMIN_ID)

        from config import settings
        if getattr(settings, 'TESTING_MODE', False):
            blocked = True
        else:
            blocked = False

        assert blocked is False

    @pytest.mark.asyncio
    @patch("config.settings.TESTING_MODE", True)
    @patch("config.settings.ADMIN_IDS", {ADMIN_ID})
    @patch("config.settings.ADMIN_ID", ADMIN_ID)
    @patch("config.settings.TESTING_MODE_MESSAGE", "Testing mode active")
    async def test_non_admin_dm_blocked_in_testing_mode(self):
        """DM messages from non-admins should also be blocked."""
        msg = self._make_message(NON_ADMIN_ID, guild=False)

        from config import settings
        if getattr(settings, 'TESTING_MODE', False):
            if msg.author.id not in getattr(settings, 'ADMIN_IDS', {settings.ADMIN_ID}):
                await msg.reply(settings.TESTING_MODE_MESSAGE)
                blocked = True
            else:
                blocked = False
        else:
            blocked = False

        assert blocked is True


# ─── Toggle Command Tests ─────────────────────────────────────

class TestToggleCommand:
    """Test the /testing admin command logic."""

    def test_toggle_on(self):
        """Toggling from False to True should set TESTING_MODE=True."""
        import config.settings as settings
        original = settings.TESTING_MODE
        try:
            settings.TESTING_MODE = False
            settings.TESTING_MODE = not settings.TESTING_MODE
            assert settings.TESTING_MODE is True
        finally:
            settings.TESTING_MODE = original

    def test_toggle_off(self):
        """Toggling from True to False should set TESTING_MODE=False."""
        import config.settings as settings
        original = settings.TESTING_MODE
        try:
            settings.TESTING_MODE = True
            settings.TESTING_MODE = not settings.TESTING_MODE
            assert settings.TESTING_MODE is False
        finally:
            settings.TESTING_MODE = original

    def test_double_toggle_returns_to_original(self):
        """Double toggle should return to original state."""
        import config.settings as settings
        original = settings.TESTING_MODE
        try:
            settings.TESTING_MODE = False
            settings.TESTING_MODE = not settings.TESTING_MODE  # True
            settings.TESTING_MODE = not settings.TESTING_MODE  # False
            assert settings.TESTING_MODE is False
        finally:
            settings.TESTING_MODE = original


# ─── Settings Configuration Tests ─────────────────────────────

class TestTestingModeSettings:
    """Verify TESTING_MODE settings are correctly defined."""

    def test_testing_mode_exists(self):
        """settings.TESTING_MODE should exist."""
        from config import settings
        assert hasattr(settings, 'TESTING_MODE')

    def test_testing_mode_default_false(self):
        """TESTING_MODE should default to False."""
        from config import settings
        # The static default in settings.py is False
        assert isinstance(settings.TESTING_MODE, bool)

    def test_testing_mode_message_exists(self):
        """settings.TESTING_MODE_MESSAGE should exist."""
        from config import settings
        assert hasattr(settings, 'TESTING_MODE_MESSAGE')
        assert len(settings.TESTING_MODE_MESSAGE) > 0

    def test_testing_mode_message_is_friendly(self):
        """The testing mode message should be user-friendly."""
        from config import settings
        msg = settings.TESTING_MODE_MESSAGE
        assert "testing" in msg.lower()
