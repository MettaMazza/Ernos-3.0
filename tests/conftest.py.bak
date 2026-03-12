"""
Global pytest fixtures for the Ernos test suite.

Provides mock objects for Discord bot, Ollama/Llama engines,
environment variables, and async event loops used across all test files.
"""
import os
import sys
# Ensure root is in path for fixture imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
try:
    from config import settings
    sys.modules['src.core.settings'] = settings
except ImportError:
    pass
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from collections import defaultdict

@pytest.fixture
def event_loop():
    """Create a session-wide event loop for async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables for config tests."""
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_CLOUD_MODEL", "test-cloud")
    monkeypatch.setenv("OLLAMA_LOCAL_MODEL", "test-local")
    monkeypatch.setenv("STEERING_MODEL_PATH", "test.gguf")
    monkeypatch.setenv("ADMIN_ID", "123456789")
    monkeypatch.setenv("TARGET_CHANNEL_ID", "987654321")


@pytest.fixture
def mock_discord_bot():
    """Mock Discord bot with all subsystems attached."""
    bot = MagicMock()

    # Core identity
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "ErnosTest"
    bot.user.display_name = "ErnosTest"

    # Async methods
    bot.add_cog = AsyncMock()
    bot.load_extension = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.valid = False
    bot.get_context = AsyncMock(return_value=mock_ctx)

    # Event loop — run_in_executor actually invokes the callable
    async def run_in_executor_side_effect(executor, func, *args):
        if callable(func):
            return func(*args)
        return None
    bot.loop = MagicMock()
    bot.loop.create_task = MagicMock()
    bot.loop.run_in_executor = AsyncMock(side_effect=run_in_executor_side_effect)

    # Slash command tree
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()

    # Subsystems
    bot.cerebrum = MagicMock()
    bot.engine_manager = MagicMock()
    bot.tape_engine = MagicMock()
    bot.cognition = MagicMock()
    bot.cognition.process = AsyncMock(return_value=("Response", [], []))
    bot.cognition = MagicMock()
    bot.cognition.process = AsyncMock(return_value=("Response", [], []))

    # Hippocampus with proper recall/observe
    mock_recall_result = MagicMock()
    mock_recall_result.working_memory = "History"
    mock_recall_result.related_memories = []
    mock_recall_result.knowledge_graph = []
    mock_recall_result.lessons = []
    bot.hippocampus = MagicMock()
    bot.hippocampus.recall = MagicMock(return_value=mock_recall_result)
    bot.hippocampus.observe = AsyncMock()

    # Silo Manager
    bot.silo_manager = MagicMock()
    bot.silo_manager.active_silos = {}
    bot.silo_manager.check_empty_silo = AsyncMock()
    bot.silo_manager.propose_silo = AsyncMock()
    bot.silo_manager.check_text_confirmation = AsyncMock(return_value=False)
    bot.silo_manager.should_bot_reply = AsyncMock(return_value=True)
    bot.silo_manager.check_quorum = AsyncMock()

    # Channel Manager & Adapter (chat.py L114-115: adapter.normalize is async)
    from src.channels.types import UnifiedMessage
    mock_adapter = MagicMock()
    async def _normalize(raw_msg):
        author = getattr(raw_msg, 'author', MagicMock())
        channel = getattr(raw_msg, 'channel', MagicMock())
        return UnifiedMessage(
            content=getattr(raw_msg, 'content', ''),
            author_id=str(getattr(author, 'id', '0')),
            author_name=getattr(author, 'name', 'TestUser'),
            channel_id=str(getattr(channel, 'id', '0')),
            is_dm=False, is_bot=getattr(author, 'bot', False),
            attachments=[], platform="discord", raw=raw_msg,
        )
    mock_adapter.normalize = _normalize
    mock_adapter.format_mentions = AsyncMock(side_effect=lambda t: t)
    mock_adapter.platform_name = "discord"
    bot.channel_manager = MagicMock()
    bot.channel_manager.get_adapter = MagicMock(return_value=mock_adapter)

    # Processing state (chat.py: processing_users, message_queues)
    bot.processing_users = set()
    bot.message_queues = defaultdict(list)
    bot.add_processing_user = MagicMock()
    bot.remove_processing_user = MagicMock()

    # Misc state
    bot.town_hall = None
    bot.grounding_pulse = None
    bot.last_interaction = 0

    return bot


@pytest.fixture
def mock_ollama():
    """Mock Ollama client with standard test responses."""
    mock_response = {"response": "Ollama Test Response"}
    mock_embed_response = {"embedding": [0.1, 0.2, 0.3]}

    with patch("ollama.Client") as MockClient:
        instance = MockClient.return_value
        instance.generate = MagicMock(return_value=mock_response)
        instance.chat = MagicMock(return_value={"message": {"content": "Chat Response"}})
        instance.embeddings = MagicMock(return_value=mock_embed_response)
        yield instance


@pytest.fixture
def mock_llama():
    """Mock llama-cpp-python Llama class for SteeringEngine tests.

    SteeringEngine calls: output = self._llm(prompt, ...) then
    returns output['choices'][0]['text'].strip()
    """
    with patch("src.engines.steering.Llama") as MockLlama:
        mock_instance = MagicMock()
        # When called as mock_instance(prompt, ...), return llama-cpp dict format
        mock_instance.return_value = {
            "choices": [{"text": "Steering Test Response"}]
        }
        MockLlama.return_value = mock_instance
        yield MockLlama


@pytest.fixture(autouse=True)
def mock_moderation_globally(mocker):
    """
    Globally mock check_moderation_status so chat.py gate checks pass.
    Tests that need real moderation behavior override this locally.
    """
    mocker.patch(
        "src.bot.cogs.chat.check_moderation_status",
        return_value={"allowed": True}
    )
    mocker.patch("config.settings.BLOCKED_IDS", set())
    mocker.patch("config.settings.DM_BANNED_IDS", set())
    mocker.patch("config.settings.ADMIN_IDS", {123456789})
    mocker.patch("config.settings.DMS_ENABLED", True)
    mocker.patch("config.settings.TESTING_MODE", False)


@pytest.fixture(autouse=True)
def reset_data_dir():
    """
    Globally resets the cached _DATA_DIR and working directory after each
    test to prevent cross-test contamination. Tests that use
    monkeypatch.chdir(tmp_path) intentionally make `memory/` relative to
    the temp directory, so we must use a relative path here.
    """
    import src.core.data_paths
    original_data_dir = src.core.data_paths._DATA_DIR
    original_cwd = os.getcwd()
    src.core.data_paths._DATA_DIR = Path("memory")
    # Ensure required test directories exist
    (Path("memory") / "core").mkdir(parents=True, exist_ok=True)
    (Path("memory") / "public").mkdir(parents=True, exist_ok=True)
    yield
    src.core.data_paths._DATA_DIR = Path("memory")
    try:
        os.chdir(original_cwd)
    except OSError:
        pass
