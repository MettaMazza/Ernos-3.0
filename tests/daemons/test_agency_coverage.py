import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from src.daemons.agency import AgencyDaemon

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    # Simple loop representation
    class MockLoop:
        async def run_in_executor(self, executor, func, *args):
            # If it's an async mock, await it, else call it
            res = func(*args)
            if asyncio.iscoroutine(res):
                return await res
            return res
    bot.loop = MockLoop()
    bot.is_processing = False
    bot.last_interaction = 0
    return bot

@pytest.fixture
def daemon(mock_bot):
    d = AgencyDaemon(mock_bot)
    # Fast intervals for testing
    d.TICK_INTERVAL = 0.001
    d.REPORT_INTERVAL = 0.05
    return d

@pytest.mark.asyncio
async def test_start_stop(daemon):
    assert daemon._running is False
    await daemon.start()
    assert daemon._running is True
    # Start again should be a no-op
    await daemon.start()
    
    await daemon.stop()
    assert daemon._running is False
    assert daemon._task.cancelled() or daemon._task.done()

@pytest.mark.asyncio
async def test_loop_kills_on_stop(daemon):
    # Tests that the loop actually respects self._running
    daemon._running = True
    
    async def side_effect_stop(*args, **kwargs):
        daemon._running = False
        
    with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=side_effect_stop):
        await daemon._loop()
    
    assert daemon._running is False

@pytest.mark.asyncio
async def test_loop_transparency_report(daemon):
    daemon.last_report_time = 0
    daemon._running = True
    
    async def stop_loop(*args, **kwargs):
        daemon._running = False
    
    with patch.object(daemon, '_send_transparency_report', new_callable=AsyncMock) as mock_req, \
         patch("asyncio.sleep", new_callable=AsyncMock, side_effect=stop_loop):
        await daemon._loop()
        mock_req.assert_called_once()

@pytest.mark.asyncio
async def test_loop_bot_is_processing(daemon):
    daemon._running = True
    daemon.bot.is_processing = True
    
    async def stop_loop(*args):
        daemon._running = False
        
    with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=stop_loop), \
         patch.object(daemon, '_get_context', new_callable=AsyncMock) as mock_ctx:
        await daemon._loop()
        mock_ctx.assert_not_called()

@pytest.mark.asyncio
async def test_loop_not_idle_enough(daemon):
    daemon._running = True
    daemon.bot.is_processing = False
    daemon.bot.last_interaction = time.time() # Just interacted!
    
    async def stop_loop(*args):
        daemon._running = False
        
    with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=stop_loop), \
         patch.object(daemon, '_get_context', new_callable=AsyncMock) as mock_ctx:
        await daemon._loop()
        mock_ctx.assert_not_called()

@pytest.mark.asyncio
async def test_loop_quota_blocked(daemon):
    daemon._running = True
    daemon.bot.is_processing = False
    daemon.bot.last_interaction = time.time() - 300 # Past IDLE_THRESHOLD
    daemon._last_quota_log = 0 
    
    async def stop_loop(*args):
        daemon._running = False
        
    with patch("src.tools.weekly_quota.is_quota_met", return_value=False), \
         patch("src.tools.weekly_quota.get_remaining_quota", return_value=5.0), \
         patch("asyncio.sleep", new_callable=AsyncMock, side_effect=stop_loop), \
         patch.object(daemon, '_get_context', new_callable=AsyncMock) as mock_ctx:
        await daemon._loop()
        mock_ctx.assert_not_called()

@pytest.mark.asyncio
async def test_loop_full_execution_sleep_decision(daemon):
    daemon._running = True
    daemon.bot.is_processing = False
    daemon.bot.last_interaction = time.time() - 300 
    
    async def stop_loop(*args):
        daemon._running = False
        
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True), \
         patch.object(daemon, '_get_context', new_callable=AsyncMock, return_value="CTX"), \
         patch.object(daemon, '_consult_autonomy_lobe', new_callable=AsyncMock) as mock_consult, \
         patch("asyncio.sleep", new_callable=AsyncMock, side_effect=stop_loop):
        
        mock_consult.return_value = {"action": "SLEEP"}
        await daemon._loop()
        assert daemon.consecutive_sleeps == 1

@pytest.mark.asyncio
async def test_loop_consecutive_sleep_reflection(daemon):
    # Test forcing reflection after MAX sleeps
    daemon._running = True
    daemon.consecutive_sleeps = daemon.MAX_CONSECUTIVE_SLEEP
    daemon.bot.last_interaction = time.time() - 300 
    
    async def stop_loop(*args):
        daemon._running = False
        
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True), \
         patch.object(daemon, '_get_context', new_callable=AsyncMock, return_value="CTX"), \
         patch.object(daemon, '_consult_autonomy_lobe', new_callable=AsyncMock) as mock_consult, \
         patch.object(daemon, '_execute_decision', new_callable=AsyncMock) as mock_exec, \
         patch("asyncio.sleep", new_callable=AsyncMock, side_effect=stop_loop):
        
        mock_consult.return_value = {"action": "SLEEP"}
        await daemon._loop()
        assert daemon.consecutive_sleeps == 0
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0][0]
        assert args["action"] == "REFLECTION"

@pytest.mark.asyncio
async def test_get_context_all_present(daemon):
    # Hippocampus, Goals, globals
    mock_hippo = MagicMock()
    mock_hippo.stream.get_context.return_value = "Memory Blob"
    daemon.bot.hippocampus = mock_hippo
    
    with patch("src.memory.goals.get_goal_manager") as mock_gm, \
         patch("src.bot.globals.activity_log", [{"timestamp": "12:00", "summary": "act1"}]):
        
        mock_gm.return_value.list_goals.return_value = "Goal 1"
        res = await daemon._get_context()
        assert "Memory Blob" in res
        assert "Goal 1" in res
        assert "act1" in res

@pytest.mark.asyncio
async def test_get_context_empty(daemon):
    daemon.bot.hippocampus = None
    with patch("src.memory.goals.get_goal_manager", side_effect=Exception("No Goals")), \
         patch("src.bot.globals.activity_log", []):
             
         res = await daemon._get_context()
         assert res == "No context available."

@pytest.mark.asyncio
async def test_consult_autonomy_lobe_success(daemon):
    mock_engine = MagicMock()
    mock_engine.generate_response.return_value = 'Here is the plan:\n{"action": "RESEARCH", "target": "Python"}'
    daemon.bot.engine_manager.get_active_engine.return_value = mock_engine
    
    res = await daemon._consult_autonomy_lobe({"uncertainty": 50, "social_connection": 50, "system_health": 100}, "Ctx")
    assert res == {"action": "RESEARCH", "target": "Python"}

@pytest.mark.asyncio
async def test_consult_autonomy_lobe_no_engine(daemon):
    daemon.bot.engine_manager.get_active_engine.return_value = None
    res = await daemon._consult_autonomy_lobe({"uncertainty": 50, "social_connection": 50, "system_health": 100}, "Ctx")
    assert res is None

@pytest.mark.asyncio
async def test_consult_autonomy_lobe_invalid_json(daemon):
    mock_engine = MagicMock()
    mock_engine.generate_response.return_value = 'I will just talk'
    daemon.bot.engine_manager.get_active_engine.return_value = mock_engine
    
    res = await daemon._consult_autonomy_lobe({"uncertainty": 50, "social_connection": 50, "system_health": 100}, "Ctx")
    assert res is None

@pytest.mark.asyncio
async def test_execute_decision_sleep_bypass(daemon):
    await daemon._execute_decision({"action": "SLEEP"})
    assert len(daemon.action_log) == 0

@pytest.mark.asyncio
async def test_execute_decision_outreach(daemon):
    with patch.object(daemon, '_perform_outreach', new_callable=AsyncMock) as mock_outreach, \
         patch("src.bot.globals.activity_log", []):
         
         await daemon._execute_decision({"action": "OUTREACH", "target": "123", "reason": "say hi"})
         mock_outreach.assert_called_once_with("123", "say hi")
         assert len(daemon.action_log) == 1
         assert "OUTREACH" in daemon.action_log[0]

@pytest.mark.asyncio
async def test_execute_decision_research(daemon):
    with patch.object(daemon, '_perform_research', new_callable=AsyncMock) as mock_research, \
         patch("src.bot.globals.activity_log", []):
         
         await daemon._execute_decision({"action": "RESEARCH", "target": "cats", "reason": "curiosity"})
         mock_research.assert_called_once_with("cats", "curiosity")

@pytest.mark.asyncio
async def test_execute_decision_reflection(daemon):
    with patch.object(daemon, '_perform_reflection', new_callable=AsyncMock) as mock_reflection, \
         patch("src.bot.globals.activity_log", []):
         
         await daemon._execute_decision({"action": "REFLECTION", "reason": "pondering"})
         mock_reflection.assert_called_once_with("pondering")

@pytest.mark.asyncio
async def test_perform_outreach_no_cerebrum(daemon):
    daemon.bot.cerebrum = None
    await daemon._perform_outreach("123", "Hi")
    # Returns safely

@pytest.mark.asyncio
async def test_perform_outreach_placeholder_target(daemon):
    daemon.bot.cerebrum = MagicMock()
    await daemon._perform_outreach("user", "Hi")

@pytest.mark.asyncio
async def test_perform_outreach_resolve_target_by_name(daemon):
    mock_member = MagicMock()
    mock_member.display_name = "Alice"
    mock_member.id = 999
    
    mock_guild = MagicMock()
    mock_guild.members = [mock_member]
    daemon.bot.guilds = [mock_guild]
    
    # Needs engine for generation
    mock_engine = MagicMock()
    mock_engine.process = AsyncMock(return_value=("Hello Alice!", [], []))
    daemon.bot.cognition = mock_engine
    
    # Needs user fetch
    mock_user = MagicMock()
    mock_user.display_name = "Alice"
    daemon.bot.fetch_user = AsyncMock(return_value=mock_user)
    
    # Needs OutreachManager
    with patch("src.memory.outreach.OutreachManager.deliver_outreach", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = (True, "sent ok")
        await daemon._perform_outreach("Alice", "Checking in")
        mock_deliv.assert_called_once()
        assert mock_deliv.call_args[0][1] == 999

@pytest.mark.asyncio
async def test_perform_outreach_engine_empty_response(daemon):
    daemon.bot.cerebrum = MagicMock()
    mock_engine = MagicMock()
    mock_engine.process = AsyncMock(return_value=("", [], []))
    daemon.bot.cognition = mock_engine
    await daemon._perform_outreach("123", "Checking in")

@pytest.mark.asyncio
async def test_perform_research_success(daemon):
    mock_research = AsyncMock()
    mock_research.execute.return_value = "Research data"
    
    mock_lobe = MagicMock()
    mock_lobe.get_ability.return_value = mock_research
    daemon.bot.cerebrum.get_lobe.return_value = mock_lobe
    
    daemon.bot.hippocampus.stream.add_turn = AsyncMock()
    
    await daemon._perform_research("Cats", "Why purr")
    daemon.bot.hippocampus.stream.add_turn.assert_called_once()

@pytest.mark.asyncio
async def test_perform_reflection_success(daemon):
    mock_engine = MagicMock()
    mock_engine.process = AsyncMock(return_value=("Insightful thought", [], []))
    daemon.bot.cognition = mock_engine
    
    daemon.bot.cerebrum = MagicMock()
    
    daemon.bot.hippocampus.stream.add_turn = AsyncMock()
    
    await daemon._perform_reflection("Why exist")
    daemon.bot.hippocampus.stream.add_turn.assert_called_once()

@pytest.mark.asyncio
async def test_outreach_passes_context_to_cognition(daemon):
    """Regression: cognition.process() requires 'context' positional arg."""
    daemon.bot.cerebrum = MagicMock()
    mock_engine = MagicMock()
    mock_engine.process = AsyncMock(return_value=("Hello!", [], []))
    daemon.bot.cognition = mock_engine

    mock_user = MagicMock()
    mock_user.display_name = "TestUser"
    daemon.bot.fetch_user = AsyncMock(return_value=mock_user)

    with patch("src.memory.outreach.OutreachManager.deliver_outreach", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = (True, "sent ok")
        await daemon._perform_outreach("123", "Check-in")

    mock_engine.process.assert_called_once()
    _, kwargs = mock_engine.process.call_args
    assert "context" in kwargs, "cognition.process() must receive 'context' kwarg"
    assert kwargs["context"] == ""

@pytest.mark.asyncio
async def test_reflection_passes_context_to_cognition(daemon):
    """Regression: cognition.process() requires 'context' positional arg."""
    mock_engine = MagicMock()
    mock_engine.process = AsyncMock(return_value=("Deep thought", [], []))
    daemon.bot.cognition = mock_engine
    daemon.bot.cerebrum = MagicMock()
    daemon.bot.hippocampus.stream.add_turn = AsyncMock()

    await daemon._perform_reflection("Self-assessment")

    mock_engine.process.assert_called_once()
    _, kwargs = mock_engine.process.call_args
    assert "context" in kwargs, "cognition.process() must receive 'context' kwarg"
    assert kwargs["context"] == ""

@pytest.mark.asyncio
async def test_send_transparency_report_success(daemon):
    daemon.action_log = ["Action 1", "Action 2"]
    daemon.bot.send_to_mind = AsyncMock()
    
    await daemon._send_transparency_report()
    daemon.bot.send_to_mind.assert_called_once()
    assert len(daemon.action_log) == 0

@pytest.mark.asyncio
async def test_send_transparency_report_empty(daemon):
    daemon.action_log = []
    daemon.bot.send_to_mind = AsyncMock()
    
    await daemon._send_transparency_report()
    daemon.bot.send_to_mind.assert_not_called()

# --- Edge Cases & Exceptions (15%) ---

@pytest.mark.asyncio
async def test_loop_quota_import_error(daemon):
    daemon._running = True
    daemon.bot.is_processing = False
    daemon.bot.last_interaction = time.time() - 300 
    
    async def stop_loop(*args, **kwargs):
        daemon._running = False
        
    with patch.dict('sys.modules', {'src.tools.weekly_quota': None}), \
         patch.object(daemon, '_get_context', new_callable=AsyncMock, return_value="CTX"), \
         patch.object(daemon, '_consult_autonomy_lobe', new_callable=AsyncMock, return_value={"action": "SLEEP"}), \
         patch("asyncio.sleep", new_callable=AsyncMock, side_effect=stop_loop):
        
        await daemon._loop()
        assert not daemon._running

@pytest.mark.asyncio
async def test_loop_action_not_sleep(daemon):
    daemon._running = True
    daemon.bot.is_processing = False
    daemon.bot.last_interaction = time.time() - 300 
    daemon.consecutive_sleeps = 2
    
    async def stop_loop(*args, **kwargs):
        daemon._running = False
        
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True), \
         patch.object(daemon, '_get_context', new_callable=AsyncMock, return_value="CTX"), \
         patch.object(daemon, '_consult_autonomy_lobe', new_callable=AsyncMock, return_value={"action": "OUTREACH"}), \
         patch.object(daemon, '_execute_decision', new_callable=AsyncMock), \
         patch("asyncio.sleep", new_callable=AsyncMock, side_effect=stop_loop):
        
        await daemon._loop()
        assert daemon.consecutive_sleeps == 0

@pytest.mark.asyncio
async def test_loop_exception(daemon):
    daemon._running = True
    daemon.bot.is_processing = False
    daemon.bot.last_interaction = time.time() - 300 
    
    async def stop_loop(*args, **kwargs):
        daemon._running = False
        
    with patch("src.tools.weekly_quota.is_quota_met", return_value=True), \
         patch.object(daemon, '_get_context', side_effect=Exception("Test Loop Error")), \
         patch("asyncio.sleep", new_callable=AsyncMock, side_effect=stop_loop):
        
        await daemon._loop()

@pytest.mark.asyncio
async def test_get_context_hippocampus_exception(daemon):
    mock_hippo = MagicMock()
    mock_hippo.stream.get_context.side_effect = Exception("Memory Read Error")
    daemon.bot.hippocampus = mock_hippo
    
    with patch("src.memory.goals.get_goal_manager", side_effect=Exception("No Goals")), \
         patch("src.bot.globals.activity_log", []):
         res = await daemon._get_context()
         assert res == "No context available."

@pytest.mark.asyncio
async def test_get_context_globals_exception(daemon):
    daemon.bot.hippocampus = None
    with patch("src.memory.goals.get_goal_manager", side_effect=Exception("No Goals")), \
         patch("src.bot.globals.activity_log", None):
        res = await daemon._get_context()
        assert "No context available." in res

@pytest.mark.asyncio
async def test_execute_decision_globals_exception(daemon):
    with patch("src.bot.globals.activity_log", MagicMock(append=MagicMock(side_effect=Exception("Log Err")))):
        await daemon._execute_decision({"action": "RESEARCH", "target": "tests", "reason": "why"})
        assert "RESEARCH" in daemon.action_log[-1]

@pytest.mark.asyncio
async def test_perform_outreach_unresolvable_target(daemon):
    daemon.bot.cerebrum = MagicMock()
    daemon.bot.guilds = []
    
    await daemon._perform_outreach("GhostUser", "Looking for ghosts")

@pytest.mark.asyncio
async def test_perform_outreach_no_engine(daemon):
    daemon.bot.cerebrum = MagicMock()
    daemon.bot.cognition = None
    
    await daemon._perform_outreach("123", "Checking in")

@pytest.mark.asyncio
async def test_perform_outreach_user_not_found(daemon):
    daemon.bot.cerebrum = MagicMock()
    mock_engine = MagicMock()
    mock_engine.process = AsyncMock(return_value=("Hello unknown!", [], []))
    daemon.bot.cognition = mock_engine
    
    daemon.bot.fetch_user = AsyncMock(return_value=None)
    
    await daemon._perform_outreach("123", "Checking in")

@pytest.mark.asyncio
async def test_perform_outreach_delivery_blocked(daemon):
    daemon.bot.cerebrum = MagicMock()
    mock_engine = MagicMock()
    mock_engine.process = AsyncMock(return_value=("Hello blocked!", [], []))
    daemon.bot.cognition = mock_engine
    
    daemon.bot.fetch_user = AsyncMock(return_value=MagicMock(display_name="Blocked"))
    
    with patch("src.memory.outreach.OutreachManager.deliver_outreach", new_callable=AsyncMock) as mock_deliv:
        mock_deliv.return_value = (False, "User opted out")
        await daemon._perform_outreach("123", "Checking in")

@pytest.mark.asyncio
async def test_perform_outreach_exception(daemon):
    # Pass an integer for target when it expects a string, which triggers `.strip()` crash
    await daemon._perform_outreach(None, "Crash reason")

@pytest.mark.asyncio
async def test_perform_research_components_missing(daemon):
    # No cerebrum
    daemon.bot.cerebrum = None
    await daemon._perform_research("Cats", "Why purr")
    
    daemon.bot.cerebrum = MagicMock()
    
    # Missing Interaction Lobe
    daemon.bot.cerebrum.get_lobe.return_value = None
    await daemon._perform_research("Cats", "Why purr")
    
    # Missing Research Ability
    mock_lobe = MagicMock()
    mock_lobe.get_ability.return_value = None
    daemon.bot.cerebrum.get_lobe.return_value = mock_lobe
    await daemon._perform_research("Cats", "Why purr")
    
    # Exception during research
    mock_ability = MagicMock()
    mock_ability.execute = AsyncMock(side_effect=Exception("Research API Down"))
    mock_lobe.get_ability.return_value = mock_ability
    await daemon._perform_research("Cats", "Why purr")

@pytest.mark.asyncio
async def test_perform_reflection_components_missing_and_exception(daemon):
    # No cerebrum
    daemon.bot.cerebrum = None
    await daemon._perform_reflection("Life")
    
    daemon.bot.cerebrum = MagicMock()
    
    # Missing Cognition
    daemon.bot.cognition = None
    await daemon._perform_reflection("Life")
    
    # Exception during reflection memory persistence
    mock_engine = MagicMock()
    mock_engine.process = AsyncMock(return_value=("Insight", [], []))
    daemon.bot.cognition = mock_engine
    
    mock_hippo = MagicMock()
    mock_hippo.stream.add_turn = AsyncMock(side_effect=Exception("DB Error"))
    daemon.bot.hippocampus = mock_hippo
    
    await daemon._perform_reflection("Life")

@pytest.mark.asyncio
async def test_send_transparency_report_exception(daemon):
    daemon.action_log = ["Action 1"]
    daemon.bot.send_to_mind = AsyncMock(side_effect=Exception("Discord API Down"))
    
    await daemon._send_transparency_report()

@pytest.mark.asyncio
async def test_global_activity_log_exception(daemon):
    # Triggers the 'except Exception:' in _get_context around globals.activity_log setup
    daemon.bot.hippocampus = None
    with patch("src.memory.goals.get_goal_manager", side_effect=Exception("No Goals")), \
         patch("src.bot.globals.activity_log", [MagicMock(get=MagicMock(side_effect=Exception("Iter Err")))]):
        res = await daemon._get_context()
        assert "No context available." in res

@pytest.mark.asyncio
async def test_perform_outreach_overall_exception(daemon):
    daemon.bot.cerebrum = MagicMock()
    # Trigger exception overall by passing a bad type to str() resolution that fails early
    class ExplodingStr:
        def __str__(self):
            raise Exception("Str Exploded")
    await daemon._perform_outreach(ExplodingStr(), "Say hi")

@pytest.mark.asyncio
async def test_perform_reflection_overall_exception(daemon):
    # Trigger exception overall
    daemon.bot.cerebrum = MagicMock()
    daemon.bot.cerebrum.get_lobe.side_effect = Exception("Overall Reflection Exploded")
    await daemon._perform_reflection("Life")

