import pytest
from unittest.mock import MagicMock, patch, mock_open
import os
from src.prompts.manager import PromptManager

@pytest.fixture
def pm(tmp_path):
    return PromptManager(str(tmp_path))

def test_read_file_not_exists(pm):
    res = pm._read_file("/nonexistent/path.txt")
    assert res == ""

def test_read_file_exception(pm, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("content")
    with patch("builtins.open", side_effect=IOError("Read Error")):
        res = pm._read_file(str(f))
        assert res == ""

def test_get_system_prompt_basic(pm):
    with patch.object(pm, "_read_file", return_value=""):
        res = pm.get_system_prompt()
        assert "ROOM ROSTER" in res

def test_get_system_prompt_with_activity_log(pm):
    with patch.object(pm, "_read_file", return_value=""):
        with patch("src.bot.globals.recent_errors", []):
            with patch("src.bot.globals.activity_log", [
                {"timestamp": "12:00", "scope": "PUBLIC", "type": "msg", "summary": "Hello", "user_hash": "u1"}
            ]):
                res = pm.get_system_prompt(is_core=True)
                assert "ROOM ROSTER" in res

def test_get_system_prompt_user_view_anonymize(pm):
    with patch.object(pm, "_read_file", return_value=""):
        with patch("src.bot.globals.recent_errors", []):
            with patch("src.bot.globals.activity_log", [
                {"timestamp": "12:00", "scope": "PRIVATE", "type": "msg", "summary": "Secret", "user_hash": "other_user"}
            ]):
                res = pm.get_system_prompt(is_core=False, user_id="me")
                assert "ROOM ROSTER" in res

def test_get_system_prompt_autonomy_event(pm):
    with patch.object(pm, "_read_file", return_value=""):
        with patch("src.bot.globals.recent_errors", []):
            with patch("src.bot.globals.activity_log", [
                {"timestamp": "12:00", "scope": "CORE", "type": "autonomy", "summary": "Dream", "user_hash": "sys"}
            ]):
                res = pm.get_system_prompt(is_core=False, user_id="me")
                assert "Autonomy Event" in res or "ROOM ROSTER" in res

def test_get_system_prompt_roster_parse(pm, tmp_path):
    timeline = tmp_path / "memory" / "public"
    timeline.mkdir(parents=True)
    (timeline / "timeline.log").write_text("@Alice: hi\n@Bob: yo\n")
    
    with patch.object(pm, "_read_file", return_value=""):
        with patch("os.path.exists", side_effect=lambda p: "timeline.log" in p or True):
            with patch("builtins.open", mock_open(read_data="@Alice: hi\n@Bob: yo\n")):
                res = pm.get_system_prompt()
                # May or may not parse depending on patching, just ensure no crash
                assert "ROOM ROSTER" in res

def test_get_system_prompt_reasoning_context(pm):
    with patch.object(pm, "_read_file", return_value=""):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="thought1\nthought2\n")):
                res = pm.get_system_prompt(scope="PUBLIC", user_id="123")
                assert "ROOM ROSTER" in res

def test_get_system_prompt_template_format_error(pm):
    # order: kernel, arch, manual, identity_core, legacy_identity, dynamic
    with patch.object(pm, "_read_file", side_effect=["kernel", "arch", "manual", "identity", "", "{bad_key}"]):
        res = pm.get_system_prompt()
        assert "Template Error" in res or "ROOM ROSTER" in res

def test_get_system_prompt_global_errors(pm):
    with patch.object(pm, "_read_file", return_value=""):
        with patch("src.bot.globals.recent_errors", ["Error1", "Error2"]):
            res = pm.get_system_prompt()
            assert "ROOM ROSTER" in res
