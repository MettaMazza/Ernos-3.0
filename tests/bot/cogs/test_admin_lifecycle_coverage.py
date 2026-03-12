"""
Coverage tests for admin_lifecycle.py — nuke, cycle_and_rotate, and edge cases.
Complements existing tests in test_admin_coverage.py which cover cycle_reset and purge_all.
Missing lines: 21, 94-96, 170-171, 178-179, 224-229, 247-263, 312-534, 538
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_bot():
    bot = MagicMock()
    bot.engine_manager = MagicMock()
    bot.tree = AsyncMock()
    bot.guilds = []
    bot.get_channel = MagicMock(return_value=None)
    bot.fetch_channel = AsyncMock(return_value=None)
    bot.fetch_user = AsyncMock(return_value=None)
    bot.get_cog = MagicMock(return_value=None)
    bot.tape_engine = AsyncMock()
    bot.close = AsyncMock()
    bot.hippocampus = MagicMock()
    bot.hippocampus._shutting_down = False
    bot.hippocampus.stream = None
    bot.hippocampus.vector_store = None
    bot.hippocampus.kg_consolidator = None
    return bot


def _make_ctx():
    ctx = AsyncMock()
    ctx.send = AsyncMock()
    ctx.defer = AsyncMock()
    ctx.author = MagicMock()
    ctx.author.id = 42
    ctx.channel = AsyncMock()
    return ctx


def _lifecycle_cog(bot=None):
    from src.bot.cogs.admin_lifecycle import AdminLifecycle
    return AdminLifecycle(bot or _make_bot())


def _neo4j_mocks(total=10, core=2):
    neo4j_mod = MagicMock()
    mock_driver = MagicMock()
    mock_sess = MagicMock()
    results = [{"c": total}, {"c": core}]
    call_count = [0]
    def run_side(query):
        result = MagicMock()
        idx = min(call_count[0], len(results) - 1)
        result.single.return_value = results[idx]
        call_count[0] += 1
        return result
    mock_sess.run = MagicMock(side_effect=run_side)
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    neo4j_mod.GraphDatabase.driver.return_value = mock_driver
    return neo4j_mod


# ─── cog_check edge case ────────────────────────────────────────────

class TestCogCheckLifecycle:
    @pytest.mark.asyncio
    async def test_non_admin_fails(self):
        cog = _lifecycle_cog()
        ctx = _make_ctx()
        ctx.author.id = 999
        with patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_IDS = {42}
            assert await cog.cog_check(ctx) is False


# ─── nuke ────────────────────────────────────────────────────────────

class TestNuke:
    @pytest.mark.asyncio
    async def test_no_confirmation(self):
        cog = _lifecycle_cog()
        ctx = _make_ctx()
        await cog.nuke.callback(cog, ctx, confirmation=None)
        assert "CONFIRMNUKE" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_wrong_confirmation(self):
        cog = _lifecycle_cog()
        ctx = _make_ctx()
        await cog.nuke.callback(cog, ctx, confirmation="wrong")
        assert "CONFIRMNUKE" in ctx.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_full_nuke_happy_path(self):
        bot = _make_bot()
        # Setup hippocampus with stream, vector, kg
        stream = MagicMock()
        stream.turns = []
        state_cls = type(MagicMock())
        stream.state = MagicMock()
        bot.hippocampus.stream = stream
        bot.hippocampus.vector_store = MagicMock()
        bot.hippocampus.vector_store._data = MagicMock()
        bot.hippocampus.vector_store.reset = MagicMock()
        bot.hippocampus.kg_consolidator = MagicMock()
        bot.hippocampus.kg_consolidator._buffer = MagicMock()

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 50}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=[]), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()
        assert ctx.send.call_count >= 5

    @pytest.mark.asyncio
    async def test_nuke_inmemory_flush_fails(self):
        bot = _make_bot()
        bot.hippocampus = MagicMock()
        bot.hippocampus._shutting_down = False
        type(bot.hippocampus).stream = property(lambda _: (_ for _ in ()).throw(RuntimeError("bad")))

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=[]), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nuke_salt_rotation_fails(self):
        bot = _make_bot()
        rotate_mod = MagicMock()
        rotate_mod.rotate_salt.side_effect = RuntimeError("salt err")
        prov_mod = MagicMock()

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=[]), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nuke_with_filesystem_content(self):
        """Covers file/dir deletion and persona/voice model preservation."""
        bot = _make_bot()
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        def exists_side(p):
            return "personas" in str(p) or "voice_models" in str(p)

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", side_effect=exists_side), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=[]), \
             patch("shutil.copytree"), \
             patch("shutil.rmtree"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nuke_neo4j_fail(self):
        bot = _make_bot()
        neo4j_mod = MagicMock()
        neo4j_mod.GraphDatabase.driver.side_effect = RuntimeError("neo4j down")
        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=[]), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nuke_remaining_memory_items(self):
        """Covers os.listdir("memory") cleanup of remaining items."""
        bot = _make_bot()
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        def exists_side(p):
            return p == "memory"

        def isdir_side(p):
            return "leftover_dir" in str(p)

        def isfile_side(p):
            return "leftover.txt" in str(p)

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", side_effect=exists_side), \
             patch("os.path.isdir", side_effect=isdir_side), \
             patch("os.path.isfile", side_effect=isfile_side), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=["leftover_dir", "leftover.txt"]), \
             patch("os.remove"), \
             patch("shutil.rmtree"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()


# ─── cycle_and_rotate ────────────────────────────────────────────────

class TestCycleAndRotate:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        # Mock cycle_reset to avoid going through the command decorator
        cog.cycle_reset = AsyncMock()

        with patch.dict("sys.modules", {
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }):
            await cog.cycle_and_rotate.callback(cog, ctx)

        rotate_mod.rotate_salt.assert_called_once_with(confirm=True)
        cog.cycle_reset.assert_called_once_with(ctx)

    @pytest.mark.asyncio
    async def test_salt_rotation_fails(self):
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        rotate_mod = MagicMock()
        rotate_mod.rotate_salt.side_effect = RuntimeError("salt fail")
        prov_mod = MagicMock()

        # Mock cycle_reset to avoid going through the command decorator
        cog.cycle_reset = AsyncMock()

        with patch.dict("sys.modules", {
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }):
            await cog.cycle_and_rotate.callback(cog, ctx)

        # Should still proceed and call cycle_reset
        cog.cycle_reset.assert_called_once_with(ctx)


# ─── cycle_reset edge cases (not in test_admin_coverage.py) ──────────

class TestCycleResetEdgeCasesNew:
    @pytest.mark.asyncio
    async def test_inmemory_flush_fails(self):
        """Covers lines 94-96: in-memory flush exception."""
        bot = _make_bot()
        # Make hippocampus._shutting_down assignment work but stream access throws
        hippo = MagicMock()
        hippo._shutting_down = False
        type(hippo).stream = property(lambda _: (_ for _ in ()).throw(RuntimeError("oops")))
        bot.hippocampus = hippo

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        backup_mod = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        backup_mod.BackupManager.return_value = mock_mgr

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        with patch.dict("sys.modules", {
                "src.backup.manager": backup_mod,
                "neo4j": neo4j_mod,
             }), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_persona_restore_fail(self):
        """Covers lines 170-171: persona restore raises."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        backup_mod = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        backup_mod.BackupManager.return_value = mock_mgr

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        call_num = [0]
        def exists_side(p):
            if "personas" in str(p):
                return True
            if "voice_models" in str(p):
                return True
            return False

        def copytree_side(*a, **kw):
            call_num[0] += 1
            if call_num[0] == 3:  # The restore call
                raise OSError("restore fail")

        with patch.dict("sys.modules", {
                "src.backup.manager": backup_mod,
                "neo4j": neo4j_mod,
             }), \
             patch("os.path.exists", side_effect=exists_side), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=["p1"]), \
             patch("shutil.copytree", side_effect=copytree_side), \
             patch("shutil.rmtree"), \
             patch("shutil.copy2"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_monetization_sync(self):
        """Covers lines 224-229: monetization cog sync."""
        bot = _make_bot()
        mon_cog = AsyncMock()
        mon_cog.sync_tiers = AsyncMock()
        bot.get_cog = MagicMock(return_value=mon_cog)
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        backup_mod = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        backup_mod.BackupManager.return_value = mock_mgr

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        with patch.dict("sys.modules", {
                "src.backup.manager": backup_mod,
                "neo4j": neo4j_mod,
             }), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)

        mon_cog.sync_tiers.assert_called_once()
        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_voice_models_restore_fail(self):
        """Covers lines 178-179: voice_models copytree restore raises."""
        bot = _make_bot()
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        backup_mod = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        backup_mod.BackupManager.return_value = mock_mgr

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        def exists_side(p):
            return "personas" in str(p) or "voice_models" in str(p)

        call_num = [0]
        def copytree_side(*a, **kw):
            call_num[0] += 1
            # copytree calls: 1=backup personas, 2=backup voice_models,
            # 3=restore personas, 4=restore voice_models
            if call_num[0] == 4:
                raise OSError("voice restore fail")

        with patch.dict("sys.modules", {
                "src.backup.manager": backup_mod,
                "neo4j": neo4j_mod,
             }), \
             patch("os.path.exists", side_effect=exists_side), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=["p1"]), \
             patch("shutil.copytree", side_effect=copytree_side), \
             patch("shutil.rmtree"), \
             patch("shutil.copy2"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_monetization_sync_fail(self):
        """Covers lines 227-229: monetization sync_tiers raises."""
        bot = _make_bot()
        mon_cog = AsyncMock()
        mon_cog.sync_tiers = AsyncMock(side_effect=RuntimeError("sync fail"))
        bot.get_cog = MagicMock(return_value=mon_cog)
        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        backup_mod = MagicMock()
        mock_mgr = MagicMock()
        mock_mgr.export_master_backup = AsyncMock(return_value=None)
        mock_mgr.export_all_users_on_reset = AsyncMock(return_value=0)
        backup_mod.BackupManager.return_value = mock_mgr

        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver

        with patch.dict("sys.modules", {
                "src.backup.manager": backup_mod,
                "neo4j": neo4j_mod,
             }), \
             patch("os.path.exists", return_value=False), \
             patch("os.makedirs"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.ADMIN_ID = 42
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.cycle_reset.callback(cog, ctx)

        all_send = " ".join(str(c) for c in ctx.send.call_args_list)
        assert "Monetization sync failed" in all_send
        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nuke_dir_deletion_success_and_fail(self):
        """Covers lines 411-416: nuke_dirs exist, try/except on rmtree."""
        bot = _make_bot()
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        # Make all paths exist
        def exists_side(p):
            return True

        rmtree_calls = [0]
        def rmtree_side(p, *a, **kw):
            # Only count and fail on nuke_dirs (memory/users, memory/cache, etc.)
            if "memory/" in str(p) and "_backup" not in str(p):
                rmtree_calls[0] += 1
                if rmtree_calls[0] == 2:
                    raise OSError("perm denied")

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", side_effect=exists_side), \
             patch("os.path.isdir", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=[]), \
             patch("shutil.copytree"), \
             patch("shutil.rmtree", side_effect=rmtree_side), \
             patch("os.remove"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nuke_file_deletion_success_and_fail(self):
        """Covers lines 436-441: nuke_files exist, try/except on os.remove."""
        bot = _make_bot()
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        remove_calls = [0]
        def remove_side(p, *a, **kw):
            remove_calls[0] += 1
            if remove_calls[0] == 1:
                raise OSError("locked")

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=[]), \
             patch("shutil.copytree"), \
             patch("shutil.rmtree"), \
             patch("os.remove", side_effect=remove_side), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nuke_remaining_cleanup_fail(self):
        """Covers lines 455-456: remaining memory item cleanup exception."""
        bot = _make_bot()
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        def exists_side(p):
            return str(p) in ("memory",)

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", side_effect=exists_side), \
             patch("os.path.isdir", return_value=True), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=["bad_dir"]), \
             patch("shutil.rmtree", side_effect=OSError("fail")), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nuke_persona_restore_fail(self):
        """Covers lines 477-479: persona restore after nuke fails."""
        bot = _make_bot()
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        copytree_calls = [0]
        def copytree_side(*a, **kw):
            copytree_calls[0] += 1
            if copytree_calls[0] == 1:
                pass  # backup copy succeeds
            elif copytree_calls[0] == 3:
                raise OSError("restore fail")

        def exists_side(p):
            return "personas" in str(p) or "voice_models" in str(p) or str(p).endswith("_backup")

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", side_effect=exists_side), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=[]), \
             patch("shutil.copytree", side_effect=copytree_side), \
             patch("shutil.rmtree"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_nuke_voice_restore_fail(self):
        """Covers lines 487-489: voice_models restore fails."""
        bot = _make_bot()
        neo4j_mod = MagicMock()
        mock_driver = MagicMock()
        mock_sess = MagicMock()
        mock_sess.run.return_value.single.return_value = {"c": 0}
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        neo4j_mod.GraphDatabase.driver.return_value = mock_driver
        rotate_mod = MagicMock()
        prov_mod = MagicMock()

        cog = _lifecycle_cog(bot)
        ctx = _make_ctx()

        copytree_calls = [0]
        def copytree_side(*a, **kw):
            copytree_calls[0] += 1
            # Let persona backup+restore succeed, fail on voice_models restore
            if copytree_calls[0] == 4:
                raise OSError("voice restore fail")

        def exists_side(p):
            return True

        with patch.dict("sys.modules", {
                "neo4j": neo4j_mod,
                "src.security.rotate_salt": rotate_mod,
                "src.security.provenance": prov_mod,
             }), \
             patch("os.path.exists", side_effect=exists_side), \
             patch("os.path.isdir", return_value=False), \
             patch("os.path.isfile", return_value=False), \
             patch("os.makedirs"), \
             patch("os.listdir", return_value=[]), \
             patch("shutil.copytree", side_effect=copytree_side), \
             patch("shutil.rmtree"), \
             patch("os.remove"), \
             patch("src.bot.cogs.admin_lifecycle.settings") as s:
            s.TESTING_MODE = False
            s.NEO4J_URI = "bolt://x"
            s.NEO4J_USER = "u"
            s.NEO4J_PASSWORD = "p"
            await cog.nuke.callback(cog, ctx, confirmation="CONFIRMNUKE")

        bot.close.assert_called_once()


# ─── setup ───────────────────────────────────────────────────────────

class TestSetup:
    @pytest.mark.asyncio
    async def test_setup(self):
        from src.bot.cogs.admin_lifecycle import setup
        bot = MagicMock()
        bot.add_cog = AsyncMock()
        await setup(bot)
        bot.add_cog.assert_called_once()
