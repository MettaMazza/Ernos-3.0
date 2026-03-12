"""
Coverage tests for gaming/adapters/__init__.py — targets uncovered lines 1-37.

Tests: GameAdapter ABC — interface contract, property returns, abstract method enforcement.
"""
import pytest
from abc import ABC
from src.gaming.adapters import GameAdapter


class TestGameAdapterABC:
    """Verify GameAdapter is a proper abstract base class."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            GameAdapter()

    def test_is_abstract(self):
        assert issubclass(GameAdapter, ABC)


class TestGameAdapterConcreteSubclass:
    """Create a concrete subclass and test each method."""

    @pytest.fixture
    def concrete_adapter(self):
        class TestAdapter(GameAdapter):
            def __init__(self):
                self._connected = False

            async def connect(self, config: dict) -> bool:
                self._connected = True
                return True

            async def disconnect(self):
                self._connected = False

            async def execute(self, command: str, params: dict = None) -> dict:
                return {"command": command, "params": params, "success": True}

            async def get_status(self) -> dict:
                return {"connected": self._connected, "health": 20}

            @property
            def is_connected(self) -> bool:
                return self._connected

        return TestAdapter()

    @pytest.mark.asyncio
    async def test_connect(self, concrete_adapter):
        result = await concrete_adapter.connect({"host": "localhost"})
        assert result is True
        assert concrete_adapter.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, concrete_adapter):
        await concrete_adapter.connect({})
        await concrete_adapter.disconnect()
        assert concrete_adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_execute(self, concrete_adapter):
        result = await concrete_adapter.execute("test", {"key": "val"})
        assert result["success"] is True
        assert result["command"] == "test"

    @pytest.mark.asyncio
    async def test_get_status(self, concrete_adapter):
        status = await concrete_adapter.get_status()
        assert isinstance(status, dict)
        assert "health" in status

    def test_is_connected_default(self, concrete_adapter):
        assert concrete_adapter.is_connected is False


class TestGameAdapterPartialImplementation:
    """Verify that partial implementations can't be instantiated."""

    def test_missing_connect_raises(self):
        class BadAdapter(GameAdapter):
            async def disconnect(self): pass
            async def execute(self, command, params=None): pass
            async def get_status(self): pass
            @property
            def is_connected(self): return False

        with pytest.raises(TypeError):
            BadAdapter()

    def test_missing_execute_raises(self):
        class BadAdapter(GameAdapter):
            async def connect(self, config): pass
            async def disconnect(self): pass
            async def get_status(self): pass
            @property
            def is_connected(self): return False

        with pytest.raises(TypeError):
            BadAdapter()

    def test_missing_get_status_raises(self):
        class BadAdapter(GameAdapter):
            async def connect(self, config): pass
            async def disconnect(self): pass
            async def execute(self, command, params=None): pass
            @property
            def is_connected(self): return False

        with pytest.raises(TypeError):
            BadAdapter()

    def test_missing_is_connected_raises(self):
        class BadAdapter(GameAdapter):
            async def connect(self, config): pass
            async def disconnect(self): pass
            async def execute(self, command, params=None): pass
            async def get_status(self): pass

        with pytest.raises(TypeError):
            BadAdapter()
