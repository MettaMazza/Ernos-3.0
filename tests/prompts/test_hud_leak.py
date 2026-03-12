import pytest
from unittest.mock import patch, mock_open
from src.prompts.hud_loaders import load_ernos_hud

def test_hud_log_sanitization_leak():
    """
    Verify that sensitive log lines are redacted even in PRIVATE scope,
    preventing cross-persona leaks via system logs.
    """
    # Simulate a log file containing sensitive info from another persona/user
    sensitive_logs = [
        "2026-02-07 10:00:00 [INFO] ChatCog: Received message from UserA: 'My secret password is 123'\n",
        "2026-02-07 10:00:01 [INFO] Tool: update_persona executed for Solance\n",
        "2026-02-07 10:00:02 [INFO] ChatCog: Sending response to UserA: 'Secret stored.'\n"
    ]
    
    mock_file = mock_open(read_data="".join(sensitive_logs))
    
    # 1. Test PUBLIC scope (Already sanitized)
    with patch("builtins.open", mock_file):
        with patch("os.path.exists", return_value=True):
            hud = load_ernos_hud("PUBLIC", "UserB", is_core=False)
            logs = hud["terminal_tail"]
            assert "secret password" not in logs
            assert "UserA" not in logs # sanitized
            
    # 2. Test PRIVATE scope (THE LEAK)
    # Before fix, this would show raw logs. After fix, it should be sanitized.
    with patch("builtins.open", mock_file):
        with patch("os.path.exists", return_value=True):
            # Simulate UserB (Ernos) looking at logs in DM (PRIVATE)
            hud = load_ernos_hud("PRIVATE", "UserB", is_core=False)
            logs = hud["terminal_tail"]
            
            # This assertion validates the Fix
            if "secret password" in logs:
                pytest.fail("LEAK DETECTED: PRIVATE scope HUD reveals sensitive log data!")
            
    # 3. Test CORE scope (God Mode)
    # This should still show raw logs for debugging by Admin
    with patch("builtins.open", mock_file):
        with patch("os.path.exists", return_value=True):
            hud = load_ernos_hud("CORE", "Admin", is_core=True)
            logs = hud["terminal_tail"]
            assert "secret password" in logs # Admin should see it
