"""
Tests for knowledge_base.py — Dynamic Minecraft recipe lookup.
"""

import pytest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestMinecraftKnowledge:
    """Tests for MinecraftKnowledge class."""

    @pytest.fixture
    def kb(self, tmp_path, monkeypatch):
        """Create a knowledge base with temp cache file."""
        from src.gaming.knowledge_base import MinecraftKnowledge

        cache_file = str(tmp_path / "mc_knowledge.json")
        monkeypatch.setattr(MinecraftKnowledge, "CACHE_FILE", cache_file)
        return MinecraftKnowledge()

    def test_lookup_static_recipe(self, kb):
        """Should find items in static tech tree."""
        result = kb.lookup_recipe("wooden_pickaxe")
        assert result is not None
        assert result["source"] == "tech_tree"
        assert "oak_planks" in result["ingredients"]

    def test_lookup_static_smelting(self, kb):
        """Should find smelting recipes."""
        result = kb.lookup_recipe("iron_ingot")
        assert result is not None
        assert result["source"] == "tech_tree_smelting"
        assert "iron_ore" in result["ingredients"]

    def test_lookup_raw_material(self, kb):
        """Should identify raw materials."""
        result = kb.lookup_recipe("oak_log")
        assert result is not None
        assert result["source"] == "raw_material"
        assert result["type"] == "collect"
        assert result["ingredients"] == {}

    def test_lookup_unknown_returns_none(self, kb):
        """Should return None for unknown items (sync lookup)."""
        result = kb.lookup_recipe("netherite_ingot")
        assert result is None

    def test_cache_persistence(self, tmp_path, monkeypatch):
        """Cached recipes should persist across instances."""
        from src.gaming.knowledge_base import MinecraftKnowledge

        cache_file = str(tmp_path / "persist_test.json")
        monkeypatch.setattr(MinecraftKnowledge, "CACHE_FILE", cache_file)

        # First instance — populate cache
        kb1 = MinecraftKnowledge()
        kb1._cache["test_item"] = {"ingredients": {"a": 1}, "source": "test"}
        kb1._save_cache()

        # Second instance — should load from disk
        kb2 = MinecraftKnowledge()
        result = kb2.lookup_recipe("test_item")
        assert result is not None
        assert result["source"] == "test"

    def test_cache_saves_on_disk(self, kb, tmp_path, monkeypatch):
        """_save_cache should write to disk."""
        from src.gaming.knowledge_base import MinecraftKnowledge

        cache_file = str(tmp_path / "save_test.json")
        monkeypatch.setattr(MinecraftKnowledge, "CACHE_FILE", cache_file)
        kb2 = MinecraftKnowledge()
        kb2._cache["test_item"] = {"ingredients": {"b": 2}, "source": "test"}
        kb2._save_cache()

        assert os.path.exists(cache_file)
        with open(cache_file) as f:
            data = json.load(f)
        assert "test_item" in data

    def test_lookup_caches_static_recipes(self, kb):
        """Looking up static recipe should cache it."""
        kb.lookup_recipe("furnace")
        assert "furnace" in kb._cache

    def test_crafting_table_recipe(self, kb):
        """Crafting table should be findable."""
        result = kb.lookup_recipe("crafting_table")
        assert result is not None
        assert "oak_planks" in result["ingredients"]

    def test_load_missing_cache_file(self, tmp_path, monkeypatch):
        """Should handle missing cache file gracefully."""
        from src.gaming.knowledge_base import MinecraftKnowledge

        monkeypatch.setattr(MinecraftKnowledge, "CACHE_FILE", str(tmp_path / "nonexistent.json"))
        kb = MinecraftKnowledge()
        assert kb._cache == {}

    def test_load_corrupt_cache_file(self, tmp_path, monkeypatch):
        """Should handle corrupt cache file gracefully."""
        from src.gaming.knowledge_base import MinecraftKnowledge

        cache_file = tmp_path / "corrupt.json"
        cache_file.write_text("not valid json{{{")
        monkeypatch.setattr(MinecraftKnowledge, "CACHE_FILE", str(cache_file))
        kb = MinecraftKnowledge()
        assert kb._cache == {}


class TestKnowledgeBaseAsync:
    """Tests for async LLM recipe lookup."""

    @pytest.fixture
    def kb(self, tmp_path, monkeypatch):
        from src.gaming.knowledge_base import MinecraftKnowledge
        monkeypatch.setattr(MinecraftKnowledge, "CACHE_FILE", str(tmp_path / "async_test.json"))
        return MinecraftKnowledge()

    @pytest.mark.asyncio
    async def test_lookup_async_known_item(self, kb):
        """Async lookup of known item should work without engine."""
        result = await kb.lookup_recipe_async("wooden_pickaxe", engine=None)
        assert result is not None
        assert result["source"] == "tech_tree"

    @pytest.mark.asyncio
    async def test_lookup_async_unknown_no_engine(self, kb):
        """Async lookup of unknown item with no engine returns None."""
        result = await kb.lookup_recipe_async("netherite_ingot", engine=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_async_with_mock_engine(self, kb):
        """Async lookup should use LLM engine for unknown items."""
        from unittest.mock import AsyncMock

        mock_engine = AsyncMock()
        mock_engine.process.return_value = (
            '{"ingredients": {"gold_ingot": 4, "redstone": 1}, "needs_table": true}',
        )

        result = await kb.lookup_recipe_async("clock", engine=mock_engine)
        assert result is not None
        assert result["source"] == "llm"
        assert "gold_ingot" in result["ingredients"]

    @pytest.mark.asyncio
    async def test_lookup_async_llm_error_handling(self, kb):
        """Should handle LLM errors gracefully."""
        from unittest.mock import AsyncMock

        mock_engine = AsyncMock()
        mock_engine.process.side_effect = Exception("API timeout")

        result = await kb.lookup_recipe_async("netherite_ingot", engine=mock_engine)
        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_async_llm_not_craftable(self, kb):
        """Should handle 'not craftable' LLM response."""
        from unittest.mock import AsyncMock

        mock_engine = AsyncMock()
        mock_engine.process.return_value = ('{"error": "not craftable"}',)

        result = await kb.lookup_recipe_async("bedrock", engine=mock_engine)
        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_async_caches_llm_result(self, kb):
        """LLM results should be cached after lookup."""
        from unittest.mock import AsyncMock

        mock_engine = AsyncMock()
        mock_engine.process.return_value = (
            '{"ingredients": {"string": 3, "stick": 3}, "needs_table": true}',
        )

        await kb.lookup_recipe_async("fishing_rod", engine=mock_engine)
        # Should be cached now
        assert "fishing_rod" in kb._cache
        # Second call should not hit LLM
        mock_engine.process.reset_mock()
        result = await kb.lookup_recipe_async("fishing_rod", engine=mock_engine)
        assert result is not None
        mock_engine.process.assert_not_called()


class TestGetKnowledgeBase:
    """Tests for singleton getter."""

    def test_singleton(self):
        """get_knowledge_base should return same instance."""
        import src.gaming.knowledge_base as mod
        mod._knowledge_base = None  # Reset

        kb1 = mod.get_knowledge_base()
        kb2 = mod.get_knowledge_base()
        assert kb1 is kb2

        mod._knowledge_base = None  # Cleanup
