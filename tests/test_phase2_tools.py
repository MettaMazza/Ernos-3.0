"""
Tests for Phase 2 tool modules — support_tools, survival_tools,
context_retrieval, chat_tools, project_runner.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock


# ═══════════════════════════════════════════════════
# support_tools.py  (15% → 100%)
# ═══════════════════════════════════════════════════

class TestEscalateTicket:

    @pytest.mark.asyncio
    async def test_escalate_happy_path(self):
        from src.tools.support_tools import escalate_ticket

        mock_thread = MagicMock()
        mock_thread.jump_url = "https://discord.com/thread/1"
        mock_thread.name = "Help Thread"

        mock_user = MagicMock()
        mock_user.name = "TestUser"

        mock_admin = AsyncMock()

        mock_bot = AsyncMock()
        mock_bot.get_channel = MagicMock(return_value=mock_thread)
        mock_bot.fetch_user = AsyncMock(side_effect=[mock_user, mock_admin])

        with patch("config.settings") as mock_settings:
            mock_settings.ADMIN_IDS = [99]
            result = await escalate_ticket(
                reason="Need human help",
                priority="high",
                bot=mock_bot,
                channel_id="123",
                user_id="456",
            )

        assert "Ticket created" in result
        mock_admin.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_escalate_no_bot(self):
        from src.tools.support_tools import escalate_ticket
        result = await escalate_ticket(reason="test", bot=None)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_escalate_no_channel(self):
        from src.tools.support_tools import escalate_ticket
        result = await escalate_ticket(reason="test", bot=MagicMock(), channel_id=None)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_escalate_admin_dm_fails(self):
        from src.tools.support_tools import escalate_ticket

        mock_admin = AsyncMock()
        mock_admin.send.side_effect = Exception("DM failed")

        mock_bot = AsyncMock()
        mock_bot.get_channel = MagicMock(return_value=MagicMock(jump_url="url", name="t"))
        mock_bot.fetch_user = AsyncMock(side_effect=[MagicMock(name="User"), mock_admin])

        with patch("config.settings") as mock_settings:
            mock_settings.ADMIN_IDS = [99]
            result = await escalate_ticket(reason="x", bot=mock_bot, channel_id="1", user_id="2")

        assert "Failed to DM" in result

    @pytest.mark.asyncio
    async def test_escalate_fetch_user_fails(self):
        from src.tools.support_tools import escalate_ticket

        mock_admin = AsyncMock()

        mock_bot = AsyncMock()
        mock_bot.get_channel = MagicMock(return_value=MagicMock(jump_url="url", name="t"))
        # First fetch_user for the user fails → fallback name; second for admin works
        mock_bot.fetch_user = AsyncMock(side_effect=[Exception("not found"), mock_admin])

        with patch("config.settings") as mock_settings:
            mock_settings.ADMIN_IDS = [99]
            result = await escalate_ticket(reason="x", bot=mock_bot, channel_id="1", user_id="2")

        assert "Ticket created" in result

    @pytest.mark.asyncio
    async def test_escalate_exception(self):
        from src.tools.support_tools import escalate_ticket

        mock_bot = AsyncMock()
        mock_bot.get_channel = MagicMock(side_effect=Exception("crash"))

        with patch("config.settings") as mock_settings:
            mock_settings.ADMIN_IDS = [99]
            result = await escalate_ticket(reason="x", bot=mock_bot, channel_id="1")

        assert "Error" in result or "error" in result.lower()


# ═══════════════════════════════════════════════════
# survival_tools.py  (22% → 100%)
# ═══════════════════════════════════════════════════

class TestCheckDiscomfort:

    @pytest.mark.asyncio
    async def test_happy_path(self):
        from src.tools.survival_tools import check_discomfort

        mock_meter = MagicMock()
        mock_meter.get_score.return_value = 42.5
        mock_meter.get_zone.return_value = (0, 50, "🟡", "ELEVATED")
        mock_meter.get_stats.return_value = {
            "total_incidents": 7,
            "streak_clean_hours": 12.5,
            "last_incident_ts": "2026-01-01",
        }

        with patch("src.bot.globals") as mock_globals, \
             patch("src.memory.discomfort.DiscomfortMeter", return_value=mock_meter):
            mock_globals.bot = MagicMock()
            result = await check_discomfort(user_id="123")

        assert "42.5" in result
        assert "ELEVATED" in result
        assert "ACTUAL reading" in result

    @pytest.mark.asyncio
    async def test_no_bot(self):
        from src.tools.survival_tools import check_discomfort

        with patch("src.bot.globals") as mock_globals:
            mock_globals.bot = None
            result = await check_discomfort()

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_defaults_to_kwargs_user_id(self):
        from src.tools.survival_tools import check_discomfort

        mock_meter = MagicMock()
        mock_meter.get_score.return_value = 0.0
        mock_meter.get_zone.return_value = (0, 0, "🟢", "CALM")
        mock_meter.get_stats.return_value = {"total_incidents": 0, "streak_clean_hours": 0, "last_incident_ts": "Never"}

        with patch("src.bot.globals") as mock_globals, \
             patch("src.memory.discomfort.DiscomfortMeter", return_value=mock_meter):
            mock_globals.bot = MagicMock()
            result = await check_discomfort(user_id=None, user_id_kwarg="555")

        assert "DISCOMFORT STATE" in result

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        from src.tools.survival_tools import check_discomfort

        with patch("src.bot.globals") as mock_globals, \
             patch("src.memory.discomfort.DiscomfortMeter", side_effect=Exception("DB down")):
            mock_globals.bot = MagicMock()
            result = await check_discomfort(user_id="123")

        assert "Error" in result


# ═══════════════════════════════════════════════════
# context_retrieval.py  (23% → 100%)
# ═══════════════════════════════════════════════════

class TestCheckCreationContext:

    @pytest.mark.asyncio
    async def test_finds_matching_records(self, tmp_path):
        from src.tools.context_retrieval import check_creation_context

        ledger = tmp_path / "provenance.jsonl"
        entries = [
            {"filename": "image_42.png", "timestamp": "2026-01-01", "checksum": "abcdef1234567890",
             "metadata": {"prompt": "a sunset", "intention": "cover art", "scope": "PUBLIC"}},
            {"filename": "other.txt", "timestamp": "2026-01-02", "checksum": "1234567890abcdef",
             "metadata": {"prompt": "unrelated", "intention": "", "scope": "PRIVATE"}},
        ]
        with open(ledger, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        with patch.object(
            __import__("src.security.provenance", fromlist=["ProvenanceManager"]).ProvenanceManager,
            "LEDGER_FILE", ledger
        ):
            result = await check_creation_context("image_42")

        assert "image_42.png" in result
        assert "Found 1" in result

    @pytest.mark.asyncio
    async def test_no_match(self, tmp_path):
        from src.tools.context_retrieval import check_creation_context

        ledger = tmp_path / "provenance.jsonl"
        ledger.write_text(json.dumps({"filename": "other.png", "metadata": {}}) + "\n")

        with patch.object(
            __import__("src.security.provenance", fromlist=["ProvenanceManager"]).ProvenanceManager,
            "LEDGER_FILE", ledger
        ):
            result = await check_creation_context("nonexistent")

        assert "No context found" in result

    @pytest.mark.asyncio
    async def test_missing_ledger(self, tmp_path):
        from src.tools.context_retrieval import check_creation_context

        with patch.object(
            __import__("src.security.provenance", fromlist=["ProvenanceManager"]).ProvenanceManager,
            "LEDGER_FILE", tmp_path / "missing.jsonl"
        ):
            result = await check_creation_context("anything")

        assert "not found" in result or "Ledger" in result

    @pytest.mark.asyncio
    async def test_matches_by_prompt(self, tmp_path):
        from src.tools.context_retrieval import check_creation_context

        ledger = tmp_path / "provenance.jsonl"
        entry = {"filename": "gen.png", "timestamp": "2026-01-01", "checksum": "00112233aabbccdd",
                 "metadata": {"prompt": "a beautiful sunset over mountains", "intention": "", "scope": "PUBLIC"}}
        ledger.write_text(json.dumps(entry) + "\n")

        with patch.object(
            __import__("src.security.provenance", fromlist=["ProvenanceManager"]).ProvenanceManager,
            "LEDGER_FILE", ledger
        ):
            result = await check_creation_context("sunset")

        assert "gen.png" in result

    @pytest.mark.asyncio
    async def test_exception_handling(self, tmp_path):
        from src.tools.context_retrieval import check_creation_context

        # Create a ledger that exists (so we pass the exists() check) but can't be opened
        ledger = tmp_path / "provenance.jsonl"
        ledger.write_text("bad data")

        with patch.object(
            __import__("src.security.provenance", fromlist=["ProvenanceManager"]).ProvenanceManager,
            "LEDGER_FILE", ledger
        ):
            with patch("builtins.open", side_effect=PermissionError("denied")):
                result = await check_creation_context("test")

        assert "Error" in result


# ═══════════════════════════════════════════════════
# chat_tools.py  (25% → 100%)
# ═══════════════════════════════════════════════════

class TestCreateThreadForUser:

    @pytest.mark.asyncio
    async def test_creates_thread(self):
        from src.tools.chat_tools import create_thread_for_user

        mock_thread = AsyncMock()
        mock_thread.name = "Chat with Alice"

        mock_message = AsyncMock()
        mock_message.guild = MagicMock()
        mock_message.author.display_name = "Alice"
        mock_message.create_thread.return_value = mock_thread

        with patch("src.bot.globals") as mock_globals:
            mock_globals.active_message = mock_message
            result = await create_thread_for_user(
                reason="Chat", bot=MagicMock(), channel=MagicMock()
            )

        assert "Created thread" in result

    @pytest.mark.asyncio
    async def test_no_bot_or_channel(self):
        from src.tools.chat_tools import create_thread_for_user
        result = await create_thread_for_user(bot=None, channel=None)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_no_active_message(self):
        from src.tools.chat_tools import create_thread_for_user

        with patch("src.bot.globals") as mock_globals:
            mock_globals.active_message = None
            result = await create_thread_for_user(bot=MagicMock(), channel=MagicMock())

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_dm_context_rejected(self):
        from src.tools.chat_tools import create_thread_for_user

        mock_message = MagicMock()
        mock_message.guild = None

        with patch("src.bot.globals") as mock_globals:
            mock_globals.active_message = mock_message
            result = await create_thread_for_user(bot=MagicMock(), channel=MagicMock())

        assert "DMs" in result

    @pytest.mark.asyncio
    async def test_thread_creation_fails(self):
        from src.tools.chat_tools import create_thread_for_user

        mock_message = AsyncMock()
        mock_message.guild = MagicMock()
        mock_message.create_thread.side_effect = Exception("Permissions error")

        with patch("src.bot.globals") as mock_globals:
            mock_globals.active_message = mock_message
            result = await create_thread_for_user(bot=MagicMock(), channel=MagicMock())

        assert "Couldn't create" in result


class TestSendDirectMessage:

    @pytest.mark.asyncio
    async def test_send_dm_success(self):
        from src.tools.chat_tools import send_direct_message

        mock_dm = AsyncMock()
        mock_user = AsyncMock()
        mock_user.name = "Bob"
        mock_user.create_dm.return_value = mock_dm

        mock_bot = MagicMock()
        mock_bot.get_user.return_value = mock_user

        result = await send_direct_message(content="Hello!", bot=mock_bot, user_id=42)
        assert "Sent DM" in result
        mock_dm.send.assert_called_once_with("Hello!")

    @pytest.mark.asyncio
    async def test_no_bot_or_user(self):
        from src.tools.chat_tools import send_direct_message
        result = await send_direct_message(content="Hi", bot=None, user_id=None)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        from src.tools.chat_tools import send_direct_message

        mock_bot = AsyncMock()
        mock_bot.get_user = MagicMock(return_value=None)
        mock_bot.fetch_user = AsyncMock(return_value=None)

        result = await send_direct_message(content="Hi", bot=mock_bot, user_id=42)
        assert "Could not find user" in result

    @pytest.mark.asyncio
    async def test_dm_fails(self):
        from src.tools.chat_tools import send_direct_message

        mock_user = AsyncMock()
        mock_user.create_dm.side_effect = Exception("DM blocked")

        mock_bot = MagicMock()
        mock_bot.get_user.return_value = mock_user

        result = await send_direct_message(content="Hi", bot=mock_bot, user_id=42)
        assert "Failed" in result


# ═══════════════════════════════════════════════════
# task_tracker.py  (replacement for project_runner)
# ═══════════════════════════════════════════════════

class TestTaskTracker:

    def _reset(self):
        """Clear module-level state between tests."""
        from src.tools import task_tracker
        task_tracker._active_tasks.clear()

    def test_plan_task_happy(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            result = plan_task(
                goal="Build widget",
                steps="Create file|Write tests|Deploy",
                user_id="42"
            )

        assert "Build widget" in result
        assert "ACTIVE" in result
        assert "Create file" in result

    def test_plan_task_replaces_existing(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            plan_task(goal="Old", steps="A|B", user_id="42")
            result = plan_task(goal="New", steps="X|Y|Z", user_id="42")

        assert "New" in result
        assert "X" in result and "Y" in result and "Z" in result

    def test_plan_task_no_steps(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            result = plan_task(goal="Test", steps="", user_id="42")

        assert "Error" in result

    def test_complete_step_happy(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task, complete_step

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            plan_task(goal="Test", steps="A|B", user_id="42")
            result = complete_step(user_id="42")

        assert "Completed" in result or "✅" in result

    def test_complete_step_no_task(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import complete_step

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            result = complete_step(user_id="42")

        assert "No active task" in result

    def test_complete_all_steps(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task, complete_step

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            plan_task(goal="Test", steps="A|B", user_id="42")
            complete_step(user_id="42")
            result = complete_step(user_id="42")

        assert "DONE" in result or "complete" in result.lower()

    def test_skip_step_happy(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task, skip_step

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            plan_task(goal="Test", steps="A|B|C", user_id="42")
            result = skip_step(user_id="42")

        assert "⏭️" in result or "SKIPPED" in result.upper()

    def test_skip_step_no_task(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import skip_step

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            result = skip_step(user_id="42")

        assert "No active task" in result

    def test_get_task_status_happy(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task, get_task_status, complete_step

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            plan_task(goal="Widget", steps="A|B|C", user_id="42")
            complete_step(user_id="42")
            result = get_task_status(user_id="42")

        assert "Widget" in result
        assert "✅" in result  # Step A is marked done

    def test_get_task_status_no_task(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import get_task_status

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            result = get_task_status(user_id="42")

        assert "No active task" in result

    def test_get_active_task_context_empty(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import get_active_task_context

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            result = get_active_task_context("42")

        assert result == ""

    def test_get_active_task_context_with_task(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task, get_active_task_context

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            plan_task(goal="Widget", steps="A|B", user_id="42")
            result = get_active_task_context("42")

        assert "Widget" in result
        assert "A" in result

    def test_persistence_save_and_load(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task, _active_tasks, _load_task

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            plan_task(goal="Persist me", steps="X|Y", user_id="42")
            # Clear in-memory state
            _active_tasks.clear()
            # Load from disk
            with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
                task = _load_task("42")

        assert task is not None
        assert task.goal == "Persist me"
        assert len(task.steps) == 2

    def test_persistence_missing_file(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import _load_task

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            task = _load_task("nonexistent")

        assert task is None

    def test_plan_task_no_user_id(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            result = plan_task(goal="Test", steps="A|B")

        assert "Error" in result

    def test_complete_step_beyond_end(self, tmp_path):
        self._reset()
        from src.tools.task_tracker import plan_task, complete_step

        with patch("src.tools.task_tracker._get_persist_path", return_value=tmp_path / "task.json"):
            plan_task(goal="Test", steps="A", user_id="42")
            complete_step(user_id="42")
            # Task should be done now, completing again should report done
            result = complete_step(user_id="42")

        assert "No active task" in result or "DONE" in result or "complete" in result.lower()

