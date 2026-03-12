import pytest
import os
import shutil
from unittest.mock import patch, MagicMock, AsyncMock
from src.engines.evolution_sandbox import SandboxController

@pytest.fixture
def sandbox_env(tmp_path):
    """Sets up a mock Ernos root directory with dummy src and tests folders."""
    root = tmp_path / "Ernos_Mock"
    src = root / "src"
    tests = root / "tests"
    
    src.mkdir(parents=True)
    tests.mkdir(parents=True)
    
    # Create a dummy target file
    (src / "dummy.py").write_text("def test(): return True")
    
    # Create a passing dummy test
    (tests / "test_dummy.py").write_text("from src.dummy import test\ndef test_pass(): assert test() == True")
    
    # Mock bot
    bot = MagicMock()
    sandbox = SandboxController(bot)
    
    # Override paths to use tmp_path
    sandbox.root_dir = str(root)
    sandbox.sandbox_dir = str(root / ".sandbox")
    
    yield sandbox, root

@pytest.mark.asyncio
async def test_sandbox_clone_creates_isolation(sandbox_env):
    sandbox, root = sandbox_env
    
    sandbox._clone_organism()
    
    # Assert sandbox directory isolated creation
    assert os.path.exists(sandbox.sandbox_dir)
    assert os.path.exists(os.path.join(sandbox.sandbox_dir, "src", "dummy.py"))
    assert os.path.exists(os.path.join(sandbox.sandbox_dir, "tests", "test_dummy.py"))
    
@pytest.mark.asyncio
async def test_sandbox_fitness_evaluation_pass(sandbox_env):
    sandbox, root = sandbox_env
    sandbox._clone_organism()
    
    # Mock process run
    with patch("asyncio.create_subprocess_shell") as mock_subprocess:
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"All 1 tests passed.", b"")
        mock_subprocess.return_value = mock_proc
        
        success, out = await sandbox._run_fitness_evaluation()
        
        assert success is True
        assert "All 1 tests passed." in out
        
@pytest.mark.asyncio
async def test_sandbox_fitness_evaluation_fail(sandbox_env):
    sandbox, root = sandbox_env
    sandbox._clone_organism()
    
    with patch("asyncio.create_subprocess_shell") as mock_subprocess:
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"1 failed.", b"Traceback...")
        mock_subprocess.return_value = mock_proc
        
        success, out = await sandbox._run_fitness_evaluation()
        
        assert success is False
        assert "1 failed." in out
        
@pytest.mark.asyncio
async def test_sandbox_full_lifecycle_merge(sandbox_env):
    sandbox, root = sandbox_env
    
    # Mock evaluation to pass
    with patch.object(sandbox, "_run_fitness_evaluation", new_callable=AsyncMock) as mock_fit:
        mock_fit.return_value = (True, "Passed")
        
        # Run mutation
        result = await sandbox.evaluate_mutation("test_mutation")
        
        assert "SUCCESS" in result
        assert not os.path.exists(sandbox.sandbox_dir) # cleanup should clear it
        
@pytest.mark.asyncio
async def test_sandbox_full_lifecycle_death(sandbox_env):
    sandbox, root = sandbox_env
    
    # Mock evaluation to fail
    with patch.object(sandbox, "_run_fitness_evaluation", new_callable=AsyncMock) as mock_fit:
        mock_fit.return_value = (False, "Failed")
        
        # Run mutation
        result = await sandbox.evaluate_mutation("bad_mutation")
        
        # Assert DEATH
        assert "DEATH" in result
        assert not os.path.exists(sandbox.sandbox_dir) # cleanup clears failed bodies
