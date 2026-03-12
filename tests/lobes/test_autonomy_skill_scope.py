import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_autonomy_run_task_delegates_to_cognition():
    """
    Verify that AutonomyAbility.run_task correctly delegates to the cognition 
    pipeline, passing down the user_id for proper skill scoping.
    """
    from src.lobes.creative.autonomy import AutonomyAbility

    # Mock dependencies
    mock_bot = MagicMock()
    
    # Mock Cognition Engine
    mock_bot.cognition.process = AsyncMock(return_value="Task executed.")

    # Mock Lobe/Ability structure
    mock_lobe = MagicMock()
    mock_lobe.cerebrum.bot = mock_bot
    
    # Instantiate
    autonomy = AutonomyAbility(mock_lobe)
    
    # Execute run_task
    user_id = "user_123"
    instruction = "Run global nexus."
    
    result = await autonomy.run_task(instruction, user_id=user_id)

    # Assert Delegation
    mock_bot.cognition.process.assert_called_once()
    call_kwargs = mock_bot.cognition.process.call_args.kwargs
    
    assert call_kwargs['user_id'] == user_id
    assert call_kwargs['complexity'] == "COMPLEX"
    assert "SCHEDULED AUTONOMOUS TASK" in call_kwargs['input_text']
    assert instruction in call_kwargs['input_text']
    assert result == "Task executed."
