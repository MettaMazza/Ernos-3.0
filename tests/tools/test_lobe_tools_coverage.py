import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.cerebrum = MagicMock()
    return bot

@pytest.fixture
def mock_globals(mock_bot):
    with patch("src.bot.globals.bot", mock_bot) as m:
        yield m

class TestLobeToolsCoverage:

    @pytest.mark.asyncio
    async def test_get_bot(self):
        from src.tools.lobe_tools import _get_bot
        with patch("src.bot.globals.bot", "dummy"):
            assert _get_bot() == "dummy"

    @pytest.mark.asyncio
    async def test_safe_get_ability_errors(self, mock_globals):
        from src.tools.lobe_tools import _safe_get_ability
        
        # Test lobe not found
        mock_globals.cerebrum.get_lobe.return_value = None
        ability, err = _safe_get_ability(mock_globals, "FakeLobe", "FakeAbility")
        assert ability is None
        assert "not loaded" in err

        # Test ability not found
        mock_lobe = MagicMock()
        mock_lobe.get_ability.return_value = None
        mock_globals.cerebrum.get_lobe.return_value = mock_lobe
        ability, err = _safe_get_ability(mock_globals, "RealLobe", "FakeAbility")
        assert ability is None
        assert "not found in RealLobe" in err

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_func, lobe_name, ability_name, kwargs, expected_substr, ability_return", [
        ("consult_gardener_lobe", "StrategyLobe", "GardenerAbility", {"query": "test"}, "analyzed", "analyzed"),
        ("consult_architect_lobe", "StrategyLobe", "ArchitectAbility", {"query": "test"}, "arch", "arch"),
        ("consult_project_lead", "StrategyLobe", "ProjectLeadAbility", {"query": "test"}, "proj", "proj"),
        ("consult_bridge_lobe", "InteractionLobe", "BridgeAbility", {"query": "test"}, "bridge", "bridge"),
        ("consult_predictor", "StrategyLobe", "PredictorAbility", {"query": "test"}, "pred", "pred"),
        ("consult_coder_lobe", "StrategyLobe", "CoderAbility", {"spec": "test"}, "code", "code"),
        ("consult_performance_lobe", "StrategyLobe", "PerformanceAbility", {"query": "test"}, "perf", "perf"),
        ("deep_think", "InteractionLobe", "DeepReasoningAbility", {"query": "test"}, "deep", "deep"),
        ("consult_journalist_lobe", "MemoryLobe", "JournalistAbility", {"query": "test"}, "journ", "journ"),
        ("consult_social_lobe", "InteractionLobe", "SocialAbility", {"query": "test"}, "social", "social"),
        ("consult_world_lobe", "InteractionLobe", "ResearchAbility", {"query": "test"}, "world", "world"),
        ("consult_subconscious", "CreativeLobe", "AutonomyAbility", {"query": "test"}, "sub", "sub"),
        ("review_reasoning", "InteractionLobe", "DeepReasoningAbility", {"chain": "test"}, "rev", "rev"),
        ("manage_projects", "StrategyLobe", "ProjectLeadAbility", {"action": "list"}, "mng", "mng"),
        ("consult_librarian", "MemoryLobe", "LibrarianAbility", {"instruction": "read", "path": "/test"}, "lib", "lib"),
        ("consult_curator", "MemoryLobe", "CuratorAbility", {"instruction": "read"}, "cur", "cur"),
    ])
    async def test_standard_consult_methods(self, mock_globals, tool_func, lobe_name, ability_name, kwargs, expected_substr, ability_return):
        import src.tools.lobe_tools as lt
        func = getattr(lt, tool_func)
        
        # Test bot not initialized
        with patch("src.bot.globals.bot", None):
            res = await func(**kwargs)
            assert "Error:" in res
            
        # Test happy path
        mock_lobe = MagicMock()
        mock_ability = AsyncMock()
        mock_ability.execute.return_value = ability_return
        mock_lobe.get_ability.return_value = mock_ability
        mock_globals.cerebrum.get_lobe.return_value = mock_lobe
        
        res = await func(**kwargs)
        assert expected_substr in res
        
        # Test empty fallbacks
        if len(kwargs) == 1 and not isinstance(list(kwargs.values())[0], int):
            # Pass empty instruction to trigger default instruction logic
            empty_kwargs = {k: "" for k in kwargs}
            if tool_func == "consult_world_lobe":
                res = await func(**empty_kwargs)
                assert "Error: No instruction provided" in res
            elif tool_func == "consult_science_lobe":
                res = await func(**empty_kwargs)
                assert "Error: No instruction provided" in res
            else:
                await func(**empty_kwargs)

    @pytest.mark.asyncio
    async def test_maintain_knowledge_graph(self, mock_globals):
        from src.tools.lobe_tools import maintain_knowledge_graph
        mock_lobe = MagicMock()
        mock_ability = AsyncMock()
        mock_ability.refine_graph.return_value = "refined"
        mock_ability.connect_graph.return_value = "connected"
        mock_obe_get = MagicMock()
        mock_obe_get.get_ability.return_value = mock_ability
        mock_globals.cerebrum.get_lobe.return_value = mock_lobe
        mock_lobe.get_ability.return_value = mock_ability
        
        res_refine = await maintain_knowledge_graph(mode="refine")
        assert "refined" in res_refine
        
        res_full = await maintain_knowledge_graph(mode="full")
        assert "refined" in res_full and "connected" in res_full
        
        res_default = await maintain_knowledge_graph()
        assert "connected" in res_default

    def test_execute_technical_plan(self):
        from src.tools.lobe_tools import execute_technical_plan
        res1 = execute_technical_plan("goal1")
        assert "Error: Security context missing" in res1
        
        res2 = execute_technical_plan("goal2", user_id="123")
        assert "deprecated" in res2

    @pytest.mark.asyncio
    async def test_propose_prompt_update(self, mock_globals):
        from src.tools.lobe_tools import propose_prompt_update
        mock_lobe = MagicMock()
        mock_ability = MagicMock()
        mock_ability.propose_modification.return_value = {"id": "1", "status": "pending"}
        mock_lobe.get_ability.return_value = mock_ability
        mock_globals.cerebrum.get_lobe.return_value = mock_lobe
        
        # Test missing file
        assert "Missing required argument" in await propose_prompt_update("", "sec", "cur", "prop", "rat")
        # Test delete missing current
        assert "delete' operation requires" in await propose_prompt_update("f", "s", "", "", "r", operation="delete")
        # Test replace missing proposed
        assert "requires proposed_text" in await propose_prompt_update("f", "s", "c", "", "r", operation="replace")
        
        # Success path with admin notification success
        mock_channel = AsyncMock()
        mock_globals.get_channel.return_value = mock_channel
        res = await propose_prompt_update("f", "s", "c", "p", "r", operation="replace")
        assert "✅ Proposal Submitted" in res
        mock_channel.send.assert_called_once()
        
        # Success path with admin notification logic failing / none channel
        mock_globals.get_channel.return_value = None
        await propose_prompt_update("f", "s", "c", "p", "r", operation="replace")

        # Success path with exception during notification
        mock_globals.get_channel.side_effect = Exception("err")
        await propose_prompt_update("f", "s", "c", "p", "r", operation="replace")

    @pytest.mark.asyncio
    async def test_check_prompt_status(self, mock_globals):
        from src.tools.lobe_tools import check_prompt_status
        mock_lobe = MagicMock()
        mock_ability = MagicMock()
        mock_lobe.get_ability.return_value = mock_ability
        mock_globals.cerebrum.get_lobe.return_value = mock_lobe
        
        # Empty
        mock_ability.get_recent_proposals.return_value = []
        assert "No recent proposals found" in await check_prompt_status()
        
        # Populated
        mock_ability.get_recent_proposals.return_value = [
            {"status": "pending", "id": "1", "prompt_file": "f", "section": "s", "proposed_text": "x" * 150}
        ]
        res = await check_prompt_status()
        assert "Recent Prompt Proposals" in res
        assert "x" * 100 in res

    @pytest.mark.asyncio
    async def test_produce_audiobook(self, mock_globals):
        from src.tools.lobe_tools import produce_audiobook
        mock_lobe = MagicMock()
        mock_ability = AsyncMock()
        mock_ability.execute.return_value = "audiobook_done"
        mock_lobe.get_ability.return_value = mock_ability
        mock_globals.cerebrum.get_lobe.return_value = mock_lobe
        assert await produce_audiobook("script") == "audiobook_done"

    @pytest.mark.asyncio
    @patch("os.path.exists", return_value=True)
    async def test_mix_audio_exceptions(self, mock_exists, mock_globals):
        from src.tools.lobe_tools import mix_audio
        # test invalid paths
        assert "Error: Base audio" in await mix_audio("", "o.wav")
        
        with patch("os.path.exists", return_value=False):
            assert "Error: Base audio file not found" in await mix_audio("b.wav", "o.wav")

    @pytest.mark.asyncio
    @patch("os.path.exists", return_value=True)
    async def test_mix_audio_success(self, mock_exists, mock_globals):
        from src.tools.lobe_tools import mix_audio
        import numpy as np
        
        with patch("soundfile.read") as mock_read, \
             patch("soundfile.write") as mock_write, \
             patch("src.lobes.creative.audiobook_producer.normalize_audio", return_value=np.array([0.1, 0.2])) as mock_norm, \
             patch("src.lobes.creative.audiobook_producer.overlay_audio", return_value=np.array([0.1, 0.2])) as mock_overlay, \
             patch("src.lobes.creative.audio_utils.wav_to_mp3", return_value="out.mp3"):
            
            # Base data mono, overlay data stereo
            mock_read.side_effect = [
                (np.array([0.1, 0.2]), 44100),       # base
                (np.array([[0.1, 0.1], [0.2, 0.2]]), 22050) # overlay to trigger resample
            ]
            
            res = await mix_audio("base.wav", "overlay.wav", base_volume_db=-5, overlay_volume_db=-10)
            assert "✅ Audio mixed successfully" in res

    @pytest.mark.asyncio
    @patch("os.path.exists", return_value=True)
    async def test_adjust_volume_success(self, mock_exists, mock_globals):
        from src.tools.lobe_tools import adjust_volume
        import numpy as np
        
        with patch("soundfile.read", return_value=(np.array([[0.1, 0.1], [0.2, 0.2]]), 44100)), \
             patch("soundfile.write") as mock_write, \
             patch("src.lobes.creative.audiobook_producer.normalize_audio", return_value=np.array([0.1, 0.2])), \
             patch("src.lobes.creative.audio_utils.wav_to_mp3", return_value="vol.mp3"):
            
            res = await adjust_volume("file.wav", volume_db=-5)
            assert "✅ Volume adjusted" in res

    @pytest.mark.asyncio
    async def test_consult_ima(self, mock_globals):
        from src.tools.lobe_tools import consult_ima
        mock_lobe = MagicMock()
        mock_ability = AsyncMock()
        mock_ability._one_shot_dream.return_value = "ima_done"
        mock_lobe.get_ability.return_value = mock_ability
        mock_globals.cerebrum.get_lobe.return_value = mock_lobe
        assert await consult_ima("q") == "ima_done"

    @pytest.mark.asyncio
    async def test_consult_ontologist_extended(self, mock_globals):
        from src.tools.lobe_tools import consult_ontologist
        mock_lobe = MagicMock()
        mock_ability = AsyncMock()
        mock_ability.execute.return_value = "onto_done"
        mock_lobe.get_ability.return_value = mock_ability
        mock_globals.cerebrum.get_lobe.return_value = mock_lobe
        
        # Test arrow parsing
        res = await consult_ontologist(instruction="A -> B C")
        assert res == "onto_done"
        
        # Test arrow parsing with predicate
        res2 = await consult_ontologist(instruction="A -LOVES-> B")
        assert res2 == "onto_done"
        
        # Test unparseable
        assert "Error: Could not parse" in await consult_ontologist(instruction="A")

    @pytest.mark.asyncio
    async def test_introspect(self, mock_globals):
        from src.tools.lobe_tools import introspect
        
        # Base failure
        assert "Error: No claim" in await introspect("")
        
        with patch("src.memory.epistemic.introspect_claim", new_callable=AsyncMock) as mock_ic:
            mock_ic.return_value = "introspected"
            assert await introspect("claim") == "introspected"

    def test_autobiography_tools(self, mock_globals):
        from src.tools.lobe_tools import read_autobiography, search_autobiography, list_autobiography_archives, read_autobiography_archive
        
        with patch("src.memory.autobiography.get_autobiography_manager") as mock_mgr:
            m_instance = MagicMock()
            mock_mgr.return_value = m_instance
            
            m_instance.read.return_value = ""
            assert "autobiography is empty" in read_autobiography()
            
            # Successful read
            m_instance.read.return_value = "\n## Chapter 1"
            m_instance.get_entry_count.return_value = 1
            assert "1 entries" in read_autobiography()
            
            # Error in read
            m_instance.read.side_effect = Exception("read_err")
            assert "read error" in read_autobiography()
            
            # Search empty
            assert "Provide a query" in search_autobiography()
            
            # Search success
            m_instance.search.return_value = "search_res"
            assert "search_res" in search_autobiography("term")
            
            # Search exception
            m_instance.search.side_effect = Exception("search_err")
            assert "search error" in search_autobiography("term")
            
            # List archives
            m_instance.list_archives.return_value = "archive1"
            assert "archive1" in list_autobiography_archives()
            
            # List archives err
            m_instance.list_archives.side_effect = Exception("list_err")
            assert "listing error" in list_autobiography_archives()
            
            # Read archive empty
            assert "Provide a filename" in read_autobiography_archive()
            
            # Read archive success
            m_instance.read_archive.return_value = "arc_text"
            assert "arc_text" in read_autobiography_archive("arc1")
            
            # Read archive err
            m_instance.read_archive.side_effect = Exception("read_arc_err")
            assert "Archive read error" in read_autobiography_archive("arc1")

    @pytest.mark.asyncio
    async def test_generation_tools(self, mock_globals):
        from src.tools.lobe_tools import generate_ascii_diagram, generate_image, generate_video, generate_music, generate_speech
        
        mock_lobe = MagicMock()
        mock_ability = AsyncMock()
        mock_ability.generate_system_map.return_value = "sys"
        mock_ability.generate_art.return_value = "art"
        mock_ability.generate_diagram.return_value = "diag"
        mock_ability.execute.return_value = "exec"
        mock_lobe.get_ability.return_value = mock_ability
        mock_globals.cerebrum.get_lobe.return_value = mock_lobe

        assert await generate_ascii_diagram("subject", mode="system_map") == "sys"
        assert await generate_ascii_diagram("subject", mode="art") == "art"
        assert await generate_ascii_diagram("subject", mode="diagram") == "diag"
        
        assert await generate_image("prompt") == "exec"
        assert await generate_video("prompt") == "exec"
        assert await generate_music("prompt") == "exec"
        assert await generate_speech("prompt") == "exec"
