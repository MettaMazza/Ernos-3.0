"""
Comprehensive coverage tests for src/prompts/hud_loaders.py
Targeting 55% → 95% coverage.
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, mock_open


def _make_globals_mod(recent_errors=None, activity_log=None):
    """Create a mock globals module for src.bot.globals with the given data."""
    m = MagicMock()
    m.recent_errors = recent_errors or []
    m.activity_log = activity_log or []
    return m


def _ernos_hud(scope, user_id, is_core, globals_mod, exists_fn=None, extra_open=None):
    """Shared helper that patches all lazy imports and runs load_ernos_hud."""
    import importlib
    import src.prompts.hud_loaders as _mod
    # Inject the mock globals module into sys.modules so `from src.bot import globals` resolves
    bot_mock = MagicMock()
    bot_mock.globals = globals_mod
    with patch.dict("sys.modules", {"src.bot": bot_mock, "src.bot.globals": globals_mod}):
        with patch("src.prompts.hud_loaders.os.path.exists", side_effect=exists_fn or (lambda p: False)), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            if extra_open:
                with patch("builtins.open", side_effect=extra_open):
                    return _mod.load_ernos_hud(scope, user_id, is_core)
            return _mod.load_ernos_hud(scope, user_id, is_core)


# --------------- load_ernos_hud ---------------

class TestLoadErnosHudBasic:
    def test_returns_dict(self):
        hud = _ernos_hud("PUBLIC", "u1", False, _make_globals_mod())
        assert isinstance(hud, dict)
        assert "terminal_tail" in hud


class TestTerminalAwareness:
    def test_core_scope_raw_logs(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_ernos.os.path.exists", side_effect=lambda p: p == "ernos_bot.log"), \
             patch("builtins.open", mock_open(read_data="log-line-1\nlog-line-2\n")), \
             patch("src.prompts.hud_ernos._load_room_roster", return_value=""), \
             patch("src.prompts.hud_ernos._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("CORE", "u1", True)
        assert "log-line" in hud["terminal_tail"]

    def test_public_scope_sanitized(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_ernos.os.path.exists", side_effect=lambda p: p == "ernos_bot.log"), \
             patch("builtins.open", mock_open(read_data="clean line\n")), \
             patch("src.prompts.hud_ernos._sanitize_logs", return_value="sanitized"), \
             patch("src.prompts.hud_ernos._load_room_roster", return_value=""), \
             patch("src.prompts.hud_ernos._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert hud["terminal_tail"] == "sanitized"

    def test_public_scope_empty_sanitized(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_ernos.os.path.exists", side_effect=lambda p: p == "ernos_bot.log"), \
             patch("builtins.open", mock_open(read_data="line\n")), \
             patch("src.prompts.hud_ernos._sanitize_logs", return_value=""), \
             patch("src.prompts.hud_ernos._load_room_roster", return_value=""), \
             patch("src.prompts.hud_ernos._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert "System logs active" in hud["terminal_tail"]


class TestErrorAwareness:
    def test_with_recent_errors(self):
        hud = _ernos_hud("PUBLIC", "u1", False, _make_globals_mod(recent_errors=["err1", "err2"]))
        assert "err1" in hud["error_log"]

    def test_no_recent_errors(self):
        hud = _ernos_hud("PUBLIC", "u1", False, _make_globals_mod())
        assert "No recent errors" in hud["error_log"]


class TestActivityStream:
    def _entry(self, **kw):
        return {"timestamp": "12:00", "scope": "PUBLIC", "type": "msg", "summary": "...", "user_hash": "", **kw}

    def test_core_sees_raw(self):
        hud = _ernos_hud("CORE", "u1", True, _make_globals_mod(activity_log=[self._entry(summary="hello")]))
        assert "[12:00]" in hud["activity_tail"]
        assert "hello" in hud["activity_tail"]

    def test_autonomy_event_redacted(self):
        hud = _ernos_hud("PUBLIC", "u1", False, _make_globals_mod(
            activity_log=[self._entry(type="autonomy", summary="secret")]))
        assert "<Autonomy Event>" in hud["activity_tail"]
        assert "secret" not in hud["activity_tail"]

    def test_public_scope_visible(self):
        hud = _ernos_hud("PUBLIC", "u1", False, _make_globals_mod(
            activity_log=[self._entry(scope="PUBLIC", summary="pub msg")]))
        assert "pub msg" in hud["activity_tail"]

    def test_private_scope_own_user(self):
        hud = _ernos_hud("PRIVATE", "u1", False, _make_globals_mod(
            activity_log=[self._entry(scope="PRIVATE", summary="my dm", user_hash="u1")]))
        assert "my dm" in hud["activity_tail"]

    def test_internal_scope(self):
        hud = _ernos_hud("PUBLIC", "u1", False, _make_globals_mod(
            activity_log=[self._entry(scope="INTERNAL", summary="self talk")]))
        assert "[SELF]" in hud["activity_tail"]

    def test_other_user_private_redacted(self):
        hud = _ernos_hud("PUBLIC", "u1", False, _make_globals_mod(
            activity_log=[self._entry(scope="PRIVATE", summary="secret dm", user_hash="other_user")]))
        assert "You are speaking to" in hud["activity_tail"]
        assert "secret dm" not in hud["activity_tail"]


class TestAwarenessException:
    def test_awareness_exception(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=RuntimeError("boom")), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert "Error reading logs" in hud["terminal_tail"]


class TestTestHealth:
    def _run(self, data):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        def side_exists(p):
            return p == "memory/system/test_health.json"
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=side_exists), \
             patch("builtins.open", mock_open(read_data=json.dumps(data))), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            return load_ernos_hud("PUBLIC", "u1", False)

    def test_healthy(self):
        hud = self._run({"passed": 10, "failed": 0, "total": 10, "status": "HEALTHY", "timestamp": "12:00"})
        assert "✅ PASSED" in hud["test_health"]

    def test_degraded(self):
        hud = self._run({"passed": 8, "failed": 2, "total": 10, "status": "DEGRADED", "timestamp": "12:00"})
        assert "DEGRADED" in hud["test_health"]

    def test_unknown(self):
        hud = self._run({"passed": 5, "failed": 0, "total": 5, "status": "WEIRD", "timestamp": "12:00"})
        assert "UNKNOWN" in hud["test_health"]

    def test_exception(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        def side_exists(p):
            return p == "memory/system/test_health.json"
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=side_exists), \
             patch("builtins.open", side_effect=Exception("nope")), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert "unavailable" in hud["test_health"].lower() or "Error" in hud["test_health"]


class TestSleepCycle:
    def test_dream_and_compression(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        comp_data = json.dumps({"last_run": "2024-01-01", "compression_ratio": "2.5"})

        def fake_open(path, *a, **kw):
            if "dream_journal" in str(path):
                return mock_open(read_data="Dream entry\n")()
            if "compression_log" in str(path):
                return mock_open(read_data=comp_data)()
            return mock_open(read_data="")()

        def side_exists(p):
            return p in ("memory/core/dream_journal.md", "memory/core/compression_log.json")

        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=side_exists), \
             patch("builtins.open", side_effect=fake_open), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert "Dream entry" in hud["dream_status"]
        assert "2024-01-01" in hud["compression_status"]


class TestProactiveIntentions:
    def test_with_intentions(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        intents = [{"description": "Check in with user", "completed": False},
                   {"description": "Done task", "completed": True}]

        mock_home = MagicMock()
        mock_intentions = MagicMock()
        mock_intentions.exists.return_value = True
        mock_home.__truediv__ = MagicMock(return_value=mock_intentions)

        # Patch ScopeManager at the import location inside the function
        mock_scope = MagicMock()
        mock_scope.ScopeManager.get_user_home.return_value = mock_home

        with patch.dict("sys.modules", {
                "src.bot": MagicMock(), "src.bot.globals": g,
                "src.privacy": MagicMock(), "src.privacy.scopes": mock_scope}), \
             patch("src.prompts.hud_loaders.os.path.exists", return_value=False), \
             patch("builtins.open", mock_open(read_data=json.dumps(intents))), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert "Check in with user" in hud["proactive_intentions"]


# --------------- load_persona_hud ---------------

class TestLoadPersonaHud:
    def test_returns_defaults_no_registry(self):
        from src.prompts.hud_loaders import load_persona_hud
        with patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", return_value=None):
            hud = load_persona_hud("Echo")
        assert isinstance(hud, dict)
        assert hud["lessons_learned"] == "No lessons recorded."

    def test_loads_lessons(self, tmp_path):
        from src.prompts.hud_loaders import load_persona_hud
        (tmp_path / "lessons.json").write_text(json.dumps(["lesson1", "lesson2"]))
        with patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", return_value=tmp_path):
            hud = load_persona_hud("Echo")
        assert "lesson1" in hud["lessons_learned"]

    def test_loads_relationships(self, tmp_path):
        from src.prompts.hud_loaders import load_persona_hud
        (tmp_path / "relationships.json").write_text(json.dumps({"Alice": "friend", "Bob": "rival"}))
        with patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", return_value=tmp_path):
            hud = load_persona_hud("Echo")
        assert "Alice: friend" in hud["kg_relationships"]

    def test_loads_opinions(self, tmp_path):
        from src.prompts.hud_loaders import load_persona_hud
        (tmp_path / "opinions.json").write_text(json.dumps({"cats": "great", "dogs": "also great"}))
        with patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", return_value=tmp_path):
            hud = load_persona_hud("Echo")
        assert "cats: great" in hud["kg_beliefs"]

    def test_loads_context_jsonl(self, tmp_path):
        from src.prompts.hud_loaders import load_persona_hud
        (tmp_path / "context.jsonl").write_text(json.dumps({"speaker": "Echo", "content": "Hello world"}))
        with patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", return_value=tmp_path):
            hud = load_persona_hud("Echo")
        assert "Echo: Hello world" in hud["reasoning_context"]

    def test_context_bad_json_skipped(self, tmp_path):
        from src.prompts.hud_loaders import load_persona_hud
        (tmp_path / "context.jsonl").write_text("not json\n" + json.dumps({"speaker": "A", "content": "ok"}))
        with patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", return_value=tmp_path):
            hud = load_persona_hud("Echo")
        assert "A: ok" in hud["reasoning_context"]

    def test_exception_handled(self):
        from src.prompts.hud_loaders import load_persona_hud
        with patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", side_effect=RuntimeError("fail")):
            hud = load_persona_hud("Echo")
        assert isinstance(hud, dict)

    def test_empty_files(self, tmp_path):
        from src.prompts.hud_loaders import load_persona_hud
        (tmp_path / "lessons.json").write_text("[]")
        (tmp_path / "relationships.json").write_text("{}")
        (tmp_path / "opinions.json").write_text("{}")
        with patch("src.memory.public_registry.PublicPersonaRegistry.get_persona_path", return_value=tmp_path):
            hud = load_persona_hud("Echo")
        assert hud["lessons_learned"] == "No lessons recorded."


# --------------- load_fork_hud ---------------

class TestLoadForkHud:
    def _make_user_home(self, tmp_path):
        home = tmp_path / "user_home"
        home.mkdir()
        return home

    def test_returns_defaults(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert isinstance(fhud, dict)
        assert fhud["message_count"] == "0"

    def test_loads_persona_content(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "persona.txt").write_text("I am a custom persona with lots of detail.")
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "custom persona" in fhud["current_persona_content"]

    def test_empty_persona_file(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "persona.txt").write_text("   ")
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "Empty persona file" in fhud["current_persona_content"]

    def test_conversation_history(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        entries = [
            {"user": "What about machine learning algorithms?", "bot": "Great topic!", "ts": "2024-01-01T12:00:00"},
            {"user": "Tell me more about neural networks today", "bot": "Sure!", "ts": "2024-01-02T12:00:00"},
        ]
        (home / "context_private.jsonl").write_text("\n".join(json.dumps(e) for e in entries))
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert fhud["message_count"] == "2"
        assert "Alice:" in fhud["full_conversation_history"]

    def test_first_interaction(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "context_private.jsonl").write_text(json.dumps({"user": "hi", "bot": "hello", "ts": "2024-01-01T12:00:00"}))
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "2024-01-01" in fhud["first_interaction"]

    def test_relationship_deep(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "timeline.jsonl").write_text("\n".join(["{}"] * 60))
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "Deep relationship" in fhud["relationship_context"]

    def test_relationship_established(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "timeline.jsonl").write_text("\n".join(["{}"] * 20))
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "Established" in fhud["relationship_context"]

    def test_relationship_new(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "timeline.jsonl").write_text("{}\n{}\n{}")
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "New relationship" in fhud["relationship_context"]

    def test_user_preferences(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "preferences.json").write_text(json.dumps({"theme": "dark"}))
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "dark" in fhud["user_preferences"]

    def test_identity_in_relationship(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "persona.txt").write_text("Custom Identity Line 1\nSecond line")
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "Custom Identity Line 1" in fhud["identity_in_relationship"]
        assert fhud["your_role"] == "Custom fork identity active."

    def test_glossary(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "glossary.json").write_text(json.dumps({"yeet": "throw", "bruh": "dude"}))
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "yeet: throw" in fhud["private_glossary"]

    def test_emotional_tone_warm(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "reasoning_private.log").write_text("agree yes good appreciate thank love happy " * 10 + "\n")
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "Warm" in fhud["emotional_tone"]

    def test_emotional_tone_challenging(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "reasoning_private.log").write_text("no wrong disagree issue problem frustrated " * 10 + "\n")
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "Challenging" in fhud["emotional_tone"]

    def test_emotional_tone_balanced(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "reasoning_private.log").write_text("agree no good wrong\n")
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert "Balanced" in fhud["emotional_tone"]

    def test_exception_handled(self):
        from src.prompts.hud_loaders import load_fork_hud
        with patch("src.privacy.scopes.ScopeManager.get_user_home", side_effect=RuntimeError("fail")):
            fhud = load_fork_hud("u1", "Alice")
        assert isinstance(fhud, dict)

    def test_bad_jsonl_line_skipped(self, tmp_path):
        from src.prompts.hud_loaders import load_fork_hud
        home = self._make_user_home(tmp_path)
        (home / "context_private.jsonl").write_text("not json\n" + json.dumps({"user": "ok", "bot": "hi", "ts": "2024-01-01"}))
        with patch("src.privacy.scopes.ScopeManager.get_user_home", return_value=home):
            fhud = load_fork_hud("u1", "Alice")
        assert fhud["message_count"] == "2"


# --------------- _sanitize_logs ---------------

class TestSanitizeLogs:
    def test_filters_blocked_terms(self):
        from src.prompts.hud_loaders import _sanitize_logs
        lines = ["clean line\n", "user_message: secret\n", "INFO normal\n"]
        result = _sanitize_logs(lines)
        assert "clean line" in result
        assert "secret" not in result

    def test_all_blocked(self):
        from src.prompts.hud_loaders import _sanitize_logs
        lines = ["user: hi\n", "content: data\n"]
        result = _sanitize_logs(lines)
        assert result == ""

    def test_persona_blocklist(self):
        from src.prompts.hud_loaders import _sanitize_logs
        lines = ["Persona override injected\n", "clean\n"]
        result = _sanitize_logs(lines)
        assert "clean" in result
        assert "Persona" not in result


# --------------- _load_room_roster ---------------

class TestLoadRoomRoster:
    def test_no_file(self):
        from src.prompts.hud_loaders import _load_room_roster
        with patch("src.prompts.hud_loaders.os.path.exists", return_value=False):
            result = _load_room_roster()
        assert "No active users detected" in result

    def test_with_entries(self):
        from src.prompts.hud_loaders import _load_room_roster
        entries = [json.dumps({"user_name": "Alice", "user_id": "1", "timestamp": "12:00"})]
        with patch("src.prompts.hud_loaders.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="\n".join(entries))):
            result = _load_room_roster()
        assert "Alice" in result
        assert "<roster>" in result

    def test_unknown_user(self):
        from src.prompts.hud_loaders import _load_room_roster
        entries = [json.dumps({"user_name": "Unknown", "user_id": "1", "timestamp": "12:00"})]
        with patch("src.prompts.hud_loaders.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="\n".join(entries))):
            result = _load_room_roster()
        assert "[Unknown User]" in result

    def test_name_dedup(self):
        from src.prompts.hud_loaders import _load_room_roster
        entries = [
            json.dumps({"user_name": "Alice", "user_id": "1", "timestamp": "12:00"}),
            json.dumps({"user_name": "Unknown", "user_id": "1", "timestamp": "12:05"}),
        ]
        with patch("src.prompts.hud_loaders.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="\n".join(entries))):
            result = _load_room_roster()
        assert "Alice" in result

    def test_bad_json_ignored(self):
        from src.prompts.hud_loaders import _load_room_roster
        data = "not json\n" + json.dumps({"user_name": "Bob", "user_id": "2", "timestamp": "12:00"})
        with patch("src.prompts.hud_loaders.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=data)):
            result = _load_room_roster()
        assert "Bob" in result

    def test_empty_roster_map(self):
        from src.prompts.hud_loaders import _load_room_roster
        entries = [json.dumps({"user_name": "X", "timestamp": "12:00"})]
        with patch("src.prompts.hud_loaders.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="\n".join(entries))):
            result = _load_room_roster()
        # No user_id → empty roster_map → falls through to "No users detected" or default
        assert "No" in result and "users" in result

    def test_exception(self):
        from src.prompts.hud_loaders import _load_room_roster
        with patch("src.prompts.hud_loaders.os.path.exists", side_effect=RuntimeError("disk")):
            result = _load_room_roster()
        assert "roster_error" in result


# --------------- _load_reasoning_context ---------------

class TestLoadReasoningContext:
    def test_no_trace(self):
        from src.prompts.hud_loaders import _load_reasoning_context
        with patch("src.prompts.hud_loaders.os.path.exists", return_value=False):
            result = _load_reasoning_context("PUBLIC", "u1")
        assert "No previous thoughts" in result

    def test_with_trace(self):
        from src.prompts.hud_loaders import _load_reasoning_context
        with patch("src.prompts.hud_loaders.os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="thought 1\nthought 2\n")):
            result = _load_reasoning_context("PUBLIC", "u1")
        assert "thought" in result

    def test_exception(self):
        from src.prompts.hud_loaders import _load_reasoning_context
        with patch("src.prompts.hud_loaders.os.path.exists", side_effect=RuntimeError("boom")):
            result = _load_reasoning_context("PUBLIC", "u1")
        assert "No previous thoughts" in result


# --------------- Extended HUD ---------------

class TestExtendedHud:
    def test_provenance_ledger(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        entry = json.dumps({"filename": "doc.pdf", "type": "claim", "timestamp": "2024-01-01T12:00:00"})
        def side_exists(p):
            return p == "memory/core/provenance_ledger.jsonl"
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=side_exists), \
             patch("builtins.open", mock_open(read_data=entry + "\n")), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert "doc.pdf" in hud["provenance_recent"]

    def test_tool_call_history(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        entry = json.dumps({"user_message": "search for something"})
        def side_exists(p):
            return p == "memory/core/system_turns.jsonl"
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=side_exists), \
             patch("builtins.open", mock_open(read_data=entry + "\n")), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("CORE", "u1", True)
        assert "search for something" in hud["tool_call_history"]

    def test_autonomy_log(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        def side_exists(p):
            return p == "memory/core/stream_of_consciousness.log"
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=side_exists), \
             patch("builtins.open", mock_open(read_data="autonomous thought\n")), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("CORE", "u1", True)
        assert "autonomous thought" in hud["autonomy_log"]

    def test_goals(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        goals = [{"description": "Build spaceship", "completed": False}, {"description": "Done", "completed": True}]
        def side_exists(p):
            return p == "memory/core/goals.json"
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=side_exists), \
             patch("builtins.open", mock_open(read_data=json.dumps(goals))), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert "Build spaceship" in hud["incomplete_goals"]

    def test_research_files(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        def side_exists(p):
            return p == "memory/core/research"
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=side_exists), \
             patch("src.prompts.hud_loaders.glob.glob", return_value=["/fake/report.md"]), \
             patch("src.prompts.hud_loaders.os.path.getmtime", return_value=1700000000), \
             patch("src.prompts.hud_loaders.os.path.basename", return_value="report.md"), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert "report.md" in hud["pending_research"]

    def test_extended_hud_exception(self):
        from src.prompts.hud_loaders import load_ernos_hud
        g = _make_globals_mod()
        def side_exists(p):
            if p == "memory/core/provenance_ledger.jsonl":
                raise RuntimeError("disk error")
            return False
        with patch.dict("sys.modules", {"src.bot": MagicMock(), "src.bot.globals": g}), \
             patch("src.prompts.hud_loaders.os.path.exists", side_effect=side_exists), \
             patch("src.prompts.hud_loaders._load_room_roster", return_value=""), \
             patch("src.prompts.hud_loaders._load_reasoning_context", return_value=""):
            hud = load_ernos_hud("PUBLIC", "u1", False)
        assert isinstance(hud, dict)

    def test_private_scope_skips_provenance_and_tools(self):
        hud = _ernos_hud("PRIVATE", "u1", False, _make_globals_mod())
        assert hud["provenance_recent"] == "No recent claims."
        assert hud["tool_call_history"] == "No recent tool calls."
