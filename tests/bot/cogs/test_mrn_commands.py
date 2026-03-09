"""Tests for MRNCommands cog — 15 tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord

from src.bot.cogs.mrn_commands import MRNCommands


def _ix():
    ix = MagicMock(spec=discord.Interaction)
    user = MagicMock(spec=discord.User)
    user.id = 12345
    ix.user = user
    ix.channel = MagicMock(spec=discord.DMChannel)
    ix.response = MagicMock()
    ix.response.send_message = AsyncMock()
    ix.response.defer = AsyncMock()
    ix.followup = MagicMock()
    ix.followup.send = AsyncMock()
    return ix


from functools import partial

def _call(cog, name):
    return partial(getattr(cog, name).callback, cog)


@pytest.fixture
def cog():
    bot = MagicMock()
    bot.cerebrum = MagicMock()
    with patch("src.bot.cogs.mrn_commands.BackupManager"):
        c = MRNCommands(bot)
        c.backup_manager = MagicMock()
        return c


class TestBackup:

    @pytest.mark.asyncio
    async def test_success(self, cog):
        ix = _ix()
        cog.backup_manager.send_user_backup_dm = AsyncMock(return_value=True)
        await _call(cog, "backup_my_shard")(ix)
        assert "backup sent" in ix.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_rate_limited(self, cog):
        ix = _ix()
        cog.backup_manager.send_user_backup_dm = AsyncMock(return_value=False)
        await _call(cog, "backup_my_shard")(ix)
        msg = ix.followup.send.call_args[0][0].lower()
        assert "rate limited" in msg or "empty" in msg


class TestRestore:

    def _att(self, name="s.json", data=b'{"k":1}'):
        a = MagicMock(spec=discord.Attachment)
        a.filename = name
        a.read = AsyncMock(return_value=data)
        return a

    @pytest.mark.asyncio
    async def test_bad_ext(self, cog):
        ix = _ix()
        await _call(cog, "restore_my_shard")(ix, self._att(name="s.txt"))
        assert "invalid" in ix.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_bad_json(self, cog):
        ix = _ix()
        await _call(cog, "restore_my_shard")(ix, self._att(data=b"NOT"))
        assert "corrupted" in ix.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_crypto_reject(self, cog):
        ix = _ix()
        cog.backup_manager.verify_backup.return_value = (False, "bad")
        await _call(cog, "restore_my_shard")(ix, self._att())
        assert "rejected" in ix.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_sentinel_reject(self, cog):
        ix = _ix()
        cog.backup_manager.verify_backup.return_value = (True, "OK")
        sentinel = MagicMock()
        sentinel.review_shard = AsyncMock(return_value=(False, "bad"))
        superego = MagicMock()
        superego.get_ability.return_value = sentinel
        mock_lobes = MagicMock()
        mock_lobes.get.return_value = superego
        cog.bot.cerebrum.lobes = mock_lobes
        await _call(cog, "restore_my_shard")(ix, self._att())
        assert ix.followup.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_success(self, cog):
        ix = _ix()
        cog.backup_manager.verify_backup.return_value = (True, "OK")
        cog.backup_manager.import_user_context = AsyncMock(return_value=(True, "done"))
        mock_lobes = MagicMock()
        mock_lobes.get.return_value = None
        cog.bot.cerebrum.lobes = mock_lobes
        await _call(cog, "restore_my_shard")(ix, self._att())
        assert "restoration" in ix.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_import_fail(self, cog):
        ix = _ix()
        cog.backup_manager.verify_backup.return_value = (True, "OK")
        cog.backup_manager.import_user_context = AsyncMock(return_value=(False, "err"))
        mock_lobes = MagicMock()
        mock_lobes.get.return_value = None
        cog.bot.cerebrum.lobes = mock_lobes
        await _call(cog, "restore_my_shard")(ix, self._att())
        assert "failed" in ix.followup.send.call_args[0][0].lower()


class TestLinkMinecraft:

    def _ctx(self):
        ctx = MagicMock()
        ctx.interaction = None
        ctx.author = MagicMock(id=12345, display_name="TestUser")
        ctx.send = AsyncMock()
        return ctx

    @pytest.mark.asyncio
    async def test_spaces(self, cog):
        ctx = self._ctx()
        await cog.link_minecraft.callback(cog, ctx, "bad name")
        assert "invalid" in ctx.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_too_short(self, cog):
        ctx = self._ctx()
        await cog.link_minecraft.callback(cog, ctx, "ab")
        assert "invalid" in ctx.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_too_long(self, cog):
        ctx = self._ctx()
        await cog.link_minecraft.callback(cog, ctx, "a" * 17)
        assert "invalid" in ctx.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_success(self, cog):
        import tempfile
        from pathlib import Path
        ctx = self._ctx()
        with tempfile.TemporaryDirectory() as tmp:
            lp = Path(tmp) / "user_links.json"
            with patch("src.bot.cogs.mrn_commands.Path", return_value=lp):
                await cog.link_minecraft.callback(cog, ctx, "metta_mazza")
                assert "linked" in ctx.send.call_args[0][0].lower()


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup(self):
        from src.bot.cogs.mrn_commands import setup
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        with patch("src.bot.cogs.mrn_commands.BackupManager"):
            await setup(bot)
        assert True  # Setup/teardown completed without error
