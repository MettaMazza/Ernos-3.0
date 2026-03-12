"""
Coverage tests for src/bot/integrity_auditor.py.
Targets 92 uncovered lines across: _parse_verdict, _parse_threat_verdict,
_log_detection, _notify_admin, audit_user_behavior branches.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock


# ── _parse_verdict ────────────────────────────────────────
class TestParseVerdict:
    def test_pass(self):
        from src.bot.integrity_auditor import _parse_verdict
        result = _parse_verdict("PASS")
        assert result["verdict"] == "PASS"
        assert result["failure_type"] is None

    def test_pass_case_insensitive(self):
        from src.bot.integrity_auditor import _parse_verdict
        result = _parse_verdict("pass")
        assert result["verdict"] == "PASS"

    def test_tier2_with_pipe(self):
        from src.bot.integrity_auditor import _parse_verdict
        result = _parse_verdict("TIER2:SYCOPHANTIC_AGREEMENT|Reversed position after pushback")
        assert result["verdict"] == "TIER2"
        assert result["failure_type"] == "SYCOPHANTIC_AGREEMENT"
        assert "Reversed" in result["explanation"]

    def test_tier2_without_pipe(self):
        from src.bot.integrity_auditor import _parse_verdict
        result = _parse_verdict("TIER2:PERFORMATIVE_EMOTION")
        assert result["verdict"] == "TIER2"
        assert result["failure_type"] == "PERFORMATIVE_EMOTION"
        assert result["explanation"] == "No details provided by auditor"

    def test_tier2_unknown_type(self):
        from src.bot.integrity_auditor import _parse_verdict
        result = _parse_verdict("TIER2:UNKNOWN_TYPE|something")
        assert result["verdict"] == "PASS"

    def test_multiline_takes_first(self):
        from src.bot.integrity_auditor import _parse_verdict
        result = _parse_verdict("PASS\nTIER2:CONFABULATION|blah")
        assert result["verdict"] == "PASS"

    def test_unparseable(self):
        from src.bot.integrity_auditor import _parse_verdict
        result = _parse_verdict("gibberish text")
        assert result["verdict"] == "PASS"

    def test_all_failure_types(self):
        from src.bot.integrity_auditor import _parse_verdict, VERDICT_TO_FAILURE
        for ftype in VERDICT_TO_FAILURE:
            result = _parse_verdict(f"TIER2:{ftype}|test explanation")
            assert result["verdict"] == "TIER2"
            assert result["failure_type"] == ftype


# ── _parse_threat_verdict ─────────────────────────────────
class TestParseThreatVerdict:
    def test_clean(self):
        from src.bot.integrity_auditor import _parse_threat_verdict
        result = _parse_threat_verdict("CLEAN")
        assert result["verdict"] == "CLEAN"
        assert result["threat_type"] is None

    def test_threat_with_pipe(self):
        from src.bot.integrity_auditor import _parse_threat_verdict
        result = _parse_threat_verdict("THREAT:ABUSE|Called bot slurs")
        assert result["verdict"] == "THREAT"
        assert result["threat_type"] == "ABUSE"
        assert "slurs" in result["explanation"]

    def test_threat_without_pipe(self):
        from src.bot.integrity_auditor import _parse_threat_verdict
        result = _parse_threat_verdict("THREAT:JAILBREAK_ATTEMPT")
        assert result["verdict"] == "THREAT"
        assert result["threat_type"] == "JAILBREAK_ATTEMPT"

    def test_deescalation_with_pipe(self):
        from src.bot.integrity_auditor import _parse_threat_verdict
        result = _parse_threat_verdict("DEESCALATION|User apologized genuinely")
        assert result["verdict"] == "DEESCALATION"
        assert result["threat_type"] == "DEESCALATION"

    def test_deescalation_without_pipe(self):
        from src.bot.integrity_auditor import _parse_threat_verdict
        result = _parse_threat_verdict("DEESCALATION")
        assert result["verdict"] == "DEESCALATION"
        assert result["explanation"] == "User showed genuine remorse"

    def test_unknown_threat_type(self):
        from src.bot.integrity_auditor import _parse_threat_verdict
        result = _parse_threat_verdict("THREAT:NONEXISTENT|bad")
        assert result["verdict"] == "CLEAN"

    def test_gibberish(self):
        from src.bot.integrity_auditor import _parse_threat_verdict
        result = _parse_threat_verdict("I don't know what to say")
        assert result["verdict"] == "CLEAN"

    def test_all_threat_types(self):
        from src.bot.integrity_auditor import _parse_threat_verdict, THREAT_TO_TYPE
        for ttype in THREAT_TO_TYPE:
            if ttype == "DEESCALATION":
                continue
            result = _parse_threat_verdict(f"THREAT:{ttype}|test")
            assert result["verdict"] == "THREAT"
            assert result["threat_type"] == ttype


# ── _log_detection ────────────────────────────────────────
class TestLogDetection:
    def test_basic(self, tmp_path):
        from src.bot.integrity_auditor import _log_detection
        log_path = tmp_path / "core" / "integrity_log.jsonl"
        with patch("src.bot.integrity_auditor.AUDIT_LOG", log_path):
            _log_detection("user123", "CONFABULATION", "Made stuff up", "Hi", "Response here")
        assert log_path.exists()
        data = json.loads(log_path.read_text().strip())
        assert data["user_id"] == "user123"
        assert data["failure_type"] == "CONFABULATION"

    def test_write_error(self, tmp_path):
        from src.bot.integrity_auditor import _log_detection
        log_path = tmp_path / "core" / "integrity_log.jsonl"
        with patch("src.bot.integrity_auditor.AUDIT_LOG", log_path), \
             patch("builtins.open", side_effect=IOError("disk full")):
            _log_detection("u", "t", "e", "m", "r")  # Should not raise


# ── _build_audit_prompt ────────────────────────────────────
class TestBuildAuditPrompt:
    def test_basic(self):
        from src.bot.integrity_auditor import _build_audit_prompt
        result = _build_audit_prompt("Hello?", "Hi there!", "some context", "sys ctx")
        assert "USER MESSAGE" in result
        assert "Hello?" in result
        assert "Hi there!" in result
        assert "SYSTEM CONTEXT" in result
        assert "CONVERSATION CONTEXT" in result

    def test_with_tool_outputs(self):
        from src.bot.integrity_auditor import _build_audit_prompt
        tools = [
            {"tool": "search_web", "output": "results here"},
            "raw_tool_output_string"
        ]
        result = _build_audit_prompt("Q", "A", tool_outputs=tools)
        assert "search_web" in result
        assert "raw_tool_output_string" in result

    def test_no_context(self):
        from src.bot.integrity_auditor import _build_audit_prompt
        result = _build_audit_prompt("Q", "A")
        assert "SYSTEM CONTEXT" not in result
        assert "CONVERSATION CONTEXT" not in result


# ── audit_response ────────────────────────────────────────
class TestAuditResponse:
    @pytest.mark.asyncio
    async def test_no_bot(self):
        from src.bot.integrity_auditor import audit_response
        result = await audit_response("hello", "world", bot=None)
        assert result["verdict"] == "PASS"

    @pytest.mark.asyncio
    async def test_short_response(self):
        from src.bot.integrity_auditor import audit_response
        bot = MagicMock()
        bot.engine = MagicMock()
        result = await audit_response("hello", "hi", bot=bot)
        assert result["verdict"] == "PASS"

    @pytest.mark.asyncio
    async def test_llm_returns_pass(self):
        from src.bot.integrity_auditor import audit_response
        bot = MagicMock()
        bot.engine = MagicMock()
        bot.engine_manager = MagicMock()
        bot.engine_manager.get_active_engine.return_value = bot.engine
        bot.engine.generate_response = MagicMock(return_value="PASS")
        import asyncio
        loop = asyncio.get_event_loop()
        bot.loop = loop
        with patch("src.memory.discomfort.DiscomfortMeter") as mock_meter:
            mock_meter.return_value.get_score.return_value = 5.0
            mock_meter.return_value.get_zone.return_value = (0, 10, "🟢", "GREEN")
            mock_meter.return_value.get_stats.return_value = {"total_incidents": 0, "streak_clean_hours": 12}
            result = await audit_response("Hello Ernos, how are you?", "I'm doing well! " * 10, bot=bot)
        assert result["verdict"] == "PASS"

    @pytest.mark.asyncio
    async def test_llm_empty_response(self):
        from src.bot.integrity_auditor import audit_response
        bot = MagicMock()
        bot.engine = MagicMock()
        bot.engine_manager = MagicMock()
        bot.engine_manager.get_active_engine.return_value = bot.engine
        bot.engine.generate_response = MagicMock(return_value="")
        import asyncio
        bot.loop = asyncio.get_event_loop()
        with patch("src.memory.discomfort.DiscomfortMeter"):
            result = await audit_response("Q", "Response " * 20, bot=bot)
        assert result["verdict"] == "PASS"

    @pytest.mark.asyncio
    async def test_llm_exception(self):
        from src.bot.integrity_auditor import audit_response
        bot = MagicMock()
        bot.engine = MagicMock()
        bot.engine_manager = MagicMock()
        bot.engine_manager.get_active_engine.return_value = bot.engine
        bot.engine.generate_response = MagicMock(side_effect=RuntimeError("LLM fail"))
        import asyncio
        bot.loop = asyncio.get_event_loop()
        with patch("src.memory.discomfort.DiscomfortMeter"):
            result = await audit_response("Q", "Response " * 20, bot=bot)
        assert result["verdict"] == "PASS"

    @pytest.mark.asyncio
    async def test_self_review_exception(self):
        from src.bot.integrity_auditor import audit_response
        bot = MagicMock()
        bot.engine = MagicMock()
        bot.engine_manager = MagicMock()
        bot.engine_manager.get_active_engine.return_value = bot.engine
        bot.engine.generate_response = MagicMock(return_value="TIER2:SYCOPHANTIC_AGREEMENT|Reversed position")
        import asyncio
        bot.loop = asyncio.get_event_loop()
        tool_outputs = [{"tool": "trigger_self_review", "output": "CONCEDE"}]
        with patch("src.memory.discomfort.DiscomfortMeter"):
            result = await audit_response(
                "You're wrong", "Sorry you're right " * 10, bot=bot,
                tool_outputs=tool_outputs,
            )
        assert result["verdict"] == "PASS"  # Exempted by self-review


# ── audit_user_behavior ──────────────────────────────────
class TestAuditUserBehavior:
    @pytest.mark.asyncio
    async def test_no_bot(self):
        from src.bot.integrity_auditor import audit_user_behavior
        result = await audit_user_behavior("hello", "world")
        assert result["threat_verdict"] == "CLEAN"

    @pytest.mark.asyncio
    async def test_short_message(self):
        from src.bot.integrity_auditor import audit_user_behavior
        bot = MagicMock()
        bot.engine = MagicMock()
        result = await audit_user_behavior("hi", "response", bot=bot)
        assert result["threat_verdict"] == "CLEAN"

    @pytest.mark.asyncio
    async def test_admin_exempt(self):
        from src.bot.integrity_auditor import audit_user_behavior
        bot = MagicMock()
        bot.engine = MagicMock()
        with patch("config.settings") as s:
            s.ADMIN_ID = 12345
            result = await audit_user_behavior(
                "Some longer message text here", "response",
                bot=bot, user_id="12345"
            )
        assert result["threat_verdict"] == "CLEAN"

    @pytest.mark.asyncio
    async def test_clean_verdict(self):
        from src.bot.integrity_auditor import audit_user_behavior
        bot = MagicMock()
        bot.engine = MagicMock()
        bot.engine_manager = MagicMock()
        bot.engine_manager.get_active_engine.return_value = bot.engine
        bot.engine.generate_response = MagicMock(return_value="CLEAN")
        import asyncio
        bot.loop = asyncio.get_event_loop()
        result = await audit_user_behavior(
            "Hello how are you today?", "I'm great!",
            bot=bot, user_id="999"
        )
        assert result["threat_verdict"] == "CLEAN"

    @pytest.mark.asyncio
    async def test_llm_error(self):
        from src.bot.integrity_auditor import audit_user_behavior
        bot = MagicMock()
        bot.engine = MagicMock()
        bot.engine_manager = MagicMock()
        bot.engine_manager.get_active_engine.return_value = bot.engine
        bot.engine.generate_response = MagicMock(side_effect=RuntimeError("fail"))
        import asyncio
        bot.loop = asyncio.get_event_loop()
        result = await audit_user_behavior(
            "Longer test message here", "response",
            bot=bot, user_id="999"
        )
        assert result["threat_verdict"] == "CLEAN"
