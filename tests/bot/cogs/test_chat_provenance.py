import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.bot.cogs.chat import ChatListener
from src.security.provenance import ProvenanceManager
import importlib

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.loop = AsyncMock()
    # Mocking run_in_executor to execute the function directly for testing simplicity
    bot.loop.run_in_executor = AsyncMock(side_effect=lambda _, func, *args: func(*args) if callable(func) else None)
    bot.silo_manager = AsyncMock()
    bot.silo_manager.check_text_confirmation.return_value = False
    bot.silo_manager.should_bot_reply.return_value = True
    bot.hippocampus = MagicMock()
    bot.hippocampus.recall.return_value = MagicMock(
        working_memory="", related_memories=[], knowledge_graph=[], lessons=[]
    )
    
    # Mock Provenance
    bot.provenance = MagicMock()
    
    # Explicitly mock cognition and its async process method
    bot.cognition = MagicMock()
    bot.cognition.process = AsyncMock(return_value=("Test Response", [], []))
    
    # Fix adapter mocking for awaitable
    adapter_mock = MagicMock()
    unified_mock = MagicMock()
    unified_mock.is_dm = True # Bypass channel checks
    unified_mock.author_name = "TestUser" 
    adapter_mock.normalize = AsyncMock(return_value=unified_mock)
    # Mock format_mentions to be awaitable (identity function)
    adapter_mock.format_mentions = AsyncMock(side_effect=lambda text: text)
    bot.channel_manager.get_adapter.return_value = adapter_mock
    
    # Mock context to be invalid (so it's processed as chat, not command)
    ctx_mock = MagicMock()
    ctx_mock.valid = False
    bot.get_context = AsyncMock(return_value=ctx_mock)
    
    return bot

@pytest.mark.asyncio
async def test_image_attachment_provenance_injection(mock_bot):
    """
    Verify that self-generated images inject their PROMPT and INTENTION into the context.
    """
    files = {
        "src.bot.cogs.chat.UnifiedPreProcessor": MagicMock(),
        "src.bot.cogs.chat.PromptManager": MagicMock(),
        "src.bot.cogs.chat.check_moderation_status": MagicMock(return_value={"allowed": True}),
        "src.bot.cogs.chat.settings": MagicMock(
            TARGET_CHANNEL_ID=1000, 
            ADMIN_IDS={123}, 
            BLOCKED_IDS=set(),
            TESTING_MODE=False,
            DMS_ENABLED=True
        ),
        "config": MagicMock(settings=MagicMock(
            TARGET_CHANNEL_ID=1000, 
            ADMIN_IDS={123}, 
            BLOCKED_IDS=set(),
            TESTING_MODE=False,
            DMS_ENABLED=True
        )),
    }
    
    with patch.dict("sys.modules", files):
        from src.bot.cogs.chat import ChatListener
        
        cog = ChatListener(mock_bot)
        # Mock preprocessor to return a standard analysis
        cog.preprocessor.process = AsyncMock(return_value={
            "complexity": "LOW",
            "intent": "chat",
            "reality_check": False
        })
        
        # Mock Provenance Manager (on the bot instance)
        # Setup known checksum and record
        mock_bot.provenance.compute_checksum.return_value = "deadbeef1234"
        mock_bot.provenance.lookup_by_checksum.return_value = {
            "timestamp": "2023-01-01 12:00:00",
            "type": "image",
            "metadata": {
                "prompt": "A futuristic city with flying cars",
                "intention": "To visualize the concept of future transport",
                "user_id": "CORE",
                "is_autonomy": True
            }
        }
            
        # Create a mock message with an image attachment
        message = AsyncMock()
        message.id = 12345
        message.author.id = 999
        message.author.bot = False
        message.channel.id = 1000
        message.content = "Look at this image"
        message.guild = MagicMock()
        
        # Mock typing context manager explicitly as MagicMock (not AsyncMock)
        # discord.abc.Messageable.typing() is a regular method returning a context manager
        typing_cm = MagicMock()
        typing_cm.__aenter__ = AsyncMock(return_value=None)
        typing_cm.__aexit__ = AsyncMock(return_value=None)
        
        # Important: Replace the auto-created mock with a simple MagicMock
        message.channel.typing = MagicMock(return_value=typing_cm)
        
        attachment = AsyncMock()
        attachment.filename = "future_city.png"
        attachment.content_type = "image/png"
        attachment.read.return_value = b"fake_image_bytes"
        attachment.size = 1024
        message.attachments = [attachment]
        
        # Trigger on_message
        await cog.on_message(message)
        
        # Verify cognition called
        assert mock_bot.cognition.process.called
        
        # Helper to access arguments passed to process
        call_kwargs = mock_bot.cognition.process.call_args.kwargs
        input_text = call_kwargs.get("input_text", "")
        
        # ASSERTIONS
        assert "future_city.png" in input_text
        assert "[SELF-GENERATED IMAGE: future_city.png]" in input_text
        
        # The Critical Requirement: Prompt and Intention must be in the input text
        assert 'Prompt: "A futuristic city with flying cars"' in input_text, "Prompt was not injected into context"
        assert 'Intention: "To visualize the concept of future transport"' in input_text, "Intention was not injected into context"

    # Restore the real chat module to prevent pollution of downstream tests
    import src.bot.cogs.chat
    importlib.reload(src.bot.cogs.chat)
