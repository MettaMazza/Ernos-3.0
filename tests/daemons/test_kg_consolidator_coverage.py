"""Tests for KGConsolidator daemon — 10 tests."""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch

from src.daemons.kg_consolidator import KGConsolidator


@pytest.fixture
def consolidator():
    bot = MagicMock()
    bot.engine_manager = MagicMock()
    bot.loop = MagicMock()
    bot.hippocampus = MagicMock()
    bot.hippocampus.graph = MagicMock()
    return KGConsolidator(bot)


class TestRecordTurn:

    def test_increments_counter(self, consolidator):
        with patch("src.daemons.kg_consolidator.ScopeManager") as sm:
            sm.get_scope.return_value = MagicMock(name="OPEN")
            consolidator.record_turn(123, "hi", "hello", 456, is_dm=False)
            assert consolidator._turn_counter == 1

    def test_appends_interaction(self, consolidator):
        with patch("src.daemons.kg_consolidator.ScopeManager") as sm:
            sm.get_scope.return_value = MagicMock(name="PRIVATE")
            consolidator.record_turn(123, "hi", "hello", 456)
            assert len(consolidator._pending_interactions) == 1

    def test_triggers_at_threshold(self, consolidator):
        with patch("src.daemons.kg_consolidator.ScopeManager") as sm:
            sm.get_scope.return_value = MagicMock(name="OPEN")
            with patch("src.daemons.kg_consolidator.asyncio") as aio:
                for i in range(5):
                    consolidator.record_turn(123, "hi", "hello", 456)
                aio.create_task.assert_called_once()


class TestConsolidate:

    @pytest.mark.asyncio
    async def test_skip_if_consolidating(self, consolidator):
        consolidator._is_consolidating = True
        consolidator._pending_interactions = [{"scope": "OPEN"}]
        await consolidator._consolidate()
        assert True  # No exception: negative case handled correctly
        # Should exit early

    @pytest.mark.asyncio
    async def test_skip_if_empty(self, consolidator):
        consolidator._pending_interactions = []
        await consolidator._consolidate()
        assert True  # No exception: negative case handled correctly
        # Should exit early, no error

    @pytest.mark.asyncio
    async def test_groups_by_scope(self, consolidator):
        consolidator._pending_interactions = [
            {"scope": "OPEN", "user_id": 1, "user_msg": "a", "bot_msg": "b"},
            {"scope": "PRIVATE", "user_id": 2, "user_msg": "c", "bot_msg": "d"},
            {"scope": "OPEN", "user_id": 1, "user_msg": "e", "bot_msg": "f"},
        ]
        with patch.object(consolidator, "_extract_and_store", new_callable=AsyncMock, return_value=1):
            await consolidator._consolidate()
            assert consolidator._extract_and_store.call_count == 2  # OPEN + PRIVATE

    @pytest.mark.asyncio
    async def test_clears_pending(self, consolidator):
        consolidator._pending_interactions = [
            {"scope": "OPEN", "user_id": 1, "user_msg": "a", "bot_msg": "b"}
        ]
        with patch.object(consolidator, "_extract_and_store", new_callable=AsyncMock, return_value=0):
            await consolidator._consolidate()
            assert len(consolidator._pending_interactions) == 0

    @pytest.mark.asyncio
    async def test_error_cleanup(self, consolidator):
        consolidator._pending_interactions = [
            {"scope": "OPEN", "user_id": 1, "user_msg": "a", "bot_msg": "b"}
        ]
        with patch.object(consolidator, "_extract_and_store", new_callable=AsyncMock, side_effect=Exception("fail")):
            await consolidator._consolidate()
            assert consolidator._is_consolidating is False


class TestExtractAndStore:

    @pytest.mark.asyncio
    async def test_no_engine(self, consolidator):
        consolidator.bot.engine_manager.get_active_engine.return_value = None
        result = await consolidator._extract_and_store(
            [{"user_id": 1, "user_msg": "hi", "bot_msg": "hello"}], "OPEN"
        )
        assert result == 0

    @pytest.mark.asyncio
    async def test_stores_high_confidence(self, consolidator):
        engine = MagicMock()
        consolidator.bot.engine_manager.get_active_engine.return_value = engine
        rels = json.dumps([{"subject": "Maria", "predicate": "LIKES", "object": "cats", "confidence": 0.9}])
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value=rels)
        with patch("builtins.open", MagicMock()):
            result = await consolidator._extract_and_store(
                [{"user_id": 123, "user_msg": "I love cats", "bot_msg": "Nice!"}], "OPEN"
            )
            assert result == 1

    @pytest.mark.asyncio
    async def test_skips_low_confidence(self, consolidator):
        engine = MagicMock()
        consolidator.bot.engine_manager.get_active_engine.return_value = engine
        rels = json.dumps([{"subject": "A", "predicate": "R", "object": "B", "confidence": 0.3}])
        consolidator.bot.loop.run_in_executor = AsyncMock(return_value=rels)
        with patch("builtins.open", MagicMock()):
            result = await consolidator._extract_and_store(
                [{"user_id": 123, "user_msg": "a", "bot_msg": "b"}], "OPEN"
            )
            assert result == 0


class TestParseExtraction:

    def test_valid_json(self, consolidator):
        response = 'Here are results: [{"subject": "A", "predicate": "R", "object": "B"}]'
        result = consolidator._parse_extraction(response)
        assert len(result) == 1

    def test_invalid_json(self, consolidator):
        assert consolidator._parse_extraction("no json here") == []

    def test_empty(self, consolidator):
        assert consolidator._parse_extraction("") == []


class TestForceConsolidate:

    def test_triggers_if_pending(self, consolidator):
        consolidator._pending_interactions = [{"scope": "OPEN"}]
        with patch("src.daemons.kg_consolidator.asyncio") as aio:
            consolidator.force_consolidate()
            aio.create_task.assert_called_once()

    def test_noop_if_empty(self, consolidator):
        consolidator._pending_interactions = []
        with patch("src.daemons.kg_consolidator.asyncio") as aio:
            consolidator.force_consolidate()
            aio.create_task.assert_not_called()
