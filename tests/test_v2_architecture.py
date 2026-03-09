import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from unittest.mock import MagicMock, AsyncMock, patch
from src.prompts.manager import PromptManager
from src.agents.preprocessor import UnifiedPreProcessor
from src.bot.cogs.chat import ChatListener
from src.bot import globals
from helpers import patch_channel_manager

# --- TRINITY STACK TESTS ---

def test_trinity_stack_assembly():
    """Verify Kernel + Architecture + Identity are stacked."""
    # Mock file reading
    with patch.object(PromptManager, '_read_file') as mock_read:
        mock_read.side_effect = lambda f: f"CONTENT:{f.split('/')[-1]}"
        
        pm = PromptManager(prompt_dir=".")
        prompt = pm.get_system_prompt()
        
        assert "CONTENT:kernel.txt" in prompt
        assert "CONTENT:architecture.txt" in prompt
        assert "CONTENT:identity.txt" in prompt

# --- PRE-PROCESSOR TESTS ---

@pytest.mark.asyncio
async def test_preprocessor_analysis():
    """Verify JSON parsing from PreProcessor."""
    mock_bot = MagicMock()
    mock_engine = MagicMock()
    # Simulate LLM returning JSON
    mock_engine.generate_response.return_value = '```json\n{"intent": "Test", "complexity": "LOW", "reality_check": false, "security_flag": false}\n```'
    mock_bot.engine_manager.get_active_engine.return_value = mock_engine
    mock_bot.loop.run_in_executor = AsyncMock(side_effect=lambda e, f, *a: f(*a))
    
    agent = UnifiedPreProcessor(mock_bot)
    result = await agent.process("Hello")
    
    assert result["intent"] == "Test"
    assert result["complexity"] == "LOW"
    assert not result["security_flag"]

@pytest.mark.asyncio
async def test_preprocessor_security_flag():
    """Verify Security Flag prevents processing."""
    mock_bot = MagicMock()
    mock_engine = MagicMock()
    mock_engine.generate_response.return_value = '{"security_flag": true}'
    mock_bot.engine_manager.get_active_engine.return_value = mock_engine
    mock_bot.loop.run_in_executor = AsyncMock(side_effect=lambda e, f, *a: f(*a))
    
    agent = UnifiedPreProcessor(mock_bot)
    result = await agent.process("Unsafe input")
    
    assert result["security_flag"] is True

@pytest.mark.asyncio
async def test_preprocessor_attachment_info():
    """Verify attachment_info is included in context for clarification awareness."""
    mock_bot = MagicMock()
    mock_engine = MagicMock()
    mock_engine.generate_response.return_value = '{"intent": "file_analysis", "complexity": "MEDIUM", "reality_check": false, "security_flag": false, "clarification_needed": null}'
    mock_bot.engine_manager.get_active_engine.return_value = mock_engine
    mock_bot.loop.run_in_executor = AsyncMock(side_effect=lambda e, f, *a: f(*a))
    
    agent = UnifiedPreProcessor(mock_bot)
    attachment_info = "ATTACHMENTS:\n- config.json (file, 2048 bytes)\n- screenshot.png (image, 45000 bytes)"
    result = await agent.process(
        "analyze this file", 
        context="", 
        has_images=True,
        attachment_info=attachment_info
    )
    
    # Verify context was passed to engine with attachment info
    call_args = mock_engine.generate_response.call_args
    context_arg = call_args[0][1]  # Second positional arg is context
    assert "ATTACHMENTS:" in context_arg
    assert "config.json" in context_arg
    assert "screenshot.png" in context_arg
    assert result["intent"] == "file_analysis"
    assert result["clarification_needed"] is None  # No clarification needed for files

# --- CHAT INTEGRATION TESTS ---

@pytest.mark.asyncio
async def test_chat_integration_security_rejection():
    """Verify Chat rejects unsafe input based on PreProcessor."""
    mock_bot = MagicMock()
    patch_channel_manager(mock_bot)
    mock_bot.loop = MagicMock()
    mock_bot.loop.run_in_executor = AsyncMock(side_effect=lambda e, f, *a: f(*a))
    mock_bot.get_context = AsyncMock(return_value=MagicMock(valid=False))
    mock_engine = MagicMock() # Ensure engine exists
    mock_engine.generate_response.return_value = "{}"
    mock_bot.engine_manager.get_active_engine.return_value = mock_engine
    mock_bot.silo_manager = MagicMock()
    mock_bot.silo_manager.propose_silo = AsyncMock()
    mock_bot.silo_manager.check_text_confirmation = AsyncMock(return_value=False)
    mock_bot.silo_manager.should_bot_reply = AsyncMock(return_value=True)

    with patch("src.bot.cogs.chat.UnifiedPreProcessor") as MockPP:
        instance = MockPP.return_value
        instance.process = AsyncMock(return_value={"security_flag": True})
        
        cog = ChatListener(mock_bot)
        
        msg = MagicMock()
        msg.reply = AsyncMock()
        msg.author.bot = False
        msg.channel.id = 123
        msg.content = "Unsafe" # Set content

        # Mock Cerebrum/Strategy for Superego check (Line 254)
        mock_strategy = MagicMock()
        mock_superego = MagicMock()
        mock_superego.execute = AsyncMock(return_value="SAFE") # Or whatever needed
        mock_strategy.get_ability.return_value = mock_superego
        mock_bot.cerebrum.get_lobe.return_value = mock_strategy
        
        with patch("config.settings.TARGET_CHANNEL_ID", 123):
            await cog.on_message(msg)
            
            # Should NOT reply with rejection (Disabled feature)
            # msg.reply.assert_called_with("Request rejected by Cognitive Security Protocol.")
            # Should proceed to Silo/Recall
            mock_bot.silo_manager.propose_silo.assert_awaited()

@pytest.mark.asyncio
async def test_chat_integration_intent_injection():
    """Verify Intent is injected into system prompt."""
    mock_bot = MagicMock()
    patch_channel_manager(mock_bot)
    mock_bot.loop = MagicMock()
    mock_bot.loop.run_in_executor = AsyncMock(side_effect=lambda e, f, *a: f(*a))
    mock_bot.get_context = AsyncMock(return_value=MagicMock(valid=False))
    mock_bot.hippocampus.recall = MagicMock()
    mock_bot.hippocampus.observe = AsyncMock()
    mock_bot.cerebrum.get_lobe.return_value = MagicMock()
    mock_bot.silo_manager = MagicMock()
    mock_bot.silo_manager.propose_silo = AsyncMock()
    mock_bot.silo_manager.check_text_confirmation = AsyncMock(return_value=False)
    mock_bot.silo_manager.should_bot_reply = AsyncMock(return_value=True)
    mock_bot.processing_users = set()
    from collections import defaultdict
    mock_bot.message_queues = defaultdict(list)
    
    # Mock Cognition Engine (Async)
    mock_bot.cognition = MagicMock()
    # process returns (text, files)
    mock_bot.cognition.process = AsyncMock(return_value=("Response", [], []))
    
    mock_main_engine = MagicMock()
    mock_main_engine.generate_response.return_value = "Response"
    mock_bot.engine_manager.get_active_engine.return_value = mock_main_engine
    
    # Mock Prompt Manager AND ScopeManager
    with patch("src.bot.cogs.chat.PromptManager") as MockPM, \
         patch("src.bot.cogs.chat.UnifiedPreProcessor") as MockPP, \
         patch("src.bot.cogs.chat.ResponseFeedbackView"), \
         patch("src.bot.cogs.chat.ToolRegistry"), \
         patch("src.privacy.scopes.ScopeManager") as MockScope, \
         patch("src.privacy.guard.get_user_silo_path", return_value="/tmp/silo"), \
         patch("pathlib.Path") as MockPath: # Mock Path globally or specifically? 
         
        # Setup Path mock to pretend silo exists
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        MockPath.return_value = mock_path
         
        MockScope.get_scope.return_value.name = "PUBLIC" # Ensure valid scope
        
        pp_instance = MockPP.return_value
        pp_instance.process = AsyncMock(return_value={
            "intent": "TEST_INTENT", 
            "complexity": "HIGH", 
            "reality_check": True,
            "security_flag": False
        })
        
        pm_instance = MockPM.return_value
        # MUST include the placeholder for hot-swap to work!
        pm_instance.get_system_prompt.return_value = "System Prompt with [SYSTEM STATUS: PRE-COGNITIVE TRIAGE - ANALYZING USER INPUT]"
        
        cog = ChatListener(mock_bot)
        
        msg = MagicMock()
        msg.reply = AsyncMock()
        msg.author.bot = False
        msg.channel.id = 123
        msg.content = "Safe" # Set content
        msg.attachments = []
        cm = MagicMock(); cm.__aenter__ = AsyncMock(); cm.__aexit__ = AsyncMock()
        msg.channel.typing.return_value = cm
        
        with patch("config.settings.TARGET_CHANNEL_ID", 123):
             await cog.on_message(msg)
             
             # Check if PM was called with injected intent
             # Check if PM was called with placeholder
             assert pm_instance.get_system_prompt.called
             args, kwargs = pm_instance.get_system_prompt.call_args
             active_goals = kwargs.get("active_goals", "")
             assert "PRE-COGNITIVE TRIAGE" in active_goals
             
             # Check if Engine received the INJECTED intent (Hot-Swap verification)
             # cognition.process(input_text, context, system_context, images, ...)
             # system_context is 3rd positional argument (index 2) OR keyword arg 'system_context'
             
             assert mock_bot.cognition.process.called
             gen_args = mock_bot.cognition.process.call_args
             
             # call_args.args or call_args.kwargs
             # Invoked as keyword args in chat.py usually?
             # chat.py: await cognition.process(input_text=..., context=..., system_context=..., ...)
             
             final_system_prompt = gen_args.kwargs.get("system_context")
             if not final_system_prompt and len(gen_args.args) > 2:
                 final_system_prompt = gen_args.args[2]
                 
             assert final_system_prompt, "System context not found in arguments"
             
             assert "INTENT: TEST_INTENT" in final_system_prompt
             assert "COMPLEXITY: HIGH" in final_system_prompt
             assert "REALITY_CHECK: REQUIRED" in final_system_prompt
