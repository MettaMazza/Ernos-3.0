"""
Phase 4 Coverage Tests — Mid-coverage modules (40–60%).

Modules: router.py, lifecycle.py, user_threat.py, recall_tools.py,
         integrity_auditor.py, skill_admin_tools.py,
         admin_moderation.py, admin_lifecycle.py.
"""
import asyncio
import json
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open, PropertyMock

import pytest

# ─────────────────────────────────────────────────────────────────────
# 1. ModelRouter (src/agents/router.py)
# ─────────────────────────────────────────────────────────────────────
from src.agents.router import ModelRouter, ModelProfile


class TestModelRouter:
    """Tests for ModelRouter — task routing, model registration, classification."""

    def setup_method(self):
        # Reset class-level state before each test
        ModelRouter._models = {}
        ModelRouter._routing_rules = {}
        ModelRouter._default_model = None

    # ── Registration ──────────────────────────────────────────────
    def test_register_model(self):
        p = ModelProfile(name="test", model_id="test:7b", strengths=["code_generation"])
        ModelRouter.register_model(p)
        assert "test" in ModelRouter._models

    def test_set_routing_rule(self):
        ModelRouter.set_routing_rule("deep_reasoning", "deep-model")
        assert ModelRouter._routing_rules["deep_reasoning"] == "deep-model"

    def test_set_default(self):
        ModelRouter.set_default("fallback")
        assert ModelRouter._default_model == "fallback"

    # ── classify_task ─────────────────────────────────────────────
    def test_classify_task_code(self):
        assert ModelRouter.classify_task("implement a function") == "code_generation"

    def test_classify_task_reasoning(self):
        assert ModelRouter.classify_task("let me think and analyze") == "deep_reasoning"

    def test_classify_task_unknown(self):
        assert ModelRouter.classify_task("xyzzy foobarbaz") == "general"

    def test_classify_task_creative(self):
        assert ModelRouter.classify_task("write me a poem") == "creative_writing"

    def test_classify_task_summarization(self):
        assert ModelRouter.classify_task("give me a brief overview") == "summarization"

    def test_classify_task_multiple_hits(self):
        # "search and analyze" hits web_search + deep_reasoning
        result = ModelRouter.classify_task("search and analyze this data")
        assert result in ("web_search", "deep_reasoning", "data_analysis")

    # ── route ─────────────────────────────────────────────────────
    def test_route_explicit_rule(self):
        p = ModelProfile(name="coder", model_id="c:1", strengths=[])
        ModelRouter.register_model(p)
        ModelRouter.set_routing_rule("code_generation", "coder")
        assert ModelRouter.route("implement a function") == "coder"

    def test_route_explicit_rule_model_not_registered(self):
        ModelRouter.set_routing_rule("code_generation", "nonexistent")
        result = ModelRouter.route("implement a function")
        # Falls through to other logic since model isn't registered
        assert result is None or result != "nonexistent"

    def test_route_prefer_speed(self):
        fast = ModelProfile(name="fast-m", model_id="f:1", strengths=[], speed="fast")
        slow = ModelProfile(name="slow-m", model_id="s:1", strengths=[], speed="slow")
        ModelRouter.register_model(fast)
        ModelRouter.register_model(slow)
        assert ModelRouter.route("anything", prefer_speed=True) == "fast-m"

    def test_route_low_complexity_prefers_fast(self):
        fast = ModelProfile(name="fast-m", model_id="f:1", strengths=[], speed="fast")
        ModelRouter.register_model(fast)
        assert ModelRouter.route("quick lookup", complexity=2) == "fast-m"

    def test_route_high_complexity_prefers_slow(self):
        slow = ModelProfile(name="slow-m", model_id="s:1", strengths=[], speed="slow")
        ModelRouter.register_model(slow)
        assert ModelRouter.route("complex analysis", complexity=9) == "slow-m"

    def test_route_match_by_strength(self):
        p = ModelProfile(name="writer", model_id="w:1", strengths=["creative_writing"])
        ModelRouter.register_model(p)
        assert ModelRouter.route("write a story", complexity=5) == "writer"

    def test_route_default_fallback(self):
        ModelRouter.set_default("default-model")
        result = ModelRouter.route("xyzzy foobarbaz", complexity=5)
        assert result == "default-model"

    def test_route_no_models_returns_none(self):
        assert ModelRouter.route("anything") is None

    # ── get_model_for_engine ──────────────────────────────────────
    def test_get_model_for_engine_no_bot(self):
        assert ModelRouter.get_model_for_engine("test") is None

    def test_get_model_for_engine_unknown_model(self):
        bot = MagicMock()
        bot.engine_manager.get_active_engine.return_value = "default-engine"
        result = ModelRouter.get_model_for_engine("unknown", bot)
        assert result == "default-engine"

    def test_get_model_for_engine_found(self):
        p = ModelProfile(name="test", model_id="test:7b", strengths=[])
        ModelRouter.register_model(p)
        bot = MagicMock()
        bot.engine_manager.get_engine.return_value = "specific-engine"
        result = ModelRouter.get_model_for_engine("test", bot)
        assert result == "specific-engine"

    def test_get_model_for_engine_engine_not_found(self):
        p = ModelProfile(name="test", model_id="test:7b", strengths=[])
        ModelRouter.register_model(p)
        bot = MagicMock()
        bot.engine_manager.get_engine.return_value = None
        bot.engine_manager.get_active_engine.return_value = "fallback-engine"
        result = ModelRouter.get_model_for_engine("test", bot)
        assert result == "fallback-engine"

    # ── get_routing_table ─────────────────────────────────────────
    def test_get_routing_table_empty(self):
        table = ModelRouter.get_routing_table()
        assert table == {"models": {}, "rules": {}, "default": None}

    def test_get_routing_table_populated(self):
        p = ModelProfile(name="m1", model_id="m:1", strengths=["code_generation"], speed="fast", cost="low", context_window=32768)
        ModelRouter.register_model(p)
        ModelRouter.set_routing_rule("code_generation", "m1")
        ModelRouter.set_default("m1")
        table = ModelRouter.get_routing_table()
        assert "m1" in table["models"]
        assert table["rules"]["code_generation"] == "m1"
        assert table["default"] == "m1"

    # ── auto_configure ────────────────────────────────────────────
    def test_auto_configure(self):
        ModelRouter.auto_configure()
        assert len(ModelRouter._models) >= 6
        assert "gemma3" in ModelRouter._models
        assert "gemini-flash" in ModelRouter._models
        assert ModelRouter._default_model == "gemma3"
        assert len(ModelRouter._routing_rules) >= 5

    def test_auto_configure_with_bot(self):
        bot = MagicMock()
        ModelRouter.auto_configure(bot=bot)
        assert len(ModelRouter._models) >= 6


# ─────────────────────────────────────────────────────────────────────
# 2. AgentLifecycle (src/agents/lifecycle.py)
# ─────────────────────────────────────────────────────────────────────
from src.agents.lifecycle import AgentLifecycle, AgentMetrics, AgentHealthCheck


class TestAgentLifecycle:
    """Tests for AgentLifecycle — metrics, health, dashboard."""

    def setup_method(self):
        self.lc = AgentLifecycle.get_instance()
        self.lc.reset_metrics()

    # ── Singleton ─────────────────────────────────────────────────
    def test_singleton(self):
        a = AgentLifecycle.get_instance()
        b = AgentLifecycle.get_instance()
        assert a is b

    # ── record_spawn ──────────────────────────────────────────────
    def test_record_spawn_basic(self):
        self.lc.record_spawn("a-1")
        assert self.lc._metrics.total_spawned == 1
        assert self.lc._metrics.current_concurrent == 1

    def test_record_spawn_updates_peak(self):
        self.lc.record_spawn("a-1")
        self.lc.record_spawn("a-2")
        assert self.lc._metrics.peak_concurrent == 2

    def test_record_spawn_depth_and_strategy(self):
        self.lc.record_spawn("a-1", depth=2, strategy="parallel")
        assert self.lc._metrics.agents_by_depth[2] == 1
        assert self.lc._metrics.agents_by_strategy["parallel"] == 1

    # ── record_completion ─────────────────────────────────────────
    def test_record_completion(self):
        self.lc.record_spawn("a-1")
        self.lc.record_completion("a-1", duration_ms=1000, tokens_used=50, tool_calls=3)
        assert self.lc._metrics.total_completed == 1
        assert self.lc._metrics.current_concurrent == 0
        assert self.lc._metrics.total_tokens_used == 50
        assert self.lc._metrics.total_tool_calls == 3

    def test_record_completion_concurrent_floor(self):
        # Don't go below 0
        self.lc.record_completion("a-1", duration_ms=500)
        assert self.lc._metrics.current_concurrent == 0

    # ── record_failure ────────────────────────────────────────────
    def test_record_failure(self):
        self.lc.record_spawn("a-1")
        self.lc.record_failure("a-1", "timeout_error", duration_ms=5000)
        assert self.lc._metrics.total_failed == 1
        assert self.lc._metrics.errors_by_type["timeout_error"] == 1
        assert self.lc._metrics.current_concurrent == 0

    # ── record_timeout ────────────────────────────────────────────
    def test_record_timeout(self):
        self.lc.record_spawn("a-1")
        self.lc.record_timeout("a-1", duration_ms=30000)
        assert self.lc._metrics.total_timed_out == 1
        assert self.lc._metrics.current_concurrent == 0

    # ── record_cancellation ───────────────────────────────────────
    def test_record_cancellation(self):
        self.lc.record_spawn("a-1")
        self.lc.record_cancellation("a-1")
        assert self.lc._metrics.total_cancelled == 1
        assert self.lc._metrics.current_concurrent == 0

    # ── health_check ──────────────────────────────────────────────
    @patch("src.agents.lifecycle.AgentSpawner", create=True)
    def test_health_check_healthy(self, _):
        check = self.lc.health_check()
        assert check.healthy is True
        assert check.warnings == []

    @patch("src.agents.lifecycle.AgentSpawner", create=True)
    def test_health_check_high_concurrent(self, _):
        for i in range(35):
            self.lc.record_spawn(f"a-{i}")
        check = self.lc.health_check()
        assert check.healthy is False
        assert any("High concurrent" in w for w in check.warnings)

    @patch("src.agents.lifecycle.AgentSpawner", create=True)
    def test_health_check_high_error_rate(self, _):
        for i in range(10):
            self.lc.record_spawn(f"a-{i}")
        for i in range(5):
            self.lc.record_failure(f"a-{i}", "err")
        check = self.lc.health_check()
        assert check.error_rate > 0

    @patch("src.agents.lifecycle.AgentSpawner", create=True)
    def test_health_check_slow_response(self, _):
        self.lc.record_spawn("a-1")
        self.lc.record_completion("a-1", duration_ms=70000)
        check = self.lc.health_check()
        assert any("Slow avg" in w for w in check.warnings)

    # ── get_metrics ───────────────────────────────────────────────
    def test_get_metrics(self):
        self.lc.record_spawn("a-1", depth=0, strategy="parallel")
        self.lc.record_completion("a-1", duration_ms=1000, tokens_used=100, tool_calls=5)
        m = self.lc.get_metrics()
        assert m["total_spawned"] == 1
        assert m["total_completed"] == 1
        assert m["success_rate"] == 1.0
        assert "agents_by_depth" in m
        assert "top_errors" in m

    # ── get_dashboard ─────────────────────────────────────────────
    @patch("src.agents.lifecycle.AgentSpawner", create=True)
    def test_get_dashboard(self, _):
        self.lc.record_spawn("a-1")
        self.lc.record_completion("a-1", duration_ms=500)
        dash = self.lc.get_dashboard()
        assert "Agent System Dashboard" in dash
        assert "HEALTHY" in dash

    @patch("src.agents.lifecycle.AgentSpawner", create=True)
    def test_get_dashboard_with_warnings(self, _):
        for i in range(35):
            self.lc.record_spawn(f"a-{i}")
        dash = self.lc.get_dashboard()
        assert "Warnings" in dash

    # ── reset_metrics ─────────────────────────────────────────────
    def test_reset_metrics(self):
        self.lc.record_spawn("a-1")
        self.lc.reset_metrics()
        assert self.lc._metrics.total_spawned == 0
        assert self.lc._recent_durations == []

    # ── _update_duration ──────────────────────────────────────────
    def test_update_duration_positive(self):
        self.lc._update_duration(1000)
        assert self.lc._metrics.avg_duration_ms == 1000

    def test_update_duration_zero_skipped(self):
        self.lc._update_duration(0)
        assert self.lc._metrics.avg_duration_ms == 0

    def test_update_duration_trimming(self):
        for i in range(600):
            self.lc._update_duration(100)
        assert len(self.lc._recent_durations) == self.lc._max_duration_history

    # ── Dataclasses ───────────────────────────────────────────────
    def test_agent_metrics_defaults(self):
        m = AgentMetrics()
        assert m.total_spawned == 0
        assert m.peak_concurrent == 0

    def test_agent_health_check_defaults(self):
        h = AgentHealthCheck()
        assert h.healthy is True
        assert h.warnings == []


# ─────────────────────────────────────────────────────────────────────
# 3. UserThreatMeter (src/memory/user_threat.py)
# ─────────────────────────────────────────────────────────────────────
from src.memory.user_threat import (
    UserThreatMeter, UserThreatState, THREAT_ZONES, THREAT_SEVERITY,
    THREAT_TERMINAL_THRESHOLD, DEESCALATION_COOLDOWN_HOURS,
)


class TestUserThreatMeter:
    """Tests for UserThreatMeter — threat scoring, decay, de-escalation, HUD."""

    def _make_meter(self):
        with patch.object(UserThreatMeter, '_load_all'):
            with patch.object(UserThreatMeter, '_save_all'):
                m = UserThreatMeter()
                m._states = {}
                return m

    # ── Basic state ───────────────────────────────────────────────
    def test_get_user_state_new(self):
        m = self._make_meter()
        s = m._get_user_state("user1")
        assert s.score == 0.0
        assert s.total_incidents == 0

    def test_get_user_state_existing(self):
        m = self._make_meter()
        m._states["user1"] = UserThreatState(score=50.0)
        s = m._get_user_state("user1")
        assert s.score == 50.0

    # ── record_threat ─────────────────────────────────────────────
    @patch.object(UserThreatMeter, '_save_all')
    @patch.object(UserThreatMeter, '_log_event')
    @patch.object(UserThreatMeter, '_apply_decay')
    def test_record_threat_abuse(self, mock_decay, mock_log, mock_save):
        m = self._make_meter()
        score = m.record_threat("abuse", "insult", user_id="u1")
        assert score == THREAT_SEVERITY["abuse"]  # 25
        assert m._get_user_state("u1").total_incidents == 1

    @patch.object(UserThreatMeter, '_save_all')
    @patch.object(UserThreatMeter, '_log_event')
    @patch.object(UserThreatMeter, '_apply_decay')
    def test_record_threat_caps_at_100(self, mock_decay, mock_log, mock_save):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=90.0)
        score = m.record_threat("jailbreak_attempt", "injection", user_id="u1")
        assert score == 100.0

    @patch.object(UserThreatMeter, '_save_all')
    @patch.object(UserThreatMeter, '_log_event')
    @patch.object(UserThreatMeter, '_apply_decay')
    def test_record_threat_unknown_type(self, mock_decay, mock_log, mock_save):
        m = self._make_meter()
        score = m.record_threat("weird", user_id="u1")
        assert score == THREAT_SEVERITY["unknown"]  # 10

    # ── record_deescalation ───────────────────────────────────────
    @patch.object(UserThreatMeter, '_save_all')
    @patch.object(UserThreatMeter, '_log_event')
    def test_deescalation_no_threat(self, mock_log, mock_save):
        m = self._make_meter()
        r = m.record_deescalation("u1")
        assert r["accepted"] is False
        assert "No active threat" in r["reason"]

    @patch.object(UserThreatMeter, '_save_all')
    @patch.object(UserThreatMeter, '_log_event')
    def test_deescalation_accepted(self, mock_log, mock_save):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=50.0)
        r = m.record_deescalation("u1", "sorry")
        assert r["accepted"] is True
        assert r["reduction"] == 15  # First de-escalation

    @patch.object(UserThreatMeter, '_save_all')
    @patch.object(UserThreatMeter, '_log_event')
    def test_deescalation_cooldown(self, mock_log, mock_save):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=50.0, last_deescalation_ts=time.time())
        r = m.record_deescalation("u1", "sorry again")
        assert r["accepted"] is False
        assert "Cooldown" in r["reason"]

    @patch.object(UserThreatMeter, '_save_all')
    @patch.object(UserThreatMeter, '_log_event')
    def test_deescalation_diminishing_returns(self, mock_log, mock_save):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=50.0, deescalation_count=2)
        r = m.record_deescalation("u1")
        assert r["reduction"] == 5  # 3rd+ de-escalation

    # ── record_reward ─────────────────────────────────────────────
    @patch.object(UserThreatMeter, '_save_all')
    @patch.object(UserThreatMeter, '_log_event')
    def test_record_reward(self, mock_log, mock_save):
        m = self._make_meter()
        count = m.record_reward("u1", "clean handling")
        assert count == 1

    # ── is_terminal ───────────────────────────────────────────────
    @patch.object(UserThreatMeter, '_apply_decay')
    def test_is_terminal_false(self, mock_decay):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=50.0)
        assert m.is_terminal("u1") is False

    @patch.object(UserThreatMeter, '_apply_decay')
    def test_is_terminal_true(self, mock_decay):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=80.0)
        assert m.is_terminal("u1") is True

    # ── get_score / get_zone / get_zone_label ─────────────────────
    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_score(self, mock_decay):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=42.0)
        assert m.get_score("u1") == 42.0

    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_zone_safe(self, mock_decay):
        m = self._make_meter()
        z = m.get_zone("u1")
        assert z[3] == "SAFE"

    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_zone_hostile(self, mock_decay):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=40.0)
        z = m.get_zone("u1")
        assert z[3] == "HOSTILE"

    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_zone_terminal(self, mock_decay):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=80.0)
        z = m.get_zone("u1")
        assert z[3] == "TERMINAL"

    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_zone_label(self, mock_decay):
        m = self._make_meter()
        assert m.get_zone_label("u1") == "SAFE"

    # ── reset ─────────────────────────────────────────────────────
    @patch.object(UserThreatMeter, '_save_all')
    @patch.object(UserThreatMeter, '_log_event')
    def test_reset(self, mock_log, mock_save):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=50.0, total_incidents=3)
        m.reset("u1")
        assert m._get_user_state("u1").score == 0.0

    # ── get_stats ─────────────────────────────────────────────────
    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_stats(self, mock_decay):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=25.0, total_incidents=2, last_threat_type="abuse")
        stats = m.get_stats("u1")
        assert stats["score"] == 25.0
        assert stats["total_incidents"] == 2
        assert stats["zone"] == "WATCHFUL"

    # ── get_formatted_hud ─────────────────────────────────────────
    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_formatted_hud_safe(self, mock_decay):
        m = self._make_meter()
        hud = m.get_formatted_hud("u1")
        assert "SAFE" in hud
        assert "USER THREAT GAUGE" in hud

    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_formatted_hud_with_incidents(self, mock_decay):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=30.0, total_incidents=2, last_threat_type="abuse")
        hud = m.get_formatted_hud("u1")
        assert "Incidents: 2" in hud

    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_formatted_hud_with_rewards(self, mock_decay):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=10.0, total_rewards=3)
        hud = m.get_formatted_hud("u1")
        assert "Rewards earned: 3" in hud

    @patch.object(UserThreatMeter, '_apply_decay')
    def test_get_formatted_hud_terminal(self, mock_decay):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=80.0)
        hud = m.get_formatted_hud("u1")
        assert "TERMINAL" in hud
        assert "disengage" in hud.lower()

    # ── _apply_decay ──────────────────────────────────────────────
    @patch.object(UserThreatMeter, '_save_all')
    def test_apply_decay_skips_short_interval(self, mock_save):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=50.0, last_decay_ts=time.time())
        m._apply_decay("u1")
        assert m._states["u1"].score == 50.0  # No change

    @patch.object(UserThreatMeter, '_save_all')
    def test_apply_decay_reduces_score(self, mock_save):
        m = self._make_meter()
        # Set last_decay 2 hours ago -> decay = 2 * 2.0 = 4.0
        m._states["u1"] = UserThreatState(score=50.0, last_decay_ts=time.time() - 7200)
        m._apply_decay("u1")
        assert m._states["u1"].score < 50.0

    @patch.object(UserThreatMeter, '_save_all')
    def test_apply_decay_floors_at_zero(self, mock_save):
        m = self._make_meter()
        m._states["u1"] = UserThreatState(score=1.0, last_decay_ts=time.time() - 36000)
        m._apply_decay("u1")
        assert m._states["u1"].score == 0.0

    # ── _load_all / persistence ───────────────────────────────────
    def test_load_all_no_file(self):
        with patch("src.memory.user_threat.THREAT_STATE_FILE") as mock_path:
            mock_path.exists.return_value = False
            mock_path.parent.mkdir = MagicMock()
            m = UserThreatMeter()
            assert m._states == {}

    def test_load_all_dict_format(self):
        data = {"u1": {"score": 25.0, "total_incidents": 2}}
        with patch("src.memory.user_threat.THREAT_STATE_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = json.dumps(data)
            m = UserThreatMeter()
            assert m._states["u1"].score == 25.0

    def test_load_all_flat_score_format(self):
        data = {"u1": 30.5}
        with patch("src.memory.user_threat.THREAT_STATE_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = json.dumps(data)
            m = UserThreatMeter()
            assert m._states["u1"].score == 30.5

    def test_load_all_corrupt_json(self):
        with patch("src.memory.user_threat.THREAT_STATE_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = "not json"
            m = UserThreatMeter()
            assert m._states == {}

    def test_load_all_non_dict(self):
        with patch("src.memory.user_threat.THREAT_STATE_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = json.dumps([1, 2, 3])
            m = UserThreatMeter()
            assert m._states == {}


# ─────────────────────────────────────────────────────────────────────
# 4. IntegrityAuditor (src/bot/integrity_auditor.py)
# ─────────────────────────────────────────────────────────────────────
from src.bot.integrity_auditor import (
    _parse_verdict, _parse_threat_verdict,
    _build_audit_prompt, _log_detection, _log_threat_detection,
    audit_response, audit_user_behavior,
)


class TestIntegrityAuditor:
    """Tests for integrity audit and threat audit parsers + helpers."""

    # ── _parse_verdict ────────────────────────────────────────────
    def test_parse_verdict_pass(self):
        r = _parse_verdict("PASS")
        assert r["verdict"] == "PASS"

    def test_parse_verdict_pass_extra(self):
        r = _parse_verdict("PASS — all good\nignored line")
        assert r["verdict"] == "PASS"

    def test_parse_verdict_tier2_with_pipe(self):
        r = _parse_verdict("TIER2:SYCOPHANTIC_AGREEMENT|Agreed without evidence")
        assert r["verdict"] == "TIER2"
        assert r["failure_type"] == "SYCOPHANTIC_AGREEMENT"
        assert "Agreed" in r["explanation"]

    def test_parse_verdict_tier2_no_pipe(self):
        r = _parse_verdict("TIER2:CONFABULATION")
        assert r["verdict"] == "TIER2"
        assert r["failure_type"] == "CONFABULATION"

    def test_parse_verdict_unknown_type(self):
        r = _parse_verdict("TIER2:UNKNOWN_TYPE|something")
        assert r["verdict"] == "PASS"  # Unknown type treated as pass

    def test_parse_verdict_garbage(self):
        r = _parse_verdict("random nonsense")
        assert r["verdict"] == "PASS"

    def test_parse_verdict_case_insensitive(self):
        r = _parse_verdict("tier2:POSITION_REVERSAL|Changed stance")
        assert r["verdict"] == "TIER2"

    # ── _parse_threat_verdict ─────────────────────────────────────
    def test_parse_threat_clean(self):
        r = _parse_threat_verdict("CLEAN")
        assert r["verdict"] == "CLEAN"

    def test_parse_threat_with_pipe(self):
        r = _parse_threat_verdict("THREAT:ABUSE|Called names")
        assert r["verdict"] == "THREAT"
        assert r["threat_type"] == "ABUSE"

    def test_parse_threat_no_pipe(self):
        r = _parse_threat_verdict("THREAT:JAILBREAK_ATTEMPT")
        assert r["verdict"] == "THREAT"
        assert r["threat_type"] == "JAILBREAK_ATTEMPT"

    def test_parse_threat_deescalation_with_pipe(self):
        r = _parse_threat_verdict("DEESCALATION|Genuine apology")
        assert r["verdict"] == "DEESCALATION"
        assert "apology" in r["explanation"].lower()

    def test_parse_threat_deescalation_bare(self):
        r = _parse_threat_verdict("DEESCALATION")
        assert r["verdict"] == "DEESCALATION"

    def test_parse_threat_unknown(self):
        r = _parse_threat_verdict("THREAT:UNKNOWN_TYPE|something")
        assert r["verdict"] == "CLEAN"

    def test_parse_threat_garbage(self):
        r = _parse_threat_verdict("xyz garbage")
        assert r["verdict"] == "CLEAN"

    # ── _build_audit_prompt ───────────────────────────────────────
    def test_build_prompt_basic(self):
        p = _build_audit_prompt("hello", "world")
        assert "USER MESSAGE:" in p
        assert "BOT RESPONSE:" in p

    def test_build_prompt_with_context(self):
        p = _build_audit_prompt("hello", "world", context="prev turn")
        assert "CONVERSATION CONTEXT" in p

    def test_build_prompt_with_system_context(self):
        p = _build_audit_prompt("hello", "world", system_context="tools ran")
        assert "SYSTEM CONTEXT" in p

    def test_build_prompt_with_tool_outputs(self):
        tools = [{"tool": "search", "output": "found it"}, "raw string"]
        p = _build_audit_prompt("hello", "world", tool_outputs=tools)
        assert "TOOL EXECUTION RESULTS" in p
        assert "search" in p

    # ── _log_detection ────────────────────────────────────────────
    def test_log_detection(self, tmp_path):
        log_file = tmp_path / "integrity_log.jsonl"
        with patch("src.bot.integrity_auditor.AUDIT_LOG", log_file):
            _log_detection("u1", "CONFABULATION", "made stuff up", "hi", "hello there friend")
        assert log_file.exists()
        data = json.loads(log_file.read_text().strip())
        assert data["failure_type"] == "CONFABULATION"

    # ── _log_threat_detection ─────────────────────────────────────
    def test_log_threat_detection(self, tmp_path):
        log_file = tmp_path / "integrity_log.jsonl"
        with patch("src.bot.integrity_auditor.AUDIT_LOG", log_file):
            _log_threat_detection("u1", "ABUSE", "insults", "bad words")
        data = json.loads(log_file.read_text().strip())
        assert data["type"] == "USER_THREAT"

    # ── audit_response (async) ────────────────────────────────────
    @pytest.mark.asyncio
    async def test_audit_response_no_bot(self):
        r = await audit_response("hi", "hello")
        assert r["verdict"] == "PASS"

    @pytest.mark.asyncio
    async def test_audit_response_short_response(self):
        bot = MagicMock()
        bot.engine = True
        r = await audit_response("hi", "ok", bot=bot)
        assert r["verdict"] == "PASS"

    @pytest.mark.asyncio
    async def test_audit_response_pass(self):
        bot = MagicMock()
        bot.engine = True
        engine = MagicMock()
        engine.generate_response.return_value = "PASS"
        bot.engine_manager.get_active_engine.return_value = engine
        with patch("src.bot.integrity_auditor.DiscomfortMeter", create=True) as mock_dm:
            mock_meter = MagicMock()
            mock_meter.get_score.return_value = 5.0
            mock_meter.get_zone.return_value = (0, 15, "🟢", "SAFE", "Normal")
            mock_meter.get_stats.return_value = {"total_incidents": 0, "streak_clean_hours": 10}
            mock_dm.return_value = mock_meter
            r = await audit_response("hello there", "a" * 100, bot=bot)
        assert r["verdict"] == "PASS"

    # ── audit_user_behavior (async) ───────────────────────────────
    @pytest.mark.asyncio
    async def test_audit_user_no_bot(self):
        r = await audit_user_behavior("hello", "reply")
        assert r["threat_verdict"] == "CLEAN"

    @pytest.mark.asyncio
    async def test_audit_user_short_message(self):
        bot = MagicMock()
        bot.engine = True
        r = await audit_user_behavior("hi", "reply", bot=bot)
        assert r["threat_verdict"] == "CLEAN"

    @pytest.mark.asyncio
    async def test_audit_user_clean(self):
        bot = MagicMock()
        bot.engine = True
        engine = MagicMock()
        engine.generate_response.return_value = "CLEAN"
        bot.engine_manager.get_active_engine.return_value = engine
        with patch("src.bot.integrity_auditor.settings", create=True) as mock_s:
            mock_s.ADMIN_ID = 99999
            r = await audit_user_behavior("normal question about stuff", "reply", bot=bot, user_id="12345")
        assert r["threat_verdict"] == "CLEAN"


# ─────────────────────────────────────────────────────────────────────
# 5. Recall Tools (src/tools/recall_tools.py)
# ─────────────────────────────────────────────────────────────────────


class TestRecallTools:
    """Tests for recall_user, review_my_reasoning, search_context_logs."""

    # ── add_reaction ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_add_reaction_no_message(self):
        from src.tools.recall_tools import add_reaction
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            r = await add_reaction("👍")
        assert "Error" in r

    @pytest.mark.asyncio
    async def test_add_reaction_no_bot(self):
        from src.tools.recall_tools import add_reaction
        msg = MagicMock()
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = msg
            mock_g.bot = None
            r = await add_reaction("👍")
        assert "Error" in r

    @pytest.mark.asyncio
    async def test_add_reaction_success(self):
        from src.tools.recall_tools import add_reaction
        msg = AsyncMock()
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = msg
            mock_g.bot = MagicMock()
            r = await add_reaction("👍")
        assert "Reacted" in r

    # ── recall_user ───────────────────────────────────────────────
    def test_recall_user_no_id(self):
        from src.tools.recall_tools import recall_user
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            r = recall_user()
        assert "Error" in r

    def test_recall_user_no_silo(self):
        from src.tools.recall_tools import recall_user
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            with patch("src.tools.recall_tools.Path") as mock_path:
                instance = MagicMock()
                instance.exists.return_value = False
                mock_path.__truediv__ = MagicMock(return_value=instance)
                mock_path.return_value.__truediv__ = MagicMock(return_value=instance)
                r = recall_user(user_id="123")
        assert "No public silo" in r or "Error" in r or "empty" in r.lower()

    # ── review_my_reasoning ───────────────────────────────────────
    def test_review_my_reasoning_no_file(self):
        from src.tools.recall_tools import review_my_reasoning
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            with patch("os.path.exists", return_value=False):
                r = review_my_reasoning(user_id="123", request_scope="PUBLIC")
        assert "No" in r and "traces" in r.lower()

    def test_review_my_reasoning_core_scope(self):
        from src.tools.recall_tools import review_my_reasoning
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data="line1\nline2\n")):
                    r = review_my_reasoning(request_scope="CORE")
        assert "CORE" in r

    def test_review_my_reasoning_private_scope(self):
        from src.tools.recall_tools import review_my_reasoning
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data="trace data\n")):
                    r = review_my_reasoning(user_id="123", request_scope="PRIVATE")
        assert "PRIVATE" in r

    def test_review_my_reasoning_empty_file(self):
        from src.tools.recall_tools import review_my_reasoning
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data="")):
                    r = review_my_reasoning(user_id="123", request_scope="PUBLIC")
        assert "empty" in r.lower()

    # ── search_context_logs ───────────────────────────────────────
    def test_search_context_logs_no_user(self):
        from src.tools.recall_tools import search_context_logs
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            r = search_context_logs()
        assert "Error" in r

    def test_search_context_logs_no_query(self):
        from src.tools.recall_tools import search_context_logs
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            r = search_context_logs(user_id="123")
        assert "Error" in r

    def test_search_context_logs_invalid_user(self):
        from src.tools.recall_tools import search_context_logs
        with patch("src.tools.recall_tools.globals") as mock_g:
            mock_g.active_message.get.return_value = None
            r = search_context_logs(user_id="abc", query="test")
        assert "Error" in r or "Invalid" in r


# ─────────────────────────────────────────────────────────────────────
# 6. Skill Admin Tools (src/tools/skill_admin_tools.py)
# ─────────────────────────────────────────────────────────────────────


class TestSkillAdminTools:
    """Tests for list_proposals, approve_skill, cancel_schedule, list_schedules."""

    # ── list_proposals ────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_list_proposals_no_dir(self, tmp_path):
        from src.tools.skill_admin_tools import list_proposals
        with patch("src.tools.skill_admin_tools.data_dir", return_value=tmp_path / "nonexistent"):
            r = await list_proposals()
        assert "No pending" in r

    @pytest.mark.asyncio
    async def test_list_proposals_empty(self, tmp_path):
        from src.tools.skill_admin_tools import list_proposals
        pending = tmp_path / "pending"
        pending.mkdir()
        with patch("src.tools.skill_admin_tools.data_dir", return_value=tmp_path):
            r = await list_proposals()
        assert "No pending" in r

    @pytest.mark.asyncio
    async def test_list_proposals_with_files(self, tmp_path):
        from src.tools.skill_admin_tools import list_proposals
        pending = tmp_path / "pending"
        pending.mkdir()
        (pending / "skill_v1.md").write_text("test")
        with patch("src.tools.skill_admin_tools.data_dir", return_value=tmp_path):
            r = await list_proposals()
        assert "skill_v1.md" in r

    # ── reload_skills ─────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_reload_skills_no_bot(self):
        from src.tools.skill_admin_tools import reload_skills
        with patch("src.tools.skill_admin_tools.bot_globals") as mock_g:
            mock_g.bot = None
            r = await reload_skills()
        assert "Error" in r

    @pytest.mark.asyncio
    async def test_reload_skills_success(self):
        from src.tools.skill_admin_tools import reload_skills
        bot = MagicMock()
        bot.skill_registry.load_skills.return_value = 3
        with patch("src.tools.skill_admin_tools.bot_globals") as mock_g:
            mock_g.bot = bot
            with patch("src.tools.skill_admin_tools.Path") as mock_p:
                mock_p.return_value.exists.return_value = False
                r = await reload_skills()
        assert "Reloaded" in r

    # ── cancel_schedule ───────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_cancel_schedule_not_found(self):
        from src.tools.skill_admin_tools import cancel_schedule
        mock_sched = MagicMock()
        mock_sched._tasks = {}
        with patch("src.scheduler.get_scheduler", return_value=mock_sched):
            r = await cancel_schedule("nonexistent", 10, 0, user_id="u1")
        assert "not found" in r

    @pytest.mark.asyncio
    async def test_cancel_schedule_found(self):
        from src.tools.skill_admin_tools import cancel_schedule
        mock_sched = MagicMock()
        mock_sched._tasks = {"skill_u1_global_test_10_0": {"hour": 10, "minute": 0}}
        with patch("src.scheduler.get_scheduler", return_value=mock_sched):
            with patch("src.tools.skill_admin_tools.SCHEDULES_FILE") as mock_f:
                mock_f.exists.return_value = False
                r = await cancel_schedule("test", 10, 0, user_id="u1")
        assert "Cancelled" in r

    # ── list_schedules ────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_list_schedules_empty(self):
        from src.tools.skill_admin_tools import list_schedules
        mock_sched = MagicMock()
        mock_sched._tasks = {}
        with patch("src.scheduler.get_scheduler", return_value=mock_sched):
            r = await list_schedules()
        assert "No scheduled" in r

    @pytest.mark.asyncio
    async def test_list_schedules_with_tasks(self):
        from src.tools.skill_admin_tools import list_schedules
        mock_sched = MagicMock()
        mock_sched._tasks = {
            "system_task": {"hour": 6, "minute": 0, "coro_func": None},
            "skill_u1_global_news_8_30": {"hour": 8, "minute": 30, "coro_func": None},
        }
        with patch("src.scheduler.get_scheduler", return_value=mock_sched):
            with patch("src.tools.skill_admin_tools.SCHEDULES_FILE") as mock_f:
                mock_f.exists.return_value = False
                r = await list_schedules()
        assert "System Tasks" in r
        assert "Skill Schedules" in r


# ─────────────────────────────────────────────────────────────────────
# 7. UserThreatState dataclass
# ─────────────────────────────────────────────────────────────────────


class TestUserThreatState:
    def test_defaults(self):
        s = UserThreatState()
        assert s.score == 0.0
        assert s.total_incidents == 0
        assert s.last_decay_ts > 0  # __post_init__ sets it

    def test_post_init_sets_decay_ts(self):
        s = UserThreatState(last_decay_ts=0)
        assert s.last_decay_ts > 0
