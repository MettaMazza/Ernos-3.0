"""Tests for PersonaCommands cog — 37 tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord

from functools import partial
from src.bot.cogs.persona_commands import PersonaCommands, TOWN_HALL_ONLY


def _ix(*, is_dm=True, channel_id=100):
    ix = MagicMock(spec=discord.Interaction)
    user = MagicMock(spec=discord.User)
    user.id = 12345
    user.display_name = "TestUser"
    user.mention = "<@12345>"
    ix.user = user
    if is_dm:
        ix.channel = MagicMock(spec=discord.DMChannel)
        ix.guild = None
        ix.guild_id = None
    else:
        ix.channel = MagicMock(spec=discord.TextChannel)
        ix.channel.threads = []
        ix.guild = MagicMock(spec=discord.Guild)
        ix.guild_id = 999
    ix.channel.id = channel_id
    ix.channel_id = channel_id
    ix.response = MagicMock()
    ix.response.send_message = AsyncMock()
    ix.response.defer = AsyncMock()
    ix.followup = MagicMock()
    ix.followup.send = AsyncMock()
    return ix


def _bot(**kw):
    bot = MagicMock()
    bot.user = MagicMock(id=123456789, name="ErnosTest")
    bot.add_cog = AsyncMock()
    bot.town_hall = None
    for k, v in kw.items():
        setattr(bot, k, v)
    return bot


@pytest.fixture
def cog():
    return PersonaCommands(_bot())


# Helper: call decorated @app_commands.command methods via .callback(self, ...)
def _call(cog, method_name):
    cmd = getattr(cog, method_name)
    return partial(cmd.callback, cog)


# ── persona_switch ──────────────────────────────────────────────

class TestPersonaSwitch:

    @pytest.mark.asyncio
    async def test_town_hall_blocked(self, cog):
        call = _call(cog, "persona_switch")
        for name in TOWN_HALL_ONLY:
            ix = _ix(is_dm=True)
            await call(ix, name)
            assert "Town Hall resident" in ix.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_switch_default_in_dm(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.get_active.return_value = "echo"
            await _call(cog, "persona_switch")(ix, "default")
            t.set_active.assert_called_once_with("12345", None)

    @pytest.mark.asyncio
    async def test_switch_default_aliases(self, cog):
        call = _call(cog, "persona_switch")
        for alias in ("default", "ernos", "reset", "none"):
            ix = _ix(is_dm=True)
            with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
                t.get_active.return_value = None
                await call(ix, alias)
                t.set_active.assert_called()

    @pytest.mark.asyncio
    async def test_switch_default_in_guild(self, cog):
        ix = _ix(is_dm=False, channel_id=987654321)
        await _call(cog, "persona_switch")(ix, "default")
        msg = ix.response.send_message.call_args[0][0].lower()
        assert "public channel" in msg or "leave the thread" in msg

    @pytest.mark.asyncio
    async def test_returns_prev_to_town_hall(self, cog):
        ix = _ix(is_dm=True)
        th = MagicMock()
        cog.bot.town_hall = th
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.get_active.return_value = "solance"
            await _call(cog, "persona_switch")(ix, "default")
            th.mark_available.assert_called_once_with("solance")

    @pytest.mark.asyncio
    async def test_guild_wrong_channel(self, cog):
        ix = _ix(is_dm=False, channel_id=111)
        with patch("config.settings") as s:
            s.TARGET_CHANNEL_ID = 999
            await _call(cog, "persona_switch")(ix, "echo")
            assert ix.response.send_message.call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_guild_correct_channel(self, cog):
        ix = _ix(is_dm=False, channel_id=987654321)
        with patch("config.settings") as s:
            s.TARGET_CHANNEL_ID = 987654321
            with patch.object(cog, "_handle_guild_persona", new_callable=AsyncMock) as h:
                await _call(cog, "persona_switch")(ix, "echo")
                h.assert_called_once()

    @pytest.mark.asyncio
    async def test_dm_delegates(self, cog):
        ix = _ix(is_dm=True)
        with patch.object(cog, "_handle_dm_persona", new_callable=AsyncMock) as h:
            await _call(cog, "persona_switch")(ix, "echo")
            h.assert_called_once()


# ── _handle_guild_persona ───────────────────────────────────────

class TestHandleGuildPersona:

    @pytest.mark.asyncio
    async def test_not_found(self, cog):
        ix = _ix(is_dm=False, channel_id=987654321)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.get.return_value = None
            r.list_all.return_value = [{"name": "echo"}]
            await cog._handle_guild_persona(ix, "unknown", "12345")
            assert "not found" in ix.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_not_found_empty_pool(self, cog):
        ix = _ix(is_dm=False, channel_id=987654321)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.get.return_value = None
            r.list_all.return_value = []
            await cog._handle_guild_persona(ix, "unknown", "12345")
            assert "persona_create" in ix.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_duplicate_thread(self, cog):
        ix = _ix(is_dm=False, channel_id=987654321)
        thread = MagicMock()
        thread.name = "💬 Echo — TestUser"
        thread.archived = False
        thread.mention = "#t"
        ix.channel.threads = [thread]
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.get.return_value = {"display_name": "echo"}
            await cog._handle_guild_persona(ix, "echo", "12345")
            assert "already have" in ix.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_thread_creation(self, cog):
        ix = _ix(is_dm=False, channel_id=987654321)
        ix.channel.threads = []
        anchor = MagicMock()
        t = MagicMock(id=555, mention="#555")
        t.send = AsyncMock()
        anchor.create_thread = AsyncMock(return_value=t)
        ix.channel.send = AsyncMock(return_value=anchor)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.get.return_value = {"display_name": "echo"}
            r.get_persona_path.return_value = None
            with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as tr:
                await cog._handle_guild_persona(ix, "echo", "12345")
                tr.set_thread_persona.assert_called_once_with("555", "echo")

    @pytest.mark.asyncio
    async def test_thread_creation_error(self, cog):
        ix = _ix(is_dm=False, channel_id=987654321)
        ix.channel.threads = []
        ix.channel.send = AsyncMock(side_effect=Exception("fail"))
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.get.return_value = {"display_name": "echo"}
            await cog._handle_guild_persona(ix, "echo", "12345")
            assert "❌" in ix.followup.send.call_args[0][0]


# ── _handle_dm_persona ──────────────────────────────────────────

class TestHandleDmPersona:

    @pytest.mark.asyncio
    async def test_limit(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.persona_exists.return_value = False
            t.can_create_persona.return_value = False
            await cog._handle_dm_persona(ix, "x", "12345", "X")
            assert "maximum" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_existing_switch(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.persona_exists.return_value = True
            t.get_active.return_value = None
            with patch("src.privacy.scopes.ScopeManager") as s:
                pf = MagicMock()
                pf.exists.return_value = True
                ph = MagicMock()
                ph.__truediv__ = MagicMock(return_value=pf)
                s.get_user_home.return_value = ph
                await cog._handle_dm_persona(ix, "echo", "12345", "Echo")
                t.set_active.assert_called_once()
                assert "switched" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_clone_from_public(self, cog):
        ix = _ix(is_dm=True)
        import tempfile, os
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            pub = os.path.join(tmp, "pub")
            os.makedirs(pub)
            with open(os.path.join(pub, "persona.txt"), "w") as f:
                f.write("# Echo\nSignal preservation.")
            with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
                t.persona_exists.return_value = False
                t.can_create_persona.return_value = True
                t.get_active.return_value = None
                with patch("src.privacy.scopes.ScopeManager") as s:
                    s.get_user_home.return_value = Path(os.path.join(tmp, "user"))
                    with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
                        r.get_persona_path.return_value = Path(pub)
                        r.get.return_value = {"display_name": "echo"}
                        await cog._handle_dm_persona(ix, "echo", "12345", "Echo")
                        assert "cloned" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_brand_new_template(self, cog):
        ix = _ix(is_dm=True)
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
                t.persona_exists.return_value = False
                t.can_create_persona.return_value = True
                t.get_active.return_value = None
                with patch("src.privacy.scopes.ScopeManager") as s:
                    s.get_user_home.return_value = Path(tmp)
                    with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
                        r.get_persona_path.return_value = None
                        await cog._handle_dm_persona(ix, "mychar", "12345", "MyChar")
                        assert "created" in ix.response.send_message.call_args[0][0].lower()


# ── persona_list ────────────────────────────────────────────────

class TestPersonaList:

    @pytest.mark.asyncio
    async def test_dm_empty(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.list_personas.return_value = []
            await _call(cog, "persona_list")(ix)
            assert "don't have" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_dm_with_active(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.list_personas.return_value = ["echo", "solance"]
            t.get_active.return_value = "echo"
            with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
                r.list_all.return_value = []
                await _call(cog, "persona_list")(ix)
                assert "active" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_guild_public(self, cog):
        ix = _ix(is_dm=False, channel_id=987654321)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.list_all.return_value = [{"name": "echo", "creator_id": "SYSTEM"}]
            await _call(cog, "persona_list")(ix)
            assert "public" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_empty_everywhere(self, cog):
        ix = _ix(is_dm=False, channel_id=987654321)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.list_all.return_value = []
            await _call(cog, "persona_list")(ix)
            assert "no personas" in ix.response.send_message.call_args[0][0].lower()


# ── persona_create ──────────────────────────────────────────────

class TestPersonaCreate:

    @pytest.mark.asyncio
    async def test_public_limit(self, cog):
        ix = _ix(is_dm=False)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.can_create.return_value = False
            await _call(cog, "persona_create")(ix, "x", "d", public=True)
            assert "maximum" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_public_exists(self, cog):
        ix = _ix(is_dm=False)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.can_create.return_value = True
            r.exists.return_value = True
            await _call(cog, "persona_create")(ix, "echo", "d", public=True)
            assert "already exists" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_public_success(self, cog):
        ix = _ix(is_dm=False)
        th = MagicMock()
        cog.bot.town_hall = th
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.can_create.return_value = True
            r.exists.return_value = False
            r.register.return_value = True
            await _call(cog, "persona_create")(ix, "new", "cool", public=True)
            th.register_persona.assert_called_once()

    @pytest.mark.asyncio
    async def test_public_failure(self, cog):
        ix = _ix(is_dm=False)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.can_create.return_value = True
            r.exists.return_value = False
            r.register.return_value = False
            await _call(cog, "persona_create")(ix, "fail", "d", public=True)
            assert "❌" in ix.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_private_not_dm(self, cog):
        ix = _ix(is_dm=False)
        await _call(cog, "persona_create")(ix, "p", "d", public=False)
        assert "dm" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_private_limit(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.can_create_persona.return_value = False
            await _call(cog, "persona_create")(ix, "p", "d", public=False)
            assert "maximum" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_private_success(self, cog):
        ix = _ix(is_dm=True)
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
                t.can_create_persona.return_value = True
                with patch("src.privacy.scopes.ScopeManager") as s:
                    s.get_user_home.return_value = Path(tmp)
                    await _call(cog, "persona_create")(ix, "new", "cool char", public=False)
                    t.set_active.assert_called_once()


# ── persona_fork ────────────────────────────────────────────────

class TestPersonaFork:

    @pytest.mark.asyncio
    async def test_not_found(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.exists.return_value = False
            await _call(cog, "persona_fork")(ix, "x")
            assert "not found" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_private_limit(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.exists.return_value = True
            with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
                t.can_create_persona.return_value = False
                await _call(cog, "persona_fork")(ix, "echo", private=True)
                assert "maximum" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_public_limit(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.exists.return_value = True
            r.can_create.return_value = False
            await _call(cog, "persona_fork")(ix, "echo", private=False)
            assert "maximum" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_fork_success(self, cog):
        ix = _ix(is_dm=True)
        th = MagicMock()
        cog.bot.town_hall = th
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.exists.return_value = True
            r.can_create.return_value = True
            r.fork.return_value = "echo-fork"
            await _call(cog, "persona_fork")(ix, "echo", private=False)
            th.register_persona.assert_called_once()

    @pytest.mark.asyncio
    async def test_fork_failure(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PublicPersonaRegistry") as r:
            r.exists.return_value = True
            r.can_create.return_value = True
            r.fork.return_value = None
            await _call(cog, "persona_fork")(ix, "echo")
            assert "❌" in ix.response.send_message.call_args[0][0]


# ── persona_remove ──────────────────────────────────────────────

class TestPersonaRemove:

    @pytest.mark.asyncio
    async def test_not_dm(self, cog):
        ix = _ix(is_dm=False)
        await _call(cog, "persona_remove")(ix, "echo")
        assert "dm" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_not_found(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.persona_exists.return_value = False
            await _call(cog, "persona_remove")(ix, "x")
            assert "not found" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_success(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.persona_exists.return_value = True
            t.archive_persona.return_value = True
            await _call(cog, "persona_remove")(ix, "echo")
            assert "archived" in ix.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_failure(self, cog):
        ix = _ix(is_dm=True)
        with patch("src.bot.cogs.persona_commands.PersonaSessionTracker") as t:
            t.persona_exists.return_value = True
            t.archive_persona.return_value = False
            await _call(cog, "persona_remove")(ix, "echo")
            assert "❌" in ix.response.send_message.call_args[0][0]


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup(self):
        from src.bot.cogs.persona_commands import setup
        bot = _bot()
        await setup(bot)
        bot.add_cog.assert_called_once()
