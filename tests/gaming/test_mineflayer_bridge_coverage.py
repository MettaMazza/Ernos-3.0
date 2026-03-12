"""
Coverage tests for gaming/mineflayer_bridge.py — targets uncovered lines 51-398.

Tests: BridgeResponse, MineflayerBridge init, connect, disconnect,
       _read_stderr, _read_responses, execute, and all 30+ high-level commands.
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock
from src.gaming.mineflayer_bridge import MineflayerBridge, BridgeResponse


# ──────────────────────────────────────
# BridgeResponse Dataclass
# ──────────────────────────────────────

class TestBridgeResponse:
    def test_success_response(self):
        r = BridgeResponse(True, {"key": "val"})
        assert r.success is True
        assert r.data == {"key": "val"}
        assert r.error is None

    def test_error_response(self):
        r = BridgeResponse(False, error="timeout")
        assert r.success is False
        assert r.error == "timeout"


# ──────────────────────────────────────
# MineflayerBridge Init
# ──────────────────────────────────────

class TestBridgeInit:
    def test_default_init(self):
        bridge = MineflayerBridge()
        assert bridge.host == "localhost"
        assert bridge.port == 25565
        assert bridge.username == "Ernos"
        assert bridge.on_event is None
        assert bridge._connected is False

    def test_custom_init(self):
        cb = Mock()
        bridge = MineflayerBridge("192.168.1.1", 30000, "TestBot", on_event=cb)
        assert bridge.host == "192.168.1.1"
        assert bridge.port == 30000
        assert bridge.username == "TestBot"
        assert bridge.on_event is cb


# ──────────────────────────────────────
# Connect/Disconnect
# ──────────────────────────────────────

class TestBridgeConnect:
    @pytest.mark.asyncio
    async def test_connect_timeout(self):
        bridge = MineflayerBridge()
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stderr = MagicMock()
            mock_proc.stdin = MagicMock()
            mock_popen.return_value = mock_proc

            with patch.object(bridge, '_read_responses', new_callable=AsyncMock):
                with patch.object(bridge, '_read_stderr', new_callable=AsyncMock):
                    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                        with patch.object(bridge, 'disconnect', new_callable=AsyncMock):
                            result = await bridge.connect()
                            assert result is False


class TestBridgeDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_no_process(self):
        bridge = MineflayerBridge()
        bridge.process = None
        await bridge.disconnect()
        assert bridge._connected is False

    @pytest.mark.asyncio
    async def test_disconnect_with_process(self):
        bridge = MineflayerBridge()
        mock_proc = MagicMock()
        bridge.process = mock_proc
        bridge._reader_task = AsyncMock()
        bridge._reader_task.cancel = Mock()
        bridge._connected = True

        with patch.object(bridge, 'execute', new_callable=AsyncMock):
            await bridge.disconnect()
        assert bridge._connected is False
        assert bridge.process is None


# ──────────────────────────────────────
# Execute
# ──────────────────────────────────────

class TestBridgeExecute:
    @pytest.mark.asyncio
    async def test_execute_no_process(self):
        bridge = MineflayerBridge()
        bridge.process = None
        result = await bridge.execute("test")
        assert result.success is False
        assert result.error == "Not connected"

    @pytest.mark.asyncio
    async def test_execute_dead_process(self):
        bridge = MineflayerBridge()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # Exit code indicating death
        bridge.process = mock_proc
        result = await bridge.execute("test")
        assert result.success is False
        assert "Process died" in result.error
        assert bridge._connected is False

    @pytest.mark.asyncio
    async def test_execute_success(self):
        bridge = MineflayerBridge()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Still alive
        mock_proc.stdin = MagicMock()
        bridge.process = mock_proc
        bridge._reader_alive = True  # Reader must be alive

        async def mock_wait_for(future, timeout):
            return BridgeResponse(True, {"result": "ok"})

        with patch("asyncio.wait_for", side_effect=mock_wait_for):
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_future = asyncio.Future()
                mock_future.set_result(BridgeResponse(True, {"result": "ok"}))
                mock_loop.return_value.create_future.return_value = mock_future
                result = await bridge.execute("status")
                assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        bridge = MineflayerBridge()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdin = MagicMock()
        bridge.process = mock_proc
        bridge._reader_alive = True  # Reader must be alive

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_future = asyncio.Future()
                mock_loop.return_value.create_future.return_value = mock_future
                result = await bridge.execute("slow_cmd", timeout=1.0)
                assert result.success is False
                assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_timeout_dead_process(self):
        """Process dies during wait."""
        bridge = MineflayerBridge()
        mock_proc = MagicMock()
        # First call: alive, second call (during timeout check): dead
        mock_proc.poll.side_effect = [None, 42]
        mock_proc.stdin = MagicMock()
        bridge.process = mock_proc

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_future = asyncio.Future()
                mock_loop.return_value.create_future.return_value = mock_future
                result = await bridge.execute("dying_cmd")
                assert result.success is False
                assert bridge._connected is False


# ──────────────────────────────────────
# Read Responses
# ──────────────────────────────────────

class TestBridgeReadResponses:
    @pytest.mark.asyncio
    async def test_read_responses_event(self):
        bridge = MineflayerBridge()
        bridge.on_event = Mock()
        bridge._spawn_callback = Mock()

        lines = [
            json.dumps({"event": "spawn", "data": {}}) + "\n",
            ""  # EOF
        ]
        line_iter = iter(lines)

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        bridge.process = mock_proc

        async def mock_run_in_executor(_, fn):
            return next(line_iter)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor
            await bridge._read_responses()

        bridge._spawn_callback.assert_called_once()
        bridge.on_event.assert_called_once_with("spawn", {})

    @pytest.mark.asyncio
    async def test_read_responses_command_success(self):
        bridge = MineflayerBridge()
        future = asyncio.Future()
        bridge.pending = {"abc123": future}

        lines = [
            json.dumps({"id": "abc123", "success": True, "data": {"hp": 20}}) + "\n",
            ""
        ]
        line_iter = iter(lines)

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        bridge.process = mock_proc

        async def mock_run_in_executor(_, fn):
            return next(line_iter)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor
            await bridge._read_responses()

        result = future.result()
        assert result.success is True
        assert result.data == {"hp": 20}

    @pytest.mark.asyncio
    async def test_read_responses_command_failure(self):
        bridge = MineflayerBridge()
        future = asyncio.Future()
        bridge.pending = {"abc456": future}

        lines = [
            json.dumps({"id": "abc456", "success": False, "error": "not found"}) + "\n",
            ""
        ]
        line_iter = iter(lines)

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        bridge.process = mock_proc

        async def mock_run_in_executor(_, fn):
            return next(line_iter)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor
            await bridge._read_responses()

        result = future.result()
        assert result.success is False
        assert result.error == "not found"

    @pytest.mark.asyncio
    async def test_read_responses_json_error(self):
        bridge = MineflayerBridge()

        lines = ["not json\n", ""]
        line_iter = iter(lines)

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        bridge.process = mock_proc

        async def mock_run_in_executor(_, fn):
            return next(line_iter)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor
            await bridge._read_responses()  # Should not raise
        assert True  # No exception: error handled gracefully


class TestBridgeReadStderr:
    @pytest.mark.asyncio
    async def test_read_stderr(self):
        bridge = MineflayerBridge()

        lines = ["Error: something\n", ""]
        line_iter = iter(lines)

        mock_proc = MagicMock()
        mock_proc.stderr = MagicMock()
        bridge.process = mock_proc

        async def mock_run_in_executor(_, fn):
            return next(line_iter)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = mock_run_in_executor
            await bridge._read_stderr()
        assert True  # Execution completed without error


# ──────────────────────────────────────
# High-Level Commands — each delegates to execute()
# ──────────────────────────────────────

class TestBridgeHighLevelCommands:
    """Test every high-level command method delegates correctly to execute()."""

    @pytest.fixture
    def bridge(self):
        b = MineflayerBridge()
        b.execute = AsyncMock(return_value=BridgeResponse(True, {}))
        return b

    @pytest.mark.asyncio
    async def test_goto(self, bridge):
        await bridge.goto(10, 64, 20, range=2)
        bridge.execute.assert_called_with("goto", {"x": 10, "y": 64, "z": 20, "range": 2}, timeout=120)

    @pytest.mark.asyncio
    async def test_follow(self, bridge):
        await bridge.follow("player1", range=5)
        bridge.execute.assert_called_with("follow", {"username": "player1", "range": 5}, timeout=30)

    @pytest.mark.asyncio
    async def test_stop_follow(self, bridge):
        await bridge.stop_follow()
        bridge.execute.assert_called_with("stop_follow")

    @pytest.mark.asyncio
    async def test_collect(self, bridge):
        await bridge.collect("oak_log", 5)
        bridge.execute.assert_called_with("collect", {"block_type": "oak_log", "count": 5}, timeout=120)

    @pytest.mark.asyncio
    async def test_attack(self, bridge):
        await bridge.attack("hostile")
        bridge.execute.assert_called_with("attack", {"entity_type": "hostile"}, timeout=35)

    @pytest.mark.asyncio
    async def test_craft(self, bridge):
        await bridge.craft("planks", 4)
        bridge.execute.assert_called_with("craft", {"item": "planks", "count": 4}, timeout=60)

    @pytest.mark.asyncio
    async def test_get_status(self, bridge):
        await bridge.get_status()
        bridge.execute.assert_called_with("status")

    @pytest.mark.asyncio
    async def test_chat(self, bridge):
        await bridge.chat("Hello!")
        bridge.execute.assert_called_with("chat", {"message": "Hello!"})

    @pytest.mark.asyncio
    async def test_protect_without_coords(self, bridge):
        await bridge.protect("user1", 50)
        bridge.execute.assert_called_with("protect", {"username": "user1", "radius": 50}, timeout=30)

    @pytest.mark.asyncio
    async def test_protect_with_coords(self, bridge):
        await bridge.protect("user1", 50, x=10, y=64, z=20)
        bridge.execute.assert_called_with("protect", {"username": "user1", "radius": 50, "x": 10, "y": 64, "z": 20}, timeout=30)

    @pytest.mark.asyncio
    async def test_list_protected_zones(self, bridge):
        await bridge.list_protected_zones()
        bridge.execute.assert_called_with("list_protected_zones")

    @pytest.mark.asyncio
    async def test_get_screenshot_success(self, bridge):
        bridge.execute = AsyncMock(return_value=BridgeResponse(True, {"image": "base64data"}))
        result = await bridge.get_screenshot()
        assert result == "base64data"

    @pytest.mark.asyncio
    async def test_get_screenshot_failure(self, bridge):
        bridge.execute = AsyncMock(return_value=BridgeResponse(False, error="no screen"))
        result = await bridge.get_screenshot()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_screenshot_no_data(self, bridge):
        bridge.execute = AsyncMock(return_value=BridgeResponse(True, {}))
        result = await bridge.get_screenshot()
        assert result is None

    @pytest.mark.asyncio
    async def test_equip(self, bridge):
        await bridge.equip("diamond_sword", "hand")
        bridge.execute.assert_called_with("equip", {"item": "diamond_sword", "slot": "hand"})

    @pytest.mark.asyncio
    async def test_shield(self, bridge):
        await bridge.shield(True)
        bridge.execute.assert_called_with("shield", {"activate": True})

    @pytest.mark.asyncio
    async def test_sleep(self, bridge):
        await bridge.sleep()
        bridge.execute.assert_called_with("sleep")

    @pytest.mark.asyncio
    async def test_wake(self, bridge):
        await bridge.wake()
        bridge.execute.assert_called_with("wake")

    @pytest.mark.asyncio
    async def test_smelt(self, bridge):
        await bridge.smelt("iron_ore", "coal", 4)
        bridge.execute.assert_called_with("smelt", {"input": "iron_ore", "fuel": "coal", "count": 4}, timeout=120)

    @pytest.mark.asyncio
    async def test_store_no_args(self, bridge):
        await bridge.store()
        bridge.execute.assert_called_with("store", {}, timeout=30)

    @pytest.mark.asyncio
    async def test_store_with_args(self, bridge):
        await bridge.store("iron", 10)
        bridge.execute.assert_called_with("store", {"item": "iron", "count": 10}, timeout=30)

    @pytest.mark.asyncio
    async def test_take_no_args(self, bridge):
        await bridge.take()
        bridge.execute.assert_called_with("take", {}, timeout=30)

    @pytest.mark.asyncio
    async def test_take_with_args(self, bridge):
        await bridge.take("diamond", 5)
        bridge.execute.assert_called_with("take", {"item": "diamond", "count": 5}, timeout=30)

    @pytest.mark.asyncio
    async def test_place_no_coords(self, bridge):
        await bridge.place("cobblestone")
        bridge.execute.assert_called_with("place", {"block": "cobblestone"}, timeout=30)

    @pytest.mark.asyncio
    async def test_place_with_coords(self, bridge):
        await bridge.place("stone", x=1, y=2, z=3)
        bridge.execute.assert_called_with("place", {"block": "stone", "x": 1, "y": 2, "z": 3}, timeout=30)

    @pytest.mark.asyncio
    async def test_farm(self, bridge):
        await bridge.farm("wheat", 5)
        bridge.execute.assert_called_with("farm", {"crop": "wheat", "radius": 5}, timeout=60)

    @pytest.mark.asyncio
    async def test_harvest(self, bridge):
        await bridge.harvest(8)
        bridge.execute.assert_called_with("harvest", {"radius": 8}, timeout=30)

    @pytest.mark.asyncio
    async def test_plant(self, bridge):
        await bridge.plant("carrot", 3)
        bridge.execute.assert_called_with("plant", {"seed": "carrot", "count": 3}, timeout=30)

    @pytest.mark.asyncio
    async def test_fish(self, bridge):
        await bridge.fish(60)
        bridge.execute.assert_called_with("fish", {"duration": 60}, timeout=70)

    @pytest.mark.asyncio
    async def test_save_location(self, bridge):
        await bridge.save_location("home")
        bridge.execute.assert_called_with("save_location", {"name": "home"})

    @pytest.mark.asyncio
    async def test_goto_location_with_name(self, bridge):
        await bridge.goto_location("base")
        bridge.execute.assert_called_with("goto_location", {"name": "base"}, timeout=120)

    @pytest.mark.asyncio
    async def test_goto_location_no_name(self, bridge):
        await bridge.goto_location()
        bridge.execute.assert_called_with("goto_location", {}, timeout=120)

    @pytest.mark.asyncio
    async def test_copy_build(self, bridge):
        await bridge.copy_build("house", radius=10, height=15)
        bridge.execute.assert_called_with("copy_build", {"name": "house", "radius": 10, "height": 15})

    @pytest.mark.asyncio
    async def test_build(self, bridge):
        await bridge.build("house", gather_resources=True)
        bridge.execute.assert_called_with("build", {"name": "house", "gatherResources": True}, timeout=300)

    @pytest.mark.asyncio
    async def test_list_locations(self, bridge):
        await bridge.list_locations()
        bridge.execute.assert_called_with("list_locations")

    @pytest.mark.asyncio
    async def test_list_blueprints(self, bridge):
        await bridge.list_blueprints()
        bridge.execute.assert_called_with("list_blueprints")

    @pytest.mark.asyncio
    async def test_drop(self, bridge):
        await bridge.drop("iron", 5)
        bridge.execute.assert_called_with("drop", {"item": "iron", "count": 5})

    @pytest.mark.asyncio
    async def test_give(self, bridge):
        await bridge.give("player1", "diamond", 3)
        bridge.execute.assert_called_with("give", {"player": "player1", "item": "diamond", "count": 3}, timeout=60)

    @pytest.mark.asyncio
    async def test_find_without_go(self, bridge):
        await bridge.find("diamond_ore")
        bridge.execute.assert_called_with("find", {"block": "diamond_ore", "go": False, "radius": 256}, timeout=30)

    @pytest.mark.asyncio
    async def test_find_with_go(self, bridge):
        await bridge.find("diamond_ore", go=True)
        bridge.execute.assert_called_with("find", {"block": "diamond_ore", "go": True, "radius": 256}, timeout=120)

    @pytest.mark.asyncio
    async def test_eat_no_food(self, bridge):
        await bridge.eat()
        bridge.execute.assert_called_with("eat", {})

    @pytest.mark.asyncio
    async def test_eat_with_food(self, bridge):
        await bridge.eat("bread")
        bridge.execute.assert_called_with("eat", {"food": "bread"})

    @pytest.mark.asyncio
    async def test_share(self, bridge):
        await bridge.share("iron_ingot")
        bridge.execute.assert_called_with("share", {"item": "iron_ingot"})

    @pytest.mark.asyncio
    async def test_scan(self, bridge):
        await bridge.scan(64)
        bridge.execute.assert_called_with("scan", {"radius": 64})

    @pytest.mark.asyncio
    async def test_coop_mode(self, bridge):
        await bridge.coop_mode("player1", "on")
        bridge.execute.assert_called_with("coop_mode", {"player": "player1", "mode": "on"})


class TestBridgeIsConnected:
    def test_is_connected_default(self):
        bridge = MineflayerBridge()
        assert bridge.is_connected is False

    def test_is_connected_after_set(self):
        bridge = MineflayerBridge()
        bridge._connected = True
        bridge._reader_alive = True  # Reader must be alive
        bridge._consecutive_timeouts = 0  # No consecutive timeouts
        assert bridge.is_connected is True
