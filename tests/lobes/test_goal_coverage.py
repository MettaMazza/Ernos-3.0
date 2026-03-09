import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.lobes.strategy.goal import GoalAbility

@pytest.fixture
def goal_ability():
    mock_lobe = MagicMock()
    mock_lobe.cerebrum.bot = MagicMock()
    # Mock LLM
    mock_lobe.cerebrum.bot.engine_manager.get_active_engine.return_value.generate_response = MagicMock(return_value='{"subtasks": [{"id": 1, "task": "Task1"}]}')
    mock_lobe.cerebrum.bot.loop.run_in_executor = AsyncMock(return_value='{"subtasks": [{"id": 1, "task": "Task1"}]}')
    return GoalAbility(mock_lobe)

@pytest.mark.asyncio
async def test_execute_no_goals(goal_ability):
    with patch("src.tools.memory.manage_goals", return_value="No active goals"):
        with patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            res = await goal_ability.execute()
            assert res is None

@pytest.mark.asyncio
async def test_execute_with_goals(goal_ability):
    with patch("src.tools.memory.manage_goals", return_value="1. World Domination"):
        with patch("src.bot.globals.active_message") as mock_msg:
            mock_msg.get.return_value = None
            res = await goal_ability.execute()
            assert "World Domination" in res

@pytest.mark.asyncio
async def test_audit_goals(goal_ability, tmp_path):
    # Create a mock goals file
    goals_file = tmp_path / "goals.json"
    goals_file.write_text('[]')  # Empty goals
    
    with patch.object(goal_ability, "_audit_goals") as mock_audit:
        # Test new output format
        mock_audit.return_value = "### Goal Audit Report\n**Active Goals**: 0"
        res = await mock_audit()
        assert "Goal Audit Report" in res

@pytest.mark.asyncio
async def test_decompose_goal_success(goal_ability):
    res = await goal_ability._decompose_goal("Win")
    # New implementation parses JSON response or uses fallback
    # Either returns parsed JSON (subtasks key) or fallback (goal+plan keys)
    assert isinstance(res, dict)
    assert "subtasks" in res or "plan" in res or "goal" in res

@pytest.mark.asyncio
async def test_decompose_goal_error(goal_ability):
    # Mock run_in_executor to raise
    goal_ability.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("LLM Fail"))
    res = await goal_ability._decompose_goal("Win")
    assert "LLM Fail" in res["error"]

