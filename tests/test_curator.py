import pytest
from unittest.mock import MagicMock, AsyncMock
from src.lobes.memory.curator import CuratorAbility
from src.memory.hippocampus import ContextObject
from src.bot import globals

@pytest.mark.asyncio
async def test_curator_filters_private_data_in_public_scope():
    """
    Test that CuratorAbility filters out PRIVATE graph nodes when accessed from PUBLIC scope.
    """
    # 1. Setup Mock Architecture
    # BaseAbility.hippocampus traverses -> self.lobe.cerebrum.bot.hippocampus
    mock_lobe = MagicMock()
    mock_hippo = MagicMock()
    mock_lobe.cerebrum.bot.hippocampus = mock_hippo
    
    mock_hippo.working = MagicMock()
    mock_hippo.working.add_turn = AsyncMock()
    
    # Mock Recall Return (Simulating a Leak)
    leak_context = ContextObject(
        working_memory="",
        related_memories=[],
        knowledge_graph=["(User_123) -[FAVORITE_COLOR]-> (Neon Green) [PRIVATE]"], 
        lessons=[],
        scope="PUBLIC"
    )
    mock_hippo.recall = MagicMock(return_value=leak_context)
    
    # 2. Initialize Ability
    curator = CuratorAbility(mock_lobe)
    
    # 3. Execute with PUBLIC Scope
    result_public = await curator.execute("find my color", request_scope="PUBLIC", user_id="123")
    
    # 4. Assertions for PUBLIC
    # Should NOT contain the private string
    assert "Neon Green" not in result_public, "Curator leaked Private data in Public scope!"
    assert "No relevant public memory" in result_public or result_public == ""
    
    # 5. Execute with PRIVATE Scope
    result_private = await curator.execute("find my color", request_scope="PRIVATE", user_id="123")
    
    # 6. Assertions for PRIVATE
    # Should contain the private string
    assert "Neon Green" in result_private, "Curator blocked Private data in Private scope!"
    print("\n✅ Curator Logic Verification Passed: Private data filtered from Public retrieval.")

if __name__ == "__main__":
    # Helper to run async test manually
    import asyncio
    asyncio.run(test_curator_filters_private_data_in_public_scope())
