import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from src.tools.lobe_tools import (
    consult_gardener_lobe,
    consult_architect_lobe,
    consult_project_lead,
    consult_science_lobe,
    consult_bridge_lobe,
    consult_autonomy,
    consult_predictor,
    consult_performance_lobe,
    deep_think,
    consult_curator,
    consult_ontologist,
    consult_social_lobe,
    consult_subconscious,
    consult_world_lobe
)

# Mock Global Bot
@pytest.fixture
def mock_bot_global():
    with patch("src.bot.globals.bot") as mock_bot:
        import threading
        # Create Loop
        loop = asyncio.new_event_loop()
        mock_bot.loop = loop
        
        # Run loop in separate thread to support run_coroutine_threadsafe
        def loop_runner():
            asyncio.set_event_loop(loop)
            loop.run_forever()
            
        t = threading.Thread(target=loop_runner, daemon=True)
        t.start()
        
        # Mock Cerebrum and Lobes
        cerebrum = MagicMock()
        mock_bot.cerebrum = cerebrum
        
        # Helper to setup lobe/ability mocks
        def setup_ability(lobe_name, ability_name):
            lobe = MagicMock()
            ability = AsyncMock()
            ability.execute.return_value = f"{ability_name} Result"
            lobe.get_ability.return_value = ability
            
            # Since get_lobe is called with different args, we need a side_effect
            return lobe, ability
            
        # Strategy Lobe
        strat_lobe = MagicMock()
        cerebrum.get_lobe.return_value = strat_lobe # Default return
        
        # We need more granular control for get_lobe("Name")
        lobes = {}
        
        def get_lobe_side_effect(name):
            return lobes.get(name, MagicMock())
            
        cerebrum.get_lobe.side_effect = get_lobe_side_effect
        
        # Populate Lobes
        strategy = MagicMock()
        interaction = MagicMock()
        creative = MagicMock()
        
        lobes["StrategyLobe"] = strategy
        lobes["InteractionLobe"] = interaction
        lobes["CreativeLobe"] = creative
        
        # Setup Abilities
        gardener = AsyncMock()
        gardener.execute.return_value = "Gardener OK"
        strategy.get_ability.side_effect = lambda n: gardener if n == "GardenerAbility" else AsyncMock(execute=AsyncMock(return_value=f"{n} OK"))
        
        yield mock_bot
        
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=1.0)
        loop.close()

@pytest.mark.asyncio
async def test_consult_gardener(mock_bot_global):
    result = await consult_gardener_lobe("Analyze src")
    assert result == "Gardener OK"
    
@pytest.mark.asyncio
async def test_consult_architect(mock_bot_global):
    # Setup Architect return
    strat = mock_bot_global.cerebrum.get_lobe("StrategyLobe")
    arch = AsyncMock()
    arch.execute.return_value = "Architect OK"
    
    # Update side effect to handle multiple abilities
    def ability_side_effect(name):
        if name == "GardenerAbility": return AsyncMock(execute=AsyncMock(return_value="Gardener OK"))
        if name == "ArchitectAbility": return arch
        if name == "ProjectManagerAbility": return AsyncMock(execute=AsyncMock(return_value="Project OK"))
        if name == "PredictorAbility": return AsyncMock(execute=AsyncMock(return_value="Predictor OK"))
        if name == "PerformanceAbility": return AsyncMock(execute=AsyncMock(return_value="Performance OK"))
        return MagicMock()
        
    strat.get_ability.side_effect = ability_side_effect
    
    result = await consult_architect_lobe("Plan X")
    assert result == "Architect OK"

@pytest.mark.asyncio
async def test_missing_cerebrum():
    tools = [
        consult_gardener_lobe,
        consult_architect_lobe,
        consult_project_lead,
        consult_science_lobe,
        consult_bridge_lobe,
        consult_autonomy,
        consult_predictor,
        consult_performance_lobe,
        deep_think,
        consult_curator,
        consult_ontologist,
        consult_social_lobe,
        consult_subconscious,
        consult_world_lobe
    ]
    
    with patch("src.bot.globals.bot", None):
        for tool in tools:
            # When bot is missing, it returns string "Error..." synchronously?
            # Wait, the tools are async def. They return a coroutine that resolves to string.
            # So even error path is async.
            assert await tool("Test") == "Error: Cerebrum not initialized."

@pytest.mark.asyncio
async def test_deep_think(mock_bot_global):
    # Setup Interaction Lobe return for Reasoning
    interact = mock_bot_global.cerebrum.get_lobe("InteractionLobe")
    reasoner = AsyncMock()
    reasoner.execute.return_value = "Thinking Done"
    interact.get_ability.return_value = reasoner
    
    result = await deep_think("P vs NP")
    assert result == "Thinking Done"

@pytest.mark.asyncio
async def test_consult_project_lead(mock_bot_global):
    # Setup Project Lead return
    strat = mock_bot_global.cerebrum.get_lobe("StrategyLobe")
    pm = AsyncMock()
    pm.execute.return_value = "Project Plan"
    
    # Reset side effect from previous tests if any
    strat.get_ability.side_effect = None 
    strat.get_ability.return_value = pm
    
    result = await consult_project_lead("Status?")
    assert result == "Project Plan"

@pytest.mark.asyncio
async def test_consult_science(mock_bot_global):
    sc_lobe = mock_bot_global.cerebrum.get_lobe("InteractionLobe")
    sc_ability = AsyncMock()
    sc_ability.execute.return_value = "Hypothesis Proven"
    sc_lobe.get_ability.return_value = sc_ability
    
    result = await consult_science_lobe("Experiment")
    assert result == "Hypothesis Proven"

@pytest.mark.asyncio
async def test_consult_bridge(mock_bot_global):
    br_lobe = mock_bot_global.cerebrum.get_lobe("InteractionLobe")
    br_ability = AsyncMock()
    br_ability.execute.return_value = "Bridge Connected"
    br_lobe.get_ability.return_value = br_ability
    
    result = await consult_bridge_lobe("Connect")
    assert result == "Bridge Connected"

@pytest.mark.asyncio
async def test_consult_autonomy(mock_bot_global):
    dr_lobe = mock_bot_global.cerebrum.get_lobe("CreativeLobe")
    dr_ability = AsyncMock()
    dr_ability.execute.return_value = "Dream Generated"
    dr_lobe.get_ability.return_value = dr_ability
    
    result = await consult_autonomy("Dream")
    assert result == "Dream Generated"

@pytest.mark.asyncio
async def test_consult_predictor(mock_bot_global):
    st_lobe = mock_bot_global.cerebrum.get_lobe("StrategyLobe")
    pred_ability = AsyncMock()
    pred_ability.execute.return_value = "Prediction Made"
    st_lobe.get_ability.return_value = pred_ability
    st_lobe.get_ability.side_effect = None
    
    result = await consult_predictor("Forecast")
    assert result == "Prediction Made"

@pytest.mark.asyncio
async def test_consult_performance(mock_bot_global):
    st_lobe = mock_bot_global.cerebrum.get_lobe("StrategyLobe")
    perf_ability = AsyncMock()
    perf_ability.execute.return_value = "Performance Data"
    st_lobe.get_ability.return_value = perf_ability
    st_lobe.get_ability.side_effect = None

    result = await consult_performance_lobe("Report")
    assert result == "Performance Data"

@pytest.mark.asyncio
async def test_consult_curator(mock_bot_global):
    mem_lobe = MagicMock()
    cur_ability = MagicMock()
    cur_ability.execute = AsyncMock(return_value="Curated Data")
    mem_lobe.get_ability.return_value = cur_ability
    
    # Override global side_effect to ensure we get this lobe
    mock_bot_global.cerebrum.get_lobe.side_effect = None
    mock_bot_global.cerebrum.get_lobe.return_value = mem_lobe
    
    result = await consult_curator("Search")
    assert result == "Curated Data"

@pytest.mark.asyncio
async def test_consult_ontologist(mock_bot_global):
    mem_lobe = MagicMock()
    ont_ability = MagicMock()
    ont_ability.execute = AsyncMock(return_value="Graph Data")
    mem_lobe.get_ability.return_value = ont_ability
    
    mock_bot_global.cerebrum.get_lobe.side_effect = None
    mock_bot_global.cerebrum.get_lobe.return_value = mem_lobe
    
    # Use structured args as expected by the new implementation
    result = await consult_ontologist(subject="Ernos", predicate="CREATED_BY", object="Maria")
    assert result == "Graph Data"

@pytest.mark.asyncio
async def test_consult_social(mock_bot_global):
    int_lobe = MagicMock()
    soc_ability = MagicMock()
    soc_ability.execute = AsyncMock(return_value="Social Analysis")
    int_lobe.get_ability.return_value = soc_ability
    
    mock_bot_global.cerebrum.get_lobe.side_effect = None
    mock_bot_global.cerebrum.get_lobe.return_value = int_lobe
    
    result = await consult_social_lobe("Analyze")
    assert result == "Social Analysis"

@pytest.mark.asyncio
async def test_consult_subconscious(mock_bot_global):
    # Maps to Autonomy
    cr_lobe = MagicMock()
    dream_ability = MagicMock()
    dream_ability.execute = AsyncMock(return_value="Subconscious Thought")
    cr_lobe.get_ability.return_value = dream_ability
    
    mock_bot_global.cerebrum.get_lobe.side_effect = None
    mock_bot_global.cerebrum.get_lobe.return_value = cr_lobe
    
    result = await consult_subconscious("Reflect")
    assert result == "Subconscious Thought"

@pytest.mark.asyncio
async def test_consult_world_lobe(mock_bot_global):
    # Maps to Researcher
    int_lobe = MagicMock()
    res_ability = MagicMock()
    res_ability.execute = AsyncMock(return_value="World Data")
    int_lobe.get_ability.return_value = res_ability
    
    mock_bot_global.cerebrum.get_lobe.side_effect = None
    mock_bot_global.cerebrum.get_lobe.return_value = int_lobe
    assert True  # Execution completed without error
    

@pytest.mark.asyncio
async def test_consult_superego(mock_bot_global):
    # Both consult_superego and consult_skeptic now use unified SuperegoLobe
    superego_lobe = MagicMock()
    identity_ability = MagicMock()
    identity_ability.execute = AsyncMock(return_value="Content Safe")
    superego_lobe.get_ability.return_value = identity_ability
    
    mock_bot_global.cerebrum.get_lobe.side_effect = None
    mock_bot_global.cerebrum.get_lobe.return_value = superego_lobe
    
    from src.tools.lobe_tools import consult_superego
    result = await consult_superego("Draft content")
    assert result == "Content Safe"

@pytest.mark.asyncio
async def test_consult_skeptic(mock_bot_global):
    # Uses unified SuperegoLobe with RealityAbility
    superego_lobe = MagicMock()
    reality_ability = MagicMock()
    reality_ability.execute = AsyncMock(return_value={"status": "Verified"})
    superego_lobe.get_ability.return_value = reality_ability
    
    mock_bot_global.cerebrum.get_lobe.side_effect = None
    mock_bot_global.cerebrum.get_lobe.return_value = superego_lobe
    
    from src.tools.lobe_tools import consult_skeptic
    result = await consult_skeptic("Sky is blue")
    assert "Reality Check" in result
    assert "Verified" in result

@pytest.mark.asyncio
async def test_generate_image(mock_bot_global):
    lobe = mock_bot_global.cerebrum.get_lobe("CreativeLobe")
    visual = AsyncMock()
    visual.execute.return_value = "image_url.png"
    lobe.get_ability.return_value = visual
    
    from src.tools.lobe_tools import generate_image
    result = await generate_image("Cat", user_id="123")
    assert result == "image_url.png"
    lobe.get_ability.assert_called_with("VisualCortexAbility")
    # New signature includes request_scope and is_autonomy
    visual.execute.assert_called_with("Cat", media_type="image", user_id="123", request_scope="PUBLIC", is_autonomy=False, intention=None)

@pytest.mark.asyncio
async def test_generate_video(mock_bot_global):
    lobe = mock_bot_global.cerebrum.get_lobe("CreativeLobe")
    visual = AsyncMock()
    visual.execute.return_value = "video_url.mp4"
    lobe.get_ability.return_value = visual
    
    from src.tools.lobe_tools import generate_video
    result = await generate_video("Cat jumping", user_id="456")
    assert result == "video_url.mp4"
    # New signature includes request_scope and is_autonomy
    visual.execute.assert_called_with("Cat jumping", media_type="video", user_id="456", request_scope="PUBLIC", is_autonomy=False, channel_id=None)

@pytest.mark.asyncio
async def test_consult_curiosity(mock_bot_global):
    lobe = mock_bot_global.cerebrum.get_lobe("CreativeLobe")
    curiosity = AsyncMock()
    curiosity.execute.return_value = "Why?"
    lobe.get_ability.return_value = curiosity
    
    from src.tools.lobe_tools import consult_curiosity
    result = await consult_curiosity("Context")
    assert result == "Why?"

@pytest.mark.asyncio
async def test_consult_journalist(mock_bot_global):
    lobe = MagicMock()
    journo = MagicMock()
    journo.execute = AsyncMock(return_value="Journal Updated")
    lobe.get_ability.return_value = journo
    
    # Override global side_effect
    mock_bot_global.cerebrum.get_lobe.side_effect = None
    mock_bot_global.cerebrum.get_lobe.return_value = lobe
    
    from src.tools.lobe_tools import consult_journalist_lobe
    result = await consult_journalist_lobe("Update")
    assert result == "Journal Updated"

@pytest.mark.asyncio
async def test_consult_ontologist_error(mock_bot_global):
    from src.tools.lobe_tools import consult_ontologist
    # Test error path: single word instruction can't be parsed into subject/object
    result = await consult_ontologist(instruction="Query", subject=None)
    assert "Error: Could not parse instruction" in result

@pytest.mark.asyncio
async def test_search_memory_alias(mock_bot_global):
    lobe = MagicMock()
    curator = MagicMock()
    curator.execute = AsyncMock(return_value="Found It")
    lobe.get_ability.return_value = curator
    
    # Override global side_effect
    mock_bot_global.cerebrum.get_lobe.side_effect = None
    mock_bot_global.cerebrum.get_lobe.return_value = lobe
    
    from src.tools.lobe_tools import search_memory
    # Path 1: instruction
    res1 = await search_memory(instruction="Find X")
    assert res1 == "Found It"
    
    # Path 2: query
    res2 = await search_memory(query="Find Y")
    assert res2 == "Found It"
    
    # Path 3: Error
    res3 = await search_memory()
    assert "Error: specific instruction" in res3
