import pytest
import asyncio
import os
import json
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from src.tools.definitions import (
    read_file_page, search_codebase, search_web, browse_site, 
    check_world_news, start_deep_research,
    manage_goals, add_reaction, recall_user, review_my_reasoning,
    publish_to_bridge, read_public_bridge, evaluate_advice,
    create_program, manage_project
)
from src.tools.memory import update_persona
from src.bot import globals

# --- File System Tools ---

def test_read_file_page_missing():
    assert "Error: File not found" in read_file_page("nonexistent.txt")

def test_read_file_page_error(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", side_effect=Exception("Read Fail"))
    assert "Error reading file" in read_file_page("file.txt")

def test_search_codebase_success(tmp_path):
    (tmp_path / "t.py").write_text("def test(): pass")
    res = search_codebase("def", str(tmp_path))
    assert "t.py" in res

def test_search_codebase_empty(tmp_path):
    res = search_codebase("xyz", str(tmp_path))
    assert "No matches found" in res

def test_search_codebase_error(mocker):
    mocker.patch("os.walk", side_effect=Exception("Walk error"))
    assert "Search Error" in search_codebase("query")

# --- Web Tools ---

def test_search_web_success(mocker):
    # Mock the module globally since it might not be installed
    mock_ddgs_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.text.return_value = [{'title': 'T', 'href': 'H', 'body': 'B'}]
    mock_ddgs_cls.DDGS.return_value = mock_instance
    
    with patch.dict("sys.modules", {"ddgs": mock_ddgs_cls}):
        res = search_web("q")
        assert "Title: T" in res

def test_search_web_empty(mocker):
    mock_ddgs_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.text.return_value = []
    mock_ddgs_cls.DDGS.return_value = mock_instance

    with patch.dict("sys.modules", {"ddgs": mock_ddgs_cls}):
        res = search_web("q")
        assert "No results found" in res

def test_search_web_import_error(mocker):
    # If we don't patch sys.modules, and it's missing, it raises ImportError naturally?
    # Or we verify it raises/returns error string.
    # The code: except ImportError: return "Error: duckduckgo-search module not found..."
    # If the module is really missing, calling `import duckduckgo_search` raises ImportError.
    # So we just ensure it is missing?
    # Patch the helper function to return None (simulating ImportError caught inside it)
    # or patch behaviors.
    # The code: DDGS = _get_ddgs(); if DDGS is None: raise ImportError
    # So patching _get_ddgs to return None triggers the ImportError we want.
    
    # Use Dependency Injection for robust testing
    res = search_web("q", _loader=lambda: None)
    assert "Error" in res


def test_search_web_generic_error(mocker):
    mock_ddgs_cls = MagicMock()
    mock_ddgs_cls.DDGS.side_effect = Exception("Boom")
    with patch.dict("sys.modules", {"ddgs": mock_ddgs_cls}):
         assert "Search Error" in search_web("q")

# ...

# --- Async Deep Research --- (see test below after sync tests)

# ...

def test_manage_goals_error(mocker):
    # manage_goals delegates to GoalManager via get_goal_manager.
    # Force an error by patching get_goal_manager to raise.
    mocker.patch("src.memory.goals.get_goal_manager", side_effect=Exception("Read Error"))
    res = manage_goals("list", user_id="12345")
    assert "Error" in res

# ...

def test_recall_user_error(mocker):
    # This hits "Error: No user_id..." before try block
    res = recall_user(user_id=None)
    assert "Error: No user_id" in res

# ...

def test_manage_project_crud(tmp_path):
    # Issues with Path persistence in test?
    # Let's use a real file in tmp_path without mocking Path class constructor globally if possible, 
    # but the code imports Path.
    # The side_effect lambda x: tmp_path / x works for arguments, 
    # but `Path("memory/...")` is called with a string.
    # `tmp_path / "memory/..."` might double up if not careful?
    # tmp_path / "memory/file" works.
    
    # Let's ensure parent dir exists since manage_goals does it but manage_project DOES NOT?
    # manage_goals: goal_file.parent.mkdir
    # manage_project: manifest_path = Path(...); then reads/writes.
    # If "memory" dir doesn't exist, write_text might fail?
    # But write_text doesn't auto-create dirs.
    # Let's check manage_project code.
    # It does NOT create dirs.
    # So we must fix the code OR ensure dir exists in test.
    (tmp_path / "memory").mkdir()
    
    with patch("src.tools.coding.Path", side_effect=lambda x: tmp_path / x):
        manage_project("init", "TestProj")
        manage_project("set", "k", "v")
        res = manage_project("get", "k")
        assert "v" in res

def test_browse_site_success(mocker):
    mock_resp = MagicMock()
    mock_resp.text = "<html><body><p>Hello World</p></body></html>"
    mocker.patch("requests.get", return_value=mock_resp)
    mocker.patch("src.tools.web._is_safe_url", return_value=True)
    res = browse_site("http://example.com")
    assert "Hello World" in res

def test_browse_site_error(mocker):
    mocker.patch("requests.get", side_effect=Exception("Net fail"))
    mocker.patch("src.tools.web._is_safe_url", return_value=True)
    assert "Browse Error" in browse_site("url")

def test_check_world_news_success(mocker):
    mock_feed = MagicMock()
    mock_feed.entries = [MagicMock(title="News", link="Link")]
    mocker.patch("feedparser.parse", return_value=mock_feed)
    res = check_world_news("tech")
    assert "News (Link)" in res

def test_check_world_news_empty(mocker):
    mock_feed = MagicMock()
    mock_feed.entries = []
    mocker.patch("feedparser.parse", return_value=mock_feed)
    assert "No news found" in check_world_news("tech")

def test_check_world_news_error(mocker):
    mocker.patch("feedparser.parse", side_effect=Exception("RSS Fail"))
    assert "News Error" in check_world_news()

# --- Async Deep Research ---

# Use function-scoped fixture only for this test
@pytest.fixture
def clean_ddgs_import():
    """Prepare clean state for deep research test without crashing PyO3/primp.
    
    IMPORTANT: Do NOT delete duckduckgo_search from sys.modules — the primp
    PyO3 extension module can only be initialized once per interpreter process.
    Deleting and re-importing it causes an ImportError.
    """
    import sys
    
    # Pre-seed sys.modules with a mock if not already loaded,
    # to prevent primp from being imported (which crashes on re-init)
    mock_ddgs = MagicMock()
    if "duckduckgo_search" not in sys.modules:
        sys.modules["duckduckgo_search"] = mock_ddgs
    
    # Reset globals.bot to None to prevent pollution from earlier tests
    old_bot = globals.bot
    globals.bot = None
    globals.active_message.set(None)
    
    yield
    
    # Restore after test
    globals.bot = old_bot

@pytest.mark.asyncio
async def test_start_deep_research(mocker, tmp_path, clean_ddgs_import):
    mock_ddgs_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.text.return_value = [{'title': 'Sub', 'href': 'H'}]
    mock_ddgs_cls.DDGS.return_value = mock_instance
    
    mocker.patch("builtins.open", mock_open())
    mocker.patch("os.makedirs")
    
    # Must mock BOTH 'ddgs' (used by start_deep_research) and 'duckduckgo_search'
    # to prevent PyO3/primp re-initialization crash during full suite runs
    with patch.dict("sys.modules", {"duckduckgo_search": mock_ddgs_cls, "ddgs": mock_ddgs_cls}):
        res = await start_deep_research("topic")
        assert "Deep Research initialized" in res

# --- Identity / Persona ---

def test_update_persona_core_blocked():
    """CORE scope should be blocked — redirect to PromptTuner."""
    res = update_persona("New Identity", request_scope="CORE")
    assert "PromptTuner" in res
    assert "disabled" in res

def test_update_persona_private_success(mocker):
    mocker.patch("src.tools.file_utils.surgical_edit", return_value=(True, "Success"))
    res = update_persona("New persona text", request_scope="PRIVATE", user_id="12345")
    assert "Updated" in res
    assert "persona" in res.lower()

# --- Goals ---

def test_manage_goals_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    test_user_id = "12345"
    user_silo = tmp_path / "memory" / "users" / test_user_id
    user_silo.mkdir(parents=True)
    res = manage_goals("list", user_id=test_user_id)
    assert "No active goals" in res

def test_manage_goals_crud(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    test_user_id = "12345"
    user_silo = tmp_path / "memory" / "users" / test_user_id
    user_silo.mkdir(parents=True)
    
    res = manage_goals("add", "Goal 1", user_id=test_user_id)
    assert "Goal added" in res
    
    # Extract UUID-based goal_id from the add response
    import re
    goal_id_match = re.search(r'ID: (goal_\w+)', res)
    assert goal_id_match, f"Could not extract goal_id from: {res}"
    goal_id = goal_id_match.group(1)
    
    res = manage_goals("list", user_id=test_user_id)
    assert "Goal 1" in res
    
    manage_goals("complete", goal_id=goal_id, user_id=test_user_id)
    res = manage_goals("list", user_id=test_user_id)
    assert "No active goals" in res  # completed goal not shown by default

def test_manage_goals_error_dup(mocker):
    mocker.patch("src.memory.goals.get_goal_manager", side_effect=Exception("Read Error"))
    res = manage_goals("list", user_id="12345")
    assert "Error" in res

# --- Reaction ---

@pytest.mark.asyncio
async def test_add_reaction_success(mocker):
    msg = MagicMock()
    msg.add_reaction = AsyncMock()
    globals.active_message.set(msg)
    globals.bot = MagicMock()
    
    res = await add_reaction("👍")
    assert "Reacted with" in res
    msg.add_reaction.assert_awaited_with("👍")

@pytest.mark.asyncio
async def test_add_reaction_no_msg():
    globals.active_message.set(None)
    assert "Error: No active message" in await add_reaction("x")

@pytest.mark.asyncio
async def test_add_reaction_no_bot(mocker):
    msg = MagicMock()
    globals.active_message.set(msg)
    globals.bot = None
    assert "Error: Bot instance" in await add_reaction("x")

# --- Recall ---

def test_recall_user_success(mocker):
    mocker.patch("src.tools.memory_tools.Path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data='{"timestamp":"t","description":"d"}'))
    res = recall_user(user_id="123")
    assert "Public History" in res

def test_recall_user_missing(mocker):
    mocker.patch("src.tools.memory_tools.Path.exists", return_value=False)
    assert "No public silo found" in recall_user(user_id="123")

def test_recall_user_error(mocker):
    assert "Error: No user_id" in recall_user(user_id=None)

# --- Reasoning ---

def test_review_reasoning_success(mocker):
    mocker.patch("src.privacy.guard.validate_path_scope", return_value=True)
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data="Line 1\nLine 2"))
    res = review_my_reasoning(user_id="12345")
    assert "REASONING TRACE" in res

def test_review_reasoning_missing(mocker):
    mocker.patch("src.privacy.guard.validate_path_scope", return_value=True)
    mocker.patch("os.path.exists", return_value=False)
    assert "reasoning traces" in review_my_reasoning(user_id="12345")

# --- Bridge ---

def test_publish_bridge(mocker):
    mocker.patch("builtins.open", mock_open())
    mocker.patch("os.makedirs")
    res = publish_to_bridge("Content")
    assert "success" in res

def test_read_bridge_success(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data="Line"))
    res = read_public_bridge()
    assert "Bridge Public Memory" in res

def test_read_bridge_empty(mocker):
    mocker.patch("os.path.exists", return_value=False)
    assert "empty" in read_public_bridge()

# --- Advice ---

def test_evaluate_advice():
    res = evaluate_advice("short")
    assert "Score: 0" in res
    res = evaluate_advice("long " * 20)
    assert "Score" in res

# --- Program ---

def test_create_program_security(tmp_path, mocker):
    # New scoped storage: files go to memory/core/projects/ or memory/users/{id}/projects/
    # Path traversal is blocked by the filename flattening
    mocker.patch("os.getcwd", return_value=str(tmp_path))
    mocker.patch("src.security.provenance.ProvenanceManager.log_artifact", return_value="abc12345")
    
    # Even with .., it flattens to just the filename, so we test with invalid filename
    res = create_program("", "code")  # Empty filename
    assert "Error: Invalid filename" in res

def test_create_program_success(tmp_path, mocker):
    mocker.patch("os.getcwd", return_value=str(tmp_path))
    mocker.patch("src.security.provenance.ProvenanceManager.log_artifact", return_value="abc12345")
    
    res = create_program("t.py", "code", user_id="12345")
    assert "Successfully applied" in res
    # File goes to memory/users/12345/projects/public/t.py
    assert (tmp_path / "memory" / "users" / "12345" / "projects" / "public" / "t.py").read_text() == "code"

# --- Project ---

def test_manage_project_crud(tmp_path):
    (tmp_path / "memory").mkdir()
    with patch("src.tools.definitions.Path", side_effect=lambda x: tmp_path / x):
        manage_project("init", "TestProj")
        manage_project("set", "k", "v")
        res = manage_project("get", "k")
        assert "v" in res
