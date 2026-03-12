"""
Regression tests for self_stop tool.

Tests:
1. Tool registration in ToolRegistry
2. Tool function behavior (sets cancel event, stashes reason)
3. Cancel response generation with self-stop reason vs user /stop
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch


# === Registration Tests ===

class TestSelfStopRegistration:
    """Tests that self_stop is properly registered."""

    def test_self_stop_registered(self):
        from src.tools.registry import ToolRegistry
        tool = ToolRegistry.get_tool("self_stop")
        assert tool is not None, "self_stop should be registered"
        assert tool.name == "self_stop"

    def test_self_stop_has_reason_param(self):
        from src.tools.registry import ToolRegistry
        tool = ToolRegistry.get_tool("self_stop")
        assert "reason" in tool.parameters

    def test_self_stop_description_mentions_abort(self):
        from src.tools.registry import ToolRegistry
        tool = ToolRegistry.get_tool("self_stop")
        assert "abort" in tool.description.lower() or "stop" in tool.description.lower()


# === Tool Function Tests ===

class TestSelfStopTool:
    """Tests for the self_stop tool function."""

    @pytest.mark.asyncio
    async def test_self_stop_sets_cancel_event(self):
        """self_stop should trigger request_cancel on the cognition engine."""
        from src.tools.self_stop_tool import self_stop

        mock_bot = MagicMock()
        mock_engine = MagicMock()
        mock_engine.request_cancel.return_value = True
        mock_bot.cognition = mock_engine

        result = await self_stop(
            reason="Tool 'magic_wand' doesn't exist",
            user_id="12345",
            bot=mock_bot,
        )

        assert "Self-stop triggered" in result
        mock_engine.request_cancel.assert_called_once_with("12345")

    @pytest.mark.asyncio
    async def test_self_stop_stashes_reason(self):
        """self_stop should stash the reason on engine._self_stop_reasons."""
        from src.tools.self_stop_tool import self_stop

        mock_bot = MagicMock()
        mock_engine = MagicMock()
        mock_engine.request_cancel.return_value = True
        # Ensure _self_stop_reasons doesn't exist yet
        del mock_engine._self_stop_reasons
        mock_bot.cognition = mock_engine

        await self_stop(
            reason="Cannot access external API",
            user_id="12345",
            bot=mock_bot,
        )

        assert mock_engine._self_stop_reasons["12345"] == "Cannot access external API"

    @pytest.mark.asyncio
    async def test_self_stop_no_user_id(self):
        """self_stop should return error when user_id is missing."""
        from src.tools.self_stop_tool import self_stop

        mock_bot = MagicMock()
        mock_bot.cognition = MagicMock()

        result = await self_stop(
            reason="Doesn't matter",
            bot=mock_bot,
        )

        assert "Error" in result

    @pytest.mark.asyncio
    async def test_self_stop_no_engine(self):
        """self_stop should return error when cognition engine is missing."""
        from src.tools.self_stop_tool import self_stop

        mock_bot = MagicMock(spec=[])  # no attributes
        mock_bot.cognition = None
        # Override getattr to return None for cognition
        result = await self_stop(
            reason="Doesn't matter",
            user_id="12345",
            bot=MagicMock(**{"cognition": None}),
        )
        # getattr should return None
        assert "Error" in result or "No active" in result

    @pytest.mark.asyncio
    async def test_self_stop_no_active_event(self):
        """self_stop should handle case where no cancel event exists."""
        from src.tools.self_stop_tool import self_stop

        mock_bot = MagicMock()
        mock_engine = MagicMock()
        mock_engine.request_cancel.return_value = False  # No active event
        mock_bot.cognition = mock_engine

        result = await self_stop(
            reason="Nothing to cancel",
            user_id="12345",
            bot=mock_bot,
        )

        assert "No active processing" in result


# === Cancel Response Tests ===

class TestCancelResponseWithSelfStop:
    """Tests that _generate_cancel_response handles self-stop vs user-stop."""

    @pytest.mark.asyncio
    async def test_self_stop_generates_different_prompt(self):
        """Self-stop should use a prompt that includes the reason, not '/stop'."""
        from src.engines.cognition import CognitionEngine

        mock_bot = MagicMock()
        mock_engine_manager = MagicMock()
        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = "I couldn't complete that because the tool doesn't exist."
        mock_engine_manager.get_active_engine.return_value = mock_llm
        mock_bot.engine_manager = mock_engine_manager
        mock_bot.loop = asyncio.get_event_loop()

        engine = CognitionEngine(mock_bot)
        # Stash a self-stop reason
        engine._self_stop_reasons = {"12345": "The tool 'magic_wand' doesn't exist"}

        response = await engine._generate_cancel_response(
            step=2,
            turn_history="[TOOL: magic_wand(params...)]",
            input_text="Can you use magic_wand to fix this?"
        )

        # Verify the LLM was called with a self-stop prompt (not /stop prompt)
        call_args = mock_llm.generate_response.call_args[0]
        prompt = call_args[0]
        assert "stopped yourself" in prompt
        assert "magic_wand" in prompt
        assert "/stop" not in prompt

    @pytest.mark.asyncio
    async def test_user_stop_uses_original_prompt(self):
        """User /stop should still use the original prompt format."""
        from src.engines.cognition import CognitionEngine

        mock_bot = MagicMock()
        mock_engine_manager = MagicMock()
        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = "Stopped. Let me know if you want to try again."
        mock_engine_manager.get_active_engine.return_value = mock_llm
        mock_bot.engine_manager = mock_engine_manager
        mock_bot.loop = asyncio.get_event_loop()

        engine = CognitionEngine(mock_bot)
        # No self-stop reason — this is a user /stop

        response = await engine._generate_cancel_response(
            step=1,
            turn_history="",
            input_text="Tell me about AI"
        )

        call_args = mock_llm.generate_response.call_args[0]
        prompt = call_args[0]
        assert "/stop" in prompt
        assert "stopped yourself" not in prompt

    @pytest.mark.asyncio
    async def test_self_stop_reason_is_consumed(self):
        """After generating cancel response, the self-stop reason should be cleared."""
        from src.engines.cognition import CognitionEngine

        mock_bot = MagicMock()
        mock_engine_manager = MagicMock()
        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = "Recovery response."
        mock_engine_manager.get_active_engine.return_value = mock_llm
        mock_bot.engine_manager = mock_engine_manager
        mock_bot.loop = asyncio.get_event_loop()

        engine = CognitionEngine(mock_bot)
        engine._self_stop_reasons = {"user1": "Test reason"}

        await engine._generate_cancel_response(0, "", "test")

        # Reason should be consumed/deleted
        assert "user1" not in engine._self_stop_reasons

    @pytest.mark.asyncio
    async def test_self_stop_fallback_includes_reason(self):
        """If LLM fails, fallback should still include the self-stop reason."""
        from src.engines.cognition import CognitionEngine

        mock_bot = MagicMock()
        mock_engine_manager = MagicMock()
        mock_engine_manager.get_active_engine.side_effect = Exception("LLM down")
        mock_bot.engine_manager = mock_engine_manager
        mock_bot.loop = asyncio.get_event_loop()

        engine = CognitionEngine(mock_bot)
        engine._self_stop_reasons = {"user1": "Database tool missing"}

        response = await engine._generate_cancel_response(0, "", "test")

        assert "Database tool missing" in response
