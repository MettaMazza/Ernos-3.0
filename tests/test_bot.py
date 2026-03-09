import pytest
import discord
from discord.ext import commands
from src.bot.cogs.chat import ChatListener
from src.bot.cogs.admin import AdminFunctions
from src.bot.client import ErnosBot
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_chat_listener_on_message(mock_discord_bot, tmp_path, mocker):
    """Test message processing pipeline."""
    # Patch settings
    mocker.patch("config.settings.TARGET_CHANNEL_ID", 987654321)
    
    # Setup Cog
    cog = ChatListener(mock_discord_bot)
    # Point prompt manager to temp dir
    cog.prompt_manager.prompt_dir = str(tmp_path)
    (tmp_path / "kernel.txt").write_text("SysPrompt")
    (tmp_path / "identity.txt").write_text("Identity")
    (tmp_path / "dynamic_context.txt").write_text("Time: {timestamp}")
    
    # Mock Cerebrum for chat.py
    mock_discord_bot.cerebrum = MagicMock()
    mock_discord_bot.cerebrum.get_lobe.return_value = MagicMock()
    
    # Mock Engine Manager
    mock_engine = MagicMock()
    mock_engine.generate_response.return_value = "AI Reply"
    mock_discord_bot.engine_manager.get_active_engine.return_value = mock_engine
    
    # Mock Run Executor Side Effect
    mock_ctx_obj = MagicMock()
    mock_ctx_obj.working_memory = "History"
    mock_ctx_obj.related_memories = ["Fact"]
    mock_ctx_obj.knowledge_graph = ["Graph"]
    
    async def side_effect(executor, func, *args):
        # We can identify by args or func name if possible
        # func is a callable. 
        # Recall signature: hippocampus.recall
        if "recall" in str(func): return mock_ctx_obj
        if "generate" in str(func): return "AI Reply"
        return None
        
    mock_discord_bot.loop.run_in_executor = AsyncMock(side_effect=side_effect)
    
    # Mock Message from target channel
    msg = MagicMock()
    msg.author.bot = False
    msg.content = "Hello"
    msg.channel.id = 987654321 # Matches patched ID
    msg.reply = AsyncMock()
    
    await cog.on_message(msg)
    
    # Verify
    mock_discord_bot.engine_manager.get_active_engine.assert_called()
    from unittest.mock import ANY
    msg.reply.assert_called_with("AI Reply", view=ANY, files=ANY)

@pytest.mark.asyncio
async def test_bot_setup_hook(mocker):
    """Test setup hook registers engines and loads extensions."""
    mocker.patch("config.settings.STEERING_MODEL_PATH", "dummy.gguf")
    mock_engine_manager = MagicMock()
    
    # We need to spy on the instance's manager
    # We need to spy on the instance's manager
    mocker.patch("src.bot.client.EngineManager", return_value=mock_engine_manager)
    if True: # Indentation preserve hack or just de-indent? De-indent is better but requires more lines.
        # Let's just run the code.
        bot = ErnosBot()
        
        # Mock load_extension
        bot.load_extension = AsyncMock()
        bot.tree.sync = AsyncMock()
        
        await bot.setup_hook()
        
        # Verify 4 engines registered: cloud, local, local1, local2 (renamed to LocalSteer?)
        # Wait, client code does: cloud, local, LocalSteer
        # local1/local2 were intermediate. Now it's cloud, local, LocalSteer.
        # Check calls
        assert mock_engine_manager.register_engine.call_count >= 3
        calls = [args[0] for args, _ in mock_engine_manager.register_engine.call_args_list]
        assert "cloud" in calls
        assert "local" in calls
        assert "LocalSteer" in calls
        
        assert bot.load_extension.call_count == 12

@pytest.mark.asyncio
async def test_admin_switch_command(mock_discord_bot, mocker):
    """Test switching engines via admin cog."""
    # Patch ID
    mocker.patch("config.settings.ADMIN_ID", 123456789)
    
    cog = AdminFunctions(mock_discord_bot)
    
    # Context
    ctx = MagicMock()
    ctx.author.id = 123456789 
    ctx.send = AsyncMock()
    
    # Mock Engine Manager success
    mock_discord_bot.engine_manager.set_active_engine.return_value = True
    
    # Call callback directly to bypass HybridCommand magic
    await cog.switch_cloud.callback(cog, ctx)
    
    mock_discord_bot.engine_manager.set_active_engine.assert_called_with("cloud")
    ctx.send.assert_called()

@pytest.mark.asyncio
async def test_admin_other_switches(mock_discord_bot, mocker):
    """Test Local and LocalSteer switches."""
    mocker.patch("config.settings.ADMIN_ID", 123456789)
    cog = AdminFunctions(mock_discord_bot)
    ctx = MagicMock()
    ctx.author.id = 123456789
    ctx.send = AsyncMock()
    mock_discord_bot.engine_manager.set_active_engine.return_value = True

    await cog.switch_local.callback(cog, ctx)
    mock_discord_bot.engine_manager.set_active_engine.assert_called_with("local")
    
    await cog.switch_local_steer.callback(cog, ctx)
    mock_discord_bot.engine_manager.set_active_engine.assert_called_with("LocalSteer")
    
    # Test Sync
    mock_discord_bot.tree.sync = AsyncMock(return_value=[1,2,3])
    await cog.sync_commands.callback(cog, ctx)
    ctx.send.assert_called()

@pytest.mark.asyncio
async def test_chat_chunking(mock_discord_bot, tmp_path, mocker):
    """Test splitting long messages."""
    mocker.patch("config.settings.TARGET_CHANNEL_ID", 987654321)
    cog = ChatListener(mock_discord_bot)
    cog.prompt_manager.prompt_dir = str(tmp_path)
    cog.prompt_manager.prompt_dir = str(tmp_path)
    (tmp_path / "kernel.txt").write_text("S")
    (tmp_path / "identity.txt").write_text("I")
    (tmp_path / "dynamic_context.txt").write_text("D")
    
    mock_discord_bot.cerebrum = MagicMock()
    
    # Generate 3000 chars - mock cognition.process to return long response
    long_resp = "A" * 3000
    mock_discord_bot.cognition.process = AsyncMock(return_value=(long_resp, [], []))
    
    mock_engine = MagicMock()
    mock_discord_bot.engine_manager.get_active_engine.return_value = mock_engine
    
    # Mock ScopeManager
    mock_scope = MagicMock()
    mock_scope.name = "PUBLIC"
    mocker.patch("src.privacy.scopes.ScopeManager.get_scope", return_value=mock_scope)
    
    msg = MagicMock()
    msg.author.bot = False
    msg.channel.id = 987654321
    msg.content = "Long pls"
    msg.reply = AsyncMock()
    msg.attachments = []
    
    await cog.on_message(msg)
    
    # Should reply twice (2000 + 1000)
    assert msg.reply.call_count == 2

@pytest.mark.asyncio
async def test_admin_check_fail(mock_discord_bot):
    """Test permission failure."""
    cog = AdminFunctions(mock_discord_bot)
    
    ctx = MagicMock()
    ctx.author.id = 999999999 # Wrong ID
    
    # Direct access to check logic
    can_run = await cog.cog_check(ctx)
    assert can_run is False

@pytest.mark.asyncio
async def test_admin_switch_failures(mock_discord_bot, mocker):
    """Test engine switch failure paths."""
    mocker.patch("config.settings.ADMIN_ID", 123456789)
    cog = AdminFunctions(mock_discord_bot)
    ctx = MagicMock()
    ctx.author.id = 123456789
    ctx.send = AsyncMock()
    
    # Mock failure
    mock_discord_bot.engine_manager.set_active_engine.return_value = False
    
    await cog.switch_cloud.callback(cog, ctx)
    ctx.send.assert_called_with("Failed to switch to Cloud.")
    
    await cog.switch_local.callback(cog, ctx)
    ctx.send.assert_called_with("Failed to switch to Local.")

    await cog.switch_local_steer.callback(cog, ctx)
    ctx.send.assert_called_with("Failed to switch to Local Steering.")

@pytest.mark.asyncio
async def test_chat_ignore_cases(mock_discord_bot):
    """Test ignoring bots and wrong channels."""
    cog = ChatListener(mock_discord_bot)
    msg = MagicMock()
    
    # Case 1: Bot author
    msg.author.bot = True
    await cog.on_message(msg)
    msg.reply.assert_not_called()
    
    # Case 2: Wrong Channel
    msg.author.bot = False
    msg.channel.id = 00000 # Wrong
    await cog.on_message(msg)
    msg.reply.assert_not_called()

@pytest.mark.asyncio
async def test_chat_ignore_commands(mock_discord_bot, mocker, tmp_path):
    """Test ignoring messages that start with prefixes."""
    mocker.patch("config.settings.TARGET_CHANNEL_ID", 123)
    cog = ChatListener(mock_discord_bot)
    cog.prompt_manager.prompt_dir = str(tmp_path)
    (tmp_path / "kernel.txt").write_text("K")
    (tmp_path / "identity.txt").write_text("I")
    (tmp_path / "dynamic_context.txt").write_text("D")
    mock_discord_bot.cerebrum = MagicMock()
    
    msg = MagicMock()
    msg.author.bot = False
    msg.channel.id = 123
    msg.content = "/command"
    
    # Mock get_context
    mock_ctx_obj = MagicMock()
    mock_ctx_obj.working_memory = "User: Hello"
    mock_ctx_obj.related_memories = ["Fact 1"]
    mock_ctx_obj.knowledge_graph = ["Node A->Node B"]
    mock_ctx_obj.valid = True # Ensure it's a valid command context
    mock_discord_bot.get_context = AsyncMock(return_value=mock_ctx_obj)
    
    await cog.on_message(msg)
    msg.reply.assert_not_called()
    
    # Test invalid but starts with prefix
    msg.content = "!invalid"
    mock_ctx_obj.valid = False
    await cog.on_message(msg)
    msg.reply.assert_not_called()

@pytest.mark.asyncio
async def test_chat_engine_missing(mock_discord_bot, mocker, tmp_path):
    """Test error when no engine active."""
    mocker.patch("config.settings.TARGET_CHANNEL_ID", 123)
    
    cog = ChatListener(mock_discord_bot)
    cog.prompt_manager.prompt_dir = str(tmp_path)
    (tmp_path / "kernel.txt").write_text("K")
    (tmp_path / "identity.txt").write_text("I")
    (tmp_path / "dynamic_context.txt").write_text("D")
    mock_discord_bot.cerebrum = MagicMock()
    mock_discord_bot.engine_manager.get_active_engine.return_value = None
    
    msg = MagicMock()
    msg.author.bot = False
    msg.channel.id = 123
    msg.content = "Hello world" # Must not start with / or !
    msg.reply = AsyncMock()
    
    await cog.on_message(msg)
    msg.reply.assert_not_called()

@pytest.mark.asyncio
async def test_chat_exception(mock_discord_bot, mocker, tmp_path):
    """Test exception handling during generation."""
    mocker.patch("config.settings.TARGET_CHANNEL_ID", 123)
    cog = ChatListener(mock_discord_bot)
    cog.prompt_manager.prompt_dir = str(tmp_path)
    (tmp_path / "kernel.txt").write_text("K")
    (tmp_path / "identity.txt").write_text("I")
    (tmp_path / "dynamic_context.txt").write_text("D")
    
    mock_discord_bot.cerebrum = MagicMock()
    
    mock_engine = MagicMock()
    mock_discord_bot.engine_manager.get_active_engine.return_value = mock_engine
    
    # Make cognition.process raise exception
    mock_discord_bot.cognition.process = AsyncMock(side_effect=Exception("Boom"))
    
    # Mock ScopeManager
    mock_scope = MagicMock()
    mock_scope.name = "PUBLIC"
    mocker.patch("src.privacy.scopes.ScopeManager.get_scope", return_value=mock_scope)
    
    msg = MagicMock()
    msg.author.bot = False
    msg.channel.id = 123
    msg.content = "Generate" # Must not start with / or !
    msg.reply = AsyncMock()
    msg.attachments = []
    
    await cog.on_message(msg)
    # Error handling now replies with error
    msg.reply.assert_called()
    assert "Cognitive Engine Failure: Boom" in str(msg.reply.call_args)

@pytest.mark.asyncio
async def test_cog_setups(mock_discord_bot):
    """Cover async def setup(bot) in cogs."""
    from src.bot.cogs import chat, admin
    
    mock_discord_bot.add_cog = AsyncMock()
    
    await chat.setup(mock_discord_bot)
    mock_discord_bot.add_cog.assert_called()
    
    await admin.setup(mock_discord_bot)
    mock_discord_bot.add_cog.assert_called()

def test_client_init_hippocampus_fail(mocker):
    """Test ErnosBot crashes if Hippocampus fails."""
    mocker.patch("src.bot.client.Hippocampus", side_effect=Exception("Critical Mem Fail"))
    with pytest.raises(Exception, match="Critical Mem Fail"):
        ErnosBot()

@pytest.mark.asyncio
async def test_chat_hippocampus_failures(mock_discord_bot, mocker, tmp_path):
    """Test Hippocampus recall/observe errors."""
    mocker.patch("config.settings.TARGET_CHANNEL_ID", 123)
    cog = ChatListener(mock_discord_bot)
    cog.prompt_manager.prompt_dir = str(tmp_path)
    (tmp_path / "kernel.txt").write_text("K")
    (tmp_path / "identity.txt").write_text("I")
    (tmp_path / "dynamic_context.txt").write_text("D")
    
    # Setup mocks
    mock_discord_bot.cerebrum = MagicMock()
    mock_engine = MagicMock()
    mock_engine.generate_response.return_value = "Reply"
    mock_discord_bot.engine_manager.get_active_engine.return_value = mock_engine
    
    # Mock cognition to return "Reply"
    mock_discord_bot.cognition.process = AsyncMock(return_value=("Reply", [], []))
    
    # Mock Hippocampus that fails on recall
    mock_HC = MagicMock()
    mock_HC.recall = MagicMock(side_effect=Exception("Recall Fail"))
    mock_HC.observe = AsyncMock()
    mock_discord_bot.hippocampus = mock_HC
    
    # Mock ScopeManager
    mock_scope = MagicMock()
    mock_scope.name = "PUBLIC"
    mocker.patch("src.privacy.scopes.ScopeManager.get_scope", return_value=mock_scope)
    
    msg = MagicMock()
    msg.author.bot = False
    msg.channel.id = 123
    msg.content = "Test"
    msg.reply = AsyncMock()
    msg.attachments = []
    
    await cog.on_message(msg)
    
    # Should still generate and reply (Graceful degradation)
    from unittest.mock import ANY
    msg.reply.assert_called_with("Reply", view=ANY, files=ANY)
    
    # 2. Observe Failure (should be logged but not crash)
    mock_HC.recall = MagicMock(return_value=MagicMock(
        working_memory="WM", 
        related_memories=[], 
        knowledge_graph=[],
        lessons=[]
    ))
    mock_HC.observe = AsyncMock(side_effect=Exception("Observe Fail"))
    
    msg.reset_mock()
    msg.id = 999999  # Unique ID to avoid message dedup filter
    await cog.on_message(msg)
    
    # Should still generate and reply (Graceful degradation)
    msg.reply.assert_called_with("Reply", view=ANY, files=ANY)
