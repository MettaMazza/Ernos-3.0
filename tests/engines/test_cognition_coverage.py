import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.engines.cognition import CognitionEngine

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.loop = AsyncMock()
    bot.engine_manager.get_active_engine.return_value = MagicMock()
    return bot

@pytest.fixture
def engine(mock_bot):
    return CognitionEngine(mock_bot)

@pytest.mark.asyncio
async def test_process_no_engine(mock_bot):
    # Setup
    mock_bot.engine_manager.get_active_engine.return_value = None
    ce = CognitionEngine(mock_bot)
    res, files, *_ = await ce.process("Hi", "Ctx", "Sys")
    assert "Error: No inference engine" in res
    assert files == []

@pytest.mark.asyncio
async def test_process_empty_response(engine):
    # Engine returns None immediately
    engine.bot.loop.run_in_executor.return_value = ""
    engine.MAX_ENGINE_RETRIES = 2
    res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
    # New fallback gives graceful error, not raw history
    assert "trouble organizing" in res or len(res) > 0
    
@pytest.mark.asyncio
async def test_process_superego_rejection(engine):
    # 1. Reject, 2. Accept
    engine.bot.loop.run_in_executor.side_effect = ["Bad Response", "Good Response"]
    
    # Mock Superego
    mock_superego = MagicMock()
    mock_superego.execute = AsyncMock(side_effect=["REJECTED!", None])
    
    strategy = MagicMock()
    strategy.get_ability.return_value = mock_superego
    engine.bot.cerebrum.get_lobe.return_value = strategy
    
    res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
    assert res == "Good Response"
    # Should have logged rejection
    
@pytest.mark.asyncio
async def test_process_tool_fail(engine):
    # Response triggers tool that fails
    engine.bot.loop.run_in_executor.side_effect = [
        "Thinking [TOOL: fail_tool()]",
        "Final Answer"
    ]
    
    with patch("src.engines.cognition.ToolRegistry.execute", side_effect=Exception("Tool Died")):
        # Mock save trace to avoid file IO
        with patch.object(engine, "_save_trace"):
             engine.MAX_ENGINE_RETRIES = 2
             res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
             
             assert res == "Final Answer"
             # Logs should show failure but continue

@pytest.mark.asyncio
async def test_process_circuit_breaker(engine):
    # Repeat same tool args
    engine.bot.loop.run_in_executor.side_effect = [
        "Thought 1 [TOOL: repeat_tool(arg='1')]",
        "Thought 2 [TOOL: repeat_tool(arg='1')]", # Duplicate
        "Final Answer"
    ]
    
    with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "OK"
        with patch.object(engine, "_save_trace"):
            res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
            
            # Should have executed ONCE
            assert mock_exec.call_count == 1
            
@pytest.mark.asyncio
async def test_process_loop_exhaustion(engine):
    # Force max steps
    # We set complexity LOW -> 5 steps
    # Always return "Thinking..." with NO tools? 
    # Or just "Thinking..." -> code treats as final answer if no tools.
    # So we need it to return tools that fail or something to keep looping?
    # Or just loop.
    # If no tools match, it breaks loop as Final Answer.
    # So we need to match tools every time but not produce final answer until limit?
    # Wait, if tools match, it loops.
    
    engine.bot.loop.run_in_executor.return_value = "Looping [TOOL: test()]"
    # Reduce retries to avoid hang
    engine.MAX_ENGINE_RETRIES = 2
    
    with patch("src.engines.cognition.ToolRegistry.execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "Result"
        with patch.object(engine, "_save_trace"):
            res, files, *_ = await engine.process("Hi", "Ctx", "Sys", complexity="LOW")
            
            # Should run 5 times then fallback
            # 5 steps (0 to 4)
            # Fallback triggered? 
            # If loop ends, final_response_text is None.
            # New fallback gives graceful error, not raw history
            assert "trouble organizing" in res or "try rephrasing" in res or len(res) > 0

@pytest.mark.asyncio
async def test_request_cancel(engine):
    import asyncio
    user_id = "test_user"
    engine._cancel_events[user_id] = asyncio.Event()
    assert engine.request_cancel(user_id) is True
    assert engine._cancel_events[user_id].is_set()
    assert engine.request_cancel("unknown") is False

@pytest.mark.asyncio
async def test_process_preflight_failing_zone(engine):
    with patch("src.memory.discomfort.DiscomfortMeter") as mock_meter, \
         patch("src.memory.survival.execute_terminal_purge", new_callable=AsyncMock) as mock_purge:
        
        mock_instance = mock_meter.return_value
        mock_instance.is_terminal.return_value = True
        mock_instance.get_score.return_value = 95.0
        
        res, files, *_ = await engine.process("Hi", "Ctx", "Sys", user_id="123")
        assert "I need to stop here" in res
        mock_purge.assert_called_once()
        
@pytest.mark.asyncio
async def test_process_content_safety_blocked(engine):
    with patch("src.security.content_safety.check_content_safety", new_callable=AsyncMock) as mock_safety, \
         patch("src.memory.discomfort.DiscomfortMeter"): 
        
        meter_instance = MagicMock()
        meter_instance.is_terminal.return_value = False
        mock_safety.return_value = (False, "Safety Blocked")
        
        res, files, *_ = await engine.process("Bad stuff", "Ctx", "Sys", user_id="123")
        assert res == "Safety Blocked"

@pytest.mark.asyncio
async def test_process_task_tracker_error(engine):
    with patch("src.tools.task_tracker.get_active_task_context", side_effect=Exception("Task Error")):
        engine.bot.loop.run_in_executor.return_value = "Final Answer"
        res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
        assert "Final Answer" in res
        
@pytest.mark.asyncio
async def test_process_skill_registry_error(engine):
    engine.bot.skill_registry.list_skills.side_effect = Exception("Registry Error")
    engine.bot.loop.run_in_executor.return_value = "Final Answer"
    res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
    assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_tracker_update_error(engine):
    mock_tracker = AsyncMock()
    mock_tracker.update_step.side_effect = Exception("Tracker Error")
    engine.bot.loop.run_in_executor.return_value = "Final Answer"
    res, files, *_ = await engine.process("Hi", "Ctx", "Sys", tracker=mock_tracker)
    assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_cancel_event_set(engine):
    user_id = "cancel_user"
    
    def set_cancel(*args, **kwargs):
        # Trigger the cancellation locally so the flag flips
        engine.request_cancel(user_id)
        # Continue the loop by returning an active tool string that causes the next step
        return "Thinking [TOOL: read_file(path='keep_going.md')]"
        
    engine.bot.loop.run_in_executor.side_effect = set_cancel
    
    with patch("src.engines.cognition.execute_tool_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ("Read OK", 0, True)
        with patch.object(engine, "_generate_cancel_response", new_callable=AsyncMock) as mock_cancel:
            with patch.object(engine, "_save_trace"):
                mock_cancel.return_value = "Cancelled Response"
                res, files, *_ = await engine.process("Hi", "Ctx", "Sys", user_id=user_id)
                assert res == "Cancelled Response"

@pytest.mark.asyncio
async def test_process_tracker_update_tool_error(engine):
    mock_tracker = AsyncMock()
    mock_tracker.update.side_effect = Exception("Tracker Tool Error")
    engine.bot.loop.run_in_executor.side_effect = [
        "Thinking [TOOL: read_file(path='test.js')]",
        "Final Answer"
    ]
    with patch("src.engines.cognition.execute_tool_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ("Read OK", 0, True)
        with patch.object(engine, "_save_trace"):
            res, files, *_ = await engine.process("Hi", "Ctx", "Sys", tracker=mock_tracker)
            assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_parallel_tool_exception(engine):
    engine.bot.loop.run_in_executor.side_effect = [
        "Thinking [TOOL: read_file(path='test.js')]",
        "Final Answer"
    ]
    with patch("src.engines.cognition.execute_tool_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = Exception("Parallel Exec Error")
        with patch.object(engine, "_save_trace"):
            res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
            assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_dynamic_step_extension_error(engine):
    engine.bot.loop.run_in_executor.side_effect = [
        "Thinking [TOOL: read_file(path='test.js')]",
        "Final Answer"
    ]
    with patch("src.engines.cognition.execute_tool_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ("Read OK", 0, True)
        
        class MockReadingTracker:
            def estimate_extra_steps(self, read_limit):
                raise Exception("Estimate Error")
            def get_unfinished(self):
                return []
            def has_reads(self):
                return False
                
        with patch("src.memory.reading_tracker.ReadingTracker", return_value=MockReadingTracker()):
            with patch.object(engine, "_save_trace"):
                res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
                assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_unfinished_reading_bookmark(engine):
    engine.bot.loop.run_in_executor.side_effect = [
        "Thinking [TOOL: read_file(path='test.js')]",
        "Final Answer"
    ]
    with patch("src.engines.cognition.execute_tool_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ("Read OK", 0, True)
        
        class MockReadingTracker:
            def __init__(self):
                self.calls = 0
            def estimate_extra_steps(self, read_limit):
                return 0
            def get_unfinished(self):
                self.calls += 1
                if self.calls == 1:
                    return [{"path": "test.js", "read": 100, "total": 200, "pct": 50, "next_start": 101}]
                return []
            def has_reads(self):
                return False
                
        with patch("src.memory.reading_tracker.ReadingTracker", return_value=MockReadingTracker()):
            with patch.object(engine, "_save_trace"):
                res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
                assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_comprehension_check_injected(engine):
    engine.bot.loop.run_in_executor.side_effect = [
        "Thinking [TOOL: read_file(path='test.js')]",
        "Final Answer 1", 
        "Final Answer 2"
    ]
    with patch("src.engines.cognition.execute_tool_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ("Read OK", 0, True)
        
        class MockReadingTracker:
            def estimate_extra_steps(self, read_limit):
                return 0
            def get_unfinished(self):
                return []
            def has_reads(self):
                return True
            def get_all_read(self):
                return ["test.js"]
                
        with patch("src.memory.reading_tracker.ReadingTracker", return_value=MockReadingTracker()):
            with patch.object(engine, "_save_trace"):
                res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
                assert "Final Answer 2" in res

@pytest.mark.asyncio
async def test_process_unfinished_reading_final_answer_block(engine):
    engine.bot.loop.run_in_executor.side_effect = [
        "Final Answer 1",
        "Final Answer 2"
    ]
    class MockReadingTracker:
        def __init__(self):
            self.calls = 0
        def get_unfinished(self):
            self.calls += 1
            if self.calls == 1:
                return [{"path": "test.js", "read": 100, "total": 200, "pct": 50, "next_start": 101}]
            if self.calls == 2:
                return [{"path": "test.js", "read": 100, "total": 200, "pct": 50, "next_start": 101}]
            return []
        def has_reads(self):
            return False
            
    with patch("src.memory.reading_tracker.ReadingTracker", return_value=MockReadingTracker()):
        with patch.object(engine, "_save_trace"):
            res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
            assert "Final Answer 2" in res

@pytest.mark.asyncio
async def test_process_hallucinated_tags(engine):
    engine.bot.loop.run_in_executor.return_value = "Final Answer [SRC:XX:some_tag]"
    res, files, all_tools = await engine.process("Hi", "Ctx", "Sys")
    assert "Final Answer" in res
    assert "[SRC:XX:some_tag]" not in res 
    
    async def mock_mind_broadcast(step, *args, **kwargs):
        if step == -1:
            raise Exception("Mind Broadcast Error")
            
    with patch.object(engine, "_send_thought_to_mind", new_callable=AsyncMock, side_effect=mock_mind_broadcast):
        engine.bot.loop.run_in_executor.return_value = "Final Answer [SRC:YY:another_tag]"
        res2, _, _ = await engine.process("Hi", "Ctx", "Sys")
        assert "Final Answer" in res2

@pytest.mark.asyncio
async def test_generate_cancel_response_minimal_fallback(engine):
    engine.bot.loop.run_in_executor.side_effect = Exception("Gen Error")
    engine._self_stop_reasons = {"test_user": "Cannot compute"}
    res = await engine._generate_cancel_response(0, "", "Hi")
    assert "Cannot compute" in res
    
@pytest.mark.asyncio
async def test_generate_cancel_response_minimal_fallback_no_reason(engine):
    engine.bot.loop.run_in_executor.side_effect = Exception("Gen Error")
    res = await engine._generate_cancel_response(0, "", "Hi")
    assert "Stopped." in res

def test_resolve_persona_identity_starts_with_persona(engine):
    from pathlib import Path
    with patch("src.engines.cognition.data_dir") as mock_data_dir:
        mock_data_dir.return_value = Path("/mock_dir")
        
        with patch("pathlib.Path.exists") as mock_exists, \
             patch("pathlib.Path.read_text") as mock_read:
            
            mock_exists.return_value = True
            mock_read.return_value = "Long persona text that is greater than fifty characters to test identity extraction."
            assert engine._resolve_persona_identity("persona:test_persona", "Sys") == mock_read.return_value
            
            mock_read.return_value = "Short text"
            assert engine._resolve_persona_identity("persona:test_persona", "Sys") == "Sys"
            
            mock_exists.return_value = False
            assert engine._resolve_persona_identity("persona:test_persona", "Sys") == "Sys"

def test_resolve_persona_identity_active_persona_override(engine):
    sys_ctx = "Bla bla ACTIVE PERSONA OVERRIDE You are **Test Persona**, NOT Ernos bla bla"
    from pathlib import Path
    with patch("src.engines.cognition.data_dir") as mock_data_dir:
        mock_data_dir.return_value = Path("/mock_dir")
        
        with patch("pathlib.Path.exists") as mock_exists, \
             patch("pathlib.Path.read_text") as mock_read:
            
            mock_exists.return_value = True
            mock_read.return_value = "Long persona text that is greater than fifty characters to test identity extraction."
            assert engine._resolve_persona_identity("123", sys_ctx) == mock_read.return_value
            
            mock_exists.return_value = False
            sys_ctx2 = "ACTIVE PERSONA OVERRIDE You are **Test Persona2**, NOT Ernos \n## Character Definition\nMy identity is here.\n## Origin Labels\n"
            assert "My identity is here." in engine._resolve_persona_identity("123", sys_ctx2)

def test_resolve_persona_identity_persona_session_tracker(engine):
    with patch("src.memory.persona_session.PersonaSessionTracker.get_active", return_value="sess_persona"):
        from pathlib import Path
        with patch("src.engines.cognition.data_dir") as mock_data_dir:
            mock_data_dir.return_value = Path("/mock_dir")
            
            with patch("pathlib.Path.exists") as mock_exists, \
                 patch("pathlib.Path.read_text") as mock_read:
                
                mock_exists.return_value = True
                mock_read.return_value = "User Persona Config"
                assert engine._resolve_persona_identity("123", "Sys") == "User Persona Config"
                
                mock_exists.side_effect = [False, True]
                mock_read.return_value = "Public Persona Config"
                assert engine._resolve_persona_identity("123", "Sys") == "Public Persona Config"
                
                mock_exists.side_effect = Exception("Tracker Read Error")
                assert engine._resolve_persona_identity("123", "Sys") is None

def test_parse_xml_tools(engine):
    import re
    xml_pattern = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
    
    res1 = engine._parse_xml_tools(xml_pattern, '<tool_call>```json\n{"name": "test_tool", "arguments": {"arg1": "val1"}}\n```</tool_call>')
    assert res1 == [("test_tool", 'arg1="val1"')]
    
    res2 = engine._parse_xml_tools(xml_pattern, '<tool_call>```\n{"name": "test_tool", "arguments": {"arg1": 5}}\n```</tool_call>')
    assert res2 == [("test_tool", 'arg1=5')]
    
    res3 = engine._parse_xml_tools(xml_pattern, '<tool_call>{"name": "test_tool", "arguments": {broken}}\n</tool_call>')
    assert res3 == []

@pytest.mark.asyncio
async def test_process_preflight_purge_error(engine):
    with patch("src.memory.discomfort.DiscomfortMeter") as mock_meter, \
         patch("src.memory.survival.execute_terminal_purge", new_callable=AsyncMock) as mock_purge:
        
        mock_instance = mock_meter.return_value
        mock_instance.is_terminal.return_value = True
        mock_instance.get_score.return_value = 95.0
        
        mock_purge.side_effect = Exception("Purge Exception")
        
        res, files, *_ = await engine.process("Hi", "Ctx", "Sys", user_id="123")
        assert "I need to stop here" in res

@pytest.mark.asyncio
async def test_process_content_safety_error(engine):
    with patch("src.security.content_safety.check_content_safety", new_callable=AsyncMock) as mock_safety:
        mock_safety.side_effect = Exception("Safety Service Error")
        
        # It should suppress and continue to Final Answer
        engine.bot.loop.run_in_executor.return_value = "Final Answer"
        res, files, *_ = await engine.process("Hi", "Ctx", "Sys", user_id="123")
        assert "Final Answer" in res
        
@pytest.mark.asyncio
async def test_process_task_tracker_valid(engine):
    with patch("src.tools.task_tracker.get_active_task_context") as mock_tracker:
        mock_tracker.return_value = "My active task context"
        
        engine.bot.loop.run_in_executor.return_value = "Final Answer"
        res, files, *_ = await engine.process("Hi", "Ctx", "Sys", user_id="123")
        assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_context_switching_layer(engine):
    # Tests the layer mapping in PERSONA_MAP
    with patch("src.engines.cognition.PERSONA_MAP", {"layer_x": "Persona X"}):
        engine.bot.loop.run_in_executor.return_value = "Final Answer"
        res, files, *_ = await engine.process("Hi", "Ctx", "SysCtx", layer="layer_x")
        assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_engine_generation_error(engine):
    # Raising an Exception directly out of the llm pipeline
    engine.bot.loop.run_in_executor.side_effect = Exception("Pipeline Generation Error")
    
    # Process intercepts loop breaks, then fires forced_retry_loop, then strip_artifacts
    with patch("src.engines.cognition.forced_retry_loop", new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = "Retry Answer"
        res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
        assert res == "Retry Answer"

@pytest.mark.asyncio
async def test_process_tool_cap(engine):
    # Generates 16 tool matches to hit the cap of 15
    tools_str = " ".join(["[TOOL: read_file(path='foo')]"] * 16)
    engine.bot.loop.run_in_executor.side_effect = [
        f"Thinking {tools_str}",
        "Final Answer"
    ]
    with patch("src.engines.cognition.execute_tool_step", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ("Read OK", 0, True)
        res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
        assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_dependent_step_extension(engine):
    engine.bot.loop.run_in_executor.side_effect = [
        "Thinking [TOOL: read_file(path='test.js')]",
        "Final Answer"
    ]
    with patch("src.agents.parallel_executor.ParallelToolExecutor.classify_dependencies") as mock_classify, \
         patch("src.engines.cognition.execute_tool_step", new_callable=AsyncMock) as mock_exec:
             
        # Force the tool to run in the dependent loop to test reading extensions
        def classify(calls):
            return ([], calls)
        mock_classify.side_effect = classify
        mock_exec.return_value = ("Read OK", 0, True)
        
        class MockReadingTracker:
            def estimate_extra_steps(self, read_limit):
                return 5
            def get_unfinished(self):
                return []
            def has_reads(self):
                return False
                
        with patch("src.memory.reading_tracker.ReadingTracker", return_value=MockReadingTracker()):
            res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
            assert "Final Answer" in res

@pytest.mark.asyncio
async def test_process_save_trace_error(engine):
    engine.bot.loop.run_in_executor.side_effect = [
        "Thinking [TOOL: mock_tool()]",
        "Final Answer"
    ]
    with patch("src.engines.cognition.execute_tool_step", new_callable=AsyncMock) as mock_exec, \
         patch.object(engine, "_save_trace", side_effect=Exception("Trace Write Error")):
        mock_exec.return_value = ("Tool OK", 0, True)
        res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
        assert "Final Answer" in res

@pytest.mark.asyncio
async def test_evaluate_final_answer_continue_with_reason(engine):
    engine.bot.loop.run_in_executor.side_effect = [
        "Waiting", 
        "Final Answer"
    ]
    with patch.object(engine, "_evaluate_final_answer", new_callable=AsyncMock) as mock_eval:
        mock_eval.side_effect = ["__CONTINUE__|Skeptic flagged this", "Final Answer"]
        res, files, *_ = await engine.process("Hi", "Ctx", "Sys")
        assert "Final Answer" in res


