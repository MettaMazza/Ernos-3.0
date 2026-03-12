"""
Tests for src/web/web_chat_handler.py — Web chat message processing pipeline.

Covers: handle_web_message full flow, hippocampus recall, system prompt generation,
        preprocessor analysis, cognition engine processing, post-processing, error paths.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock
from pathlib import Path


# ── Helper: Build Mock Bot ─────────────────────────────────

def _mock_bot():
    """Create a mock bot with cognition engine and hippocampus."""
    bot = MagicMock()
    bot.tape_engine = MagicMock()
    bot.cognition.process = AsyncMock(return_value=("Hello from Ernos!", [], []))
    bot.cognition.process = AsyncMock(return_value=("Hello from Ernos!", [], []))
    bot.hippocampus = MagicMock()
    bot.hippocampus.early_recall = MagicMock(return_value=None)
    bot.hippocampus.observe = AsyncMock()
    bot.last_interaction = 0
    return bot


# ── Module-level setup ────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_prompt_manager():
    """Reset the module-level prompt manager singleton."""
    import src.web.web_chat_handler as mod
    mod._prompt_manager = None
    yield
    mod._prompt_manager = None


def _standard_patches():
    """Return a list of context managers for common patches used by most tests."""
    return [
        patch("src.web.web_chat_handler.PromptManager"),
        patch("src.bot.integrity_auditor.audit_response", new_callable=AsyncMock),
        patch("src.bot.globals"),
    ]


async def _run_message(bot=None, content="hello", user_id="u1", username="Alice", **kwargs):
    """Helper to run handle_web_message with standard patches."""
    from src.web.web_chat_handler import handle_web_message
    if bot is None:
        bot = _mock_bot()

    with patch("src.web.web_chat_handler.PromptManager") as MockPM:
        MockPM.return_value.get_system_prompt.return_value = ""
        with patch("src.bot.integrity_auditor.audit_response", new_callable=AsyncMock):
            with patch("src.bot.globals") as mock_globals:
                mock_globals.activity_log = []
                return await handle_web_message(bot, content, user_id, username, **kwargs)


# ── Core Flow ─────────────────────────────────────────────

class TestHandleWebMessage:
    @pytest.mark.asyncio
    async def test_returns_startup_message_when_no_bot(self):
        from src.web.web_chat_handler import handle_web_message
        text, files = await handle_web_message(None, "hello", "u1", "Alice")
        assert "starting up" in text.lower()
        assert files == []

    @pytest.mark.asyncio
    async def test_returns_startup_message_when_no_cognition(self):
        from src.web.web_chat_handler import handle_web_message
        bot = MagicMock()
        bot.cognition = None
        text, files = await handle_web_message(bot, "hello", "u1", "Alice")
        assert "starting up" in text.lower()

    @pytest.mark.asyncio
    async def test_basic_message_processing(self):
        text, files = await _run_message()
        assert text == "Hello from Ernos!"
        assert files == []

    @pytest.mark.asyncio
    async def test_strips_origin_tags(self):
        bot = _mock_bot()
        bot.cognition.process = AsyncMock()
        bot.cognition.process = AsyncMock(
            return_value=("[SELF-GENERATED]: This is clean text", [], [])
        )
        text, _ = await _run_message(bot=bot)
        assert "[SELF" not in text
        assert "This is clean text" in text

    @pytest.mark.asyncio
    async def test_strips_external_tags(self):
        bot = _mock_bot()
        bot.cognition.process = AsyncMock()
        bot.cognition.process = AsyncMock(
            return_value=("[EXTERNAL:web]: External info", [], [])
        )
        text, _ = await _run_message(bot=bot)
        assert "[EXTERNAL" not in text

    @pytest.mark.asyncio
    async def test_strips_system_block_tags(self):
        bot = _mock_bot()
        bot.cognition.process = AsyncMock()
        bot.cognition.process = AsyncMock(
            return_value=("[SYSTEM BLOCK]: System info", [], [])
        )
        text, _ = await _run_message(bot=bot)
        assert "[SYSTEM BLOCK" not in text


# ── Hippocampus Recall ────────────────────────────────────

class TestHippocampusRecall:
    @pytest.mark.asyncio
    async def test_includes_recent_topics(self):
        bot = _mock_bot()
        ctx_obj = MagicMock()
        ctx_obj.recent_topics = ["python", "AI"]
        ctx_obj.user_preferences = None
        ctx_obj.conversation_summary = None
        bot.hippocampus.early_recall.return_value = ctx_obj
        text, _ = await _run_message(bot=bot)
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_includes_user_preferences(self):
        bot = _mock_bot()
        ctx_obj = MagicMock()
        ctx_obj.recent_topics = None
        ctx_obj.user_preferences = "Dark mode, casual tone"
        ctx_obj.conversation_summary = None
        bot.hippocampus.early_recall.return_value = ctx_obj
        text, _ = await _run_message(bot=bot)
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_includes_conversation_summary(self):
        bot = _mock_bot()
        ctx_obj = MagicMock()
        ctx_obj.recent_topics = None
        ctx_obj.user_preferences = None
        ctx_obj.conversation_summary = "We talked about AI safety"
        bot.hippocampus.early_recall.return_value = ctx_obj
        text, _ = await _run_message(bot=bot)
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_recall_error_handled(self):
        bot = _mock_bot()
        bot.hippocampus.early_recall.side_effect = Exception("recall broke")
        text, _ = await _run_message(bot=bot)
        assert isinstance(text, str)


# ── System Prompt ─────────────────────────────────────────

class TestSystemPrompt:
    @pytest.mark.asyncio
    async def test_system_prompt_error_handled(self):
        from src.web.web_chat_handler import handle_web_message
        bot = _mock_bot()
        with patch("src.web.web_chat_handler.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.side_effect = Exception("prompt error")
            with patch("src.bot.integrity_auditor.audit_response", new_callable=AsyncMock):
                with patch("src.bot.globals") as mg:
                    mg.activity_log = []
                    text, _ = await handle_web_message(bot, "hi", "u1", "Alice")
        assert isinstance(text, str)


# ── Preprocessor ──────────────────────────────────────────

class TestPreprocessor:
    @pytest.mark.asyncio
    async def test_preprocessor_adds_context(self):
        import sys
        from src.web.web_chat_handler import handle_web_message
        bot = _mock_bot()

        mock_analysis = MagicMock()
        mock_analysis.context_injection = "extra context"
        mock_preprocessor_instance = MagicMock()
        mock_preprocessor_instance.analyze = AsyncMock(return_value=mock_analysis)

        # Create a fake module for the local import to resolve
        mock_unified_module = MagicMock()
        mock_unified_module.UnifiedPreProcessor.return_value = mock_preprocessor_instance

        with patch("src.web.web_chat_handler.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = ""
            with patch.dict(sys.modules, {"src.preprocessors": MagicMock(), "src.preprocessors.unified": mock_unified_module}):
                with patch("src.bot.integrity_auditor.audit_response", new_callable=AsyncMock):
                    with patch("src.bot.globals") as mg:
                        mg.activity_log = []
                        text, _ = await handle_web_message(bot, "hi", "u1", "Alice")
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_preprocessor_error_handled(self):
        import sys
        from src.web.web_chat_handler import handle_web_message
        bot = _mock_bot()

        with patch("src.web.web_chat_handler.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = ""
            # Import will fail gracefully since preprocessor is in a try block
            with patch.dict(sys.modules, {"src.preprocessors": None, "src.preprocessors.unified": None}):
                with patch("src.bot.integrity_auditor.audit_response", new_callable=AsyncMock):
                    with patch("src.bot.globals") as mg:
                        mg.activity_log = []
                        text, _ = await handle_web_message(bot, "hi", "u1", "Alice")
        assert isinstance(text, str)


# ── Cognition Engine Results ──────────────────────────────

class TestCognitionResults:
    @pytest.mark.asyncio
    async def test_tuple_3_result(self):
        bot = _mock_bot()
        bot.cognition.process = AsyncMock(return_value=("response", [Path("/tmp/file.txt")]))
        bot.cognition.process = AsyncMock(return_value=("response", [Path("/tmp/file.txt")]))
        text, files = await _run_message(bot=bot)
        assert text == "response"
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_tuple_2_result(self):
        bot = _mock_bot()
        bot.cognition.process = AsyncMock(return_value=("response", []))
        bot.cognition.process = AsyncMock(return_value=("response", []))
        text, files = await _run_message(bot=bot)
        assert text == "response"

    @pytest.mark.asyncio
    async def test_tuple_1_result(self):
        bot = _mock_bot()
        bot.cognition.process = AsyncMock(return_value=("response",))
        bot.cognition.process = AsyncMock(return_value=("response",))
        text, files = await _run_message(bot=bot)
        assert text == "response"
        assert files == []

    @pytest.mark.asyncio
    async def test_string_result(self):
        bot = _mock_bot()
        bot.cognition.process = AsyncMock(return_value="just a string")
        bot.cognition.process = AsyncMock(return_value="just a string")
        text, files = await _run_message(bot=bot)
        assert text == "just a string"
        assert files == []

    @pytest.mark.asyncio
    async def test_cognition_error(self):
        from src.web.web_chat_handler import handle_web_message
        bot = _mock_bot()
        bot.cognition.process = AsyncMock(side_effect=Exception("engine exploded"))
        bot.cognition.process = AsyncMock(side_effect=Exception("engine exploded"))
        with patch("src.web.web_chat_handler.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = ""
            text, files = await handle_web_message(bot, "hi", "u1", "Alice")
        assert "error" in text.lower()
        assert files == []


# ── Post-Processing ───────────────────────────────────────

class TestPostProcessing:
    @pytest.mark.asyncio
    async def test_hippocampus_observe_called(self):
        bot = _mock_bot()
        await _run_message(bot=bot)
        bot.hippocampus.observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_processing_error_handled(self):
        bot = _mock_bot()
        bot.hippocampus.observe = AsyncMock(side_effect=Exception("observe failed"))
        text, _ = await _run_message(bot=bot)
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_integrity_audit_error_handled(self):
        from src.web.web_chat_handler import handle_web_message
        bot = _mock_bot()
        with patch("src.web.web_chat_handler.PromptManager") as MockPM:
            MockPM.return_value.get_system_prompt.return_value = ""
            with patch("src.bot.integrity_auditor.audit_response", new_callable=AsyncMock, side_effect=Exception("audit error")):
                with patch("src.bot.globals") as mg:
                    mg.activity_log = []
                    text, _ = await handle_web_message(bot, "hi", "u1", "Alice")
        assert isinstance(text, str)


# ── Prompt Manager Singleton ──────────────────────────────

class TestPromptManager:
    def test_get_prompt_manager_creates_singleton(self):
        import src.web.web_chat_handler as mod
        with patch("src.web.web_chat_handler.PromptManager") as MockPM:
            MockPM.return_value = MagicMock()
            pm1 = mod._get_prompt_manager()
            pm2 = mod._get_prompt_manager()
            assert pm1 is pm2
            MockPM.assert_called_once()
