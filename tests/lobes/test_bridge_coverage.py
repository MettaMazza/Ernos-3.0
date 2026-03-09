import pytest
from unittest.mock import MagicMock
from src.lobes.interaction.bridge import BridgeAbility

@pytest.fixture
def bridge_ability():
    mock_lobe = MagicMock()
    ability = BridgeAbility(mock_lobe)
    # Mock hippocampus to avoid real connections
    mock_lobe.cerebrum.bot.hippocampus = None
    return ability

@pytest.mark.asyncio
async def test_bridge_execute(bridge_ability):
    res = await bridge_ability.execute("Connect")
    assert "Bridge Access" in res
    # New implementation returns structured output
    assert "Connect" in res or "No public knowledge" in res

