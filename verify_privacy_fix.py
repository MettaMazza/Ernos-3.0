import asyncio
import os
import sys
from unittest.mock import patch, mock_open

# Ensure src is in path
sys.path.append(os.getcwd())

from src.prompts.manager import PromptManager

async def test():
    print("Verifying Privacy Leak Fix...")
    pm = PromptManager()
    
    # 1. Test System Turns Leak (Global tool history)
    print("1. Checking System Turns Leak (Global Tool History)...")
    mock_turns = '{"user_message": "SECRET_LEAK_MESSAGE", "ts": "2026-02-06"}\n'
    
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=mock_turns)):
             # Generate prompt in PRIVATE scope
             prompt = pm.get_system_prompt(scope="PRIVATE", user_id="test_user", channel_id="dm")
             
             if "SECRET_LEAK_MESSAGE" in prompt:
                 print("FAIL: Global tool history (SECRET_LEAK_MESSAGE) found in PRIVATE prompt!")
                 sys.exit(1)
             else:
                 print("PASS: Global tool history redacted in PRIVATE scope.")

    # 2. Test Autonomy Log Leak (Internal thoughts)
    print("2. Checking Autonomy Log Leak (Internal Thoughts)...")
    mock_soc = 'Thinking about SECRET_OTHER_USER private data...\n'
    
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=mock_soc)):
             prompt = pm.get_system_prompt(scope="PRIVATE", user_id="test_user", channel_id="dm")
             
             if "SECRET_OTHER_USER" in prompt:
                 print("FAIL: Autonomy log (SECRET_OTHER_USER) found in PRIVATE prompt!")
                 sys.exit(1)
             else:
                 print("PASS: Autonomy log redacted in PRIVATE scope.")

    # 3. Test Provenance Leak
    print("3. Checking Provenance Ledger Leak...")
    mock_prov = '{"filename": "SECRET_FILE.txt", "type": "create"}\n'
    
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=mock_prov)):
             prompt = pm.get_system_prompt(scope="PRIVATE", user_id="test_user", channel_id="dm")
             
             if "SECRET_FILE.txt" in prompt:
                 print("FAIL: Provenance ledger (SECRET_FILE.txt) found in PRIVATE prompt!")
                 sys.exit(1)
             else:
                 print("PASS: Provenance ledger redacted in PRIVATE scope.")

    print("\nSUCCESS: All privacy checks PASSED. No global data leaks in PRIVATE scope.")

if __name__ == "__main__":
    try:
        asyncio.run(test())
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
