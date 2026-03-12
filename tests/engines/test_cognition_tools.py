import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.engines.cognition_tools import execute_tool_step

@pytest.mark.asyncio
async def test_tape_edit_code_aliases():
    """Verify that tape_edit_code can parse LLM-hallucinated aliases like 'file' and 'path'."""
    bot = MagicMock()
    # Mock tape_engine/hippocampus
    tape_machine = MagicMock()
    bot.hippocampus.get_tape.return_value = tape_machine
    
    # We don't bother setting up a real user or scope, just test the tool intercept
    
    # 1. Standard arguments
    args_str = 'file_path="src/main.py", target_string="foo", replacement="bar"'
    res, count, flag = await execute_tool_step(
        bot, MagicMock(), "tape_edit_code", args_str,
        [], {}, 0, "123", None, None, {}, MagicMock(), 100,
        lambda x: {"file_path": "src/main.py", "target_string": "foo", "replacement": "bar"},
        1, False, "turn_1"
    )
    tape_machine.op_edit_code.assert_called_with("src/main.py", "foo", "bar")
    
    # 2. Hallucinated aliases
    tape_machine.reset_mock()
    args_str_alias = 'file="src/test.py", old_string="baz", new_string="qux"'
    res, count, flag = await execute_tool_step(
        bot, MagicMock(), "tape_edit_code", args_str_alias,
        [], {}, 0, "123", None, None, {}, MagicMock(), 100,
        lambda x: {"file": "src/test.py", "old_string": "baz", "new_string": "qux"},
        1, False, "turn_1"
    )
    tape_machine.op_edit_code.assert_called_with("src/test.py", "baz", "qux")

@pytest.mark.asyncio
async def test_tape_revert_code_aliases():
    """Verify that tape_revert_code can parse LLM-hallucinated aliases like 'file'."""
    bot = MagicMock()
    tape_machine = MagicMock()
    bot.hippocampus.get_tape.return_value = tape_machine
    
    args_str_alias = 'file="src/test.py"'
    res, count, flag = await execute_tool_step(
        bot, MagicMock(), "tape_revert_code", args_str_alias,
        [], {}, 0, "123", None, None, {}, MagicMock(), 100,
        lambda x: {"file": "src/test.py"},
        1, False, "turn_1"
    )
    tape_machine.op_revert_code.assert_called_with("src/test.py")
