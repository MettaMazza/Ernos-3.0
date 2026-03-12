"""
Tests for src/lobes/creative/generators.py — targeting all uncovered lines.
Heavy mocking required since all generation depends on GPU hardware / HuggingFace.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import types
from config import settings as real_settings


# ─── get_generator factory ────────────────────────────────────────────────

class TestGetGenerator:

    def setup_method(self):
        from src.lobes.creative.generators import CloudMediaGenerator, LocalMediaGenerator
        CloudMediaGenerator._instance = None
        LocalMediaGenerator._instance = None

    def teardown_method(self):
        from src.lobes.creative.generators import CloudMediaGenerator, LocalMediaGenerator
        CloudMediaGenerator._instance = None
        LocalMediaGenerator._instance = None

    def test_admin_gets_cloud(self):
        from src.lobes.creative.generators import CloudMediaGenerator, get_generator
        CloudMediaGenerator._instance = None

        with patch.object(real_settings, 'ADMIN_IDS', {12345}):
            gen = get_generator(user_id=12345)
        assert type(gen).__name__ == "CloudMediaGenerator"
        CloudMediaGenerator._instance = None  # cleanup

    @patch("src.lobes.creative.generators.settings")
    def test_system_id_gets_local(self, mock_settings):
        mock_settings.ADMIN_IDS = []
        from src.lobes.creative.generators import LocalMediaGenerator
        LocalMediaGenerator._instance = None

        from src.lobes.creative.generators import get_generator
        gen = get_generator(user_id="CORE")
        assert type(gen).__name__ == "LocalMediaGenerator"
        LocalMediaGenerator._instance = None

    @patch("src.lobes.creative.generators.settings")
    def test_paid_user_gets_cloud(self, mock_settings):
        mock_settings.ADMIN_IDS = []
        from src.lobes.creative.generators import CloudMediaGenerator
        CloudMediaGenerator._instance = None

        with patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.get_tier.return_value = 1
            from src.lobes.creative.generators import get_generator
            gen = get_generator(user_id=99999)
        assert type(gen).__name__ == "CloudMediaGenerator"
        CloudMediaGenerator._instance = None

    @patch("src.lobes.creative.generators.settings")
    def test_free_user_gets_local(self, mock_settings):
        mock_settings.ADMIN_IDS = []
        from src.lobes.creative.generators import LocalMediaGenerator
        LocalMediaGenerator._instance = None

        with patch("src.core.flux_capacitor.FluxCapacitor") as MockFlux:
            MockFlux.return_value.get_tier.return_value = 0
            from src.lobes.creative.generators import get_generator
            gen = get_generator(user_id=88888)
        assert type(gen).__name__ == "LocalMediaGenerator"
        LocalMediaGenerator._instance = None

    @patch("src.lobes.creative.generators.settings")
    def test_no_user_id_gets_local(self, mock_settings):
        from src.lobes.creative.generators import LocalMediaGenerator
        LocalMediaGenerator._instance = None

        from src.lobes.creative.generators import get_generator
        gen = get_generator(user_id=None)
        assert type(gen).__name__ == "LocalMediaGenerator"
        LocalMediaGenerator._instance = None

    @patch("src.lobes.creative.generators.settings")
    def test_tier_lookup_failure_falls_back_to_local(self, mock_settings):
        mock_settings.ADMIN_IDS = []
        from src.lobes.creative.generators import LocalMediaGenerator
        LocalMediaGenerator._instance = None

        with patch("src.core.flux_capacitor.FluxCapacitor", side_effect=RuntimeError("boom")):
            from src.lobes.creative.generators import get_generator
            gen = get_generator(user_id=77777)
        assert type(gen).__name__ == "LocalMediaGenerator"
        LocalMediaGenerator._instance = None


# ─── CloudMediaGenerator ──────────────────────────────────────────────────

class TestCloudMediaGenerator:

    def setup_method(self):
        from src.lobes.creative.generators import CloudMediaGenerator
        CloudMediaGenerator._instance = None

    def teardown_method(self):
        from src.lobes.creative.generators import CloudMediaGenerator
        CloudMediaGenerator._instance = None

    def test_singleton(self):
        from src.lobes.creative.generators import CloudMediaGenerator
        a = CloudMediaGenerator()
        b = CloudMediaGenerator()
        assert a is b

    def test_client_property_no_token_raises(self):
        from src.lobes.creative.generators import CloudMediaGenerator
        gen = CloudMediaGenerator()
        with patch.object(real_settings, 'HF_API_TOKEN', ''), \
             patch('os.getenv', return_value=''):
            with pytest.raises(ValueError, match="HF_API_TOKEN not set"):
                _ = gen.client

    def test_client_property_with_token(self):
        from src.lobes.creative.generators import CloudMediaGenerator
        gen = CloudMediaGenerator()
        with patch.object(real_settings, 'HF_API_TOKEN', 'test-token'), \
             patch("huggingface_hub.InferenceClient") as MockClient:
            MockClient.return_value = MagicMock()
            client = gen.client
            assert client is not None
            MockClient.assert_called_once_with(token="test-token")

    @patch("src.lobes.creative.generators.settings")
    def test_generate_image_success(self, mock_settings):
        mock_settings.FLUX_MODEL_PATH = "test-model"
        from src.lobes.creative.generators import CloudMediaGenerator
        gen = CloudMediaGenerator()

        mock_image = MagicMock()
        gen._client = MagicMock()
        gen._client.text_to_image.return_value = mock_image

        result = gen.generate_image("a cat", "/tmp/test.png")
        assert result == "/tmp/test.png"
        mock_image.save.assert_called_once_with("/tmp/test.png")

    @patch("src.lobes.creative.generators.settings")
    def test_generate_image_failure_falls_back_to_local(self, mock_settings):
        mock_settings.FLUX_MODEL_PATH = "test-model"
        from src.lobes.creative.generators import CloudMediaGenerator, LocalMediaGenerator
        gen = CloudMediaGenerator()

        gen._client = MagicMock()
        gen._client.text_to_image.side_effect = RuntimeError("API down")

        with patch.object(LocalMediaGenerator, 'generate_image', return_value="/tmp/local.png") as mock_local:
            result = gen.generate_image("a cat", "/tmp/test.png")
        assert result == "/tmp/local.png"

    @patch("src.lobes.creative.generators.settings")
    def test_generate_video_success(self, mock_settings):
        mock_settings.LTX_MODEL_PATH = "test-video-model"
        from src.lobes.creative.generators import CloudMediaGenerator
        gen = CloudMediaGenerator()

        gen._client = MagicMock()
        gen._client.text_to_video.return_value = b"video-bytes"

        import builtins
        mock_file = MagicMock()
        with patch.object(builtins, 'open', return_value=mock_file):
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            result = gen.generate_video("a sunset", "/tmp/test.mp4")
        assert result == "/tmp/test.mp4"

    @patch("src.lobes.creative.generators.settings")
    def test_generate_video_failure_falls_back_to_local(self, mock_settings):
        mock_settings.LTX_MODEL_PATH = "test-video-model"
        from src.lobes.creative.generators import CloudMediaGenerator, LocalMediaGenerator
        gen = CloudMediaGenerator()

        gen._client = MagicMock()
        gen._client.text_to_video.side_effect = RuntimeError("API down")

        with patch.object(LocalMediaGenerator, 'generate_video', return_value="/tmp/local.mp4"):
            result = gen.generate_video("a sunset", "/tmp/test.mp4")
        assert result == "/tmp/local.mp4"


# ─── LocalMediaGenerator ─────────────────────────────────────────────────

class TestLocalMediaGenerator:

    def setup_method(self):
        from src.lobes.creative.generators import LocalMediaGenerator
        LocalMediaGenerator._instance = None
        LocalMediaGenerator._flux_pipe = None
        LocalMediaGenerator._ltx_pipe = None
        LocalMediaGenerator._musicgen_model = None
        LocalMediaGenerator._musicgen_processor = None
        LocalMediaGenerator._tts_models = {}

    def teardown_method(self):
        from src.lobes.creative.generators import LocalMediaGenerator
        LocalMediaGenerator._instance = None
        LocalMediaGenerator._flux_pipe = None
        LocalMediaGenerator._ltx_pipe = None
        LocalMediaGenerator._musicgen_model = None
        LocalMediaGenerator._musicgen_processor = None
        LocalMediaGenerator._tts_models = {}

    def test_dtype_cpu(self):
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()
        with patch.object(type(gen), 'device', new_callable=PropertyMock, return_value="cpu"):
            import torch
            assert gen.dtype == torch.float32

    def test_dtype_mps(self):
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()
        with patch.object(type(gen), 'device', new_callable=PropertyMock, return_value="mps"):
            import torch
            assert gen.dtype == torch.float16

    # ─── _patch_scheduler ─────────────────────────────────────────────

    def test_patch_scheduler_normal_step(self):
        """Lines 189-206: Scheduler patching — normal step passes through."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_scheduler = MagicMock()
        mock_scheduler._is_patched = False
        expected_result = MagicMock()
        mock_scheduler.step.return_value = expected_result

        gen._patch_scheduler(mock_scheduler)
        assert mock_scheduler._is_patched is True

    def test_patch_scheduler_index_error_return_dict(self):
        """Lines 194-202: Scheduler step raises IndexError, returns PatchedOutput."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_scheduler = MagicMock()
        mock_scheduler._is_patched = False
        mock_scheduler.step.side_effect = IndexError("out of bounds")

        gen._patch_scheduler(mock_scheduler)

        sample = MagicMock()
        result = mock_scheduler.step(MagicMock(), MagicMock(), sample, return_dict=True)
        assert result.prev_sample is sample

    def test_patch_scheduler_index_error_no_return_dict(self):
        """Lines 196-197: return_dict=False returns (sample,) tuple."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_scheduler = MagicMock()
        mock_scheduler._is_patched = False
        mock_scheduler.step.side_effect = IndexError("out of bounds")

        gen._patch_scheduler(mock_scheduler)

        sample = MagicMock()
        result = mock_scheduler.step(MagicMock(), MagicMock(), sample, return_dict=False)
        assert result == (sample,)

    def test_patch_scheduler_already_patched(self):
        """Line 187: Skip if already patched."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_scheduler = MagicMock()
        mock_scheduler._is_patched = True
        original_step = mock_scheduler.step

        gen._patch_scheduler(mock_scheduler)
        # Step should NOT have been replaced
        assert mock_scheduler.step is original_step

    # ─── _get_musicgen / unload_musicgen ──────────────────────────────

    def test_get_musicgen_loads_model(self):
        """Lines 238-252: Lazy-load MusicGen."""
        import sys
        import torch
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        # Create a fake transformers module to avoid triggering the real import
        # (which crashes on psutil.__spec__ in the full suite)
        mock_model = MagicMock()
        mock_proc = MagicMock()
        fake_transformers = types.ModuleType("transformers")
        fake_transformers.AutoProcessor = MagicMock()
        fake_transformers.AutoProcessor.from_pretrained.return_value = mock_proc
        fake_transformers.MusicgenForConditionalGeneration = MagicMock()
        fake_transformers.MusicgenForConditionalGeneration.from_pretrained.return_value = mock_model

        # Pin both fake transformers AND real torch to prevent reimport cascade
        saved_modules = {'transformers': fake_transformers, 'torch': torch}
        with patch.object(type(gen), 'device', new_callable=PropertyMock, return_value="cpu"), \
             patch.object(type(gen), 'dtype', new_callable=PropertyMock, return_value="float32"), \
             patch.dict(sys.modules, saved_modules):
            model, processor = gen._get_musicgen()
            assert model is mock_model
            fake_transformers.MusicgenForConditionalGeneration.from_pretrained.assert_called_once()

    def test_unload_musicgen(self):
        """Lines 256-267: Free MusicGen from memory."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        # Set up as if model is loaded — set BOTH instance and class vars
        # (unload_musicgen does `del self._musicgen_model` then sets class var)
        mock_model = MagicMock()
        mock_proc = MagicMock()
        gen._musicgen_model = mock_model
        gen._musicgen_processor = mock_proc
        gen.__class__._musicgen_model = mock_model
        gen.__class__._musicgen_processor = mock_proc

        with patch("torch.cuda.is_available", return_value=False):
            gen.unload_musicgen()

        assert gen.__class__._musicgen_model is None
        assert gen.__class__._musicgen_processor is None

    def test_unload_musicgen_when_none(self):
        """Lines 256: No-op when model not loaded."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()
        gen.__class__._musicgen_model = None
        gen.unload_musicgen()  # Should not raise

    # ─── _get_tts_model / _load_tts_variant ───────────────────────────

    def test_get_tts_model_loads_variant(self):
        """Lines 274-284: Lazy-load TTS model variant."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        with patch.object(gen, '_load_tts_variant') as mock_load:
            # Simulate _load_tts_variant populating the dict
            def load_side(variant):
                gen._tts_models[variant] = MagicMock()
            mock_load.side_effect = load_side

            model = gen._get_tts_model("CustomVoice")
            mock_load.assert_called_once_with("CustomVoice")
            assert model is not None

    def test_get_tts_model_preloads_buddy(self):
        """Lines 279-282: Preloads paired variant for audiobook."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        with patch.object(gen, '_load_tts_variant') as mock_load:
            def load_side(variant):
                gen._tts_models[variant] = MagicMock()
            mock_load.side_effect = load_side

            model = gen._get_tts_model("VoiceDesign")
            # Should have loaded VoiceDesign AND Base (buddy)
            assert mock_load.call_count == 2

    def test_load_tts_variant(self):
        """Lines 288-305: Actual model loading."""
        import sys
        import torch
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_model = MagicMock()
        fake_qwen_tts = types.ModuleType("qwen_tts")
        fake_qwen_tts.Qwen3TTSModel = MagicMock()
        fake_qwen_tts.Qwen3TTSModel.from_pretrained.return_value = mock_model

        # Ensure torch stays in sys.modules (prevent reimport crash)
        saved_modules = {'qwen_tts': fake_qwen_tts, 'torch': torch}
        with patch.object(type(gen), 'device', new_callable=PropertyMock, return_value="cpu"), \
             patch.object(type(gen), 'dtype', new_callable=PropertyMock, return_value="float32"), \
             patch.dict(sys.modules, saved_modules):
            gen._load_tts_variant("CustomVoice")
            assert "CustomVoice" in gen._tts_models
            fake_qwen_tts.Qwen3TTSModel.from_pretrained.assert_called_once()

    def test_load_tts_variant_mps_uses_sdpa(self):
        """Line 299-300: MPS device adds sdpa attn_implementation."""
        import sys
        import torch
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_model = MagicMock()
        fake_qwen_tts = types.ModuleType("qwen_tts")
        fake_qwen_tts.Qwen3TTSModel = MagicMock()
        fake_qwen_tts.Qwen3TTSModel.from_pretrained.return_value = mock_model

        saved_modules = {'qwen_tts': fake_qwen_tts, 'torch': torch}
        with patch.object(type(gen), 'device', new_callable=PropertyMock, return_value="mps"), \
             patch.object(type(gen), 'dtype', new_callable=PropertyMock, return_value="float16"), \
             patch.dict(sys.modules, saved_modules):
            gen._load_tts_variant("CustomVoice")
            call_kwargs = fake_qwen_tts.Qwen3TTSModel.from_pretrained.call_args[1]
            assert call_kwargs["attn_implementation"] == "sdpa"

    def test_generate_music_disabled(self):
        """Lines 348-349: MusicGen is disabled and raises RuntimeError."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()
        
        with pytest.raises(RuntimeError, match="MusicGen is temporarily disabled"):
            gen.generate_music("jazz melody", "/tmp/music.wav")

    # ─── generate_speech ──────────────────────────────────────────────

    def test_generate_speech_custom_mode(self):
        """Lines 448-458: Custom voice mode."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_model = MagicMock()
        mock_model.generate_custom_voice.return_value = ([[0.1, 0.2]], 22050)

        with patch.object(gen, '_get_tts_model', return_value=mock_model), \
             patch("soundfile.write"), \
             patch("src.lobes.creative.audio_utils.wav_to_mp3", return_value="/tmp/out.mp3"):
            result = gen.generate_speech("hello", "/tmp/out.wav")
        assert result == "/tmp/out.mp3"

    def test_generate_speech_design_mode(self):
        """Lines 431-437: Voice design mode."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_model = MagicMock()
        mock_model.generate_voice_design.return_value = ([[0.1, 0.2]], 22050)

        with patch.object(gen, '_get_tts_model', return_value=mock_model), \
             patch("soundfile.write"), \
             patch("src.lobes.creative.audio_utils.wav_to_mp3", return_value="/tmp/out.mp3"):
            result = gen.generate_speech("hello", "/tmp/out.wav", mode="design")
        assert result == "/tmp/out.mp3"

    def test_generate_speech_clone_mode(self):
        """Lines 438-447: Voice clone mode."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_model = MagicMock()
        mock_model.generate_voice_clone.return_value = ([[0.1, 0.2]], 22050)

        with patch.object(gen, '_get_tts_model', return_value=mock_model), \
             patch("soundfile.write"), \
             patch("src.lobes.creative.audio_utils.wav_to_mp3", return_value="/tmp/out.mp3"):
            result = gen.generate_speech(
                "hello", "/tmp/out.wav",
                mode="clone", ref_audio="/tmp/ref.wav", ref_text="reference"
            )
        assert result == "/tmp/out.mp3"

    def test_generate_speech_clone_mode_no_ref_raises(self):
        """Lines 439-440: Clone mode without ref_audio raises ValueError."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        with pytest.raises(ValueError, match="ref_audio"):
            gen.generate_speech("hello", "/tmp/out.wav", mode="clone")

    def test_generate_speech_custom_with_instruct(self):
        """Lines 456-457: Custom voice mode with instruct kwarg."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_model = MagicMock()
        mock_model.generate_custom_voice.return_value = ([[0.1, 0.2]], 22050)

        with patch.object(gen, '_get_tts_model', return_value=mock_model), \
             patch("soundfile.write"), \
             patch("src.lobes.creative.audio_utils.wav_to_mp3", return_value="/tmp/out.mp3"):
            result = gen.generate_speech(
                "hello", "/tmp/out.wav",
                voice="Chelsie", instruct="Speak with excitement"
            )
        call_kwargs = mock_model.generate_custom_voice.call_args[1]
        assert call_kwargs["instruct"] == "Speak with excitement"

    def test_device_cuda(self):
        """Lines 151-152: device returns 'cuda' when MPS unavailable but CUDA available."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()
        import torch
        with patch.object(torch.backends.mps, 'is_available', return_value=False), \
             patch.object(torch.cuda, 'is_available', return_value=True):
            assert gen.device == "cuda"

    def test_device_cpu(self):
        """Line 153: device returns 'cpu' when nothing available."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()
        import torch
        with patch.object(torch.backends.mps, 'is_available', return_value=False), \
             patch.object(torch.cuda, 'is_available', return_value=False):
            assert gen.device == "cpu"

    def test_unload_musicgen_cuda_path(self):
        """Lines 264-265: CUDA cache empty in unload_musicgen when no MPS."""
        from src.lobes.creative.generators import LocalMediaGenerator
        gen = LocalMediaGenerator()

        mock_model = MagicMock()
        mock_proc = MagicMock()
        gen._musicgen_model = mock_model
        gen._musicgen_processor = mock_proc
        gen.__class__._musicgen_model = mock_model
        gen.__class__._musicgen_processor = mock_proc

        import torch

        # Temporarily hide torch.mps so hasattr(torch, 'mps') returns False
        original_mps = torch.mps
        try:
            delattr(torch, 'mps')
            with patch.object(torch.cuda, 'is_available', return_value=True), \
                 patch.object(torch.cuda, 'empty_cache') as mock_empty:
                gen.unload_musicgen()
            mock_empty.assert_called_once()
        finally:
            torch.mps = original_mps


