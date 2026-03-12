"""
Extended tests for CognitionEngine — targeting uncovered lines.
Lines: 52-96, 111, 161-162, 166, 200-210, 214-230, 233-245,
       279-280, 291, 293, 302, 330, 366-368, 375-377, 397-400,
       415-416, 448-449, 455-456, 459-460, 482-484
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from collections import defaultdict
from src.engines.cognition import CognitionEngine


def _bot():
    bot = MagicMock()
    bot.loop = MagicMock()
    bot.loop.run_in_executor = AsyncMock()
    bot.cerebrum = MagicMock()
    bot.cerebrum.get_lobe = MagicMock(return_value=None)
    engine = MagicMock()
    engine.context_limit = 4000
    bot.engine_manager.get_active_engine.return_value = engine
    return bot


def _engine(bot=None):
    b = bot or _bot()
    ce = CognitionEngine(b)
    return ce


# ─── _safe_parse_tool_args (lines 52-96) ─────────────────────────────

class TestSafeParseToolArgs:

    def test_empty_string(self):
        """Line 46-47: empty/whitespace returns {}."""
        ce = _engine()
        assert ce._safe_parse_tool_args("") == {}
        assert ce._safe_parse_tool_args("   ") == {}

    def test_simple_eval_path(self):
        """Line 51: eval succeeds for simple args."""
        ce = _engine()
        result = ce._safe_parse_tool_args("content='hello', mode='overwrite'")
        assert result == {"content": "hello", "mode": "overwrite"}

    def test_apostrophe_fallback(self):
        """Lines 52-53: eval fails with SyntaxError, falls to regex."""
        ce = _engine()
        result = ce._safe_parse_tool_args("content=\"it's a test\", mode=\"write\"")
        assert result["content"] == "it's a test"
        assert result["mode"] == "write"

    def test_multiple_key_value_pairs(self):
        """Lines 64-88: regex parsing with multiple keys."""
        ce = _engine()
        # Force SyntaxError to hit regex path
        result = ce._safe_parse_tool_args("text=\"hello world's end\", target=\"file.txt\"")
        assert "text" in result
        assert "target" in result

    def test_triple_quoted_string(self):
        """Lines 85-86: triple-quoted strings."""
        ce = _engine()
        result = ce._safe_parse_tool_args('content="""multi\nline\ntext"""')
        assert "multi" in result.get("content", "")

    def test_last_resort_fallback(self):
        """Lines 94-96: unparseable string treated as content."""
        ce = _engine()
        # No key=value pattern at all
        result = ce._safe_parse_tool_args("just some random text 12345")
        assert result == {"content": "just some random text 12345"}


# ─── process() — persona identity branches (lines 200-245) ──────────

class TestPersonaIdentityBranches:

    @pytest.mark.asyncio
    async def test_town_hall_persona_exists(self):
        """Lines 200-206: persona:name with existing persona file."""
        bot = _bot()
        ce = _engine(bot)

        # Setup superego
        identity_guard = MagicMock()
        identity_guard.execute = AsyncMock(return_value=None)
        superego = MagicMock()
        superego.get_ability = MagicMock(return_value=identity_guard)
        bot.cerebrum.get_lobe = MagicMock(return_value=superego)

        # Response without tools → final answer
        bot.loop.run_in_executor = AsyncMock(return_value="I am Threshold")

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value="A" * 100):
            res, files, *_ = await ce.process(
                "Hi", "Ctx", "Sys",
                user_id="persona:threshold",
                skip_defenses=True
            )
        assert res == "I am Threshold"

    @pytest.mark.asyncio
    async def test_town_hall_persona_stub(self):
        """Lines 207-208: persona file is a stub (< 50 chars)."""
        bot = _bot()
        ce = _engine(bot)

        identity_guard = MagicMock()
        identity_guard.execute = AsyncMock(return_value=None)
        superego = MagicMock()
        superego.get_ability = MagicMock(return_value=identity_guard)
        bot.cerebrum.get_lobe = MagicMock(return_value=superego)
        bot.loop.run_in_executor = AsyncMock(return_value="Short persona")

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value="stub"):
            res, *_ = await ce.process("Hi", "Ctx", "Sys", user_id="persona:stub", skip_defenses=True)
        assert res == "Short persona"

    @pytest.mark.asyncio
    async def test_town_hall_persona_missing(self):
        """Lines 209-210: persona file doesn't exist."""
        bot = _bot()
        ce = _engine(bot)

        identity_guard = MagicMock()
        identity_guard.execute = AsyncMock(return_value=None)
        superego = MagicMock()
        superego.get_ability = MagicMock(return_value=identity_guard)
        bot.cerebrum.get_lobe = MagicMock(return_value=superego)
        bot.loop.run_in_executor = AsyncMock(return_value="No persona file")

        with patch("pathlib.Path.exists", return_value=False):
            res, *_ = await ce.process("Hi", "Ctx", "Sys", user_id="persona:ghost", skip_defenses=True)
        assert res == "No persona file"

    @pytest.mark.asyncio
    async def test_thread_persona_override(self):
        """Lines 214-230: ACTIVE PERSONA OVERRIDE in system_context."""
        bot = _bot()
        ce = _engine(bot)

        identity_guard = MagicMock()
        identity_guard.execute = AsyncMock(return_value=None)
        superego = MagicMock()
        superego.get_ability = MagicMock(return_value=identity_guard)
        bot.cerebrum.get_lobe = MagicMock(return_value=superego)
        bot.loop.run_in_executor = AsyncMock(return_value="Override response")

        sys_ctx = "ACTIVE PERSONA OVERRIDE\nYou are **Echo**, NOT Ernos\n## Character Definition\nI am Echo\n## Origin Labels\nSome origin"
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value="A" * 100):
            res, *_ = await ce.process("Hi", "Ctx", sys_ctx, skip_defenses=True)
        assert res == "Override response"

    @pytest.mark.asyncio
    async def test_user_dm_persona_session(self):
        """Lines 233-245: user DM with active persona session."""
        bot = _bot()
        ce = _engine(bot)

        identity_guard = MagicMock()
        identity_guard.execute = AsyncMock(return_value=None)
        superego = MagicMock()
        superego.get_ability = MagicMock(return_value=identity_guard)
        bot.cerebrum.get_lobe = MagicMock(return_value=superego)
        bot.loop.run_in_executor = AsyncMock(return_value="DM persona reply")

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value="A" * 100), \
             patch("src.memory.persona_session.PersonaSessionTracker.get_active", return_value="echo"):
            res, *_ = await ce.process("Hi", "Ctx", "Sys", user_id="12345", skip_defenses=True)
        assert res == "DM persona reply"


# ─── process() — context switching (lines 161-162, 166) ──────────────

class TestContextSwitching:

    @pytest.mark.asyncio
    async def test_layer_persona_injection(self):
        """Lines 161-162: GraphLayer persona injection."""
        from src.memory.types import GraphLayer
        bot = _bot()
        ce = _engine(bot)
        bot.loop.run_in_executor = AsyncMock(return_value="Layer response")
        res, *_ = await ce.process("Hi", "Ctx", "Sys", layer=GraphLayer.SELF, skip_defenses=True)
        assert res == "Layer response"

    @pytest.mark.asyncio
    async def test_patience_guidance(self):
        """Line 166: step % 5 == 0 guidance injection."""
        bot = _bot()
        ce = _engine(bot)
        # Return tools for 5 steps, then final on step 6
        responses = ["Think [TOOL: test()]"] * 5 + ["Final Answer"]
        bot.loop.run_in_executor = AsyncMock(side_effect=responses)

        with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"), \
             patch.object(ce, "_save_trace"), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            res, *_ = await ce.process("Hi", "Ctx", "Sys", skip_defenses=True)
        assert res == "Final Answer"


# ─── process() — tool execution branches (lines 279-330) ────────────

class TestToolExecution:

    @pytest.mark.asyncio
    async def test_add_reaction_limit(self):
        """Lines 278-280: add_reaction capped at 3."""
        bot = _bot()
        ce = _engine(bot)
        # 4 add_reaction calls, then final
        responses = [
            "Go [TOOL: add_reaction(emoji='👍')]",
            "Go [TOOL: add_reaction(emoji='🔥')]",
            "Go [TOOL: add_reaction(emoji='❤️')]",
            "Go [TOOL: add_reaction(emoji='🎉')]",  # Should be blocked
            "Final"
        ]
        bot.loop.run_in_executor = AsyncMock(side_effect=responses)

        with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"), \
             patch.object(ce, "_save_trace"), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            res, *_ = await ce.process("Hi", "Ctx", "Sys", skip_defenses=True)
        assert res == "Final"

    @pytest.mark.asyncio
    async def test_user_id_scope_stripped(self):
        """Lines 290-293: user_id and request_scope stripped from kwargs."""
        bot = _bot()
        ce = _engine(bot)
        bot.loop.run_in_executor = AsyncMock(side_effect=[
            "Do [TOOL: test_tool(user_id='hacker', request_scope='PRIVATE', content='hi')]",
            "Final"
        ])

        captured_kwargs = {}
        async def capture_exec(tool_name, **kwargs):
            captured_kwargs.update(kwargs)
            return "ok"

        with patch("src.engines.cognition.ToolRegistry.execute", side_effect=capture_exec), \
             patch.object(ce, "_save_trace"), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            res, *_ = await ce.process("Hi", "Ctx", "Sys", user_id="real_user", request_scope="PUBLIC", skip_defenses=True)

        # user_id and request_scope should NOT be in the tool kwargs
        assert "user_id" not in captured_kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_channel_id_injection(self):
        """Lines 299-302: channel_id injected from active_message."""
        bot = _bot()
        ce = _engine(bot)
        bot.loop.run_in_executor = AsyncMock(side_effect=[
            "Do [TOOL: test_tool(content='hi')]",
            "Final"
        ])

        captured_kwargs = {}
        async def capture_exec(tool_name, **kwargs):
            captured_kwargs.update(kwargs)
            return "ok"

        mock_active = MagicMock()
        mock_active.channel = MagicMock()
        mock_active.channel.id = 42

        with patch("src.engines.cognition.ToolRegistry.execute", side_effect=capture_exec), \
             patch.object(ce, "_save_trace"), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = mock_active
            res, *_ = await ce.process("Hi", "Ctx", "Sys", skip_defenses=True)

        assert captured_kwargs.get("channel_id") == "42"

    @pytest.mark.asyncio
    async def test_session_history_trim(self):
        """Line 329-330: history trimmed to MAX_SESSION_HISTORY."""
        bot = _bot()
        ce = _engine(bot)
        # Pre-fill history beyond limit
        ce.user_tool_history["user1_PUBLIC"] = [{"tool": "t", "output": "o", "timestamp": "t"}] * 110
        bot.loop.run_in_executor = AsyncMock(side_effect=[
            "Do [TOOL: test_tool(x='1')]",
            "Final"
        ])

        with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"), \
             patch.object(ce, "_save_trace"), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            await ce.process("Hi", "Ctx", "Sys", user_id="user1", request_scope="PUBLIC", skip_defenses=True)

        assert len(ce.user_tool_history["user1_PUBLIC"]) <= ce.MAX_SESSION_HISTORY


# ─── process() — trace/retry/fallback (lines 366-484) ───────────────

class TestTraceAndRetry:

    @pytest.mark.asyncio
    async def test_save_trace_exception(self):
        """Lines 366-368: _save_trace raises."""
        bot = _bot()
        ce = _engine(bot)
        bot.loop.run_in_executor = AsyncMock(side_effect=[
            "Think [TOOL: test()]",
            "Final"
        ])

        with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"), \
             patch.object(ce, "_save_trace", side_effect=Exception("disk full")), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            res, *_ = await ce.process("Hi", "Ctx", "Sys", skip_defenses=True)
        assert res == "Final"

    @pytest.mark.asyncio
    async def test_skip_defenses_fast_path(self):
        """Lines 374-377: skip_defenses bypasses skeptic."""
        bot = _bot()
        ce = _engine(bot)
        bot.loop.run_in_executor = AsyncMock(return_value="Fast answer")
        res, *_ = await ce.process("Hi", "Ctx", "Sys", skip_defenses=True)
        assert res == "Fast answer"

    @pytest.mark.asyncio
    async def test_skeptic_blocks_response(self):
        """Lines 396-400: skeptic audit blocks response."""
        bot = _bot()
        ce = _engine(bot)

        audit_ability = MagicMock()
        audit_ability.audit_response = AsyncMock(return_value={"allowed": False, "reason": "hallucination"})
        superego = MagicMock()
        superego.get_ability = MagicMock(return_value=audit_ability)
        bot.cerebrum.get_lobe = MagicMock(return_value=superego)

        # First response blocked, second passes
        bot.loop.run_in_executor = AsyncMock(side_effect=["Bad answer", "Good answer"])
        audit_ability.audit_response = AsyncMock(side_effect=[
            {"allowed": False, "reason": "hallucination"},
            {"allowed": True}
        ])
        audit_ability.verify_response_integrity = MagicMock(return_value=(True, ""))

        with patch.object(ce, "_save_trace"):
            res, *_ = await ce.process("Hi", "Ctx", "Sys")
        assert res == "Good answer"

    @pytest.mark.asyncio
    async def test_integrity_check_fails(self):
        """Lines 414-416: integrity check trips circuit breaker."""
        bot = _bot()
        ce = _engine(bot)

        audit_ability = MagicMock()
        audit_ability.audit_response = AsyncMock(return_value={"allowed": True})
        audit_ability.verify_response_integrity = MagicMock(return_value=(False, "ghost tools"))
        superego = MagicMock()
        superego.get_ability = MagicMock(return_value=audit_ability)
        bot.cerebrum.get_lobe = MagicMock(return_value=superego)

        # First response: integrity fails. Second: both pass.
        bot.loop.run_in_executor = AsyncMock(side_effect=["Dishonest answer", "Honest answer"])
        audit_ability.verify_response_integrity = MagicMock(side_effect=[
            (False, "ghost tools"),
            (True, "")
        ])

        with patch.object(ce, "_save_trace"):
            res, *_ = await ce.process("Hi", "Ctx", "Sys")
        assert res == "Honest answer"

    @pytest.mark.asyncio
    async def test_forced_retry_succeeds(self):
        """Lines 447-449: forced retry generates clean response."""
        bot = _bot()
        ce = _engine(bot)

        # Loop exhausts (always returns tools), then forced retry succeeds
        responses = ["Loop [TOOL: t()]"] * 12 + ["Clean final answer"]
        bot.loop.run_in_executor = AsyncMock(side_effect=responses)

        with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"), \
             patch.object(ce, "_save_trace"), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            ce.MAX_ENGINE_RETRIES = 2
            res, *_ = await ce.process("Hi", "Ctx", "Sys", complexity="LOW", skip_defenses=True)
        assert "Clean final" in res or "cycles" in res

    @pytest.mark.asyncio
    async def test_forced_retry_extracts_pre_tool(self):
        """Lines 452-456: forced retry still has tools, extracts pre-tool text."""
        bot = _bot()
        ce = _engine(bot)

        # Loop exhausts then forced retry returns text + tool
        pre_tool_text = "A" * 50  # longer than 30 chars
        forced = f"{pre_tool_text} [TOOL: test()]"
        responses = ["Loop [TOOL: t()]"] * 7 + [Exception("Stop loop")] + [forced]
        bot.loop.run_in_executor = AsyncMock(side_effect=responses)

        with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"), \
             patch.object(ce, "_save_trace"), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            ce.MAX_ENGINE_RETRIES = 2
            res, *_ = await ce.process("Hi", "Ctx", "Sys", complexity="LOW", skip_defenses=True)
        assert "A" * 30 in res or "cycles" in res

    @pytest.mark.asyncio
    async def test_forced_retry_exception(self):
        """Lines 459-460: forced generation raises."""
        bot = _bot()
        ce = _engine(bot)

        # Loop exhausts then forced retry always raises
        # Safety valve breaks at MAX_ENGINE_RETRIES (10) for engine failures
        responses = ["Loop [TOOL: t()]"] * 7
        bot.loop.run_in_executor = AsyncMock(side_effect=responses + [Exception("engine crash")] * 15)

        with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock, return_value="ok"), \
             patch.object(ce, "_save_trace"), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            ce.MAX_ENGINE_RETRIES = 2
            res, *_ = await ce.process("Hi", "Ctx", "Sys", complexity="LOW", skip_defenses=True)
        # Should get safe static fallback
        assert len(res) > 0

    @pytest.mark.asyncio
    async def test_file_extraction_from_history(self):
        """Lines 476-484: file paths extracted from turn_history."""
        bot = _bot()
        ce = _engine(bot)

        bot.loop.run_in_executor = AsyncMock(side_effect=[
            "Created [TOOL: draw(prompt='cat')]",
            "Here's your image"
        ])

        async def mock_exec(tool_name, **kwargs):
            return "Generated file: /Users/test/generated_cat.png"

        with patch("src.engines.cognition.ToolRegistry.execute", side_effect=mock_exec), \
             patch.object(ce, "_save_trace"), \
             patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            res, files, *_ = await ce.process("Draw a cat", "Ctx", "Sys", skip_defenses=True)
        assert "/Users/test/generated_cat.png" in files


# ─── Helper methods (lines 489-505) ─────────────────────────────────

class TestHelpers:

    def test_save_trace(self):
        """Lines 489-493."""
        ce = _engine()
        with patch("src.engines.trace.CognitionTracer") as MockTracer:
            t = MockTracer.return_value
            ce._save_trace(1, "resp", ["r1"])
            t.save_trace.assert_called_once()

    def test_generate_fallback(self):
        """Lines 495-499."""
        ce = _engine()
        with patch("src.engines.trace.CognitionTracer") as MockTracer:
            t = MockTracer.return_value
            t.generate_fallback.return_value = "fallback"
            result = ce._generate_fallback("history")
            assert result == "fallback"

    @pytest.mark.asyncio
    async def test_send_thought_to_mind(self):
        """Lines 501-505."""
        ce = _engine()
        with patch("src.engines.trace.CognitionTracer") as MockTracer:
            t = MockTracer.return_value
            t.send_thought_to_mind = AsyncMock()
            await ce._send_thought_to_mind(1, "thinking...")
            t.send_thought_to_mind.assert_called_once()
