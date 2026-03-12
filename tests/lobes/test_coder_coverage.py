import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from src.lobes.strategy.coder import CoderAbility
import asyncio

@pytest.fixture
def coder_ability():
    mock_lobe = MagicMock()
    mock_lobe.cerebrum.bot = MagicMock()
    # Mock loop and engine
    mock_lobe.cerebrum.bot.loop.run_in_executor = AsyncMock(return_value="print('Hello')")
    mock_lobe.cerebrum.bot.engine_manager.get_active_engine.return_value.generate_response = MagicMock()
    return CoderAbility(mock_lobe)

@pytest.mark.asyncio
async def test_create_script_success(coder_ability):
    # Mock subprocess success logic
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Success", b"")
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("src.core.secure_loader.load_prompt", return_value="Prompt"):
             res = await coder_ability.create_script("Build app")
             
    assert res["success"] is True
    assert res["output"] == "Success"
    assert res["retries"] == 0

@pytest.mark.asyncio
async def test_create_script_retry_success(coder_ability):
    # 1. Fail first
    proc_fail = AsyncMock()
    proc_fail.returncode = 1
    proc_fail.communicate.return_value = (b"", b"SyntaxError")
    
    # 2. Success second
    proc_ok = AsyncMock()
    proc_ok.returncode = 0
    proc_ok.communicate.return_value = (b"Fixed", b"")
    
    with patch("asyncio.create_subprocess_exec", side_effect=[proc_fail, proc_ok]):
        with patch("src.core.secure_loader.load_prompt", return_value="Prompt"):
             # Mock _fix_code to verify it called LLM
             with patch.object(coder_ability, "_fix_code", return_value="print('fixed')") as mock_fix:
                 res = await coder_ability.create_script("Build app")
                 
    assert res["success"] is True
    assert res["output"] == "Fixed"
    assert res["retries"] == 1
    mock_fix.assert_awaited()

@pytest.mark.asyncio
async def test_create_script_fail_exhausted(coder_ability):
    # Always fail
    proc_fail = AsyncMock()
    proc_fail.returncode = 1
    proc_fail.communicate.return_value = (b"", b"Error")
    
    with patch("asyncio.create_subprocess_exec", return_value=proc_fail):
        with patch("src.core.secure_loader.load_prompt", return_value="Prompt"):
             res = await coder_ability.create_script("Build app")
    
    assert res["success"] is False
    assert res["retries"] == 10
    assert res["output"] == "Error"

@pytest.mark.asyncio
async def test_create_script_execution_error(coder_ability):
    # Subprocess raises Exception
    with patch("asyncio.create_subprocess_exec", side_effect=Exception("Subprocess Crash")):
        with patch("src.core.secure_loader.load_prompt", return_value="Prompt"):
             res = await coder_ability.create_script("Build app")
             
    assert res["success"] is False
    assert "Subprocess Crash" in res["error"]

@pytest.mark.asyncio
async def test_generate_code_error(coder_ability):
    # Mock secure_loader to simulate failure
    with patch("src.core.secure_loader.load_prompt", side_effect=FileNotFoundError("missing")):
        res = await coder_ability._generate_code("fail")
    assert "Generation Error" in res

@pytest.mark.asyncio
async def test_fix_code_error(coder_ability):
    # Mock secure_loader to simulate failure
    with patch("src.core.secure_loader.load_prompt", side_effect=FileNotFoundError("missing")):
        res = await coder_ability._fix_code("code", "err")
    # Returns original code on error
    assert res == "code"

@pytest.mark.asyncio
async def test_create_script_cleanup(coder_ability, tmp_path):
    # Verify file deletion
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"", b"")
    
    # We want to check unlink called.
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("src.core.secure_loader.load_prompt", return_value="Prompt"):
             with patch("os.unlink") as mock_unlink:
                 await coder_ability.create_script("test")
                 mock_unlink.assert_called()
