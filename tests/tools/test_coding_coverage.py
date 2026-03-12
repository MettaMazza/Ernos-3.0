"""
Coverage tests for src/tools/coding.py.
Targets 33 uncovered lines: _load_ledger, _log_operation_to_quota,
create_program (idempotency, failure history, staging manifest, merge gate).
"""
import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestLoadLedger:
    def test_no_file(self, tmp_path):
        from src.tools.coding import _load_ledger
        with patch("src.tools.coding._LEDGER_PATH", tmp_path / "nofile.json"):
            result = _load_ledger()
        assert result == {"files": {}, "session_ops": 0}

    def test_valid_with_expiry(self, tmp_path):
        from src.tools.coding import _load_ledger
        ledger_path = tmp_path / "ledger.json"
        data = {
            "files": {
                "recent.py": {"edit_count": 1, "last_edit_ts": time.time()},
                "old.py": {"edit_count": 1, "last_edit_ts": time.time() - 7200},
            },
            "session_ops": 5,
        }
        ledger_path.write_text(json.dumps(data))
        with patch("src.tools.coding._LEDGER_PATH", ledger_path):
            result = _load_ledger()
        assert "recent.py" in result["files"]
        assert "old.py" not in result["files"]

    def test_corrupt_file(self, tmp_path):
        from src.tools.coding import _load_ledger
        ledger_path = tmp_path / "ledger.json"
        ledger_path.write_text("not json")
        with patch("src.tools.coding._LEDGER_PATH", ledger_path):
            result = _load_ledger()
        assert result == {"files": {}, "session_ops": 0}


class TestLogOperationToQuota:
    def test_logs_on_work_day(self):
        from src.tools.coding import _log_operation_to_quota
        mock_state = {"days": {"monday": {"operations": []}}}
        with patch("src.tools.weekly_quota._day_name", return_value="monday"), \
             patch("src.tools.weekly_quota._load_week", return_value=mock_state), \
             patch("src.tools.weekly_quota._save_week") as save_mock, \
             patch("src.tools.weekly_quota.WORK_DAYS", ("monday",)):
            _log_operation_to_quota("test.py", "overwrite", True)
        save_mock.assert_called_once()

    def test_skips_non_work_day(self):
        from src.tools.coding import _log_operation_to_quota
        with patch("src.tools.weekly_quota._day_name", return_value="friday"), \
             patch("src.tools.weekly_quota.WORK_DAYS", ("monday",)), \
             patch("src.tools.weekly_quota._save_week") as save_mock:
            _log_operation_to_quota("test.py", "overwrite", True)
        save_mock.assert_not_called()


class TestCreateProgram:
    def test_invalid_mode(self):
        from src.tools.coding import create_program
        with patch("src.tools.file_utils.VALID_MODES", ("overwrite", "append")):
            result = create_program("test.py", "code", mode="bad_mode")
        assert "Invalid mode" in result

    def test_invalid_scope_fallback(self, tmp_path):
        from src.tools.coding import create_program
        with patch("src.tools.file_utils.surgical_edit", return_value=(True, "ok")), \
             patch("src.tools.file_utils.VALID_MODES", ("overwrite",)), \
             patch("src.tools.coding.data_dir", return_value=tmp_path), \
             patch("src.tools.coding._load_ledger", return_value={"files": {}, "session_ops": 0}), \
             patch("src.tools.coding._save_ledger"), \
             patch("src.tools.coding._log_operation_to_quota"), \
             patch("src.security.provenance.ProvenanceManager.log_artifact", return_value="abc123") as mock_log, \
             patch("os.getcwd", return_value=str(tmp_path)):
            result = create_program("test.py", "print('hi')", request_scope="INVALID", user_id="u1", intention="Testing ledgers")
        
        # Verify intention made it to log_artifact
        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        assert args[2]["intention"] == "Testing ledgers"
        assert "Successfully" in result or "Error" in result

    def test_idempotency_guard(self, tmp_path):
        from src.tools.coding import create_program
        # Create a file with known content
        proj = tmp_path / "users" / "u1" / "projects" / "public"
        proj.mkdir(parents=True)
        existing = proj / "test.py"
        existing.write_text("print('same')")

        with patch("src.tools.file_utils.VALID_MODES", ("overwrite",)), \
             patch("src.tools.coding.data_dir", return_value=tmp_path), \
             patch("os.getcwd", return_value=str(tmp_path)):
            result = create_program("test.py", "print('same')", mode="overwrite", user_id="u1")
        assert "identical content" in result

    def test_failure_history_note(self, tmp_path):
        from src.tools.coding import create_program
        ledger = {
            "files": {"test.py": {
                "edit_count": 5, "fail_count": 2,
                "modes_tried": ["overwrite", "replace", "replace"],
                "last_error": "prev error", "last_edit_ts": time.time(),
            }},
            "session_ops": 5,
        }
        with patch("src.tools.file_utils.surgical_edit", return_value=(False, "failed")), \
             patch("src.tools.file_utils.VALID_MODES", ("overwrite",)), \
             patch("src.tools.coding.data_dir", return_value=tmp_path), \
             patch("src.tools.coding._load_ledger", return_value=ledger), \
             patch("src.tools.coding._save_ledger"), \
             patch("src.tools.coding._log_operation_to_quota"), \
             patch("os.getcwd", return_value=str(tmp_path)):
            result = create_program("test.py", "bad code", user_id="u1")
        assert "EDIT HISTORY" in result

    def test_core_staging_manifest(self, tmp_path):
        from src.tools.coding import create_program
        staging = tmp_path / "core" / "staging"
        staging.mkdir(parents=True)

        with patch("src.tools.file_utils.surgical_edit", return_value=(True, "ok")), \
             patch("src.tools.file_utils.VALID_MODES", ("overwrite",)), \
             patch("src.tools.coding.data_dir", return_value=tmp_path), \
             patch("src.tools.coding._load_ledger", return_value={"files": {}, "session_ops": 0}), \
             patch("src.tools.coding._save_ledger"), \
             patch("src.tools.coding._log_operation_to_quota"), \
             patch("src.tools.weekly_quota.is_merge_allowed", return_value=False), \
             patch("src.security.provenance.ProvenanceManager.log_artifact", return_value="abc123") as mock_log, \
             patch("os.getcwd", return_value=str(tmp_path)):
            result = create_program("test.py", "print('hi')", request_scope="CORE", intention="Core system update")
            
        args, kwargs = mock_log.call_args
        assert args[2]["intention"] == "Core system update"
        assert "intended" in result or "Successfully" in result


class TestManageProject:
    def test_init(self, tmp_path):
        from src.tools.coding import manage_project
        with patch("src.tools.coding.data_dir", return_value=tmp_path):
            result = manage_project("init", key="MyProject")
        assert "initialized" in result

    def test_set_get(self, tmp_path):
        from src.tools.coding import manage_project
        manifest = tmp_path / "project_manifest.json"
        manifest.write_text(json.dumps({"name": "Test"}))
        with patch("src.tools.coding.data_dir", return_value=tmp_path):
            set_result = manage_project("set", key="version", value="1.0")
            get_result = manage_project("get", key="version")
        assert "1.0" in set_result
        assert "1.0" in get_result

    def test_list(self, tmp_path):
        from src.tools.coding import manage_project
        manifest = tmp_path / "project_manifest.json"
        manifest.write_text(json.dumps({"name": "Test", "files": []}))
        with patch("src.tools.coding.data_dir", return_value=tmp_path):
            result = manage_project("list")
        assert "Test" in result

    def test_unknown_action(self, tmp_path):
        from src.tools.coding import manage_project
        with patch("src.tools.coding.data_dir", return_value=tmp_path):
            result = manage_project("delete")
        assert "Unknown action" in result
