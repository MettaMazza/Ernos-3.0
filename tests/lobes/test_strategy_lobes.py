import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from src.lobes.strategy.gardener import GardenerAbility
from src.lobes.strategy.performance import PerformanceAbility
from src.lobes.strategy.predictor import PredictorAbility

# --- Gardener ---

@pytest.mark.asyncio
async def test_gardener_analysis(mocker):
    # Mock os.walk
    mocker.patch("os.walk", return_value=[
        ("src", [], ["main.py", "ignored.txt"]),
        ("src/utils", [], ["helper.py"])
    ])
    
    # Mock open robustly
    mock_files = {
        "src/main.py": "\n" * 10,
        "src/utils/helper.py": "\n" * 300
    }
    
    def side_effect(path, *args, **kwargs):
        content = mock_files.get(path, "")
        return mock_open(read_data=content).return_value

    mocker.patch("builtins.open", side_effect=side_effect)
    
    lobe = MagicMock()
    gardener = GardenerAbility(lobe)
    
    res = await gardener.execute("check")
    
    assert "Codebase Scale" in res
    assert "2 files" in res
    assert "310 lines" in res
    assert "helper.py" in res

# --- Performance ---

@pytest.mark.asyncio
async def test_performance_check(mocker):
    mocker.patch("psutil.cpu_percent", return_value=10.0)
    mocker.patch("psutil.virtual_memory").return_value.percent = 50.0
    mocker.patch("time.time", side_effect=[1000, 2000]) # 1000s elapsed
    
    lobe = MagicMock()
    lobe.cerebrum.bot.start_time = 0
    
    perf = PerformanceAbility(lobe)
    res = await perf.execute()
    
    assert "CPU Load" in res
    assert "10.0%" in res
    assert "HEALTHY" in res

@pytest.mark.asyncio
async def test_performance_check_high_load(mocker):
    mocker.patch("psutil.cpu_percent", return_value=90.0)
    mocker.patch("psutil.virtual_memory").return_value.percent = 80.0
    
    lobe = MagicMock()
    # Simulate missing bot link handling
    lobe.cerebrum = None 
    
    perf = PerformanceAbility(lobe)
    res = await perf.execute()
    
    assert "LOAD_HIGH" in res
    assert "Uptime**: Unknown" in res # Markdown awareness

# --- Predictor ---

@pytest.mark.asyncio
async def test_predictor_simulation(mocker):
    lobe = MagicMock()
    # Mock engine via lobe.cerebrum.bot chain
    lobe.cerebrum.bot.loop.run_in_executor = AsyncMock(
        return_value='{"confidence": 0.95, "primary_risk": "Test Risk", "secondary_risk": "None", "recommendation": "Proceed", "reasoning": "Low risk scenario"}'
    )
    
    predictor = PredictorAbility(lobe)
    res = await predictor.execute("Action X")
    
    assert "Confidence" in res
    assert "95%" in res
    assert "Proceed" in res
    assert "Test Risk" in res

@pytest.mark.asyncio
async def test_predictor_simulation_error(mocker):
    lobe = MagicMock()
    lobe.cerebrum.bot.loop.run_in_executor = AsyncMock(
        side_effect=Exception("Engine down")
    )
    
    predictor = PredictorAbility(lobe)
    res = await predictor.execute("Action Y")
    
    assert "Simulation Failed" in res

@pytest.mark.asyncio
async def test_predictor_simulation_no_json(mocker):
    lobe = MagicMock()
    # Engine returns plain text, no JSON
    lobe.cerebrum.bot.loop.run_in_executor = AsyncMock(
        return_value="I think this would succeed with high confidence"
    )
    
    predictor = PredictorAbility(lobe)
    res = await predictor.execute("Action Z")
    
    # Should fall back to raw response
    assert "Simulation Results" in res
    assert "high confidence" in res

