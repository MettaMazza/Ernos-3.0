"""
Coverage tests for src/tools/recall_tools.py.
Targets 51 uncovered lines across: search_context_logs, review_my_reasoning.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── search_context_logs ──────────────────────────────────
class TestSearchContextLogs:
    def test_no_user_id(self):
        from src.tools.recall_tools import search_context_logs
        with patch("src.tools.recall_tools.globals") as g:
            g.active_message.get.return_value = None
            result = search_context_logs(query="hello")
        assert "user_id is required" in result

    def test_infer_user_id(self, tmp_path):
        from src.tools.recall_tools import search_context_logs
        msg = MagicMock()
        msg.author.id = 12345
        user_dir = tmp_path / "12345"
        user_dir.mkdir()
        log = user_dir / "context_public.jsonl"
        log.write_text(json.dumps({"user": "hi", "bot": "hello", "ts": "t1", "salience": 5}) + "\n")
        with patch("src.tools.recall_tools.globals") as g, \
             patch("src.privacy.scopes.ScopeManager._resolve_user_dir", return_value=user_dir):
            g.active_message.get.return_value = msg
            result = search_context_logs(query="hi")
        assert "12345" in result

    def test_no_query(self):
        from src.tools.recall_tools import search_context_logs
        result = search_context_logs(user_id="123")
        assert "query is required" in result

    def test_invalid_user_id(self):
        from src.tools.recall_tools import search_context_logs
        result = search_context_logs(user_id="abc", query="test")
        assert "Invalid user_id" in result

    def test_no_logs_found(self, tmp_path):
        from src.tools.recall_tools import search_context_logs
        user_dir = tmp_path / "123"
        user_dir.mkdir()
        with patch("src.privacy.scopes.ScopeManager._resolve_user_dir", return_value=user_dir):
            result = search_context_logs(user_id="123", query="test")
        assert "No context logs" in result

    def test_public_search_match(self, tmp_path):
        from src.tools.recall_tools import search_context_logs
        user_dir = tmp_path / "123"
        user_dir.mkdir()
        log = user_dir / "context_public.jsonl"
        log.write_text(
            json.dumps({"user": "tell me about cats", "bot": "cats are cool", "ts": "2026-01-01", "salience": 5}) + "\n" +
            json.dumps({"user": "what about dogs", "bot": "dogs are great", "ts": "2026-01-02", "salience": 3}) + "\n"
        )
        with patch("src.privacy.scopes.ScopeManager._resolve_user_dir", return_value=user_dir):
            result = search_context_logs(user_id="123", query="cats", request_scope="PUBLIC")
        assert "cats" in result
        assert "2026-01-01" in result

    def test_private_scope_searches_both(self, tmp_path):
        from src.tools.recall_tools import search_context_logs
        user_dir = tmp_path / "123"
        user_dir.mkdir()
        (user_dir / "context_public.jsonl").write_text(
            json.dumps({"user": "public msg", "bot": "pub reply", "ts": "t1", "salience": 1}) + "\n"
        )
        (user_dir / "context_private.jsonl").write_text(
            json.dumps({"user": "private secret", "bot": "priv reply", "ts": "t2", "salience": 2}) + "\n"
        )
        with patch("src.privacy.scopes.ScopeManager._resolve_user_dir", return_value=user_dir):
            result = search_context_logs(user_id="123", query="secret", request_scope="PRIVATE")
        assert "PRIVATE" in result
        assert "secret" in result

    def test_no_matches(self, tmp_path):
        from src.tools.recall_tools import search_context_logs
        user_dir = tmp_path / "123"
        user_dir.mkdir()
        (user_dir / "context_public.jsonl").write_text(
            json.dumps({"user": "hello", "bot": "world", "ts": "t1", "salience": 1}) + "\n"
        )
        with patch("src.privacy.scopes.ScopeManager._resolve_user_dir", return_value=user_dir):
            result = search_context_logs(user_id="123", query="xyz_not_found")
        assert "No context log entries" in result

    def test_empty_lines_skipped(self, tmp_path):
        from src.tools.recall_tools import search_context_logs
        user_dir = tmp_path / "123"
        user_dir.mkdir()
        (user_dir / "context_public.jsonl").write_text(
            "\n\n" +
            json.dumps({"user": "data", "bot": "response", "ts": "t1", "salience": 1}) + "\n" +
            "bad json line\n"
        )
        with patch("src.privacy.scopes.ScopeManager._resolve_user_dir", return_value=user_dir):
            result = search_context_logs(user_id="123", query="data")
        assert "data" in result

    def test_limit(self, tmp_path):
        from src.tools.recall_tools import search_context_logs
        user_dir = tmp_path / "123"
        user_dir.mkdir()
        lines = []
        for i in range(20):
            lines.append(json.dumps({"user": f"msg {i}", "bot": "reply", "ts": f"t{i}", "salience": 1}))
        (user_dir / "context_public.jsonl").write_text("\n".join(lines) + "\n")
        with patch("src.privacy.scopes.ScopeManager._resolve_user_dir", return_value=user_dir):
            result = search_context_logs(user_id="123", query="msg", limit=3)
        assert "3 matching" in result


# ── review_my_reasoning ──────────────────────────────────
class TestReviewMyReasoning:
    def test_private_scope(self, tmp_path):
        from src.tools.recall_tools import review_my_reasoning
        trace_file = tmp_path / "reasoning_private.log"
        trace_file.write_text("TRACE: thinking about stuff\n" * 30)
        with patch("src.tools.recall_tools.globals") as g, \
             patch("src.tools.recall_tools.data_dir", return_value=tmp_path / "data"), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:
            g.active_message.get.return_value = None
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            mock_open.return_value.readlines.return_value = ["trace line\n"] * 30
            result = review_my_reasoning(limit=2, request_scope="PRIVATE", user_id="123")
        assert "PRIVATE" in result

    def test_core_scope(self, tmp_path):
        from src.tools.recall_tools import review_my_reasoning
        with patch("src.tools.recall_tools.globals") as g, \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", create=True) as mock_open:
            g.active_message.get.return_value = None
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            mock_open.return_value.readlines.return_value = ["core trace\n"]
            result = review_my_reasoning(limit=1, request_scope="CORE")
        assert "CORE" in result

    def test_no_traces_found(self):
        from src.tools.recall_tools import review_my_reasoning
        with patch("src.tools.recall_tools.globals") as g, \
             patch("os.path.exists", return_value=False):
            g.active_message.get.return_value = None
            result = review_my_reasoning(limit=1, user_id="123")
        assert "No" in result and "traces" in result.lower()
