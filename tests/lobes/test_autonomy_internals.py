import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.lobes.creative.autonomy import AutonomyAbility

@pytest.fixture
def mock_autonomy():
    lobe = MagicMock()
    lobe.cerebrum.bot.engine_manager.get_active_engine.return_value = MagicMock()
    lobe.cerebrum.bot.loop.run_in_executor = AsyncMock()
    lobe.cerebrum.bot.send_to_dev_channel = AsyncMock()
    d = AutonomyAbility(lobe)
    # d.bot property already points to lobe.cerebrum.bot
    return d

@pytest.mark.asyncio
async def test_autonomy_one_shot(mock_autonomy):
    # Setup Engine response
    mock_autonomy.bot.loop.run_in_executor.return_value = "A philosophical thought."
    
    res = await mock_autonomy.execute("What is life?")
    
    assert "[DREAM]: A philosophical thought." in res
    mock_autonomy.bot.loop.run_in_executor.assert_awaited()

@pytest.mark.asyncio
async def test_autonomy_already_running(mock_autonomy):
    mock_autonomy.is_running = True
    res = await mock_autonomy.execute()
    assert "Autonomy Loop already active." in res

@pytest.mark.asyncio
async def test_autonomy_loop_idle(mock_autonomy):
    # Verify Autonomy triggers on idle
    
    async def sleep_side_effect(duration):
        if duration == 10:
            if mock_autonomy.is_running_count > 0:
                 raise asyncio.CancelledError()
            mock_autonomy.is_running_count += 1
            return
        return 
    
    mock_autonomy.is_running_count = 0
    
    with patch("asyncio.sleep", side_effect=sleep_side_effect):
        # Setup Idle state
        mock_autonomy.bot.is_processing = False
        mock_autonomy.bot.last_interaction = 0 
        
        # Engine Response sequence: 1. Tool, 2. No Tool (Breaks loop)
        responses = [
            "Thinking... [TOOL: verify_thought(query='test')]",
            "Done thinking."
        ]
        mock_autonomy.bot.loop.run_in_executor.side_effect = responses
        
        # Tool Registry
        with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock) as mock_execute:
             mock_execute.return_value = "Verified."
             
             await mock_autonomy.execute()
             
             assert mock_autonomy.is_running is False 
             mock_execute.assert_awaited_with("verify_thought", query='test', user_id='CORE', request_scope='CORE')

@pytest.mark.asyncio
async def test_autonomy_loop_active(mock_autonomy):
    # Verify Autonomy skips if user active
    
    async def sleep_break(d):
        raise asyncio.CancelledError()
    
    with patch("asyncio.sleep", side_effect=sleep_break):
         mock_autonomy.bot.is_processing = True # Active
         await mock_autonomy.execute()
         # Should verify run_in_executor NOT called for autonomy
         # But one-shot logic checked 'instruction' arg. Here no arg.
    
    # Since we broke loop immediately, verify NO autonomy logged
    mock_autonomy.bot.loop.run_in_executor.assert_not_awaited()

@pytest.mark.asyncio
async def test_autonomy_tool_limit(mock_autonomy):
    # Test internal tool limit logic
    # Setup idle
    mock_autonomy.is_running_count = 0
    async def sleep_side_effect(duration):
        if duration == 10:
            if mock_autonomy.is_running_count > 3:
                 raise asyncio.CancelledError()
            mock_autonomy.is_running_count += 1
            return
        return
    
    mock_autonomy.bot.is_processing = False
    mock_autonomy.bot.last_interaction = 0
    
    # Response with tool
    mock_autonomy.bot.loop.run_in_executor.return_value = "I react [TOOL: add_reaction(emoji='x')]"
    
    # We want to loop internal autonomy loop multiple times to hit limit
    # The internal loop breaks if `step > 3` or `not tool_matches`.
    # If response always has tool, it loops.
    # We need to simulate multiple responses.
    
    responses = [
        "1 [TOOL: add_reaction(emoji='1')]",
        "2 [TOOL: add_reaction(emoji='2')]",
        "3 [TOOL: add_reaction(emoji='3')]",
        "4 [TOOL: add_reaction(emoji='4')]", # Should trigger limit
        "5 Done" # No tool, breaks
    ]
    from src.lobes.creative.autonomy import ToolRegistry as DreamerTR
    
    # FIX: Ensure observe is awaitable (AsyncMock)
    mock_autonomy.bot.hippocampus.observe = AsyncMock()
    # FIX: Ensure send_to_mind is awaitable (AsyncMock)
    mock_autonomy.bot.send_to_mind = AsyncMock()
    
    mock_autonomy.bot.loop.run_in_executor.side_effect = responses
    
    call_log = []
    async def fake_exec(*args, **kwargs):
        call_log.append(kwargs)
        return "Verified"
        
    # Patch the reference explicitly held by the module
    original = DreamerTR.execute
    DreamerTR.execute = fake_exec
    
    try:
         with patch("src.tools.weekly_quota.is_quota_met", return_value=True):
             with patch("asyncio.sleep", side_effect=sleep_side_effect):
                 await mock_autonomy.execute()
    finally:
         DreamerTR.execute = original
             
    # Count calls
    # Call args are in kwargs
    # Filter for 'add_reaction'
    count = 0
    for c in call_log:
        # Check if emoji is present (argument of add_reaction in test)
        if 'emoji' in c:
            count += 1
            
    assert count == 3
