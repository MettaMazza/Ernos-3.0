"""
Phase 3 Tests — Weak Coverage Files (31-59%).

Covers: browser.py, visualization_tools.py, types.py (DynamicLayerRegistry),
        reading_tracker.py, stream.py, consolidation.py, cognition_tools.py,
        visualization/server.py (deep integration paths).
"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from dataclasses import asdict


# ═══════════════════════════════════════════════════
# browser.py  (31% → 100%)
# ═══════════════════════════════════════════════════

class TestBrowseInteractive:

    @pytest.mark.asyncio
    async def test_blocked_url(self):
        from src.tools.browser import browse_interactive
        result = await browse_interactive("http://169.254.169.254/metadata")
        assert "blocked" in result.lower()

    @pytest.mark.asyncio
    async def test_success(self):
        mock_page = AsyncMock()
        mock_page.title.return_value = "Example"
        mock_page.evaluate.return_value = "Hello World\nSecond line"

        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = AsyncMock()
        mock_browser.new_context.return_value = mock_context

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_pw_cm = AsyncMock()
        mock_pw_cm.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_pw_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.browser.async_playwright", return_value=mock_pw_cm):
            from src.tools.browser import browse_interactive
            result = await browse_interactive("https://example.com")

        assert "Example" in result
        assert "Hello World" in result
        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception(self):
        mock_pw_cm = AsyncMock()
        mock_pw_cm.__aenter__ = AsyncMock(side_effect=Exception("Chromium not found"))
        mock_pw_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.browser.async_playwright", return_value=mock_pw_cm):
            from src.tools.browser import browse_interactive
            result = await browse_interactive("https://example.com")

        assert "Browser Error" in result


# ═══════════════════════════════════════════════════
# visualization_tools.py  (34% → 100%)
# ═══════════════════════════════════════════════════

class TestCaptureScreenshot:
    @pytest.mark.asyncio
    async def test_playwright_not_installed(self):
        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            # Force reimport to trigger ImportError
            import importlib
            from src.tools import visualization_tools
            with pytest.raises(RuntimeError, match="Playwright"):
                await visualization_tools._capture_screenshot()

    @pytest.mark.asyncio
    async def test_capture_success(self, tmp_path):
        import src.tools.visualization_tools as vt

        mock_page = AsyncMock()
        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_pw_cm = AsyncMock()
        mock_pw_cm.__aenter__ = AsyncMock(return_value=mock_playwright)
        mock_pw_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("src.tools.visualization_tools.SCREENSHOT_DIR", tmp_path), \
             patch("playwright.async_api.async_playwright", return_value=mock_pw_cm):
            result = await vt._capture_screenshot(wait_ms=100)

        assert str(tmp_path) in result or "kg_visualizer" in result


class TestManageKgVisualizer:

    @pytest.mark.asyncio
    async def test_status_not_running(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = None

        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.__enter__ = MagicMock(return_value=mock_sock_instance)
            mock_sock_instance.__exit__ = MagicMock(return_value=False)
            mock_sock_instance.connect_ex.return_value = 1  # Not in use
            mock_socket.return_value = mock_sock_instance

            result = await vt.manage_kg_visualizer(action="status")

        assert "not running" in result.lower()

    @pytest.mark.asyncio
    async def test_status_running(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = MagicMock()
        result = await vt.manage_kg_visualizer(action="status")
        assert "running" in result.lower()
        vt._server_instance = None

    @pytest.mark.asyncio
    async def test_start_no_bot(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = None

        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.__enter__ = MagicMock(return_value=mock_sock_instance)
            mock_sock_instance.__exit__ = MagicMock(return_value=False)
            mock_sock_instance.connect_ex.return_value = 1
            mock_socket.return_value = mock_sock_instance

            result = await vt.manage_kg_visualizer(action="start", bot=None)

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_start_success(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = None

        mock_server = AsyncMock()

        with patch("socket.socket") as mock_socket, \
             patch("src.visualization.server.KGVisualizationServer", return_value=mock_server) as mock_cls, \
             patch.dict("sys.modules", {"src.visualization.server": MagicMock(KGVisualizationServer=MagicMock(return_value=mock_server))}):
            mock_sock_instance = MagicMock()
            mock_sock_instance.__enter__ = MagicMock(return_value=mock_sock_instance)
            mock_sock_instance.__exit__ = MagicMock(return_value=False)
            mock_sock_instance.connect_ex.return_value = 1
            mock_socket.return_value = mock_sock_instance

            result = await vt.manage_kg_visualizer(action="start", bot=MagicMock())

        assert "started" in result.lower()
        vt._server_instance = None

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = MagicMock()
        result = await vt.manage_kg_visualizer(action="start", bot=MagicMock())
        assert "already running" in result.lower()
        vt._server_instance = None

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = None
        result = await vt.manage_kg_visualizer(action="stop")
        assert "not running" in result.lower()

    @pytest.mark.asyncio
    async def test_stop_success(self):
        import src.tools.visualization_tools as vt
        mock_server = AsyncMock()
        vt._server_instance = mock_server
        result = await vt.manage_kg_visualizer(action="stop")
        mock_server.stop.assert_called_once()
        assert "stopped" in result.lower()
        vt._server_instance = None

    @pytest.mark.asyncio
    async def test_stop_exception(self):
        import src.tools.visualization_tools as vt
        mock_server = AsyncMock()
        mock_server.stop.side_effect = Exception("crash")
        vt._server_instance = mock_server
        result = await vt.manage_kg_visualizer(action="stop")
        assert "Failed" in result
        vt._server_instance = None

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        import src.tools.visualization_tools as vt
        result = await vt.manage_kg_visualizer(action="nope")
        assert "Unknown action" in result

    @pytest.mark.asyncio
    async def test_screenshot_auto_start(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = None

        mock_server = AsyncMock()

        with patch("socket.socket") as mock_socket, \
             patch.dict("sys.modules", {"src.visualization.server": MagicMock(KGVisualizationServer=MagicMock(return_value=mock_server))}), \
             patch.object(vt, "_capture_screenshot", new_callable=AsyncMock, return_value="/tmp/shot.png"):
            mock_sock_instance = MagicMock()
            mock_sock_instance.__enter__ = MagicMock(return_value=mock_sock_instance)
            mock_sock_instance.__exit__ = MagicMock(return_value=False)
            mock_sock_instance.connect_ex.return_value = 1
            mock_socket.return_value = mock_sock_instance

            result = await vt.manage_kg_visualizer(action="screenshot", bot=MagicMock())

        assert "SCREENSHOT_FILE" in result or "shot.png" in result
        vt._server_instance = None

    @pytest.mark.asyncio
    async def test_screenshot_no_bot(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = None

        with patch("socket.socket") as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.__enter__ = MagicMock(return_value=mock_sock_instance)
            mock_sock_instance.__exit__ = MagicMock(return_value=False)
            mock_sock_instance.connect_ex.return_value = 1
            mock_socket.return_value = mock_sock_instance

            result = await vt.manage_kg_visualizer(action="screenshot", bot=None)

        assert "Error" in result


# ═══════════════════════════════════════════════════
# types.py — DynamicLayerRegistry  (45% → 100%)
# ═══════════════════════════════════════════════════

class TestGraphLayer:
    def test_has_26_layers(self):
        from src.memory.types import GraphLayer
        assert len(GraphLayer) == 26

    def test_builtin_layers_set(self):
        from src.memory.types import BUILTIN_LAYERS
        assert "semantic" in BUILTIN_LAYERS
        assert "narrative" in BUILTIN_LAYERS


class TestDynamicLayerRegistry:

    def _fresh_registry(self):
        """Reset singleton and return a fresh registry."""
        from src.memory.types import DynamicLayerRegistry
        DynamicLayerRegistry._instance = None
        return DynamicLayerRegistry()

    def test_singleton(self):
        from src.memory.types import DynamicLayerRegistry
        DynamicLayerRegistry._instance = None
        a = DynamicLayerRegistry()
        b = DynamicLayerRegistry()
        assert a is b
        DynamicLayerRegistry._instance = None

    def test_is_valid_builtin(self):
        reg = self._fresh_registry()
        assert reg.is_valid_layer("semantic") is True
        assert reg.is_valid_layer("made_up_layer") is False

    def test_is_builtin(self):
        reg = self._fresh_registry()
        assert reg.is_builtin("semantic") is True
        assert reg.is_builtin("custom_xyz") is False

    def test_register_new_layer(self):
        reg = self._fresh_registry()
        result = reg.register_layer("mythological", "Myths and legends")
        assert result is True
        assert reg.is_valid_layer("mythological") is True
        assert reg.is_builtin("mythological") is False

    def test_register_duplicate_returns_false(self):
        reg = self._fresh_registry()
        reg.register_layer("test_layer", "Test")
        result = reg.register_layer("test_layer", "Test again")
        assert result is False

    def test_register_builtin_name_returns_false(self):
        reg = self._fresh_registry()
        result = reg.register_layer("semantic", "Override")
        assert result is False

    def test_register_with_driver(self):
        reg = self._fresh_registry()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        result = reg.register_layer("new_layer", "New layer", driver=mock_driver)
        assert result is True
        mock_session.run.assert_called_once()

    def test_register_normalizes_name(self):
        reg = self._fresh_registry()
        reg.register_layer("My Layer Name", "Desc")
        assert reg.is_valid_layer("my_layer_name") is True

    def test_remove_custom_layer(self):
        reg = self._fresh_registry()
        reg.register_layer("temp_layer", "Temporary")
        assert reg.remove_layer("temp_layer") is True
        assert reg.is_valid_layer("temp_layer") is False

    def test_remove_builtin_fails(self):
        reg = self._fresh_registry()
        assert reg.remove_layer("semantic") is False

    def test_remove_nonexistent_fails(self):
        reg = self._fresh_registry()
        assert reg.remove_layer("nonexistent_layer") is False

    def test_remove_with_driver(self):
        reg = self._fresh_registry()
        reg.register_layer("removable", "To be removed")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        reg.remove_layer("removable", driver=mock_driver)
        mock_session.run.assert_called_once()

    def test_get_all_layers(self):
        reg = self._fresh_registry()
        reg.register_layer("extra", "Extra layer")
        all_layers = reg.get_all_layers()
        assert "semantic" in all_layers
        assert all_layers["semantic"]["builtin"] is True
        assert "extra" in all_layers
        assert all_layers["extra"]["builtin"] is False

    def test_get_custom_layers(self):
        reg = self._fresh_registry()
        reg.register_layer("custom_a", "A")
        reg.register_layer("custom_b", "B")
        custom = reg.get_custom_layers()
        assert "custom_a" in custom
        assert "custom_b" in custom
        assert "semantic" not in custom

    def test_get_parent(self):
        reg = self._fresh_registry()
        reg.register_layer("child_layer", "Child", parent_layer="narrative")
        assert reg.get_parent("child_layer") == "narrative"

    def test_get_parent_default(self):
        reg = self._fresh_registry()
        reg.register_layer("orphan", "No parent")
        assert reg.get_parent("orphan") == "semantic"

    def test_get_parent_nonexistent(self):
        reg = self._fresh_registry()
        assert reg.get_parent("nonexistent") is None

    def test_load_from_neo4j(self):
        reg = self._fresh_registry()

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = [
            {"name": "loaded_layer", "desc": "From Neo4j", "parent": "semantic", "created": "2026-01-01"}
        ]
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session

        reg.load_from_neo4j(mock_driver)
        assert reg.is_valid_layer("loaded_layer") is True

    def test_load_from_neo4j_exception(self):
        reg = self._fresh_registry()
        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("DB down")
        reg.load_from_neo4j(mock_driver)  # Should not raise


# ═══════════════════════════════════════════════════
# reading_tracker.py  (53% → 100%)
# ═══════════════════════════════════════════════════

class TestDocumentBookmark:
    def test_pct_partial(self):
        from src.memory.reading_tracker import DocumentBookmark
        bm = DocumentBookmark(path="test.py", lines_read=50, total_lines=100, last_end_line=50)
        assert bm.pct == 50

    def test_pct_zero_total(self):
        from src.memory.reading_tracker import DocumentBookmark
        bm = DocumentBookmark(path="test.py", lines_read=0, total_lines=0)
        assert bm.pct == 100

    def test_remaining(self):
        from src.memory.reading_tracker import DocumentBookmark
        bm = DocumentBookmark(path="test.py", total_lines=100, last_end_line=60)
        assert bm.remaining == 40

    def test_remaining_zero(self):
        from src.memory.reading_tracker import DocumentBookmark
        bm = DocumentBookmark(path="test.py", total_lines=100, last_end_line=100)
        assert bm.remaining == 0


class TestReadingTracker:
    def test_record_read_partial(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_read("src/bot.py", start=1, end=500, total=1200)
        assert tracker.has_reads() is True
        assert tracker.read_count == 1
        assert tracker.is_complete("src/bot.py") is False

    def test_record_read_complete(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_read("small.py", start=1, end=50, total=50)
        assert tracker.is_complete("small.py") is True

    def test_record_read_accumulates(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_read("big.py", start=1, end=500, total=2000)
        tracker.record_read("big.py", start=501, end=1000, total=2000)
        assert tracker.read_count == 2
        assert not tracker.is_complete("big.py")

    def test_record_read_completes_on_second(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_read("big.py", start=1, end=500, total=1000)
        tracker.record_read("big.py", start=501, end=1000, total=1000)
        assert tracker.is_complete("big.py") is True

    def test_record_browse_complete(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_browse("https://example.com", content_len=5000, truncated=False)
        assert tracker.is_complete("https://example.com") is True

    def test_record_browse_truncated(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_browse("https://big.com", content_len=10000, truncated=True)
        assert tracker.is_complete("https://big.com") is False

    def test_get_unfinished(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_read("done.py", 1, 100, 100)
        tracker.record_read("partial.py", 1, 500, 1200)
        unfinished = tracker.get_unfinished()
        assert len(unfinished) == 1
        assert unfinished[0]["path"] == "partial.py"
        assert unfinished[0]["next_start"] == 501
        assert unfinished[0]["remaining"] == 700

    def test_get_all_read(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_read("a.py", 1, 10, 10)
        tracker.record_browse("https://b.com", 100, False)
        assert sorted(tracker.get_all_read()) == ["a.py", "https://b.com"]

    def test_is_complete_unknown(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        assert tracker.is_complete("unknown.py") is False

    def test_estimate_extra_steps(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_read("big.py", 1, 500, 2500)
        # remaining = 2000, with read_limit=500 → 4 steps
        steps = tracker.estimate_extra_steps(read_limit=500)
        assert steps == 4

    def test_estimate_extra_steps_zero(self):
        from src.memory.reading_tracker import ReadingTracker
        tracker = ReadingTracker()
        tracker.record_read("done.py", 1, 100, 100)
        assert tracker.estimate_extra_steps() == 0


# ═══════════════════════════════════════════════════
# stream.py — ContextStream  (59% → 100%)
# ═══════════════════════════════════════════════════

class TestTurn:
    def test_dataclass_fields(self):
        from src.memory.stream import Turn
        t = Turn(
            user_id="123", user_name="Alice",
            user_message="Hello", bot_message="Hi",
            timestamp=time.time(), metadata={},
            scope="PUBLIC"
        )
        assert t.user_id == "123"
        assert t.scope == "PUBLIC"
        assert t.persona is None


class TestStateVector:
    def test_defaults(self):
        from src.memory.stream import StateVector
        sv = StateVector()
        assert sv.summary == ""
        assert sv.topics == []


class TestContextStream:

    def _make_stream(self, tmp_path):
        from src.memory.stream import ContextStream
        with patch.object(ContextStream, "PERSIST_DIR", tmp_path):
            stream = ContextStream.__new__(ContextStream)
            stream.bot = None
            stream.turns = []
            from src.memory.stream import StateVector
            stream.state = StateVector()
            import asyncio
            stream._lock = asyncio.Lock()
            stream.PERSIST_DIR = tmp_path
        return stream

    @pytest.mark.asyncio
    async def test_add_turn(self, tmp_path):
        stream = self._make_stream(tmp_path)
        with patch("asyncio.create_task"):
            await stream.add_turn("123", "Hello", "Hi", user_name="Alice")
        assert len(stream.turns) == 1
        assert stream.turns[0].user_name == "Alice"

    @pytest.mark.asyncio
    async def test_add_turn_prunes_window(self, tmp_path):
        stream = self._make_stream(tmp_path)
        from src.memory.stream import Turn
        # Fill with WINDOW_SIZE turns
        for i in range(50):
            stream.turns.append(Turn(
                user_id="u", user_name="User", user_message=f"m{i}",
                bot_message=f"r{i}", timestamp=time.time(), metadata={}
            ))
        with patch("asyncio.create_task"), \
             patch.object(stream, "_archive_turn") as mock_archive:
            await stream.add_turn("u", "new_msg", "new_reply", user_name="User")
        assert len(stream.turns) == 50
        mock_archive.assert_called_once()

    def test_get_context_empty(self, tmp_path):
        stream = self._make_stream(tmp_path)
        ctx = stream.get_context()
        assert "RECENT HISTORY" in ctx

    def test_get_context_with_state(self, tmp_path):
        stream = self._make_stream(tmp_path)
        stream.state.summary = "Alice is asking about cats"
        ctx = stream.get_context()
        assert "CURRENT SITUATION" in ctx
        assert "cats" in ctx

    def test_get_context_filters_private(self, tmp_path):
        from src.memory.stream import Turn
        stream = self._make_stream(tmp_path)
        stream.turns = [
            Turn("1", "Alice", "secret", "reply", time.time(), {}, scope="PRIVATE"),
            Turn("2", "Bob", "public", "reply", time.time(), {}, scope="PUBLIC"),
        ]
        ctx = stream.get_context(target_scope="PUBLIC", user_id="2")
        assert "public" in ctx
        assert "secret" not in ctx

    def test_get_context_private_visible_to_owner(self, tmp_path):
        from src.memory.stream import Turn
        stream = self._make_stream(tmp_path)
        stream.turns = [
            Turn("1", "Alice", "my secret", "ok", time.time(), {}, scope="PRIVATE"),
        ]
        ctx = stream.get_context(target_scope="PUBLIC", user_id="1")
        assert "my secret" in ctx

    def test_get_context_channel_isolation(self, tmp_path):
        from src.memory.stream import Turn
        stream = self._make_stream(tmp_path)
        stream.turns = [
            Turn("1", "Alice", "ch100", "reply", time.time(), {}, scope="PUBLIC", channel_id=100),
            Turn("2", "Bob", "ch200", "reply", time.time(), {}, scope="PUBLIC", channel_id=200),
        ]
        ctx = stream.get_context(channel_id=100)
        assert "ch100" in ctx
        assert "ch200" not in ctx

    def test_get_context_core_scope(self, tmp_path):
        from src.memory.stream import Turn
        stream = self._make_stream(tmp_path)
        stream.turns = [
            Turn("CORE", "CORE", "autonomy event", "result", time.time(), {}),
            Turn("1", "Alice", "hello", "hi", time.time(), {}, scope="PRIVATE"),
        ]
        ctx = stream.get_context(target_scope="CORE")
        assert "AUTONOMY EVENT" in ctx
        assert "hello" in ctx

    def test_archive_turn(self, tmp_path):
        from src.memory.stream import Turn
        stream = self._make_stream(tmp_path)
        turn = Turn("1", "A", "msg", "resp", time.time(), {})
        stream._archive_turn(turn)
        archive = tmp_path / "archive.jsonl"
        assert archive.exists()
        data = json.loads(archive.read_text().strip())
        assert data["user_message"] == "msg"

    def test_save_and_load_turns(self, tmp_path):
        from src.memory.stream import Turn, ContextStream
        stream = self._make_stream(tmp_path)
        stream.turns.append(Turn("1", "A", "m1", "r1", 1.0, {}))
        stream.turns.append(Turn("2", "B", "m2", "r2", 2.0, {}))
        stream._save_turns()

        stream2 = self._make_stream(tmp_path)
        stream2._load()
        assert len(stream2.turns) == 2
        assert stream2.turns[0].user_message == "m1"

    def test_save_and_load_state(self, tmp_path):
        from src.memory.stream import StateVector
        stream = self._make_stream(tmp_path)
        stream.state.summary = "Testing state"
        stream.state.topics = ["testing"]
        stream._save_state()

        stream2 = self._make_stream(tmp_path)
        stream2._load()
        assert stream2.state.summary == "Testing state"
        assert "testing" in stream2.state.topics

    def test_load_empty_dir(self, tmp_path):
        stream = self._make_stream(tmp_path)
        stream._load()  # Should not raise
        assert len(stream.turns) == 0

    @pytest.mark.asyncio
    async def test_update_state_vector_no_bot(self, tmp_path):
        from src.memory.stream import Turn
        stream = self._make_stream(tmp_path)
        stream.bot = None
        turn = Turn("1", "A", "msg", "resp", time.time(), {})
        await stream._update_state_vector(turn)
        assert stream.state.summary == ""

    @pytest.mark.asyncio
    async def test_update_state_vector_with_bot(self, tmp_path):
        from src.memory.stream import Turn
        stream = self._make_stream(tmp_path)
        stream.bot = MagicMock()
        stream.bot.engine_manager.get_active_engine.return_value.generate_response = MagicMock(return_value="Updated summary")
        stream.bot.loop.run_in_executor = AsyncMock(return_value="Updated summary")

        turn = Turn("1", "Alice", "msg", "resp", time.time(), {})
        await stream._update_state_vector(turn)
        assert stream.state.summary == "Updated summary"
        assert "Alice" in stream.state.active_participants

    @pytest.mark.asyncio
    async def test_update_state_vector_no_engine(self, tmp_path):
        from src.memory.stream import Turn
        stream = self._make_stream(tmp_path)
        stream.bot = MagicMock()
        stream.bot.engine_manager.get_active_engine.return_value = None

        turn = Turn("1", "A", "msg", "resp", time.time(), {})
        await stream._update_state_vector(turn)
        assert stream.state.summary == ""

    def test_set_bot(self, tmp_path):
        stream = self._make_stream(tmp_path)
        mock_bot = MagicMock()
        stream.set_bot(mock_bot)
        assert stream.bot is mock_bot


# ═══════════════════════════════════════════════════
# visualization/server.py — deep paths  (37% → higher)
# ═══════════════════════════════════════════════════

class TestKGServerDeep:

    def _make_server(self):
        from src.visualization.server import KGVisualizationServer
        bot = MagicMock(spec=["get_channel"])
        return KGVisualizationServer(bot)

    @pytest.mark.asyncio
    async def test_handle_graph_with_graph(self):
        server = self._make_server()
        mock_graph = MagicMock()
        server._get_graph = MagicMock(return_value=mock_graph)
        server._extract_graph_data = MagicMock(return_value=([], []))

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web:
            mock_web.Response = MagicMock(return_value="response")
            request = MagicMock()
            request.query = {"scope": "CORE"}
            await server._handle_graph(request)

    @pytest.mark.asyncio
    async def test_handle_graph_exception(self):
        server = self._make_server()
        server._get_graph = MagicMock(side_effect=Exception("boom"))

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web:
            mock_web.Response = MagicMock(return_value="response")
            request = MagicMock()
            request.query = {}
            await server._handle_graph(request)

    @pytest.mark.asyncio
    async def test_handle_stats_with_graph(self):
        server = self._make_server()
        mock_graph = MagicMock()
        server._get_graph = MagicMock(return_value=mock_graph)
        server._compute_stats = MagicMock(return_value={"total_nodes": 42})

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web:
            mock_web.Response = MagicMock(return_value="response")
            request = MagicMock()
            await server._handle_stats(request)

    @pytest.mark.asyncio
    async def test_handle_stats_exception(self):
        server = self._make_server()
        server._get_graph = MagicMock(side_effect=Exception("boom"))

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web:
            mock_web.Response = MagicMock(return_value="response")
            request = MagicMock()
            await server._handle_stats(request)

    @pytest.mark.asyncio
    async def test_handle_quarantine_with_file(self, tmp_path):
        server = self._make_server()
        q_file = tmp_path / "quarantine.json"
        q_file.write_text(json.dumps([{"source": "A", "target": "B"}]))

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web, \
             patch("src.visualization.server.Path", return_value=q_file):
            mock_web.Response = MagicMock(return_value="response")
            request = MagicMock()
            await server._handle_quarantine(request)

    @pytest.mark.asyncio
    async def test_handle_quarantine_from_graph(self):
        server = self._make_server()
        mock_graph = MagicMock()
        mock_graph.quarantine.peek.return_value = [{"fact": "test"}]
        server._get_graph = MagicMock(return_value=mock_graph)

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web, \
             patch("src.visualization.server.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            mock_web.Response = MagicMock(return_value="response")
            request = MagicMock()
            await server._handle_quarantine(request)

    def test_get_graph_via_direct_attr(self):
        from src.visualization.server import KGVisualizationServer
        bot = MagicMock(spec=["graph"])
        bot.graph = MagicMock()
        server = KGVisualizationServer(bot)
        result = server._get_graph()
        assert result is not None

    def test_compute_stats_with_driver(self):
        server = self._make_server()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        # 4 queries: total_nodes, total_edges, active_layers, orphaned_nodes
        results = []
        for val in [100, 200, 5, 3]:
            mr = MagicMock()
            mr.single.return_value = {"c": val}
            results.append(mr)
        mock_session.run.side_effect = results

        mock_graph = MagicMock()
        mock_graph.driver.session.return_value = mock_session

        with patch("src.visualization.server.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            stats = server._compute_stats(mock_graph)

        assert stats["total_nodes"] == 100
        assert stats["total_edges"] == 200
        assert stats["health_score"] is not None

    @pytest.mark.asyncio
    async def test_serve_frontend_missing(self):
        server = self._make_server()
        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web, \
             patch("src.visualization.server.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            mock_web.Response = MagicMock(return_value="resp")
            request = MagicMock()
            await server._serve_frontend(request)

    @pytest.mark.asyncio
    async def test_handle_crawler_status(self):
        server = self._make_server()
        server._get_graph = MagicMock(return_value=MagicMock())

        with patch("src.visualization.server.HAS_AIOHTTP", True), \
             patch("src.visualization.server.web") as mock_web:
            mock_web.Response = MagicMock(return_value="response")
            # The import will fail → exception path
            request = MagicMock()
            await server._handle_crawler_status(request)
