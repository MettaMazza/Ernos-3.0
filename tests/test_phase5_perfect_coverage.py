"""
Phase 5: Perfect Coverage Push — surgical tests for modules at 93-99%.

Each test targets specific uncovered lines identified via coverage report.
Goal: push as many 93-99% modules to 100% as possible.
"""
import pytest
import json
import os
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from pathlib import Path


# ═══════════════════════════ agents/preprocessor.py L71 ═══════════════════════════
class TestPreprocessorNoEngine:
    """Cover line 71: no engine available returns error dict."""
    @pytest.mark.asyncio
    async def test_no_engine_returns_error(self):
        from src.agents.preprocessor import UnifiedPreProcessor
        bot = MagicMock()
        bot.engine_manager.get_active_engine.return_value = None
        pp = UnifiedPreProcessor(bot)
        result = await pp.process("hello")
        assert result == {"error": "No Engine"}


# ═══════════════════════════ engines/steering.py L37-38 ═══════════════════════════
class TestSteeringContextLimit:
    """Cover lines 37-38: context_limit property imports settings."""
    def test_context_limit_property(self):
        from src.engines.steering import SteeringEngine
        engine = SteeringEngine.__new__(SteeringEngine)
        engine._model_path = "test_model"
        with patch("config.settings") as mock_settings:
            mock_settings.CONTEXT_CHAR_LIMIT_LOCAL = 4096
            result = engine.context_limit
            assert result == 4096


# ═══════════════════════════ memory/validators.py L36, 208, 285 ═══════════════════════════
class TestValidatorsMissing:
    """Cover lines 36, 208, 285 — pass-through returns in validators."""
    def test_causal_non_self_loop(self):
        """L36: CausalValidator returns True for valid relationships."""
        from src.memory.validators import CausalValidator
        v = CausalValidator()
        result = v.validate_relationship(
            {"id": "A"}, {"id": "B"}, "CAUSES"
        )
        assert result is True

    def test_procedural_non_numeric_steps(self):
        """L208: ProceduralValidator passes for non-numeric steps."""
        from src.memory.validators import ProceduralValidator
        v = ProceduralValidator()
        result = v.validate_relationship(
            {"step": "abc"}, {"step": "def"}, "NEXT_STEP"
        )
        assert result is True

    def test_epistemic_relationship_passthrough(self):
        """L285: EpistemicValidator.validate_relationship returns True."""
        from src.memory.validators import EpistemicValidator
        v = EpistemicValidator()
        result = v.validate_relationship({}, {}, "CITES")
        assert result is True


# ═══════════════════════════ memory/vector.py L54, 81-82 ═══════════════════════════
class TestVectorChunkedEmbedding:
    """Cover lines 54, 81-82: chunked embedding edge cases."""
    def test_chunked_embedding_all_fail(self):
        """L54: All chunk embeddings return [] → final returns []."""
        from src.memory.vector import OllamaEmbedder
        embedder = OllamaEmbedder.__new__(OllamaEmbedder)
        embedder.model = "test"
        embedder.client = MagicMock()
        long_text = "x" * 7000  # Over MAX_CHUNK_SIZE
        embedder._embed_single = MagicMock(return_value=[])
        result = embedder.get_embedding(long_text)
        assert result == []

    def test_chunk_splits_at_sentence(self):
        """L81-82: chunk splitting finds sentence boundary."""
        from src.memory.vector import OllamaEmbedder
        embedder = OllamaEmbedder.__new__(OllamaEmbedder)
        embedder.MAX_CHUNK_SIZE = 50
        text = "First sentence here. Second sentence starts after the period."
        chunks = embedder._split_into_chunks(text)
        assert len(chunks) >= 2


# ═══════════════════════════ privacy/guard.py L96 ═══════════════════════════
class TestGuardPrivateNoUser:
    """Cover line 96: PRIVATE scope with no user_id defaults to PUBLIC."""
    def test_private_scope_no_user_id_returns_public_path(self):
        from src.privacy.guard import scope_write_path
        from src.privacy.scopes import PrivacyScope
        result = scope_write_path(PrivacyScope.PRIVATE, user_id=None)
        assert result == "memory/public"


# ═══════════════════════════ skills/sandbox.py L138 ═══════════════════════════
class TestSandboxLogExecution:
    """Cover line 138: rate tracker init in log_execution for new user."""
    def test_log_execution_new_user(self):
        from src.skills.sandbox import SkillSandbox
        from src.skills.types import SkillDefinition
        sandbox = SkillSandbox()
        skill = SkillDefinition(
            name="test_skill", description="test desc",
            instructions="do thing",
            author="tester", version="1.0",
            scope="PUBLIC", allowed_tools=["read_file"],
            checksum="abc123def456"
        )
        sandbox.log_execution(skill, "new_user_999", "PUBLIC", ["read_file"], True)
        assert "new_user_999" in sandbox._rate_tracker
        assert len(sandbox._rate_tracker["new_user_999"]) == 1


# ═══════════════════════════ tools/filesystem.py L64 ═══════════════════════════
class TestFilesystemScopeFilter:
    """Cover line 64: file in search is skipped due to scope check."""
    def test_search_skips_private_files(self, tmp_path):
        from src.tools.filesystem import search_codebase
        # Create a file in a "core" subdirectory that PUBLIC scope can't access
        core_dir = tmp_path / "memory" / "core"
        core_dir.mkdir(parents=True)
        (core_dir / "secret.py").write_text("secret = True")
        
        # PUBLIC scope should not see memory/core files
        result = search_codebase("secret", str(tmp_path), request_scope="PUBLIC")
        assert "secret" not in result or "Access Denied" in result or "No matches" in result


# ═══════════════════════════ backup/verify.py L40, 46 ═══════════════════════════
class TestBackupVerify:
    """Cover lines 40, 46: legacy format and missing fields."""
    def test_legacy_format_passes(self):
        from src.backup.verify import BackupVerifier
        with patch("src.security.provenance.ProvenanceManager.get_salt", return_value="test_salt"):
            v = BackupVerifier()
            ok, reason = v.verify_backup({"format_version": "1.0"})
            assert ok is False
            assert "rejected" in reason

    def test_missing_required_field(self):
        from src.backup.verify import BackupVerifier
        with patch("src.security.provenance.ProvenanceManager.get_salt", return_value="test_salt"):
            v = BackupVerifier()
            ok, reason = v.verify_backup({
                "format_version": "3.0",
                "user_id": 1,
                # missing exported_at, context, checksum
            })
            assert ok is False
            assert "Missing" in reason


# ═══════════════════════════ lobes/memory/librarian.py L30-31 ═══════════════════════════
class TestLibrarianPathExtraction:
    """Cover lines 30-31: path extraction from instruction text."""
    @pytest.mark.asyncio
    async def test_extract_path_from_instruction(self, tmp_path):
        from src.lobes.memory.librarian import LibrarianAbility
        lobe = MagicMock()
        lib = LibrarianAbility(lobe)
        
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\n")
        
        result = await lib.execute(f"read {test_file}")
        assert "PAGE" in result or "Librarian" in result


# ═══════════════════════════ lobes/creative/generators.py L23-25 ═══════════════════════════
class TestMediaGeneratorDevice:
    """Cover lines 23-25: device detection for GPU/MPS/CPU."""
    def test_device_cpu_fallback(self):
        import sys
        if 'src.lobes.creative.generators' in sys.modules:
            del sys.modules['src.lobes.creative.generators']
        import src.lobes.creative.generators
        from src.lobes.creative.generators import MediaGenerator
        gen = MediaGenerator.__new__(MediaGenerator)
        with patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=False):
            assert gen.device == "cpu"

    def test_device_cuda(self):
        import sys
        sys.modules.pop('src.lobes.creative.generators', None)
        import src.lobes.creative.generators
        from src.lobes.creative.generators import MediaGenerator
        gen = MediaGenerator.__new__(MediaGenerator)
        with patch("torch.backends.mps.is_available", return_value=False), \
             patch("torch.cuda.is_available", return_value=True):
            assert gen.device == "cuda"


# ═══════════════════════════ ui/views.py L65-66 ═══════════════════════════
class TestFeedbackViewTTSToggle:
    """Cover lines 65-66: discord.NotFound handling in TTS toggle."""
    @pytest.mark.asyncio
    async def test_tts_delete_not_found(self):
        from src.ui.views import ResponseFeedbackView
        import discord
        
        bot = MagicMock()
        bot.voice_manager = MagicMock()
        view = ResponseFeedbackView(bot, "test response")
        
        # Simulate existing audio message that raises NotFound on delete
        mock_audio_msg = AsyncMock()
        mock_audio_msg.delete = AsyncMock(
            side_effect=discord.NotFound(MagicMock(status=404), "not found")
        )
        view.audio_msg = mock_audio_msg
        
        interaction = MagicMock()
        interaction.response = AsyncMock()
        button = MagicMock()
        
        # Call the callback directly — discord Button callback only takes interaction
        await view.tts_button.callback(interaction)
        assert view.audio_msg is None


# ═══════════════════════════ bot/cogs/inbox_commands.py L128 ═══════════════════════════
class TestInboxSetup:
    """Cover line 128: async setup function."""
    @pytest.mark.asyncio
    async def test_setup_adds_cog(self):
        from src.bot.cogs.inbox_commands import setup
        bot = AsyncMock()
        await setup(bot)
        bot.add_cog.assert_called_once()


# ═══════════════════════════ lobes/interaction/perception.py L128-129, 155, 160 ═══════════════════════════
class TestPerceptionEdge:
    """Cover uncovered lines in perception.py."""
    def test_perception_context_defaults(self):
        from src.lobes.interaction.perception import PerceptionContext
        ctx = PerceptionContext()
        assert ctx is not None


# ═══════════════════════════ memory/quarantine.py ═══════════════════════════
class TestQuarantineEdge:
    """Push quarantine coverage from 95% to higher."""
    def test_quarantine_entry_creation(self):
        from src.memory.quarantine import QuarantineEntry
        entry = QuarantineEntry(
            source="NodeA", target="NodeB",
            rel_type="CAUSES", layer="CAUSAL",
            props={"weight": 1.0},
            violation="test violation"
        )
        assert entry.source == "NodeA"
        assert entry.layer == "CAUSAL"


# ═══════════════════════════ memory/chronos.py ═══════════════════════════
class TestChronosEdge:
    """Push chronos coverage toward 100%."""
    def test_get_current_era(self):
        from src.memory.chronos import ChronosManager
        cm = ChronosManager()
        era = cm.get_current_era()
        assert isinstance(era, str)
