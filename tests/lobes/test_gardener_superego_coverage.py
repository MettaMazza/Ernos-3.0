import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.lobes.strategy.gardener import GardenerAbility
from src.lobes.superego.identity import IdentityAbility

# --- Gardener Tests ---
@pytest.fixture
def gardener():
    lobe = MagicMock()
    with patch("src.lobes.strategy.gardener.KnowledgeGraph"):
        return GardenerAbility(lobe)

@pytest.mark.asyncio
async def test_gardener_refine_graph(gardener):
    # Mock graph driver to return empty nodes
    mock_session = MagicMock()
    mock_session.run.return_value = []  # No nodes
    gardener.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    gardener.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
    
    res = await gardener.refine_graph()
    # New implementation returns "Graph is empty" for no nodes
    assert "empty" in res.lower() or "Graph Refinement" in res

def test_gardener_merge_nodes_success(gardener):
    mock_session = MagicMock()
    gardener.graph.driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    gardener.graph.driver.session.return_value.__exit__ = MagicMock(return_value=False)
    
    gardener._merge_nodes("keep123", "merge456")
    assert mock_session.run.call_count == 2

def test_gardener_merge_nodes_exception(gardener):
    gardener.graph.driver.session.side_effect = Exception("Neo4j Down")
    
    with patch("src.lobes.strategy.gardener.logger") as mock_logger:
        gardener._merge_nodes("k", "m")
        mock_logger.error.assert_called()

@pytest.mark.asyncio
async def test_gardener_execute(gardener, tmp_path):
    # Create temp src directory
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "small.py").write_text("x=1\n" * 50)
    (src_dir / "large.py").write_text("x=1\n" * 250)
    
    with patch("os.walk") as mock_walk:
        mock_walk.return_value = [(str(src_dir), [], ["small.py", "large.py"])]
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__ = MagicMock(return_value=MagicMock(
                readlines=MagicMock(side_effect=[["x"]*50, ["x"]*250, ["x"]*50, ["x"]*250])
            ))
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            
            res = await gardener.execute("analyze")
            assert "Gardener Analysis" in res

# --- Identity (Superego) Tests ---
@pytest.fixture
def identity_guard():
    lobe = MagicMock()
    ability = IdentityAbility(lobe)
    return ability

@pytest.mark.asyncio
async def test_identity_pass(identity_guard):
    identity_guard.bot.loop.run_in_executor = AsyncMock(return_value="PASS")
    res = await identity_guard.execute("I am helpful")
    assert res is None

@pytest.mark.asyncio
async def test_identity_reject(identity_guard):
    identity_guard.bot.loop.run_in_executor = AsyncMock(return_value="REJECT: God complex detected")
    res = await identity_guard.execute("I am omnipotent")
    assert "REJECT" in res

@pytest.mark.asyncio
async def test_identity_exception(identity_guard):
    identity_guard.bot.loop.run_in_executor = AsyncMock(side_effect=Exception("LLM Down"))
    with patch("src.lobes.superego.identity.logger") as mock_logger:
        res = await identity_guard.execute("test")
        assert res is None
        mock_logger.error.assert_called()
