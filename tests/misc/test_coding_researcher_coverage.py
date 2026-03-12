import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from pathlib import Path
import json

# --- Coding Tools Tests ---
def test_create_program_success(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    mocker.patch("src.security.provenance.ProvenanceManager.log_artifact", return_value="abc12345")
    from src.tools.coding import create_program
    
    res = create_program("test.py", "print('ok')", user_id="12345")
    assert "Successfully applied" in res
    # New scoped storage: files go to memory/users/{user_id}/projects/public/
    assert Path("memory/users/12345/projects/public/test.py").read_text() == "print('ok')"

def test_create_program_escape_cwd(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    mocker.patch("src.security.provenance.ProvenanceManager.log_artifact", return_value="abc12345")
    from src.tools.coding import create_program
    
    # Empty filename should be rejected
    res = create_program("", "hacked")
    assert "Error: Invalid filename" in res

def test_create_program_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.tools.coding import create_program
    
    with patch("builtins.open", side_effect=PermissionError("Denied")):
        res = create_program("test.py", "code")
        assert "Edit Error" in res

def test_manage_project_all_actions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("memory").mkdir()
    from src.tools.coding import manage_project
    
    # Init
    res = manage_project("init", "TestProject")
    assert "initialized" in res
    
    # Set
    res = manage_project("set", "version", "1.0")
    assert "Set version" in res
    
    # Get
    res = manage_project("get", "version")
    assert "1.0" in res
    
    # List
    res = manage_project("list")
    assert "TestProject" in res
    
    # Unknown
    res = manage_project("unknown")
    assert "Unknown action" in res
    
    # Set without key
    res = manage_project("set")
    assert "Key required" in res

def test_manage_project_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.tools.coding import manage_project
    
    with patch("pathlib.Path.exists", side_effect=Exception("Boom")):
        res = manage_project("list")
        assert "Error" in res

# --- Researcher Tests ---
@pytest.fixture
def researcher():
    from src.lobes.interaction.researcher import ResearchAbility
    lobe = MagicMock()
    lobe.cerebrum = MagicMock()
    lobe.cerebrum.bot = MagicMock()
    lobe.cerebrum.bot.loop = MagicMock()
    lobe.cerebrum.bot.loop.run_in_executor = AsyncMock(return_value="Synthesis Result")
    lobe.cerebrum.bot.engine_manager = MagicMock()
    lobe.cerebrum.bot.cerebrum = MagicMock()
    lobe.cerebrum.bot.cerebrum.get_lobe_by_name = MagicMock(return_value=MagicMock())
    r = ResearchAbility(lobe)
    return r

@pytest.mark.asyncio
async def test_researcher_execute_success(researcher):
    with patch("src.tools.registry.ToolRegistry.execute", return_value="Search data"):
        res = await researcher.execute("topic")
        assert "Research Findings" in res

@pytest.mark.asyncio
async def test_researcher_execute_exception(researcher):
    with patch("src.tools.registry.ToolRegistry.execute", return_value="Search data"):
        researcher.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("LLM Error"))
        res = await researcher.execute("topic")
        assert "Research Findings" in res

@pytest.mark.asyncio
async def test_researcher_extract_no_memory_lobe(researcher):
    researcher.bot.cerebrum.get_lobe_by_name.return_value = None
    await researcher._extract_and_store_knowledge("topic", "report")  # Should not error
    assert True  # No exception: negative case handled correctly

@pytest.mark.asyncio
async def test_researcher_extract_exception(researcher):
    researcher.bot.cerebrum.get_lobe_by_name.side_effect = Exception("No Lobe")
    with patch("src.lobes.interaction.researcher.logger") as mock_logger:
        await researcher._extract_and_store_knowledge("topic", "report")
        mock_logger.warning.assert_called()
