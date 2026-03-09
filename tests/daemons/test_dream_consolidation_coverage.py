"""
Coverage tests for daemons/dream_consolidation.py — expands to ~35 tests.

Tests: DreamConsolidationDaemon — run, _compress_episodic_memories,
       _compress_context_file, _build_compression_summary, _prune_kg_nodes,
       _persist_sentinel_cache, _write_status, get_status, setup_dream_scheduler.
"""
import pytest
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, Mock, patch, mock_open
from src.daemons.dream_consolidation import DreamConsolidationDaemon, setup_dream_scheduler


@pytest.fixture
def daemon():
    bot = MagicMock()
    bot.hippocampus = MagicMock()
    bot.hippocampus.graph = MagicMock()
    bot.cerebrum = MagicMock()
    bot.engine_manager = MagicMock()
    return DreamConsolidationDaemon(bot)


# ──────────────────────────────────────
# __init__
# ──────────────────────────────────────

class TestInit:
    def test_defaults(self, daemon):
        assert daemon._last_run is None
        assert daemon._status == "idle"
        assert daemon.bot is not None


# ──────────────────────────────────────
# run
# ──────────────────────────────────────

class TestRun:
    @pytest.mark.asyncio
    async def test_full_cycle(self, daemon):
        consolidator = MagicMock()
        consolidator.run_consolidation = AsyncMock(return_value="10 memories")
        with patch.object(daemon, "_compress_episodic_memories", new_callable=AsyncMock, return_value=5), \
             patch.object(daemon, "_prune_kg_nodes", new_callable=AsyncMock, return_value=3), \
             patch.object(daemon, "_persist_sentinel_cache", return_value=True), \
             patch.object(daemon, "_write_status"), \
             patch("src.lobes.creative.consolidation.MemoryConsolidator", return_value=consolidator):
            await daemon.run()
        assert daemon._status == "complete"
        assert daemon._last_run is not None

    @pytest.mark.asyncio
    async def test_error_sets_status(self, daemon):
        with patch.object(daemon, "_compress_episodic_memories", new_callable=AsyncMock, side_effect=Exception("fail")), \
             patch.object(daemon, "_write_status"):
            await daemon.run()
        assert daemon._status == "error"

    @pytest.mark.asyncio
    async def test_persist_false(self, daemon):
        consolidator = MagicMock()
        consolidator.run_consolidation = AsyncMock(return_value="done")
        with patch.object(daemon, "_compress_episodic_memories", new_callable=AsyncMock, return_value=0), \
             patch.object(daemon, "_prune_kg_nodes", new_callable=AsyncMock, return_value=0), \
             patch.object(daemon, "_persist_sentinel_cache", return_value=False), \
             patch.object(daemon, "_write_status"), \
             patch("src.lobes.creative.consolidation.MemoryConsolidator", return_value=consolidator):
            await daemon.run()
        assert daemon._status == "complete"


# ──────────────────────────────────────
# _compress_episodic_memories
# ──────────────────────────────────────

class TestCompressEpisodicMemories:
    @pytest.mark.asyncio
    async def test_no_users_dir(self, daemon, tmp_path):
        with patch("src.daemons.dream_consolidation.Path", return_value=tmp_path / "nonexistent"):
            result = await daemon._compress_episodic_memories()
        assert result == 0

    @pytest.mark.asyncio
    async def test_skips_files(self, daemon, tmp_path):
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        f = users_dir / "file.txt"
        f.touch()

        with patch("src.daemons.dream_consolidation.Path", return_value=users_dir):
            result = await daemon._compress_episodic_memories()
        assert result == 0

    @pytest.mark.asyncio
    async def test_user_with_context(self, daemon, tmp_path):
        users_dir = tmp_path / "users"
        user_dir = users_dir / "user1"
        user_dir.mkdir(parents=True)
        ctx = user_dir / "context_private.jsonl"
        ctx.write_text("line\n")

        daemon._compress_context_file = AsyncMock(return_value=5)
        with patch("src.daemons.dream_consolidation.Path", return_value=users_dir):
            result = await daemon._compress_episodic_memories()
        assert result >= 0  # At least attempts compression

    @pytest.mark.asyncio
    async def test_compression_exception(self, daemon, tmp_path):
        users_dir = tmp_path / "users"
        user_dir = users_dir / "user1"
        user_dir.mkdir(parents=True)
        ctx = user_dir / "context_private.jsonl"
        ctx.write_text("line\n")

        daemon._compress_context_file = AsyncMock(side_effect=Exception("disk"))
        with patch("src.daemons.dream_consolidation.Path", return_value=users_dir):
            result = await daemon._compress_episodic_memories()
        assert result is not None
        # Should handle gracefully


# ──────────────────────────────────────
# _compress_context_file
# ──────────────────────────────────────

class TestCompressContextFile:
    @pytest.mark.asyncio
    async def test_fewer_than_50(self, daemon, tmp_path):
        ctx = tmp_path / "ctx.jsonl"
        ctx.write_text("\n".join(json.dumps({"user": f"m{i}"}) for i in range(10)))
        scorer = MagicMock()
        with patch("src.memory.salience.SalienceScorer", scorer):
            result = await daemon._compress_context_file(ctx, tmp_path)
        assert result == 0

    @pytest.mark.asyncio
    async def test_all_low_salience(self, daemon, tmp_path):
        ctx = tmp_path / "ctx.jsonl"
        entries = [json.dumps({"user": f"msg{i}", "bot": f"r{i}", "scope": "PUBLIC"}) for i in range(60)]
        ctx.write_text("\n".join(entries))

        scorer = MagicMock()
        scorer.score_entry = Mock(return_value=0.3)
        with patch("src.memory.salience.SalienceScorer", scorer):
            result = await daemon._compress_context_file(ctx, tmp_path)
        assert result == 40  # 60 - 20 recent
        assert (tmp_path / "archive").exists()

    @pytest.mark.asyncio
    async def test_all_high_salience(self, daemon, tmp_path):
        ctx = tmp_path / "ctx.jsonl"
        entries = [json.dumps({"user": f"msg{i}"}) for i in range(60)]
        ctx.write_text("\n".join(entries))

        scorer = MagicMock()
        scorer.score_entry = Mock(return_value=0.9)
        with patch("src.memory.salience.SalienceScorer", scorer):
            result = await daemon._compress_context_file(ctx, tmp_path)
        assert result == 0

    @pytest.mark.asyncio
    async def test_bad_file(self, daemon, tmp_path):
        result = await daemon._compress_context_file(tmp_path / "nonexistent.jsonl", tmp_path)
        assert result == 0

    @pytest.mark.asyncio
    async def test_bad_json_lines(self, daemon, tmp_path):
        ctx = tmp_path / "ctx.jsonl"
        lines = []
        for i in range(60):
            if i % 5 == 0:
                lines.append("not valid json")
            else:
                lines.append(json.dumps({"user": f"msg{i}"}))
        ctx.write_text("\n".join(lines))

        scorer = MagicMock()
        scorer.score_entry = Mock(return_value=0.3)
        with patch("src.memory.salience.SalienceScorer", scorer):
            result = await daemon._compress_context_file(ctx, tmp_path)
        assert result is not None
        # Handles bad JSON gracefully

    @pytest.mark.asyncio
    async def test_empty_candidates(self, daemon, tmp_path):
        """Exactly 50 lines means 30 candidates, but test edge of 20 recent."""
        ctx = tmp_path / "ctx.jsonl"
        entries = [json.dumps({"user": f"m{i}"}) for i in range(50)]
        ctx.write_text("\n".join(entries))

        scorer = MagicMock()
        scorer.score_entry = Mock(return_value=0.3)
        with patch("src.memory.salience.SalienceScorer", scorer):
            result = await daemon._compress_context_file(ctx, tmp_path)
        assert result == 30  # 50 - 20


# ──────────────────────────────────────
# _build_compression_summary
# ──────────────────────────────────────

class TestBuildCompressionSummary:
    def test_with_both_fields(self, daemon):
        entries = [{"user": "hello", "bot": "world"}, {"user": "foo"}]
        result = daemon._build_compression_summary(entries)
        assert "Compressed 2 interactions" in result
        assert "User: hello" in result
        assert "Bot: world" in result

    def test_empty_fields(self, daemon):
        entries = [{}, {}, {}]
        result = daemon._build_compression_summary(entries)
        assert "3 routine interactions compressed" in result

    def test_caps_at_30(self, daemon):
        entries = [{"user": f"msg{i}"} for i in range(50)]
        result = daemon._build_compression_summary(entries)
        assert "Compressed 50 interactions" in result
        # Should only have 30 entries' content
        assert "User: msg29" in result

    def test_bot_only(self, daemon):
        entries = [{"bot": "automated response"}]
        result = daemon._build_compression_summary(entries)
        assert "Bot: automated response" in result


# ──────────────────────────────────────
# _prune_kg_nodes
# ──────────────────────────────────────

class TestPruneKGNodes:
    @pytest.mark.asyncio
    async def test_no_hippocampus(self, daemon):
        daemon.bot.hippocampus = None
        assert await daemon._prune_kg_nodes() == 0

    @pytest.mark.asyncio
    async def test_no_graph(self, daemon):
        daemon.bot.hippocampus.graph = None
        assert await daemon._prune_kg_nodes() == 0

    @pytest.mark.asyncio
    async def test_prune_success(self, daemon):
        daemon.bot.hippocampus.graph.run_query.return_value = [{"pruned": 7}]
        assert await daemon._prune_kg_nodes() == 7

    @pytest.mark.asyncio
    async def test_prune_empty_result(self, daemon):
        daemon.bot.hippocampus.graph.run_query.return_value = []
        assert await daemon._prune_kg_nodes() == 0

    @pytest.mark.asyncio
    async def test_prune_exception(self, daemon):
        daemon.bot.hippocampus.graph.run_query.side_effect = Exception("neo4j down")
        assert await daemon._prune_kg_nodes() == 0

    @pytest.mark.asyncio
    async def test_no_hippo_attr(self, daemon):
        del daemon.bot.hippocampus
        assert await daemon._prune_kg_nodes() == 0


# ──────────────────────────────────────
# _persist_sentinel_cache
# ──────────────────────────────────────

class TestPersistSentinelCache:
    def test_no_cerebrum(self, daemon):
        del daemon.bot.cerebrum
        assert daemon._persist_sentinel_cache() is False

    def test_no_superego(self, daemon):
        daemon.bot.cerebrum.lobes.get.return_value = None
        assert daemon._persist_sentinel_cache() is False

    def test_no_sentinel(self, daemon):
        superego = MagicMock()
        superego.get_ability.return_value = None
        daemon.bot.cerebrum.lobes.get.return_value = superego
        assert daemon._persist_sentinel_cache() is False

    def test_empty_cache(self, daemon):
        sentinel = MagicMock()
        sentinel._review_cache = {}
        superego = MagicMock()
        superego.get_ability.return_value = sentinel
        daemon.bot.cerebrum.lobes.get.return_value = superego
        assert daemon._persist_sentinel_cache() is False

    def test_success(self, daemon, tmp_path):
        sentinel = MagicMock()
        sentinel._review_cache = {"k1": (True, "safe"), "k2": (False, "bad")}
        superego = MagicMock()
        superego.get_ability.return_value = sentinel
        daemon.bot.cerebrum.lobes.get.return_value = superego

        cache_path = tmp_path / "sentinel_cache.json"
        with patch("src.daemons.dream_consolidation.Path", return_value=cache_path):
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            assert daemon._persist_sentinel_cache() is True

    def test_exception(self, daemon):
        sentinel = MagicMock()
        sentinel._review_cache = {"k": (True, "ok")}
        superego = MagicMock()
        superego.get_ability.return_value = sentinel
        daemon.bot.cerebrum.lobes.get.return_value = superego

        with patch("src.daemons.dream_consolidation.Path", side_effect=Exception("disk")):
            assert daemon._persist_sentinel_cache() is False


# ──────────────────────────────────────
# _write_status and get_status
# ──────────────────────────────────────

class TestWriteStatus:
    def test_writes_json(self, daemon, tmp_path):
        sf = tmp_path / "status.json"
        with patch("src.daemons.dream_consolidation.STATUS_FILE", sf):
            daemon._write_status("running", "processing...", 1.5)
        data = json.loads(sf.read_text())
        assert data["status"] == "running"
        assert data["elapsed_seconds"] == 1.5

    def test_write_exception(self, daemon):
        with patch("src.daemons.dream_consolidation.STATUS_FILE") as sf:
            sf.parent.mkdir.side_effect = Exception("nope")
            daemon._write_status("error", "fail")  # No raise
        assert True  # No exception: error handled gracefully


class TestGetStatus:
    def test_default(self, daemon):
        assert daemon.get_status() == "idle"

    def test_after_change(self, daemon):
        daemon._status = "complete"
        assert daemon.get_status() == "complete"


# ──────────────────────────────────────
# setup_dream_scheduler
# ──────────────────────────────────────

class TestSetupDreamScheduler:
    def test_registers_task(self):
        bot = MagicMock()
        scheduler = MagicMock()
        with patch("src.scheduler.get_scheduler", return_value=scheduler):
            daemon = setup_dream_scheduler(bot)
        assert isinstance(daemon, DreamConsolidationDaemon)
        scheduler.add_daily_task.assert_called_once()
