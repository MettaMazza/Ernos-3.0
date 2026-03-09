import os
import sys
import json
import time
import warnings
import pytest
import shutil
import numpy as np

# Patch for NumPy 2.0 compatibility with older libraries (chromadb/hnswlib)
if not hasattr(np, 'float_'):
    np.float_ = np.float64
from pathlib import Path
from unittest.mock import MagicMock

# Suppress external library warnings at Python level
# (pytest filterwarnings can't catch GC-triggered ResourceWarnings)
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)


# === Test Health Reporter ===
# Writes results to memory/system/test_health.json so Ernos's HUD can display live test status.
_TEST_HEALTH_PATH = Path("memory/system/test_health.json")


def pytest_sessionfinish(session, exitstatus):
    """Write test results after the full suite completes."""
    _TEST_HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    passed = session.testscollected - session.testsfailed
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": int(time.time()),
        "total": session.testscollected,
        "passed": passed,
        "failed": session.testsfailed,
        "exit_status": exitstatus,
        "status": "HEALTHY" if exitstatus == 0 else "DEGRADED",
    }
    _TEST_HEALTH_PATH.write_text(json.dumps(results, indent=2))

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Known test user IDs that are safe to clean up
TEST_USER_IDS = {'123', '456', '12345', '999', '111', '222', '12345678', 'test_user'}

@pytest.fixture(autouse=True)
def cleanup_test_user_silos():
    """Clean up any test-created user silos after each test."""
    yield  # Run the test first
    
    # Cleanup after test
    users_dir = Path("memory/users")
    if users_dir.exists():
        for folder in users_dir.iterdir():
            if folder.is_dir():
                name = folder.name
                # Remove if it's a test ID, MagicMock folder, or non-numeric
                is_mock = 'MagicMock' in name or 'mock' in name.lower()
                is_test_id = name in TEST_USER_IDS
                is_invalid = not name.isdigit() or len(name) < 10  # Real Discord IDs are 17-19 digits
                
                if is_mock or is_test_id or is_invalid:
                    try:
                        shutil.rmtree(folder)
                    except Exception:
                        pass  # Ignore cleanup errors


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set default environment variables for testing."""
    monkeypatch.setenv("DISCORD_TOKEN", "test_token")
    monkeypatch.setenv("ADMIN_ID", "123456789")
    monkeypatch.setenv("TARGET_CHANNEL_ID", "987654321")
    monkeypatch.setenv("OLLAMA_CLOUD_MODEL", "test-cloud")
    monkeypatch.setenv("OLLAMA_LOCAL_MODEL", "test-local")
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "test-embed")
    monkeypatch.setenv("STEERING_MODEL_PATH", "./models/test.gguf")
    monkeypatch.setenv("CONTROL_VECTOR_PATH", "./models/ctrl.gguf")

@pytest.fixture(autouse=True)
def reset_testing_mode():
    """Reset settings.TESTING_MODE before each test to prevent cross-test pollution.
    test_admin_coverage.py patches TESTING_MODE=True which leaks into the shared
    config.settings module, causing downstream chat tests to reject all non-admin messages."""
    from config import settings
    original = getattr(settings, 'TESTING_MODE', False)
    settings.TESTING_MODE = False
    yield
    settings.TESTING_MODE = original

@pytest.fixture
def mock_ollama(mocker):
    """Mock the Ollama client."""
    mock_client = MagicMock()
    mock_client.generate.return_value = {'response': 'Ollama Test Response'}
    mock_client.embeddings.return_value = {'embedding': [0.1, 0.2, 0.3]}
    mocker.patch('ollama.Client', return_value=mock_client)
    return mock_client

@pytest.fixture
def mock_llama(mocker):
    """Mock the Llama-cpp-python binding."""
    mock_llm = MagicMock()
    mock_llm.return_value = {'choices': [{'text': 'Steering Test Response'}]}
    
    # We need to mock the IMPORT, not just the class usage
    # Since steering.py does: from llama_cpp import Llama
    # We need to patch sys.modules or use mocker on the imported name
    mocker.patch('src.engines.steering.Llama', return_value=mock_llm)
    return mock_llm

@pytest.fixture
def mock_discord_bot(mocker):
    """Mock Discord Bot for cog testing."""
    bot = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    
    # Needs to be async
    from unittest.mock import AsyncMock
    mock_ctx = MagicMock()
    mock_ctx.valid = False # Default to not a command
    bot.get_context = AsyncMock(return_value=mock_ctx)
    bot.add_cog = AsyncMock()
    bot.load_extension = AsyncMock()
    bot.engine_manager = MagicMock() # Ensure engine manager exists
    
    # Mock Cognition Engine (Critical for chat.py)
    mock_cognition = MagicMock()
    mock_cognition.process = AsyncMock(return_value=("AI Reply", [], []))
    bot.cognition = mock_cognition
    
    # Mock Hippocampus
    mock_hippocampus = MagicMock()
    mock_recall_result = MagicMock()
    mock_recall_result.working_memory = "History"
    mock_recall_result.related_memories = []
    mock_recall_result.knowledge_graph = []
    mock_recall_result.lessons = []
    mock_hippocampus.recall = MagicMock(return_value=mock_recall_result)
    mock_hippocampus.observe = AsyncMock()
    bot.hippocampus = mock_hippocampus
    
    # Mock Loop and run_in_executor
    async def run_in_executor_side_effect(executor, func, *args):
        # If sync function, just call it
        if callable(func):
            return func(*args)
        return None
    bot.loop = MagicMock()
    bot.loop.run_in_executor = AsyncMock(side_effect=run_in_executor_side_effect)
    
    # Mock Processing Users Set
    bot.processing_users = set()
    bot.message_queues = {}
    bot.add_processing_user = MagicMock()
    bot.remove_processing_user = MagicMock()
    bot.last_interaction = 0
    bot.grounding_pulse = None
    
    # Mock Maintenance Loop (discord.ext.tasks)
    mock_maintenance = MagicMock()
    mock_maintenance.cancel = MagicMock()
    mock_maintenance.stop = MagicMock()
    bot.maintenance_loop = mock_maintenance
    
    # Mock Cerebrum
    bot.cerebrum = MagicMock()
    bot.cerebrum.get_lobe.return_value = MagicMock()
    
    bot.silo_manager = MagicMock()
    bot.silo_manager.propose_silo = AsyncMock()
    bot.silo_manager.check_quorum = AsyncMock()
    bot.silo_manager.check_text_confirmation = AsyncMock(return_value=False)
    bot.silo_manager.should_bot_reply = AsyncMock(return_value=True)
    
    # Mock Channel Manager (Synapse Bridge v3.1)
    # The adapter.normalize() call is async — must use AsyncMock
    from src.channels.types import UnifiedMessage
    mock_adapter = MagicMock()
    async def mock_normalize(raw_msg):
        """Build a UnifiedMessage from the raw mock message."""
        author = getattr(raw_msg, 'author', MagicMock())
        channel = getattr(raw_msg, 'channel', MagicMock())
        return UnifiedMessage(
            content=getattr(raw_msg, 'content', ''),
            author_id=str(getattr(author, 'id', '0')),
            author_name=getattr(author, 'display_name', None) or getattr(author, 'name', 'TestUser'),
            channel_id=str(getattr(channel, 'id', '0')),
            is_dm=False,
            is_bot=getattr(author, 'bot', False),
            attachments=[],
            platform="discord",
            raw=raw_msg,
        )
    mock_adapter.normalize = mock_normalize
    mock_adapter.format_mentions = AsyncMock(side_effect=lambda text: text)
    mock_adapter.platform_name = "discord"
    mock_channel_manager = MagicMock()
    mock_channel_manager.get_adapter.return_value = mock_adapter
    bot.channel_manager = mock_channel_manager
    
    return bot

@pytest.fixture(autouse=True)
def mock_ffmpeg(mocker):
    """Globally mock FFmpegPCMAudio to avoid binary dependency in tests.
    Patches both the discord module and the src.voice.manager module reference."""
    mock_audio = MagicMock()
    mocker.patch("discord.FFmpegPCMAudio", mock_audio)
    mocker.patch("src.voice.manager.discord.FFmpegPCMAudio", mock_audio)
    return mock_audio

@pytest.fixture(autouse=True)
def mock_moderation_check(mocker):
    """Globally mock moderation check so tests aren't silently blocked.
    Patches at the source module. chat.py does `from src.tools.moderation import check_moderation_status`
    inside on_message, so patching the source module attribute is sufficient.
    Individual moderation tests override this with their own mocks."""
    mocker.patch(
        "src.tools.moderation.check_moderation_status",
        return_value={"allowed": True, "reason": None}
    )

# ── macOS kqueue fd exhaustion prevention ──
# pytest-asyncio (auto mode) creates ~3480 event loops during the full suite.
# On macOS, each loop allocates a kqueue fd. Cumulative creation/teardown
# can exhaust the default fd limit (256), causing OSError: Bad file descriptor.
import resource
import gc

_soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (min(_hard, 8192), _hard))

@pytest.fixture
def event_loop():
    """Provide a fresh event loop with explicit selector cleanup."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    try:
        loop.close()
    except Exception:
        pass
    # Force GC to finalize any dangling selectors / kqueue fds
    gc.collect()
