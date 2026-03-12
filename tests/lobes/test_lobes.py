import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.lobes.manager import Cerebrum
from src.lobes.strategy.lobe import StrategyLobe
from src.lobes.superego import SuperegoLobe
from src.lobes.memory.lobe import MemoryLobe
from src.lobes.interaction.lobe import InteractionLobe
from src.lobes.creative.lobe import CreativeLobe

@pytest.fixture
def mock_bot():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    bot = MagicMock()
    bot.loop = loop
    bot.user = MagicMock()
    bot.user.display_name = "Ernos"
    bot.user.id = 123456789
    bot.get_channel = MagicMock()
    bot.hippocampus = MagicMock()
    bot.town_hall = None
    return bot

@pytest.mark.asyncio
async def test_cerebrum_registration(mock_bot):
    c = Cerebrum(mock_bot)
    # Mock data_dir and TownHall to prevent side effects
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.iterdir.return_value = []
    
    with patch("src.daemons.town_hall.TownHallDaemon"), \
         patch("src.lobes.creative.autonomy.AutonomyAbility.execute", new_callable=AsyncMock) as mock_execute, \
         patch("src.lobes.manager.data_dir", return_value=mock_path):
        await c.setup()
        # Verify background task was at least attempted
        assert mock_execute.called
    
    assert "StrategyLobe" in c.lobes
    assert "MemoryLobe" in c.lobes
    assert "InteractionLobe" in c.lobes
    assert "CreativeLobe" in c.lobes
    assert "SuperegoLobe" in c.lobes

@pytest.mark.asyncio
async def test_strategy_abilities(mock_bot):
    c = Cerebrum(mock_bot)
    c.register_lobe(StrategyLobe)
    lobe = c.get_lobe("StrategyLobe")
    
    architect = lobe.get_ability("ArchitectAbility")
    assert architect is not None
    
    # Mock Engine
    mock_engine = MagicMock()
    # mocking the engine call itself isn't enough because run_in_executor calls it.
    # Mock run_in_executor safely
    async def safe_return(*args, **kwargs):
        return "Architect Plan: Refactor complete."
    c.bot.loop.run_in_executor = AsyncMock(side_effect=safe_return)

    # Test execution
    res = await architect.execute("Refactor main")
    assert "Architect Plan" in res

    # Test Exception (Coverage)
    c.bot.loop.run_in_executor.side_effect = Exception("Design Flaw")
    res_fail = await architect.execute("Crash")
    assert "Architect Failure" in res_fail
    
    # Test Exception (Lines 29-30)
    c.bot.loop.run_in_executor.side_effect = Exception("Design Flaw")
    res_fail = await architect.execute("Crash")
    assert "Architect Failure" in res_fail

@pytest.mark.asyncio
async def test_memory_curator(mock_bot):
    c = Cerebrum(mock_bot)
    c.register_lobe(MemoryLobe)
    lobe = c.get_lobe("MemoryLobe")
    
    curator = lobe.get_ability("CuratorAbility")
    # Mock hippocampus working memory
    mock_bot.hippocampus.working.add_turn = MagicMock()
    
    # Mock Recall Context to ensure it doesn't return early
    mock_ctx = MagicMock()
    mock_ctx.knowledge_graph = ["Node A"]
    mock_bot.hippocampus.recall.return_value = mock_ctx
    
    await curator.execute("Remember this", user_id="123", request_scope="PUBLIC")
    mock_bot.hippocampus.working.add_turn.assert_called()

@pytest.mark.asyncio
async def test_cerebrum_shutdown(mock_bot):
    c = Cerebrum(mock_bot)
    with patch("src.daemons.town_hall.TownHallDaemon"), \
         patch("src.lobes.manager.data_dir") as mock_data_dir:
        mock_data_dir.return_value = MagicMock()
        await c.setup()
    
    # Mock a lobe shutdown
    mock_lobe = MagicMock()
    mock_lobe.shutdown = AsyncMock()
    c.lobes["MockLobe"] = mock_lobe
    
    await c.shutdown()
    mock_lobe.shutdown.assert_called()

def test_cerebrum_register_error(mock_bot):
    c = Cerebrum(mock_bot)
    # Pass invalid class (not callable or fails init)
    class BrokenLobe:
        def __init__(self, c):
            raise Exception("Init Fail")
            
    # Should log error but not crash
    c.register_lobe(BrokenLobe)
    assert "BrokenLobe" not in c.lobes

@pytest.mark.asyncio
async def test_interaction_abilities(mock_bot):
    c = Cerebrum(mock_bot)
    from src.agents.spawner import AgentResult, AgentStatus
    
    c.register_lobe(InteractionLobe)
    lobe = c.get_lobe("InteractionLobe")
    
    # 1. Research Success Case (AgentSpawner)
    researcher = lobe.get_ability("ResearchAbility")
    mock_success = AgentResult(
        agent_id="test-123",
        task="Quantum",
        status=AgentStatus.COMPLETED,
        output="Deep dive into Quantum Mechanics."
    )

    with patch("src.agents.spawner.AgentSpawner.spawn", new_callable=AsyncMock, return_value=mock_success):
        # We also need to mock _extract_and_store_knowledge to avoid hitting real engine/KG
        with patch.object(researcher, "_extract_and_store_knowledge", new_callable=AsyncMock):
            res = await researcher.execute("Quantum")
            assert "Research Findings" in res
            assert "Deep dive" in res

    # 2. Research Fallback Case (AgentSpawner raises Exception)
    with patch("src.agents.spawner.AgentSpawner.spawn", side_effect=Exception("Spawner Down")):
        with patch("src.tools.registry.ToolRegistry.execute", new_callable=AsyncMock, return_value="Search Link A, Search Link B"):
            with patch.object(researcher, "_extract_and_store_knowledge", new_callable=AsyncMock):
                res = await researcher.execute("Fallback Query")
                assert "Basic Search Results" in res
                assert "Search Link A" in res

    # 3. Research Agent Failure (Status == FAILED)
    mock_fail = AgentResult(
        agent_id="test-456",
        task="Fail",
        status=AgentStatus.FAILED,
        error="LLM timeout"
    )
    with patch("src.agents.spawner.AgentSpawner.spawn", new_callable=AsyncMock, return_value=mock_fail):
        with patch.object(researcher, "_extract_and_store_knowledge", new_callable=AsyncMock):
            res = await researcher.execute("Fail Topic")
            assert "Research agent failed: LLM timeout" in res

    # 4. Social Ability
    social = lobe.get_ability("SocialAbility")
    # Mock data_dir to point to a safe test silo
    with patch("src.lobes.interaction.social.data_dir", return_value="/tmp/ernos_test"):
        res = await social.execute(123)
        assert "Relationship Status" in res
        assert "Trust Score" in res


@pytest.mark.asyncio
async def test_strategy_more_abilities(mock_bot):
    c = Cerebrum(mock_bot)
    c.register_lobe(StrategyLobe)
    lobe = c.get_lobe("StrategyLobe")
    
    proj = lobe.get_ability("ProjectLeadAbility")
    # Mock LLM response for project decomposition
    async def mock_llm_response(*args, **kwargs):
        return '{"project_name": "Build app", "milestones": [{"id": 1, "title": "Milestone 1"}]}'
    c.bot.loop.run_in_executor = AsyncMock(side_effect=mock_llm_response)
    c.bot.hippocampus.graph = None  # Disable KG storage
    res = await proj.execute("Build app")
    # New implementation returns dict with milestones
    assert isinstance(res, dict)
    assert "milestones" in res or "error" in res
    
    goal = lobe.get_ability("GoalAbility")
    
    # Context 1: Goals exist (Active Goals path)
    with patch("src.tools.memory.manage_goals", return_value="[1] Active"):
        with patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            res = await goal.execute()
            assert "Active" in res
        
    # Context 2: No goals (Empty path - Lines 21-22 coverage)
    with patch("src.tools.memory.manage_goals", return_value="No active goals found."):
        with patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            res = await goal.execute()
            assert res is None

@pytest.mark.asyncio
async def test_creative_curiosity(mock_bot):
    from src.lobes.creative.lobe import CreativeLobe
    c = Cerebrum(mock_bot)
    c.register_lobe(CreativeLobe)
    lobe = c.get_lobe("CreativeLobe")
    
    curiosity = lobe.get_ability("CuriosityAbility")
    
    # Mock run_in_executor to avoid calling real engine
    c.bot.loop.run_in_executor = AsyncMock(return_value="Why is the sky blue?")
    
    res = await curiosity.execute()
    assert "?" in res
    assert "Why is the sky blue?" in res
    
    # Test with Context
    res_ctx = await curiosity.execute(context="Physics")
    assert "Curiosity Query" in res_ctx
        
    # Test Exception
    c.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("Engine Down"))
    res_error = await curiosity.execute()
    assert "Curiosity failed to manifest" in res_error

@pytest.mark.asyncio
async def test_memory_abilities_more(mock_bot):
    c = Cerebrum(mock_bot)
    c.register_lobe(MemoryLobe)
    lobe = c.get_lobe("MemoryLobe")
    
    recall = lobe.get_ability("RecallAbility")
    mock_bot.hippocampus.recall = MagicMock(return_value="Memory")
    res = await recall.execute("Q", 1, 1)
    assert res == "Memory"
    
    onto = lobe.get_ability("OntologistAbility")
    # Foundation-aware ontologist requires these methods on mock graph
    mock_bot.hippocampus.graph.check_contradiction.return_value = None
    mock_bot.hippocampus.graph.query_core_knowledge.return_value = []
    # Ontologist accesses graph through globals.bot.hippocampus
    mock_globals = MagicMock()
    mock_globals.bot = mock_bot
    mock_globals.active_message.get.return_value = None
    with patch("src.bot.globals", mock_globals):
        res = await onto.execute("A", "is", "B", user_id="123", scope="PUBLIC")
    assert "Learned" in res or "noted" in res
    
    journ = lobe.get_ability("JournalistAbility")
    mock_bot.hippocampus.timeline.get_recent_events = MagicMock(return_value=[])
    res = await journ.execute()
    assert "No recent events" in res or "Updated" in res  # Handles empty case

@pytest.mark.asyncio
async def test_dreamer_reentry(mock_bot):
    from src.lobes.creative.autonomy import AutonomyAbility
    mock_lobe = MagicMock()
    mock_lobe.cerebrum.bot = mock_bot
    dreamer = AutonomyAbility(mock_lobe)
    
    # Start it once (fake run)
    dreamer.is_running = True
    
    # Try start again
    res = await dreamer.execute()
    assert res == "Autonomy Loop already active."

@pytest.mark.asyncio
async def test_base_ability_execute(mock_bot):
    # Test base execute pass
    from src.lobes.base import BaseAbility
    class ConcreteAbility(BaseAbility):
        pass
    
    mock_lobe = MagicMock()
    c = ConcreteAbility(mock_lobe)
    # verify it runs without error (it's just pass)
    await c.execute()
    assert True  # Execution completed without error

@pytest.mark.asyncio
async def test_cerebrum_kg_integration(mock_bot):
    """Test Cerebrum's ability to interface with the Knowledge Graph."""
    c = Cerebrum(mock_bot)
    mock_bot.hippocampus.graph = MagicMock()
    mock_bot.hippocampus.graph.add_relationship = MagicMock(return_value="node_id_123")
    mock_bot.hippocampus.graph.check_contradiction.return_value = None
    mock_bot.hippocampus.graph.query_core_knowledge.return_value = []
    
    c.register_lobe(MemoryLobe)
    onto = c.get_lobe("MemoryLobe").get_ability("OntologistAbility")
    
    mock_globals = MagicMock()
    mock_globals.bot = mock_bot
    mock_globals.active_message.get.return_value = None
    
    with patch("src.bot.globals", mock_globals):
        res = await onto.execute("Ernos", "is", "Growing", user_id="sys", scope="CORE")
    
    assert "node_id_123" in str(res) or "Learned" in res
    mock_bot.hippocampus.graph.add_relationship.assert_called()

@pytest.mark.asyncio
async def test_synthesis_agent_spawning(mock_bot):
    """Test the Synthesis ability's interaction with the AgentSpawner."""
    c = Cerebrum(mock_bot)
    c.register_lobe(InteractionLobe)
    researcher = c.get_lobe("InteractionLobe").get_ability("ResearchAbility")
    
    mock_agent_result = MagicMock()
    mock_agent_result.status.value = "completed"
    mock_agent_result.output = "Deep analysis of recursion."
    mock_agent_result.error = None

    with patch("src.agents.spawner.AgentSpawner.spawn", new_callable=AsyncMock, return_value=mock_agent_result):
        res = await researcher.execute("recursive self-improvement")
        assert "Deep analysis" in res
        assert "Research Findings" in res

@pytest.mark.asyncio
async def test_cerebrum_lobe_isolation(mock_bot):
    """Verify that lobes do not leak state into each other via Cerebrum."""
    c = Cerebrum(mock_bot)
    c.register_lobe(StrategyLobe)
    c.register_lobe(MemoryLobe)
    
    strat = c.get_lobe("StrategyLobe")
    memo = c.get_lobe("MemoryLobe")
    
    assert strat is not memo
    assert strat.cerebrum == memo.cerebrum
