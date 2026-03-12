import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.lobes.creative.autonomy import AutonomyAbility

class DummyCognition:
    def __init__(self):
        self.response_text = ""
        self.should_raise = False
        
    async def process(self, *args, **kwargs):
        if self.should_raise:
            raise Exception("Cognition Failure")
        return self.response_text

class DummyBot:
    def __init__(self):
        self.cognition = DummyCognition()
        self.engine_manager = MagicMock()
        
        # Give it a skill registry for any remaining compatibility
        self.skill_registry = MagicMock()
        mock_skill = MagicMock()
        mock_skill.name = "test_skill"
        mock_skill.description = "A skill to test."
        self.skill_registry.list_skills.return_value = [mock_skill]
        
    def get_channel(self, channel_id):
        pass

@pytest.fixture
def autonomy():
    bot = DummyBot()
    lobe = MagicMock()
    lobe.cerebrum.bot = bot
    return AutonomyAbility(lobe)

@pytest.mark.asyncio
async def test_run_task_no_tools(autonomy):
    # Tests a response with no tools, just basic text
    autonomy.bot.cognition.response_text = "Just pure thought."
    
    with patch('src.lobes.creative.autonomy.logger') as mock_logger:
        result = await autonomy.run_task("Do something")
        assert "Just pure thought" in result

@pytest.mark.asyncio
async def test_run_task_tuple_response(autonomy):
    # Tests a response with a tuple (text, context, tools)
    autonomy.bot.cognition.response_text = ("Task output", "context", [])
    
    result = await autonomy.run_task("Do something")
    assert "Task output" in result

@pytest.mark.asyncio
async def test_run_task_engine_crash(autonomy):
    autonomy.bot.cognition.should_raise = True
    result = await autonomy.run_task("Do something")
    assert "Task Failed: Cognition Failure" in result

@pytest.mark.asyncio
async def test_send_transparency_report(autonomy):
    autonomy.summary_channel_id = 123
    mock_channel = AsyncMock()
    autonomy.bot.get_channel = MagicMock(return_value=mock_channel)
    autonomy.autonomy_log_buffer.append("Test activity")
    
    autonomy.bot.cognition.response_text = "Here is the summary."
    
    with patch('src.tools.weekly_quota.get_quota_status', return_value="Active"):
        with patch('src.memory.autobiography.get_autobiography_manager') as m_auto:
            await autonomy._send_transparency_report()
            mock_channel.send.assert_called()
            m_auto().append_entry.assert_called()

@pytest.mark.asyncio
async def test_send_transparency_report_no_channel(autonomy):
    autonomy.bot.get_channel = MagicMock(return_value=None)
    with patch('src.lobes.creative.autonomy.logger') as mock_logger:
        await autonomy._send_transparency_report()
        mock_logger.error.assert_called()

@pytest.mark.asyncio
async def test_consolidation_delegates_coverage(autonomy):
    with patch("src.lobes.creative.consolidation.MemoryConsolidator") as MockMC:
        mock_c = MockMC.return_value
        mock_c.run_consolidation = AsyncMock(return_value="done1")
        mock_c.update_user_bios = AsyncMock(return_value=3)
        mock_c.synthesize_narrative = AsyncMock(return_value=("narrative", False))
        mock_c.extract_lessons_from_narrative = AsyncMock(return_value=None)
        mock_c.process_episodic_memories = AsyncMock(return_value=1)
        
        await autonomy.run_consolidation()
        await autonomy._process_episodic_memories()
        await autonomy._update_user_bios()
        await autonomy._synthesize_narrative()
        await autonomy._extract_lessons_from_narrative("test")
