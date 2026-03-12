import pytest
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.tools.registry import ToolRegistry, ToolDefinition
from src.tools import definitions

# --- Registry Tests ---

def test_registry_registration():
    @ToolRegistry.register(name="test_tool", description="A test tool.")
    def test_tool(arg: str):
        return arg
        assert True  # Execution completed without error
    
    tools = ToolRegistry.list_tools()
    assert any(t.name == "test_tool" for t in tools)
    assert ToolRegistry.get_tool("test_tool").description == "A test tool."

@pytest.mark.asyncio
async def test_registry_execution_sync():
    res = await ToolRegistry.execute("test_tool", "echo")
    assert res == "echo"

@pytest.mark.asyncio
async def test_registry_execution_async():
    @ToolRegistry.register(name="async_tool")
    async def async_tool():
        return "async"
    
    res = await ToolRegistry.execute("async_tool")
    assert res == "async"

@pytest.mark.asyncio
async def test_registry_execution_fail():
    with pytest.raises(ValueError):
        await ToolRegistry.execute("unknown_tool")

# --- Definition Tests ---

def test_read_file_page(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("line1\nline2\nline3\nline4")
    
    # Normal read
    res = definitions.read_file_page(str(f), start_line=1, limit=2)
    assert "line1\nline2" in res
    assert "Lines: 1-2/4" in res
    
    # Offset read
    res = definitions.read_file_page(str(f), start_line=3, limit=10)
    assert "line3\nline4" in res
    
    # Missing file
    res = definitions.read_file_page("missing.txt")
    assert "Error: File not found" in res

    # Read Exception
    with patch("builtins.open", side_effect=Exception("Read Fail")):
         res = definitions.read_file_page(str(f))
         assert "Error reading file: Read Fail" in res

def test_search_codebase(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "file.py").write_text("def foo():\n    pass")
    (d / "README.md").write_text("# Ernos")
    
    # Use patch to mock os.walk to point to tmp_path or just pass path if tool allows
    # Tool def: search_codebase(query, path="./src")
    
    res = definitions.search_codebase("foo", path=str(d))
    assert "file.py:1: def foo():" in res
    
    res = definitions.search_codebase("bar", path=str(d))
    assert "No matches found." in res
    
    # Exception handling
    with patch("os.walk", side_effect=Exception("Disk Error")):
        res = definitions.search_codebase("foo")
        assert "Search Error" in res

    # Truncation Test
    # Create file with many matches
    (d / "big.py").write_text("\n".join(["match"] * 30))
    res = definitions.search_codebase("match", path=str(d))
    assert "... (truncated)" in res

def test_search_web_success():
    mock_ddgs_module = MagicMock()
    mock_ddgs_instance = mock_ddgs_module.DDGS.return_value.__enter__.return_value
    mock_ddgs_instance.text.return_value = [
        {"title": "Test Result", "href": "http://test.com", "body": "Snippet"}
    ]
    
    with patch.dict("sys.modules", {"ddgs": mock_ddgs_module}):
        result = definitions.search_web("test")
        assert "Test Result" in result

@patch("src.tools.web._fallback_yahoo_search", return_value=[])
@patch("src.tools.web._fallback_google_search", return_value=[])
@patch("src.tools.web._fallback_bing_search", return_value=[])
def test_search_web_no_results(mock_bing, mock_google, mock_yahoo):
    mock_ddgs_cls = MagicMock()
    mock_ddgs_cls.DDGS.return_value.__enter__.return_value.text.return_value = []
    
    with patch.dict("sys.modules", {"ddgs": mock_ddgs_cls}):
        result = definitions.search_web("test")
        mock_google.assert_called_once()
        mock_bing.assert_called_once()
        mock_yahoo.assert_called_once()
        assert "No results found across DDGS" in result

@patch("src.tools.web._fallback_yahoo_search", return_value=[])
@patch("src.tools.web._fallback_google_search", return_value=[])
@patch("src.tools.web._fallback_bing_search", return_value=[])
def test_search_web_import_error(mock_bing, mock_google, mock_yahoo):
    with patch.dict("sys.modules", {"ddgs": None}):
        result = definitions.search_web("test")
        mock_google.assert_called_once()
        mock_bing.assert_called_once()
        mock_yahoo.assert_called_once()
        assert "No results found across DDGS" in result

def test_browse_site_success():
    mock_requests = MagicMock()
    mock_requests.get.return_value.text = "<html><body><p>Hello World</p></body></html>"
    mock_requests.get.return_value.raise_for_status = MagicMock()
    
    mock_bs4 = MagicMock()
    mock_soup = MagicMock()
    mock_soup.get_text.return_value = "Hello World"
    # soup(["script",...]) returns iterator.
    mock_soup.return_value = [] 
    
    mock_bs4.BeautifulSoup.return_value = mock_soup
    
    with patch.dict("sys.modules", {"requests": mock_requests, "bs4": mock_bs4}), \
         patch("src.tools.web._is_safe_url", return_value=True):
        result = definitions.browse_site("http://test.com")
        assert "Hello World" in result

def test_browse_site_error(mocker):
    mock_requests = MagicMock()
    mock_requests.get.side_effect = Exception("Connection Failed")
    
    with patch.dict("sys.modules", {"requests": mock_requests, "bs4": MagicMock()}), \
         patch("src.tools.web._is_safe_url", return_value=True):
        result = definitions.browse_site("http://test.com")
        assert "Browse Error" in result

def test_manage_goals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Goals are now user-scoped, so pass user_id
    test_user_id = "12345"
    
    # Create user silo dir
    user_silo = tmp_path / "memory" / "users" / test_user_id
    user_silo.mkdir(parents=True)
    
    # Add
    res = definitions.manage_goals("add", "Take over world", user_id=test_user_id)
    assert "Goal added" in res
    
    # Extract actual goal ID from response (format: "Goal added (ID: goal_xxxx, ...)")
    import re
    goal_id_match = re.search(r'ID: (goal_\w+)', res)
    assert goal_id_match, f"Could not extract goal_id from: {res}"
    goal_id = goal_id_match.group(1)
    
    # Verify file content
    goals_file = user_silo / "goals.json"
    assert "Take over world" in goals_file.read_text()
    
    # List
    res = definitions.manage_goals("list", user_id=test_user_id)
    assert "Take over world" in res
    
    # Complete
    res = definitions.manage_goals("complete", goal_id=goal_id, user_id=test_user_id)
    assert "completed" in res.lower()
        
def test_manage_goals_error():
    with patch("src.memory.goals.get_goal_manager", side_effect=Exception("JSON Fail")):
        result = definitions.manage_goals("list", user_id="12345")
        assert "Error" in result

def test_update_persona_core_blocked():
     from src.tools.memory import update_persona
     result = update_persona("Valid persona", request_scope="CORE")
     assert "PromptTuner" in result
     assert "disabled" in result
