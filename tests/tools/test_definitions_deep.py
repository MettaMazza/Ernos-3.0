import pytest
import os
import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from src.tools.definitions import (
    browse_site, check_world_news, start_deep_research,
    manage_goals, add_reaction, recall_user,
    review_my_reasoning, publish_to_bridge, read_public_bridge,
    create_program, manage_project
)

# --- Web Tools ---
def test_browse_site_cleaning(mocker):
    # Mock requests
    mocker.patch("requests.get").return_value.text = "<html><script>bad</script><body>Good Text</body></html>"
    mocker.patch("requests.get").return_value.raise_for_status = MagicMock()
    
    # Mock imports inside function
    mock_bs = MagicMock()
    mock_soup = MagicMock()
    mock_bs.return_value = mock_soup
    
    # script decompose loop
    script = MagicMock()
    mock_soup.find_all.return_value = [script] # for script in soup([...])
    mock_soup.call_args = None # Reset
    
    # soup("script") calls __call__ on soup instance? No, soup is tag.
    # soup(list) -> find_all
    # We make the instance callable to mimic find_all? 
    # Or just mock `soup` such that `soup(["script", "style"])` returns list.
    mock_soup.side_effect = lambda x: [script] if isinstance(x, list) else None
    
    mock_soup.get_text.return_value = "Clean Content"

    with patch.dict("sys.modules", {"bs4": MagicMock(BeautifulSoup=mock_bs)}), \
         patch("src.tools.web._is_safe_url", return_value=True):
        res = browse_site("http://test.com")
        assert "Clean Content" in res

def test_check_world_news_feeds(mocker):
    mock_feedparser = MagicMock()
    entry = MagicMock()
    entry.title = "Test News"
    entry.link = "http://news.com"
    mock_feedparser.parse.return_value.entries = [entry]
    
    with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
        res = check_world_news("general")
        assert "Test News" in res

@pytest.mark.asyncio
async def test_start_deep_research_flow(mocker):
    mock_ddgs = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_ddgs
    mock_ctx.__exit__.return_value = None
    mock_ddgs.text.return_value = [{"title": "Res", "href": "url"}]
    
    mock_module = MagicMock()
    mock_module.DDGS.return_value = mock_ctx
    
    # Mock the background task so it doesn't run and fail after test ends
    mocker.patch("src.tools.web._research_task")
    
    with patch.dict("sys.modules", {"ddgs": mock_module}):
        mocker.patch("builtins.open", mock_open())
        
        # Mock globals.bot with a loop since DeepResearcher needs it
        mock_bot = MagicMock()
        mock_bot.loop = asyncio.get_event_loop()
        # Also mock engine_manager for sub-queries/synthesis
        mock_bot.engine_manager.get_active_engine.return_value = None 
        
        # Use mocker.patch for function scope to cover background task execution
        mocker.patch("src.bot.globals.bot", mock_bot)
        
        res = await start_deep_research("AI")
        assert "launched as an ASYNCHRONOUS BACKGROUND PROCESS" in res

# --- Goals ---
def test_manage_goals_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    test_user_id = "12345"
    user_silo = tmp_path / "memory" / "users" / test_user_id
    user_silo.mkdir(parents=True)

    from src.tools.memory import manage_goals
    import re

    # 1. Add
    res = manage_goals("add", "New Goal", user_id=test_user_id)
    assert "Goal added" in res

    # Verify file content
    goals_file = user_silo / "goals.json"
    assert goals_file.exists()
    assert "New Goal" in goals_file.read_text()

    # 2. Extract goal_id and complete
    goal_id_match = re.search(r'ID: (goal_\w+)', res)
    assert goal_id_match, f"Could not extract goal_id from: {res}"
    goal_id = goal_id_match.group(1)

    res = manage_goals("complete", goal_id=goal_id, user_id=test_user_id)
    assert "completed" in res.lower()

    # Verify file was updated
    data = goals_file.read_text()
    assert "completed" in data

# --- Reaction ---
@pytest.mark.asyncio
async def test_add_reaction_direct(mocker):
    # Set context vars properly
    from src.bot import globals
    from src.tools.memory import add_reaction
    
    # 1. No Active Message
    token = globals.active_message.set(None)
    try:
        res = await add_reaction("x")
        assert "No active message" in res
    finally:
        globals.active_message.reset(token)
    
    # 2. No Bot (but message exists)
    msg = MagicMock()
    token = globals.active_message.set(msg)
    
    # Check if globals.bot is None by default?
    # If not, we patch it.
    with patch("src.bot.globals.bot", None):
        try:
           res = await add_reaction("x")
           assert "Bot instance not available" in res
        finally:
           globals.active_message.reset(token)

# --- Recall User ---
def test_recall_user_paths(mocker, tmp_path):
    from src.tools.recall_tools import recall_user
    
    # 1. Not Found — no silo file
    with patch("src.tools.recall_tools.data_dir", return_value=tmp_path):
        res = recall_user("123")
        assert "No public silo" in res
    
    # 2. Empty — silo file exists but empty
    silo_dir = tmp_path / "public" / "users" / "123"
    silo_dir.mkdir(parents=True)
    silo_file = silo_dir / "timeline.jsonl"
    silo_file.write_text("")
    
    with patch("src.tools.recall_tools.data_dir", return_value=tmp_path):
        res = recall_user("123")
        assert "Silo exists but is empty" in res

# --- Reasoning Review ---
def test_review_reasoning_paths(mocker):
    # Mock scope validation since traces are now user-scoped
    mocker.patch("src.privacy.guard.validate_path_scope", return_value=True)
    
    # 1. Not Found (must pass user_id since traces are now user-scoped)
    mocker.patch("os.path.exists", return_value=False)
    res = review_my_reasoning(user_id="12345")
    assert "reasoning traces" in res
    
    # 2. Found - test with actual content
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data="Line 1\nLine 2"))
    res = review_my_reasoning(user_id="U1")
    assert "U1" in res
    assert "Line 2" in res

# --- Bridge ---
def test_bridge_ops(mocker):
    mocker.patch("os.makedirs")
    mocker.patch("builtins.open", mock_open(read_data="Entry 1"))
    
    # Publish
    assert "published" in publish_to_bridge("Content")
    
    # Read
    mocker.patch("os.path.exists", return_value=True)
    assert "Entry 1" in read_public_bridge()
    
    # Read Empty
    mocker.patch("os.path.exists", return_value=False)
    assert "empty" in read_public_bridge()

# --- Project/Program ---
def test_create_program_security(mocker):
    # New scoped storage: files go to memory/core/projects/ or memory/users/{id}/projects/
    # Path traversal is blocked by the filename flattening - test invalid filename
    mocker.patch("builtins.open", mock_open())
    mocker.patch("os.getcwd", return_value="/project")
    mocker.patch("src.security.provenance.ProvenanceManager.log_artifact", return_value="abc12345")
    
    # Empty filename should be rejected
    res = create_program("", "code")
    assert "Invalid filename" in res

def test_manage_project_actions(mocker, tmp_path):
    from src.tools.coding import manage_project
    
    with patch("src.tools.coding.data_dir", return_value=tmp_path):
        # Init
        res = manage_project("init")
        assert "initialized" in res.lower()
        
        # Set
        res = manage_project("set", "key", "val")
        assert "val" in res
        
        # Get
        res = manage_project("get", "key")
        assert "val" in res
        
        # List
        res = manage_project("list")
        assert "key" in res
