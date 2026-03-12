"""
Comprehensive coverage tests for src/bot/cogs/admin.py
Targets: 50% → 95%

All discord.ext.commands decorated methods must be called via
  method.callback(cog_instance, ctx, ...)
to bypass the decorator machinery.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


# ─── Helpers ─────────────────────────────────────────────────────────
def _make_bot():
    bot = MagicMock()
    bot.engine_manager = MagicMock()
    bot.tree = AsyncMock()
    bot.tree.sync = AsyncMock(return_value=["cmd1"])
    bot.guilds = []
    bot.get_channel = MagicMock(return_value=None)
    bot.fetch_channel = AsyncMock(return_value=None)
    bot.fetch_user = AsyncMock(return_value=None)
    bot.get_cog = MagicMock(return_value=None)
    bot.tape_engine = AsyncMock()
    bot.channel_manager = MagicMock()
    bot.close = AsyncMock()
    return bot


def _make_ctx(guild=None):
    ctx = AsyncMock()
    ctx.send = AsyncMock()
    ctx.defer = AsyncMock()
    ctx.guild = guild
    ctx.author = MagicMock()
    ctx.author.id = 12345
    ctx.channel = AsyncMock()
    ctx.channel.send = AsyncMock()
    return ctx


def _cog(bot=None):
    from src.bot.cogs.admin_engine import AdminEngine as AdminFunctions
    return AdminFunctions(bot or _make_bot())


def _lifecycle_cog(bot=None):
    from src.bot.cogs.admin_lifecycle import AdminLifecycle
    return AdminLifecycle(bot or _make_bot())


def _reports_cog(bot=None):
    from src.bot.cogs.admin_reports import AdminReports
    return AdminReports(bot or _make_bot())


def _pcog(bot=None):
    from src.bot.cogs.proxy_cog import ProxyCog
    return ProxyCog(bot or _make_bot())


# ─── cog_check ────────────────────────────────────────────────────
class TestCogCheck:
    @pytest.mark.asyncio
    async def test_admin_passes(self):
        cog = _cog()
        ctx = _make_ctx()
        ctx.author.id = 42
        with patch("src.bot.cogs.admin_engine.settings") as s:
            s.ADMIN_IDS = {42}
            assert await cog.cog_check(ctx) is True

    @pytest.mark.asyncio
    async def test_non_admin_fails(self):
        cog = _cog()
        ctx = _make_ctx()
        ctx.author.id = 99
        with patch("src.bot.cogs.admin_engine.settings") as s:
            s.ADMIN_IDS = {42}
            assert await cog.cog_check(ctx) is False


# ─── Engine Switching ────────────────────────────────────────────────
class TestEngineSwitching:
    @pytest.mark.asyncio
    async def test_switch_cloud_success(self):
        bot = _make_bot()
        bot.engine_manager.set_active_engine.return_value = True
        cog = _cog(bot)
        ctx = _make_ctx()
        await cog.switch_cloud.callback(cog, ctx)
        assert "Cloud" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_switch_cloud_fail(self):
        bot = _make_bot()
        bot.engine_manager.set_active_engine.return_value = False
        cog = _cog(bot)
        ctx = _make_ctx()
        await cog.switch_cloud.callback(cog, ctx)
        assert "Failed" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_switch_local_success(self):
        bot = _make_bot()
        bot.engine_manager.set_active_engine.return_value = True
        cog = _cog(bot)
        ctx = _make_ctx()
        await cog.switch_local.callback(cog, ctx)
        assert "Local" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_switch_local_fail(self):
        bot = _make_bot()
        bot.engine_manager.set_active_engine.return_value = False
        cog = _cog(bot)
        ctx = _make_ctx()
        await cog.switch_local.callback(cog, ctx)
        assert "Failed" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_switch_steer_success(self):
        bot = _make_bot()
        bot.engine_manager.set_active_engine.return_value = True
        cog = _cog(bot)
        ctx = _make_ctx()
        await cog.switch_local_steer.callback(cog, ctx)
        assert "Steering" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_switch_steer_fail(self):
        bot = _make_bot()
        bot.engine_manager.set_active_engine.return_value = False
        cog = _cog(bot)
        ctx = _make_ctx()
        await cog.switch_local_steer.callback(cog, ctx)
        assert "Failed" in ctx.send.call_args[0][0]


# ─── sync_commands ───────────────────────────────────────────────────
class TestSyncCommands:
    @pytest.mark.asyncio
    async def test_sync_commands(self):
        bot = _make_bot()
        bot.tree.sync = AsyncMock(return_value=["a", "b"])
        cog = _cog(bot)
        ctx = _make_ctx()
        await cog.sync_commands.callback(cog, ctx)
        assert "2 commands" in ctx.send.call_args[0][0]


# ─── sync_guild_commands (lines 49-68) ───────────────────────────────
class TestSyncGuildCommands:
    @pytest.mark.asyncio
    async def test_from_guild(self):
        bot = _make_bot()
        guild = MagicMock()
        guild.name = "G"
        bot.tree.sync = AsyncMock(return_value=["c"])
        cog = _cog(bot)
        ctx = _make_ctx(guild=guild)
        await cog.sync_guild_commands.callback(cog, ctx)
        assert "G" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_dm_via_guild_id(self):
        """line 55-57"""
        bot = _make_bot()
        g = MagicMock()
        g.name = "RG"
        bot.get_guild = MagicMock(return_value=g)
        bot.tree.sync = AsyncMock(return_value=[])
        cog = _cog(bot)
        ctx = _make_ctx(guild=None)
        with patch("src.bot.cogs.admin_engine.settings") as s:
            s.GUILD_ID = 1
            s.TARGET_CHANNEL_ID = 2
            await cog.sync_guild_commands.callback(cog, ctx)
        assert "RG" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_dm_via_target_channel(self):
        """lines 59-62"""
        bot = _make_bot()
        g = MagicMock()
        g.name = "TG"
        ch = MagicMock()
        ch.guild = g
        bot.get_guild = MagicMock(return_value=None)
        bot.get_channel = MagicMock(return_value=ch)
        bot.tree.sync = AsyncMock(return_value=[])
        cog = _cog(bot)
        ctx = _make_ctx(guild=None)
        with patch("src.bot.cogs.admin_engine.settings") as s:
            s.GUILD_ID = None
            s.TARGET_CHANNEL_ID = 2
            await cog.sync_guild_commands.callback(cog, ctx)
        assert "TG" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_dm_no_guild(self):
        """lines 63-65"""
        bot = _make_bot()
        bot.get_guild = MagicMock(return_value=None)
        bot.get_channel = MagicMock(return_value=None)
        cog = _cog(bot)
        ctx = _make_ctx(guild=None)
        with patch("src.bot.cogs.admin_engine.settings") as s:
            s.GUILD_ID = None
            s.TARGET_CHANNEL_ID = 2
            await cog.sync_guild_commands.callback(cog, ctx)
        assert "Could not determine guild" in ctx.send.call_args[0][0]


# ─── cycle_reset (lines 70-209) ─────────────────────────────────────
class TestCycleReset:
    def _patch_cycle(self, bot, backup_mgr_factory=None):
        """Return context-manager patches for cycle_reset internals."""
        import contextlib
        mock_mgr = MagicMock()
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.name = "backup.zip"
        mock_mgr.export_master_backup = AsyncMock(return_value=mock_path)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=3)
        if backup_mgr_factory:
            mock_mgr = backup_mgr_factory()
        
        admin_user = AsyncMock()
        admin_user.send = AsyncMock()
        bot.fetch_user = AsyncMock(return_value=admin_user)
        
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 5}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        
        return contextlib.ExitStack(), mock_mgr, mock_driver

    @pytest.mark.asyncio
    async def test_full_happy_path(self):
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.name = "bk.zip"
        mock_mgr.export_master_backup = AsyncMock(return_value=mock_path)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=2)
        
        admin_user = AsyncMock()
        admin_user.send = AsyncMock()
        bot.fetch_user = AsyncMock(return_value=admin_user)
        
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        
        neo4j_mod = MagicMock()
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        
        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr
        
        with patch.dict("sys.modules", {
                 "src.backup.manager": backup_mod,
                 "neo4j": neo4j_mod
             }), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)
        
        bot.close.assert_called_once()
        assert ctx.send.call_count >= 4

    def test_master_backup_no_admin_user(self):
        """Covers line 102-103: admin user not found."""
        async def _run():
            bot = _make_bot()
            cog = _lifecycle_cog(bot)
            ctx = _make_ctx()
            
            mock_mgr = MagicMock()
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.name = "bk.zip"
            mock_mgr.export_master_backup = AsyncMock(return_value=mock_path)
            mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
            bot.fetch_user = AsyncMock(return_value=None)

            neo4j_mod = MagicMock()
            mock_driver = MagicMock()
            mock_sess = MagicMock()
            mock_sess.run.return_value.single.return_value = {"c": 0}
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            neo4j_mod.GraphDatabase.driver.return_value = mock_driver

            backup_mod = MagicMock()
            backup_mod.BackupManager.return_value = mock_mgr
            
            with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
                 patch("os.path.exists", return_value=False), \
                 patch("os.makedirs"), \
                 patch("src.bot.cogs.admin_lifecycle.settings") as s:
                s.ADMIN_ID = 42
                s.NEO4J_URI = "bolt://x"
                s.NEO4J_USER = "u"
                s.NEO4J_PASSWORD = "p"
                await cog.cycle_reset.callback(cog, ctx)
            
            # Should still complete
            bot.close.assert_called_once()

        asyncio.run(_run())

    @pytest.mark.asyncio
    async def test_master_backup_path_none(self):
        """Covers lines 104-105: master backup returns None."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        
        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr
        
        with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)
        
        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_backup_phase_exception(self):
        """Covers lines 116-118: export_all_users_on_reset fails."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(side_effect=RuntimeError("fail"))
        
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        
        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr
        
        with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)
        
        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_neo4j_wipe_exception(self):
        """Covers lines 202-204: Neo4j wipe fails."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        
        neo4j_mod = MagicMock()
        neo4j_mod.GraphDatabase.driver.side_effect = RuntimeError("neo4j down")
        
        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr
        
        with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)
        
        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_persona_preservation(self):
        """Covers lines 127-134, 181-184: persona backup & restore."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr

        # os.path.exists should return True for personas_src
        def exists_side(p):
            if "personas" in str(p):
                return True
            return False

        with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
             patch("os.path.exists", side_effect=exists_side), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=["echo", "threshold"]), \
             patch("shutil.copytree"), \
             patch("shutil.rmtree"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_deletion(self):
        """Covers lines 147-172: directory and file deletion."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr

        with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
             patch("os.path.exists", return_value=True), \
             patch("os.makedirs"), \
             patch("os.remove"), \
             patch("os.listdir", return_value=[]), \
             patch("shutil.rmtree"), \
             patch("shutil.copytree"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)

        bot.close.assert_called_once()


# ─── purge_all (lines 211-241) ───────────────────────────────────────
class TestPurgeAll:
    @pytest.mark.asyncio
    async def test_success(self):
        bot = _make_bot()
        ch = AsyncMock()
        ch.purge = AsyncMock(side_effect=[["m1", "m2"], []])
        bot.get_channel = MagicMock(return_value=ch)
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        with patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TARGET_CHANNEL_ID = 1
            await cog.purge_all.callback(cog, ctx)
        assert "PURGE COMPLETE" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_channel_not_found(self):
        bot = _make_bot()
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(side_effect=Exception("nope"))
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        with patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TARGET_CHANNEL_ID = 999
            await cog.purge_all.callback(cog, ctx)
        assert "Could not find" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_purge_exception(self):
        bot = _make_bot()
        ch = AsyncMock()
        ch.purge = AsyncMock(side_effect=Exception("rate"))
        bot.get_channel = MagicMock(return_value=ch)
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        with patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TARGET_CHANNEL_ID = 1
            await cog.purge_all.callback(cog, ctx)
        assert "Purge failed" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_channel_via_fetch(self):
        """Covers lines 220-221: cache miss -> API fetch success."""
        bot = _make_bot()
        ch = AsyncMock()
        ch.purge = AsyncMock(return_value=[])
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(return_value=ch)
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        with patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TARGET_CHANNEL_ID = 1
            await cog.purge_all.callback(cog, ctx)
        assert "PURGE COMPLETE" in ctx.send.call_args[0][0]


# ─── proxy_send (lines 243-434) ─────────────────────────────────────
def _proxy_bot(ch=None, user=None, response="Hello"):
    """Create a preconfigured bot for proxy_send tests."""
    bot = _make_bot()
    if ch:
        bot.get_channel = MagicMock(return_value=ch)
    
    cog_engine = AsyncMock()
    bot.tape_engine = cog_engine
    
    cognition_engine = MagicMock()
    cognition_engine.process = AsyncMock(return_value=(response, [], []))
    bot.cognition = cognition_engine
    chat_cog = MagicMock()
    chat_cog.prompt_manager = MagicMock()
    chat_cog.prompt_manager.get_system_prompt = MagicMock(return_value="SP")
    bot.get_cog = MagicMock(return_value=chat_cog)
    bot.engine_manager.get_active_engine.return_value = MagicMock()
    
    adapter = MagicMock()
    adapter.format_mentions = AsyncMock(return_value=response)
    bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
    return bot


class TestProxySend:
    @pytest.mark.asyncio
    async def test_channel_mention(self):
        """lines 266-276"""
        ch = MagicMock()
        ch.name = "general"
        ch.send = AsyncMock()
        bot = _proxy_bot(ch=ch)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<#12345>", message="say hi")
        ch.send.assert_called()

    @pytest.mark.asyncio
    async def test_channel_mention_cache_miss(self):
        """lines 270-274"""
        ch = MagicMock()
        ch.name = "fetched"
        ch.send = AsyncMock()
        bot = _proxy_bot()
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(return_value=ch)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<#99>", message="hi")
        ch.send.assert_called()

    @pytest.mark.asyncio
    async def test_user_mention(self):
        """lines 280-288"""
        dm = MagicMock()
        dm.send = AsyncMock()
        user = MagicMock()
        user.display_name = "Alice"
        user.create_dm = AsyncMock(return_value=dm)
        bot = _proxy_bot()
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(return_value=user)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<@111222333444555666>", message="hey")
        dm.send.assert_called()

    @pytest.mark.asyncio
    async def test_raw_id_channel(self):
        """lines 291-296"""
        ch = MagicMock()
        ch.name = "raw"
        ch.send = AsyncMock()
        bot = _proxy_bot(ch=ch)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "12345", message="test")
        ch.send.assert_called()

    @pytest.mark.asyncio
    async def test_raw_id_user(self):
        """lines 297-308"""
        dm = MagicMock()
        dm.send = AsyncMock()
        user = MagicMock()
        user.display_name = "Bob"
        user.create_dm = AsyncMock(return_value=dm)
        bot = _proxy_bot()
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(side_effect=Exception("nope"))
        bot.fetch_user = AsyncMock(return_value=user)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "999888777666555444", message="hey")
        dm.send.assert_called()

    @pytest.mark.asyncio
    async def test_plain_channel(self):
        """lines 311-320"""
        ch = MagicMock()
        ch.name = "general-chat"
        ch.send = AsyncMock()
        guild = MagicMock()
        guild.text_channels = [ch]
        guild.name = "G"
        bot = _proxy_bot()
        bot.guilds = [guild]
        bot.get_channel = MagicMock(return_value=None)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "general-chat", message="hi")
        ch.send.assert_called()

    @pytest.mark.asyncio
    async def test_plain_username(self):
        """lines 323-333"""
        dm = MagicMock()
        dm.send = AsyncMock()
        member = MagicMock()
        member.name = "alice"
        member.display_name = "Alice"
        member.create_dm = AsyncMock(return_value=dm)
        guild = MagicMock()
        guild.text_channels = []
        guild.members = [member]
        bot = _proxy_bot()
        bot.guilds = [guild]
        bot.get_channel = MagicMock(return_value=None)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "alice", message="hey")
        dm.send.assert_called()

    @pytest.mark.asyncio
    async def test_unresolved(self):
        """lines 335-340"""
        bot = _proxy_bot()
        bot.guilds = []
        bot.get_channel = MagicMock(return_value=None)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "nope", message="x")
        assert "Could not resolve" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_engine(self):
        """lines 354-356"""
        ch = MagicMock()
        ch.name = "ch"
        ch.send = AsyncMock()
        bot = _proxy_bot(ch=ch)
        bot.engine_manager.get_active_engine.return_value = None
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<#1>", message="x")
        assert "No active engine" in ctx.channel.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_chat_cog(self):
        """lines 360-362"""
        ch = MagicMock()
        ch.name = "ch"
        ch.send = AsyncMock()
        bot = _proxy_bot(ch=ch)
        bot.get_cog = MagicMock(return_value=None)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<#1>", message="x")
        assert "Chat system not loaded" in ctx.channel.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_empty_response(self):
        """lines 411-413"""
        ch = MagicMock()
        ch.name = "ch"
        ch.send = AsyncMock()
        bot = _proxy_bot(ch=ch, response="")
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<#1>", message="x")
        assert "empty response" in ctx.channel.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_long_message(self):
        """lines 422-425"""
        ch = MagicMock()
        ch.name = "ch"
        ch.send = AsyncMock()
        long = "A" * 3000
        bot = _proxy_bot(ch=ch, response=long)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<#1>", message="x")
        assert ch.send.call_count >= 2

    @pytest.mark.asyncio
    async def test_cognition_exception(self):
        """lines 432-434"""
        ch = MagicMock()
        ch.name = "ch"
        ch.send = AsyncMock()
        bot = _proxy_bot(ch=ch)
        bot.cognition.process = AsyncMock(side_effect=RuntimeError("boom"))
        bot.cognition.process = AsyncMock(side_effect=RuntimeError("boom"))
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<#1>", message="x")
        assert "Failed" in ctx.channel.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cognition_fallback(self):
        """lines 392-394: No cognition attribute, creates one."""
        ch = MagicMock()
        ch.name = "ch"
        ch.send = AsyncMock()
        bot = _proxy_bot(ch=ch)
        bot.tape_engine = None
        
        mock_cog = AsyncMock()
        
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(return_value="reply")
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        
        with patch.dict("sys.modules", {
            "src.engines.cognition": MagicMock(CognitionEngine=MagicMock(return_value=mock_cog))
        }):
            cog = _pcog(bot)
            ctx = _make_ctx()
            with patch("config.settings") as s:
                s.ADMIN_ID = 12345
                await cog.proxy_send.callback(cog, ctx, "<#1>", message="x")
        ch.send.assert_called()

    @pytest.mark.asyncio
    async def test_adapter_format_mentions_exception(self):
        """Covers lines 419-420: format_mentions exception."""
        ch = MagicMock()
        ch.name = "ch"
        ch.send = AsyncMock()
        bot = _proxy_bot(ch=ch)
        adapter = MagicMock()
        adapter.format_mentions = AsyncMock(side_effect=Exception("adapter fail"))
        bot.channel_manager.get_adapter = MagicMock(return_value=adapter)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<#1>", message="x")
        # Falls back to unformatted response
        ch.send.assert_called()


# ─── townhall_suggest (lines 436-461) ────────────────────────────────
class TestTownhallSuggest:
    @pytest.mark.asyncio
    async def test_success(self):
        bot = _make_bot()
        th = MagicMock()
        th.add_suggestion.return_value = 3
        th._suggested_topics = ["a", "b", "c"]
        bot.town_hall = th
        cog = _reports_cog(bot)
        ctx = _make_ctx()
        # Use a plain MagicMock for send to avoid pending coroutines
        # that cause kqueue Bad file descriptor on async teardown
        ctx.send = AsyncMock()
        await cog.townhall_suggest.callback(cog, ctx, "A", "B", "C")
        ctx.send.assert_called_once()
        assert "3 topic(s)" in ctx.send.call_args[0][0]
        # Force GC to clean up kqueue fds before next test
        import gc; gc.collect()

    @pytest.mark.asyncio
    async def test_no_valid(self):
        bot = _make_bot()
        th = MagicMock()
        th.add_suggestion.return_value = 0
        bot.town_hall = th
        cog = _reports_cog(bot)
        ctx = _make_ctx()
        await cog.townhall_suggest.callback(cog, ctx, "a", "", "b")
        assert "No valid topics" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_town_hall(self):
        bot = _make_bot()
        bot.town_hall = None
        cog = _reports_cog(bot)
        ctx = _make_ctx()
        await cog.townhall_suggest.callback(cog, ctx, "X", "Y", "Z")
        assert "not active" in ctx.send.call_args[0][0]


# ─── setup ───────────────────────────────────────────────────────────
class TestSetup:
    @pytest.mark.asyncio
    async def test_setup(self):
        from src.bot.cogs.admin import setup
        bot = _make_bot()
        bot.load_extension = AsyncMock()
        await setup(bot)
        assert bot.load_extension.call_count == 5


# ─── Additional edge-case tests for remaining admin lines ────────────

class TestCycleResetEdgeCases:
    @pytest.mark.asyncio
    async def test_master_backup_exception(self):
        """Covers lines 106-108: export_master_backup raises."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(side_effect=RuntimeError("disk full"))
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        
        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr
        
        with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)
        
        # Should still complete despite exception
        bot.close.assert_called_once()
        # Should have sent error message about master backup
        calls = [str(c) for c in ctx.send.call_args_list]
        assert any("Master backup failed" in c for c in calls)

    @pytest.mark.asyncio
    async def test_dir_delete_exception(self):
        """Covers lines 152-153: shutil.rmtree fails on target dirs."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        
        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr
        
        # Only raise for target dirs (memory/users, etc.), not persona backup cleanup
        def rmtree_side(path, *args, **kwargs):
            p = str(path)
            # Only raise for the Phase 1 target directories
            if any(d in p for d in ["memory/users", "memory/core", "memory/public",
                                     "memory/system", "memory/traces", "memory/chroma",
                                     "logs/autonomous", "logs/errors"]):
                raise PermissionError("denied")
        
        with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
             patch("os.path.exists", return_value=True), \
             patch("os.makedirs"), \
             patch("os.remove"), \
             patch("os.listdir", return_value=[]), \
             patch("shutil.rmtree", side_effect=rmtree_side), \
             patch("shutil.copytree"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)
        
        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_delete_exception(self):
        """Covers lines 171-172: os.remove fails."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        
        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr
        
        # Only raise for the target files cyclereset tries to delete,
        # not for the salt backup cleanup (os.remove on temp file)
        target_files = [
            "memory/goals.json", "memory/project_manifest.json",
            "memory/usage.json", "memory/security_profiles.json",
            "memory/lessons.json", "memory/relationships.json",
            "memory/preferences.json", "memory/quarantine.json",
            "logs/stream_of_consciousness.log",
        ]
        def remove_side(path, *a, **kw):
            if any(path.endswith(f) or f in str(path) for f in target_files):
                raise OSError("locked")
        
        with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
             patch("os.path.exists", return_value=True), \
             patch("os.makedirs"), \
             patch("os.remove", side_effect=remove_side), \
             patch("os.listdir", return_value=[]), \
             patch("shutil.rmtree"), \
             patch("shutil.copytree"), \
             patch("shutil.copy2"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)
        
        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_neo4j_with_nodes(self):
        """Covers lines 197-204: Neo4j has user nodes to delete (CORE preserved)."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()
        
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        # Two session.run() calls: total count (10) then CORE count (3)
        total_result = MagicMock()
        total_result.single.return_value = {"c": 10}
        core_result = MagicMock()
        core_result.single.return_value = {"c": 3}
        mock_sess.run.side_effect = [total_result, core_result, MagicMock()]  # 3rd = DETACH DELETE
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        
        backup_mod = MagicMock()
        backup_mod.BackupManager.return_value = mock_mgr
        
        with patch.dict("sys.modules", {"src.backup.manager": backup_mod, "neo4j": neo4j_mod}), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)
        
        bot.close.assert_called_once()
        # Should have cleared 7 user nodes, preserved 3 CORE nodes
        calls = [str(c) for c in ctx.send.call_args_list]
        assert any("7 user nodes" in c for c in calls)
        assert any("3 CORE" in c for c in calls)


class TestProxySendEdgeCases:
    @pytest.mark.asyncio
    async def test_ephemeral_fallback_unresolved(self):
        """Covers lines 338-339: ephemeral send fails, fallback to channel."""
        bot = _proxy_bot()
        bot.guilds = []
        bot.get_channel = MagicMock(return_value=None)
        cog = _pcog(bot)
        ctx = _make_ctx()
        ctx.send = AsyncMock(side_effect=Exception("ephemeral fail"))
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "nope", message="x")
        ctx.channel.send.assert_called()
        assert "Could not resolve" in ctx.channel.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_ephemeral_fallback_working(self):
        """Covers lines 345-346: acknowledge ephemeral fails, fallback."""
        ch = MagicMock()
        ch.name = "ch"
        ch.send = AsyncMock()
        bot = _proxy_bot(ch=ch)
        cog = _pcog(bot)
        ctx = _make_ctx()
        # First ctx.send (ephemeral ack) fails, others work
        ctx.send = AsyncMock(side_effect=[Exception("eph fail"), None, None])
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "<#1>", message="hi")
        # Channel fallback should be called for the ack
        ctx.channel.send.assert_called()

    @pytest.mark.asyncio
    async def test_raw_id_fetch_channel_success(self):
        """Covers line 299-300: raw ID -> fetch_channel succeeds."""
        ch = MagicMock()
        ch.name = "fetched"
        ch.send = AsyncMock()
        bot = _proxy_bot()
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(return_value=ch)
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "999888", message="hi")
        ch.send.assert_called()

    @pytest.mark.asyncio
    async def test_raw_id_both_fail(self):
        """Covers lines 307-308: raw ID -> channel fails, user fails too."""
        bot = _proxy_bot()
        bot.guilds = []
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(side_effect=Exception("no channel"))
        bot.fetch_user = AsyncMock(side_effect=Exception("no user"))
        cog = _pcog(bot)
        ctx = _make_ctx()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            await cog.proxy_send.callback(cog, ctx, "999888777", message="x")
        assert "Could not resolve" in ctx.send.call_args[0][0]

