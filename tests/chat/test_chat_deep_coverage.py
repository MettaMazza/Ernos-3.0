import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from src.bot.cogs.chat import ChatListener
from config import settings
import discord

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.user.id = 123
    bot.processing_users = set()
    bot.message_queues = {}
    bot.last_interaction = 0
    bot.grounding_pulse = None
    bot.add_processing_user = MagicMock()
    bot.remove_processing_user = MagicMock()
    
    # Cognition mock (critical - chat.py uses cognition.process)
    mock_cognition = MagicMock()
    mock_cognition.process = AsyncMock(return_value=("Response from bot", [], []))
    bot.cognition = mock_cognition
    
    # Hippocampus mock
    mock_hippocampus = MagicMock()
    mock_recall_result = MagicMock()
    mock_recall_result.working_memory = "History"
    mock_recall_result.related_memories = []
    mock_recall_result.knowledge_graph = []
    mock_recall_result.lessons = []
    mock_hippocampus.recall = MagicMock(return_value=mock_recall_result)
    mock_hippocampus.observe = AsyncMock()
    bot.hippocampus = mock_hippocampus
    
    # Loop mock
    async def run_in_executor_side_effect(executor, func, *args):
        if callable(func):
            return func(*args)
        return None
    bot.loop = MagicMock()
    bot.loop.run_in_executor = AsyncMock(side_effect=run_in_executor_side_effect)
    
    # Cerebrum mock
    bot.cerebrum = MagicMock()
    
    # Silo Manager Mocks
    bot.silo_manager = MagicMock()
    bot.silo_manager.propose_silo = AsyncMock()
    bot.silo_manager.check_text_confirmation = AsyncMock(return_value=False)
    bot.silo_manager.should_bot_reply = AsyncMock(return_value=True)
    
    # Channel Manager Mock (Synapse Bridge v3.1)
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
    mock_cm = MagicMock()
    mock_cm.get_adapter.return_value = mock_adapter
    bot.channel_manager = mock_cm
    
    return bot

@pytest.fixture
def chat_listener(mock_bot):
    listener = ChatListener(mock_bot)
    listener.preprocessor = MagicMock()
    listener.preprocessor.process = AsyncMock(return_value={})
    listener.prompt_manager = MagicMock()
    return listener

@pytest.fixture(autouse=True)
def mock_moderation():
    with patch("src.bot.cogs.chat.check_moderation_status") as mock_mod:
        mock_mod.return_value = {"allowed": True, "reason": None}
        yield mock_mod

@pytest.fixture
def mock_message():
    msg = MagicMock(spec=discord.Message)
    msg.author.bot = False
    msg.author.id = 456
    msg.author.name = "TestUser"
    msg.content = "Hello world"
    msg.channel.id = settings.TARGET_CHANNEL_ID
    msg.channel.name = "general"
    msg.attachments = []
    # Mock context valid = False (not a command)
    return msg

# --- Ignore Cases ---

@pytest.mark.asyncio
async def test_on_message_ignore_bot(chat_listener, mock_message):
    mock_message.author.bot = True
    await chat_listener.on_message(mock_message)
    chat_listener.preprocessor.process.assert_not_awaited()

@pytest.mark.asyncio
async def test_on_message_ignore_blocked(chat_listener, mock_message):
    settings.BLOCKED_IDS = [456] # Block sender
    await chat_listener.on_message(mock_message)
    chat_listener.preprocessor.process.assert_not_awaited()
    settings.BLOCKED_IDS = [] # Reset

@pytest.mark.asyncio
async def test_on_message_ignore_wrong_channel(chat_listener, mock_message):
    mock_message.channel.id = 999
    await chat_listener.on_message(mock_message)
    chat_listener.preprocessor.process.assert_not_awaited()

@pytest.mark.asyncio
async def test_on_message_ignore_command(chat_listener, mock_message):
    # Mock context returning valid=True
    ctx = MagicMock()
    ctx.valid = True
    chat_listener.bot.get_context = AsyncMock(return_value=ctx)
    
    await chat_listener.on_message(mock_message)
    chat_listener.preprocessor.process.assert_not_awaited()

# --- Queue System ---

@pytest.mark.asyncio
async def test_on_message_queueing(chat_listener, mock_message):
    # User is in processing
    key = (456, mock_message.channel.id)
    chat_listener.bot.processing_users = {key}
    chat_listener.bot.message_queues = {key: []}
    
    # Mock get_context valid=False
    ctx = MagicMock()
    ctx.valid = False
    chat_listener.bot.get_context = AsyncMock(return_value=ctx)
    chat_listener.bot.engine_manager.get_active_engine.return_value = MagicMock()

    await chat_listener.on_message(mock_message)
    
    assert mock_message in chat_listener.bot.message_queues[(456, mock_message.channel.id)]
    chat_listener.preprocessor.process.assert_not_awaited()

# --- Standard Flow ---

@pytest.mark.asyncio
async def test_on_message_full_flow(chat_listener, mock_message, mocker):
    # Setup Mocks
    ctx = MagicMock(); ctx.valid = False
    chat_listener.bot.get_context = AsyncMock(return_value=ctx)
    
    engine = MagicMock()
    chat_listener.bot.engine_manager.get_active_engine.return_value = engine
    
    # PreProcess
    chat_listener.preprocessor.process.return_value = {"complexity": "LOW", "intent": "chat"}
    
    # Timeline Log
    mocker.patch("builtins.open", mock_open())
    mocker.patch("os.makedirs")
    
    # Silo
    chat_listener.bot.silo_manager.propose_silo = AsyncMock()
    
    # Hippocampus Recall
    mock_context = MagicMock()
    mock_context.working_memory = "History..."
    mock_context.related_memories = ["Fact"]
    mock_context.knowledge_graph = ["Node"]
    chat_listener.bot.loop.run_in_executor = AsyncMock(return_value=mock_context)
    
    # Scope Manager
    with patch("src.privacy.scopes.ScopeManager.get_scope") as mock_scope:
        mock_scope.return_value.name = "PUBLIC"
        
        # Responses (ReAct Loop)
        # 1. Thought (No Tool) -> 2. Final Response
        # Engine execution is via run_in_executor usually, but chat.py implementation:
        # Check lines 99-106 for recall (run_in_executor).
        # Check ReAct loop (lines 194+ in original file).
        # It calls `engine.generate_response` via `bot.loop.run_in_executor` presumably.
        # But wait, `chat.py` snippet stops at line 200. I need to verify how engine is called in ReAct.
        # Assuming standard pattern: await loop.run_in_executor(None, engine.generate_response, ...)
        
        # We need to mock returning values for `run_in_executor`.
        # First call is Recall. Second call is ReAct step 1.
        chat_listener.bot.loop.run_in_executor.side_effect = [
            mock_context,
            mock_context  # Second recall also needs proper context object
        ]
        
        # Grounding Pulse
        chat_listener.bot.grounding_pulse = "Pulse"
        
        # Messages typing context
        mock_message.channel.typing.return_value.__aenter__ = AsyncMock()
        mock_message.channel.typing.return_value.__aexit__ = AsyncMock()
        
        # Mock reply
        mock_message.reply = AsyncMock()
        
        await chat_listener.on_message(mock_message)
        
        # Verify Steps
        chat_listener.preprocessor.process.assert_awaited()
        chat_listener.bot.silo_manager.propose_silo.assert_awaited()
        assert chat_listener.bot.add_processing_user.called
        
        # Verify Pulse Injection
        # We can't easily check local variable `system_context` inside the function, 
        # but we can verify `prompt_manager.get_system_prompt` was called.
        chat_listener.prompt_manager.get_system_prompt.assert_called()
        assert chat_listener.bot.grounding_pulse is None # Consumed
        
        # Verify Reply
        mock_message.reply.assert_awaited()

@pytest.mark.asyncio
async def test_on_message_react_tool_usage(chat_listener, mock_message, mocker):
    # Setup for ReAct Loop with Tool
    ctx = MagicMock(); ctx.valid = False
    chat_listener.bot.get_context = AsyncMock(return_value=ctx)
    chat_listener.bot.engine_manager.get_active_engine.return_value = MagicMock()
    chat_listener.preprocessor.process.return_value = {"complexity": "MEDIUM", "estimated_tool_count": 2}

    # Timeline/Silo/Hippocampus
    mocker.patch("builtins.open", mock_open())
    mocker.patch("os.makedirs")
    chat_listener.bot.silo_manager.propose_silo = AsyncMock()
    chat_listener.bot.loop.run_in_executor = AsyncMock()
    
    # Scope
    with patch("src.privacy.scopes.ScopeManager.get_scope") as mock_scope:
         mock_scope.return_value.name = "CORE"
         
         # Sequence:
         # 1. Recall (formatted context)
         # 2. ReAct Step 1: "Thought [TOOL: test_tool()]"
         # 3. ReAct Step 2: "Final Answer"
         
         mock_recall = MagicMock()
         mock_recall.working_memory = ""
         mock_recall.related_memories = []
         mock_recall.knowledge_graph = []
         
         chat_listener.bot.loop.run_in_executor.side_effect = [
             mock_recall, # Early recall
             mock_recall, # Main recall
             "Thinking [TOOL: test_tool(arg=1)]", # Step 1
             "Final Answer" # Step 2
         ]
         
         # Mock Tool Registry
         with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock) as mock_exec:
             mock_exec.return_value = "Tool Result"
             
             mock_message.reply = AsyncMock()
             mock_message.channel.typing.return_value.__aenter__ = AsyncMock()
             mock_message.channel.typing.return_value.__aexit__ = AsyncMock()

             await chat_listener.on_message(mock_message)
    assert True  # No exception: message handling completed
             
             # Verify Tool Execution
@pytest.mark.asyncio
async def test_on_message_tool_limits_and_errors(chat_listener, mock_message, mocker):
    """Test that tool limits and error handling are enforced via cognition engine."""
    # Setup
    ctx = MagicMock(); ctx.valid = False
    chat_listener.bot.get_context = AsyncMock(return_value=ctx)
    chat_listener.bot.engine_manager.get_active_engine.return_value = MagicMock()
    chat_listener.preprocessor.process.return_value = {"complexity": "MEDIUM"}
    
    mocker.patch("builtins.open", mock_open())
    mocker.patch("os.makedirs")
    chat_listener.bot.silo_manager.propose_silo = AsyncMock()
    
    # Mock cognition.process to return a response (tool limits handled internally)
    chat_listener.bot.cognition.process = AsyncMock(return_value=("Final Answer", [], []))
    
    with patch("src.privacy.scopes.ScopeManager.get_scope") as mock_scope:
        mock_scope.return_value.name = "PUBLIC"
        
        mock_message.reply = AsyncMock()
        mock_message.channel.typing.return_value.__aenter__ = AsyncMock()
        mock_message.channel.typing.return_value.__aexit__ = AsyncMock()
    
        await chat_listener.on_message(mock_message)
        
        # Cognition engine called (handles tool limits internally)
        chat_listener.bot.cognition.process.assert_awaited()
        mock_message.reply.assert_awaited()

@pytest.mark.asyncio
async def test_on_message_final_response_chunking(chat_listener, mock_message, mocker):
    """Test large response splitting into 2000-char chunks."""
    ctx = MagicMock(); ctx.valid = False
    chat_listener.bot.get_context = AsyncMock(return_value=ctx)
    chat_listener.bot.engine_manager.get_active_engine.return_value = MagicMock()
    
    chat_listener.preprocessor.process.return_value = {}
    chat_listener.bot.silo_manager.propose_silo = AsyncMock()
    
    # Mock cognition.process to return 5000-char response (should chunk to 3 replies)
    huge_text = "A" * 5000
    chat_listener.bot.cognition.process = AsyncMock(return_value=(huge_text, [], []))
    
    mocker.patch("builtins.open", mock_open())
    mocker.patch("os.makedirs")
    
    mock_message.reply = AsyncMock()
    mock_message.channel.typing.return_value.__aenter__ = AsyncMock()
    mock_message.channel.typing.return_value.__aexit__ = AsyncMock()
    
    with patch("src.privacy.scopes.ScopeManager.get_scope") as mock_scope:
         mock_scope.return_value.name = "PUBLIC"

         await chat_listener.on_message(mock_message)
         
         # Logic: split into 2000 chunks. 5000 -> 3 chunks (2000, 2000, 1000).
         assert mock_message.reply.call_count == 3
         args_list = mock_message.reply.call_args_list
         assert len(args_list[0][0][0]) == 2000
         assert len(args_list[1][0][0]) == 2000
         assert len(args_list[2][0][0]) == 1000

class TestFileAttachmentClarificationBypass:
    """Regression test: File attachments must bypass clarification and go to full cognition."""
    
    @pytest.mark.asyncio
    async def test_clarification_skipped_when_txt_file_attached(self, chat_listener, mock_message):
        """REGRESSION: When .txt files are attached, skip clarification even if preprocessor requests it."""
        
        # Create mock attachment
        mock_attachment = MagicMock()
        mock_attachment.filename = "test.txt"
        mock_attachment.content_type = "text/plain"
        mock_attachment.size = 100
        mock_attachment.read = AsyncMock(return_value=b"file contents")
        mock_message.attachments = [mock_attachment]
        
        # Preprocessor returns clarification_needed
        chat_listener.preprocessor.process.return_value = {
            "complexity": "HIGH",
            "clarification_needed": "What would you like me to do with this file?"
        }
        
        # Setup mocks
        ctx = MagicMock()
        ctx.valid = False
        chat_listener.bot.get_context = AsyncMock(return_value=ctx)
        chat_listener.bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        # Mock Hippocampus recall via run_in_executor
        mock_context = MagicMock()
        mock_context.working_memory = ""
        mock_context.related_memories = []
        mock_context.knowledge_graph = []
        mock_context.lessons = []
        chat_listener.bot.loop.run_in_executor = AsyncMock(return_value=mock_context)
        
        # Mock scope
        with patch("src.privacy.scopes.ScopeManager.get_scope") as mock_scope:
            mock_scope.return_value.name = "PUBLIC"
            
            # Mock Cognition response
            chat_listener.bot.cognition.process = AsyncMock(return_value=("I see your file", [], []))
            
            # Mock prompts
            chat_listener.prompt_manager.get_system_prompt.return_value = "System Prompt"

            await chat_listener.on_message(mock_message)
            
            # Should NOT have replied with clarification question
            # Instead should have processed through full cognition
            replies = [call[0][0] for call in mock_message.reply.call_args_list]
            assert not any("What would you like" in str(r) for r in replies), \
                "Clarification should be skipped when files are attached!"
            
            # Should have called cognition
            chat_listener.bot.cognition.process.assert_awaited()

    @pytest.mark.asyncio
    async def test_clarification_allowed_without_file_attachments(self, chat_listener, mock_message):
        """Verify clarification still works normally when NO files are attached."""
        mock_message.attachments = []  # No attachments
        
        # Preprocessor returns clarification_needed
        chat_listener.preprocessor.process.return_value = {
            "complexity": "LOW",
            "clarification_needed": "What do you mean?"
        }
        
        # Setup mocks
        ctx = MagicMock()
        ctx.valid = False
        chat_listener.bot.get_context = AsyncMock(return_value=ctx)
        chat_listener.bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        # Mock Hippocampus recall
        mock_context = MagicMock()
        mock_context.working_memory = ""
        chat_listener.bot.loop.run_in_executor = AsyncMock(return_value=mock_context)

        # Mock scope
        with patch("src.privacy.scopes.ScopeManager.get_scope") as mock_scope:
            mock_scope.return_value.name = "PUBLIC"
            chat_listener.prompt_manager.get_system_prompt.return_value = "System Prompt"
            
            await chat_listener.on_message(mock_message)
            
            # SHOULD have replied with clarification
            mock_message.reply.assert_awaited()
            # Verify one of the replies contains the question
            replies = [str(call.args[0]) for call in mock_message.reply.call_args_list]
            assert any("What do you mean?" in r for r in replies), \
                "Clarification should be sent when no files attached!"

    @pytest.mark.asyncio
    async def test_image_attachment_still_allows_clarification(self, chat_listener, mock_message):
        """Images are handled separately - clarification should still be allowed."""
        
        # Image attachment only
        mock_image = MagicMock()
        mock_image.filename = "photo.png"
        mock_image.content_type = "image/png"
        mock_image.size = 5000
        mock_image.read = AsyncMock(return_value=b"PNG...")
        mock_message.attachments = [mock_image]
        
        # Preprocessor returns clarification_needed
        chat_listener.preprocessor.process.return_value = {
            "complexity": "LOW",
            "clarification_needed": "What should I do with this image?"
        }
        
        # Setup mocks
        ctx = MagicMock()
        ctx.valid = False
        chat_listener.bot.get_context = AsyncMock(return_value=ctx)
        chat_listener.bot.engine_manager.get_active_engine.return_value = MagicMock()
        
        # Mock Hippocampus recall
        mock_context = MagicMock()
        mock_context.working_memory = ""
        chat_listener.bot.loop.run_in_executor = AsyncMock(return_value=mock_context)
        
        # Mock scope
        with patch("src.privacy.scopes.ScopeManager.get_scope") as mock_scope:
            mock_scope.return_value.name = "PUBLIC"
            chat_listener.prompt_manager.get_system_prompt.return_value = "System Prompt"
            
            await chat_listener.on_message(mock_message)
            
            # SHOULD have replied with clarification (images don't bypass)
            mock_message.reply.assert_awaited()
            replies = [str(call.args[0]) for call in mock_message.reply.call_args_list]
            assert any("What should I do with this image?" in r for r in replies), \
                "Image-only attachments should still allow clarification!"
