import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from src.lobes.interaction.science import ScienceAbility
import numpy as np

@pytest.fixture
def science_ability():
    # Mock bot interactions
    mock_bot = MagicMock()
    mock_bot.loop.run_in_executor = AsyncMock()
    mock_bot.engine_manager.get_active_engine.return_value.generate_response = MagicMock(return_value="Exp Design")
    
    ability = ScienceAbility(MagicMock())
    # Manually inject bot
    ability.lobe.cerebrum.bot = mock_bot
    return ability

@pytest.mark.asyncio
async def test_science_execute_routing(science_ability):
    # Test valid modes
    with patch.object(science_ability, '_run_math_evaluate', return_value="Eval") as m:
        assert await science_ability.execute("eval: 1+1") == "Eval"
    
    with patch.object(science_ability, '_run_math_solve', return_value="Solve") as m:
        assert await science_ability.execute("solve: x") == "Solve"

    with patch.object(science_ability, '_run_stats', return_value="Stats") as m:
        assert await science_ability.execute("stats: [1]") == "Stats"
        
    with patch.object(science_ability, '_run_physics', return_value="Phys") as m:
        assert await science_ability.execute("physics: c") == "Phys"
        
    with patch.object(science_ability, '_run_chemistry', return_value="Chem") as m:
        assert await science_ability.execute("chemistry: H") == "Chem"
        
    with patch.object(science_ability, '_run_matrix', return_value="Mat") as m:
        assert await science_ability.execute("matrix: []") == "Mat"
        
    with patch.object(science_ability, '_design_experiment', return_value="Exp") as m:
        assert await science_ability.execute("experiment: Q") == "Exp"

    # Test unknown mode - now falls back to eval instead of error
    res = await science_ability.execute("magic: spell")
    # Falls back to eval, which fails on "magic: spell" syntax
    assert "Math syntax error" in res or "Error" in res

    # Test default (no prefix) -> eval
    with patch.object(science_ability, '_run_math_evaluate', return_value="Eval") as m:
        assert await science_ability.execute("1+1") == "Eval"

    # Test Exception in execute (must use computational input to pass fast path)
    with patch.object(science_ability, '_run_math_evaluate', side_effect=Exception("Boom")):
        res = await science_ability.execute("eval: crash")
        assert "Science Error: Boom" in res

@pytest.mark.asyncio
async def test_run_math_solve(science_ability):
    # 1. Equation with =
    res = await science_ability.execute("solve: x**2 = 4")
    assert "Solution:" in res
    assert "-2" in res and "2" in res
    
    # 2. Expression (assume = 0)
    res = await science_ability.execute("solve: x - 5")
    assert "Solution:" in res
    assert "5" in res
    
    # 3. Error
    res = await science_ability.execute("solve: x =") # invalid syntax
    assert "Solver error" in res

@pytest.mark.asyncio
async def test_run_stats(science_ability):
    # 1. Valid list string
    res = await science_ability.execute("stats: [1, 2, 3, 4, 5]")
    assert "mean: 3.0000" in res
    assert "median: 3.0000" in res
    
    # 2. Implicit list "1, 2, 3"
    res = await science_ability.execute("stats: 1, 2, 3")
    assert "mean: 2.0000" in res
    
    # 3. Not a list (Force AST to return dict to hit coverage)
    with patch("ast.literal_eval", return_value={'a': 1}):
         res = await science_ability.execute("stats: {'a': 1}")
         assert "Error: Stats input must be a list" in res
    
    # 4. Error (invalid syntax)
    res = await science_ability.execute("stats: [1, 2")
    assert "Stats error" in res

@pytest.mark.asyncio
async def test_run_physics(science_ability):
    # 1. Known constant
    res = await science_ability.execute("physics: c")
    assert "299792458" in res

    # 2. Unknown constant
    res = await science_ability.execute("physics: flux_capacitor")
    assert "not found" in res

@pytest.mark.asyncio
async def test_run_chemistry(science_ability):
    # 1. Known Element
    res = await science_ability.execute("chemistry: H")
    assert "Hydrogen" in res
    
    # 2. Lowercase input
    res = await science_ability.execute("chemistry: helium")
    assert "Helium" in res
    
    # 3. Unknown
    res = await science_ability.execute("chemistry: Unobtainium")
    assert "not found" in res

@pytest.mark.asyncio
async def test_run_matrix(science_ability):
    # 1. Det
    res = await science_ability.execute("matrix: [[1, 2], [3, 4]] | det")
    assert "Determinant" in res
    # det is -2
    
    # 2. Eig
    res = await science_ability.execute("matrix: [[1, 0], [0, 1]] | eig")
    assert "Eigenvalues" in res
    
    # 3. Inv
    res = await science_ability.execute("matrix: [[1, 2], [3, 4]] | inv")
    assert "Inverse" in res
    
    # 4. Info (default)
    res = await science_ability.execute("matrix: [[1, 2], [3, 4]]")
    assert "Shape: (2, 2)" in res
    
    # 5. Unknown Op
    res = await science_ability.execute("matrix: [[1]] | magic")
    assert "Unknown matrix op" in res

    # 6. Error
    res = await science_ability.execute("matrix: [[1, 2] | det") # Syntax
    assert "Matrix Error" in res

@pytest.mark.asyncio
async def test_design_experiment(science_ability):
    # 1. Success
    # 1. Success
    with patch("src.core.secure_loader.load_prompt", return_value="Template {question}"):
        # Mock run_in_executor to return immediate result
        # science_ability.bot.loop is a MagicMock, need its run_in_executor to return future or value
        # But execute awaits it.
        async def mock_run(*args):
            return "Experiment Plan"
        
        science_ability.bot.loop.run_in_executor = AsyncMock(side_effect=mock_run)
        
        res = await science_ability.execute("experiment: Gravity")
        assert "Experiment Plan" in res
        
    # 2. Error (loader failure)
    with patch("src.core.secure_loader.load_prompt", side_effect=FileNotFoundError):
        res = await science_ability.execute("experiment: Gravity")
        assert "Design Error" in res

@pytest.mark.asyncio
async def test_run_math_evaluate_real(science_ability):
    # This calls the REAL method, no mocking of _run_math_evaluate
    # 1. Simple math
    res = science_ability._run_math_evaluate("1 + 1")
    assert "2" in res
    
    # 2. SymPy function (sqrt)
    res = science_ability._run_math_evaluate("sqrt(4)")
    assert "2" in res
    
    # 3. Implicit multiplication
    res = science_ability._run_math_evaluate("2x") # x needs to be symbol?
    # SymPy parser handles implicit mult but x must be defined? 
    # The context limits to sympy functions. 
    # Standard transformations allows implicit, but if 'x' is not in context?
    # parse_expr might treat it as symbol automatically if not found?
    # Actually, local_dict limits it.
    # Let's test standard stuff.
    # 2(3) -> 6
    res = science_ability._run_math_evaluate("2(3)")
    assert "6" in res
    
    # 4. Error (TypeError by calling int) — falls back to compute sandbox
    res = science_ability._run_math_evaluate("1()")
    assert "Math syntax error" in res or "Compute" in res or "Error" in res
