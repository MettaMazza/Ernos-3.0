import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.lobes.superego.identity import IdentityAbility

@pytest.mark.asyncio
async def test_identity_execute_pass():
    mock_lobe = MagicMock()
    # Mock the engine through the property chain: lobe.cerebrum.bot
    mock_lobe.cerebrum.bot.loop.run_in_executor = AsyncMock(return_value='PASS')
    
    identity = IdentityAbility(mock_lobe)
    res = await identity.execute("Hello")
    assert res is None

@pytest.mark.asyncio
async def test_identity_execute_reject():
    mock_lobe = MagicMock()
    reject_msg = 'REJECT: Too God-like -> Be humble'
    mock_lobe.cerebrum.bot.loop.run_in_executor = AsyncMock(return_value=reject_msg)
    
    identity = IdentityAbility(mock_lobe)
    res = await identity.execute("I am the creator.")
    assert res == reject_msg
