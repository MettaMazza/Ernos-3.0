"""
Media generation backends: HuggingFace Cloud API or Local diffusers.

Usage:
    from src.lobes.creative.generators import get_generator
    generator = get_generator()
    generator.generate_image("a sunset over mountains", "/path/to/output.png")
"""
import logging
import os
from config import settings

logger = logging.getLogger("MediaGenerator")


def get_generator(user_id=None):
    """
    Factory: returns the appropriate media generator based on user tier.
    
    Routing logic:
      - Admin (in ADMIN_IDS)  → Cloud (fast, best quality)
      - Paid user (tier 1+)   → Cloud
      - Free user (tier 0)    → Local (slower but no API cost)
      - No user_id (autonomy) → Local (don't spend cloud credits)
    """
    if user_id is not None:
        try:
            # Admin check — always cloud
            admin_ids = {str(aid) for aid in settings.ADMIN_IDS}
            if str(user_id) in admin_ids:
                logger.info(f"Admin {user_id} → Cloud generator")
                return CloudMediaGenerator()

            # Tier check
            from src.core.flux_capacitor import FluxCapacitor
            
            # Handle non-integer system IDs (e.g. "CORE")
            uid_str = str(user_id)
            if not uid_str.isdigit():
                logger.info(f"System ID {uid_str} → Local generator")
                return LocalMediaGenerator()

            tier = FluxCapacitor().get_tier(int(user_id))
            if tier >= 1:
                logger.info(f"User {user_id} (tier {tier}) → Cloud generator")
                return CloudMediaGenerator()
            else:
                logger.info(f"User {user_id} (free) → Local generator")
                return LocalMediaGenerator()
        except Exception as e:
            logger.warning(f"Tier lookup failed for {user_id}, falling back to local: {e}")
            return LocalMediaGenerator()

    # No user_id (autonomy/system) → local
    logger.info("System/autonomy request → Local generator")
    return LocalMediaGenerator()


class CloudMediaGenerator:
    """
    Generates images/video via HuggingFace Inference API.
    No local GPU required — runs on HF cloud infrastructure.
    
    Requires: HF_API_TOKEN in settings (or env).
    Free tier: ~1000 requests/day for most models.
    Pro tier ($9/mo): Higher rate limits, access to gated models.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
        return cls._instance

    @property
    def client(self):
        if self._client is None:
            from huggingface_hub import InferenceClient
            token = getattr(settings, "HF_API_TOKEN", "") or os.getenv("HF_API_TOKEN", "")
            if not token:
                raise ValueError(
                    "HF_API_TOKEN not set. Get one at https://huggingface.co/settings/tokens "
                    "and add it to your .env file."
                )
            self._client = InferenceClient(token=token)
            logger.info("HuggingFace InferenceClient initialized (cloud mode)")
        return self._client

    def generate_image(self, prompt: str, output_path: str) -> str:
        """Generate image via HF Inference API, with local fallback on failure."""
        model = getattr(settings, "FLUX_MODEL_PATH", "black-forest-labs/FLUX.1-dev")
        logger.info(f"Cloud image generation: model={model}, prompt={prompt[:80]}...")

        try:
            image = self.client.text_to_image(
                prompt,
                model=model,
                width=1024,
                height=1024,
            )
            image.save(output_path)
            logger.info(f"Cloud image saved: {output_path}")
            return output_path
        except Exception as e:
            logger.warning(f"Cloud image generation failed, falling back to local: {e}")
            return LocalMediaGenerator().generate_image(prompt, output_path)

    def generate_video(self, prompt: str, output_path: str) -> str:
        """Generate video via HF Inference API, with local fallback on failure."""
        model = getattr(settings, "LTX_MODEL_PATH", "Lightricks/LTX-Video")
        logger.info(f"Cloud video generation: model={model}, prompt={prompt[:80]}...")

        try:
            video_bytes = self.client.text_to_video(
                prompt,
                model=model,
            )
            with open(output_path, "wb") as f:
                f.write(video_bytes)
            logger.info(f"Cloud video saved: {output_path}")
            return output_path
        except Exception as e:
            logger.warning(f"Cloud video generation failed, falling back to local: {e}")
            return LocalMediaGenerator().generate_video(prompt, output_path)


class LocalMediaGenerator:
    """
    Generates images/video/music/speech locally via diffusers/transformers pipelines.
    Requires: GPU with sufficient VRAM, or MPS on Apple Silicon (slow).
    Models downloaded to ~/.cache/huggingface on first use.
    """
    _instance = None
    _flux_pipe = None
    _ltx_pipe = None
    _musicgen_model = None
    _musicgen_processor = None
    _tts_models = {}  # keyed by variant: "CustomVoice", "VoiceDesign", "Base"
    _residency = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def device(self):
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"

    @property
    def dtype(self):
        import torch
        if self.device == "mps":
            return torch.float16
        return torch.bfloat16 if self.device != "cpu" else torch.float32

    def get_flux_pipe(self):
        from diffusers import FluxPipeline
        import torch

        if self._flux_pipe is None:
            self._purge_heavy_models(exclude="flux")
            logger.info(f"Loading Flux Pipeline on {self.device}...")
            try:
                pipe = FluxPipeline.from_pretrained(
                    settings.FLUX_MODEL_PATH,
                    torch_dtype=self.dtype
                )
                pipe.to(self.device)
                self._flux_pipe = pipe
                self._patch_scheduler(self._flux_pipe.scheduler)
                logger.info("Flux Pipeline loaded.")
            except Exception as e:
                logger.error(f"Failed to load Flux: {e}")
                raise e
        return self._flux_pipe

    def _patch_scheduler(self, scheduler):
        """Monkeypatch scheduler.step to catch IndexError at end of generation."""
        import types

        if getattr(scheduler, "_is_patched", False):
            return

        original_step = scheduler.step

        def safe_step(sk_self, model_output, timestep, sample, **kwargs):
            try:
                return original_step(model_output, timestep, sample, **kwargs)
            except IndexError:
                logger.warning("Scheduler IndexError caught. Returning sample as-is.")
                if not kwargs.get("return_dict", True):
                    return (sample,)

                class PatchedOutput:
                    def __init__(self, prev_sample):
                        self.prev_sample = prev_sample
                return PatchedOutput(prev_sample=sample)

        scheduler.step = types.MethodType(safe_step, scheduler)
        scheduler._is_patched = True
        logger.info("Scheduler patched for safe stepping.")

    def get_ltx_pipe(self):
        try:
            from diffusers import LTXPipeline
        except ImportError:
            raise ImportError("LTXPipeline not found. Ensure diffusers>=0.36.0 is installed.")

        if self._ltx_pipe is None:
            self._purge_heavy_models(exclude="ltx")
            logger.info(f"Loading LTX Pipeline on {self.device}...")
            try:
                pipe = LTXPipeline.from_pretrained(
                    settings.LTX_MODEL_PATH,
                    torch_dtype=self.dtype
                )
                pipe.to(self.device)
                
                # FIX: VAE must be float32 on MPS to avoid "pixelated blur" artifacts
                if self.device == "mps":
                    import torch
                    pipe.vae = pipe.vae.to(dtype=torch.float32)
                    logger.info("Forced LTX VAE into float32 for MPS stability.")

                self._ltx_pipe = pipe
                logger.info("LTX Pipeline loaded.")
            except Exception as e:
                logger.error(f"Failed to load LTX: {e}")
                raise e
        return self._ltx_pipe

    def _get_musicgen(self):
        """Lazy-load MusicGen Large model and processor (singleton)."""
        if self._musicgen_model is None:
            self._purge_heavy_models(exclude="musicgen")
            import torch
            from transformers import AutoProcessor, MusicgenForConditionalGeneration
            
            model_id = "facebook/musicgen-large"
            logger.info(f"Loading MusicGen Large on {self.device}...")
            
            self._musicgen_processor = AutoProcessor.from_pretrained(model_id)
            self._musicgen_model = MusicgenForConditionalGeneration.from_pretrained(
                model_id, torch_dtype=self.dtype
            )
            self._musicgen_model.to(self.device)
            logger.info("MusicGen Large loaded.")
        
        return self._musicgen_model, self._musicgen_processor

    def unload_musicgen(self):
        """Explicitly free MusicGen model from memory after audiobook production."""
        if self._musicgen_model is not None:
            import torch, gc
            self.__class__._musicgen_model = None
            self.__class__._musicgen_processor = None
            if hasattr(torch, 'mps'):
                torch.mps.empty_cache()
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            logger.info("MusicGen Large unloaded from memory.")

    # Audiobook variant pairs — preload buddy when one is requested
    _TTS_AUDIOBOOK_PAIRS = {"VoiceDesign": "Base", "Base": "VoiceDesign"}

    def _get_tts_model(self, variant: str = "CustomVoice"):
        """Lazy-load a Qwen3-TTS model variant (singleton per variant)."""
        if variant not in self._tts_models:
            self._purge_heavy_models(exclude="tts")
            self._load_tts_variant(variant)

            # Preload the paired variant for audiobook production
            # (avoids 8-min cold load mid-audiobook)
            buddy = self._TTS_AUDIOBOOK_PAIRS.get(variant)
            if buddy and buddy not in self._tts_models:
                logger.info(f"Preloading paired TTS variant '{buddy}' for audiobook readiness...")
                self._load_tts_variant(buddy)

        return self._tts_models[variant]

    def set_residency(self, model_type: str):
        """
        Public hook to force-purge VRAM and prepare for a specific model type.
        Use this to proactively manage residency during heavy sequential tasks 
        like audiobook production.
        
        Args:
            model_type: 'flux', 'ltx', 'musicgen', or 'tts'.
        """
        logger.info(f"VRAM Residency: Signaling transition to {model_type}...")
        self._purge_heavy_models(exclude=model_type)

    def _purge_heavy_models(self, exclude: str = None):
        """Mutually exclusive VRAM management: unload everything except the required model."""
        if self.__class__._residency == exclude and exclude is not None:
            return
        import torch, gc
        self.__class__._residency = exclude
        unloaded = []

        if exclude != "flux" and self._flux_pipe is not None:
            self.__class__._flux_pipe = None
            unloaded.append("Flux")

        if exclude != "ltx" and self._ltx_pipe is not None:
            self.__class__._ltx_pipe = None
            unloaded.append("LTX")

        if exclude != "musicgen" and self._musicgen_model is not None:
            self.__class__._musicgen_model = None
            self.__class__._musicgen_processor = None
            unloaded.append("MusicGen")

        if exclude != "tts" and self._tts_models:
            self._tts_models.clear()
            unloaded.append("TTS")

        if unloaded:
            if hasattr(torch, 'mps'):
                torch.mps.empty_cache()
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            logger.info(f"VRAM Guard: Unloaded {', '.join(unloaded)} to make room for {exclude or 'system'}.")

    def _load_tts_variant(self, variant: str):
        """Load a single Qwen3-TTS variant with MPS optimizations."""
        import torch
        from qwen_tts import Qwen3TTSModel

        model_id = f"Qwen/Qwen3-TTS-12Hz-1.7B-{variant}"
        logger.info(f"Loading Qwen3-TTS ({variant}) on {self.device}...")

        load_kwargs = {
            "device_map": self.device,
            "dtype": self.dtype,
        }
        # Use SDPA (Scaled Dot-Product Attention) on MPS for Metal-native kernels
        if self.device == "mps":
            load_kwargs["attn_implementation"] = "sdpa"

        self._tts_models[variant] = Qwen3TTSModel.from_pretrained(
            model_id, **load_kwargs
        )
        logger.info(f"Qwen3-TTS ({variant}) loaded.")


    def generate_image(self, prompt: str, output_path: str) -> str:
        import torch
        pipe = self.get_flux_pipe()
        logger.info(f"Local image generation: {prompt}")

        image = pipe(
            prompt,
            guidance_scale=3.5,
            num_inference_steps=50,
            width=1024,
            height=1024,
            max_sequence_length=512,
            generator=torch.Generator("cpu").manual_seed(0)
        ).images[0]

        image.save(output_path)
        return output_path

    def generate_video(self, prompt: str, output_path: str) -> str:
        from diffusers.utils import export_to_video

        pipe = self.get_ltx_pipe()
        logger.info(f"Local video generation: {prompt}")

        video = pipe(
            prompt=prompt,
            negative_prompt="low quality, worst quality, deformed, distorted, watermark",
            width=1024,
            height=576,
            num_frames=121,
            num_inference_steps=50,
            guidance_scale=3.0,
        ).frames[0]

        export_to_video(video, output_path, fps=24)
        return output_path

    def generate_music(self, prompt: str, output_path: str, duration: int = 10) -> str:
        """
        Generate music from a text prompt using MusicGen Large.
        
        Args:
            prompt: Text description (genre, mood, instruments, tempo)
            output_path: Where to save the output (WAV, will be converted to MP3)
            duration: Length in seconds (default 10, HARD CAP 30s)
        
        Returns:
            Path to the generated audio file
        """
        raise RuntimeError("MusicGen is temporarily disabled")
        
        import torch
        import scipy
        import numpy as np

        model, processor = self._get_musicgen()
        
        # MusicGen generates ~50 tokens/sec at 32kHz
        TOKENS_PER_SEC = 50
        # HARD CAP: 30s max — longer durations cause catastrophic memory usage
        # (KV-cache for MusicGen Large + generated tensor can consume 50GB+)
        duration = min(duration, 30)
        
        sample_rate = model.config.audio_encoder.sampling_rate
        
        logger.info(f"MusicGen: generating {duration}s — {prompt[:80]}...")
        inputs = processor(text=[prompt], padding=True, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            audio = model.generate(**inputs, max_new_tokens=duration * TOKENS_PER_SEC)
        
        audio_data = audio[0, 0].cpu().float().numpy()
        
        # ── Aggressive memory cleanup ──
        del audio, inputs
        if hasattr(torch, 'mps') and self.device == "mps":
            torch.mps.empty_cache()
        elif torch.cuda.is_available():
            torch.cuda.empty_cache()
        import gc
        gc.collect()
        # ────────────────────────────────
        
        # Save as WAV
        scipy.io.wavfile.write(output_path, rate=sample_rate, data=audio_data)
        logger.info(f"Music generated: {output_path} ({duration}s)")
        
        # Convert to MP3 for Discord-friendly delivery
        from src.lobes.creative.audio_utils import wav_to_mp3
        final_path = wav_to_mp3(output_path)
        
        return final_path

    def generate_speech(self, text: str, output_path: str, voice: str = "Chelsie",
                        instruct: str = "", mode: str = "custom",
                        ref_audio: str = None, ref_text: str = None) -> str:
        """
        Generate speech from text using Qwen3-TTS.
        
        Three modes:
          - "custom":  Built-in speakers with emotion/style control
          - "design":  Create a voice from a text description
          - "clone":   Clone a voice from a reference audio clip
        
        Args:
            text: The text to speak
            output_path: Where to save (WAV, converted to MP3)
            voice: Speaker name for custom mode (default "Chelsie")
            instruct: Emotion/style instruction (e.g. "Speak with excitement")
            mode: "custom", "design", or "clone"
            ref_audio: Path to reference audio (clone mode only)
            ref_text: Transcript of reference audio (clone mode only)
        
        Returns:
            Path to the generated audio file
        """
        import soundfile as sf
        
        logger.info(f"TTS generation [{mode}]: {text[:80]}...")
        
        if mode == "design":
            model = self._get_tts_model("VoiceDesign")
            wavs, sr = model.generate_voice_design(
                text=text,
                language="Auto",
                instruct=instruct or "A clear, natural speaking voice.",
            )
        elif mode == "clone":
            if not ref_audio:
                raise ValueError("Voice clone mode requires ref_audio path.")
            model = self._get_tts_model("Base")
            wavs, sr = model.generate_voice_clone(
                text=text,
                language="Auto",
                ref_audio=ref_audio,
                ref_text=ref_text or "",
            )
        else:
            # Default: custom voice with built-in speakers
            model = self._get_tts_model("CustomVoice")
            kwargs = {
                "text": text,
                "language": "Auto",
                "speaker": voice,
            }
            if instruct:
                kwargs["instruct"] = instruct
            wavs, sr = model.generate_custom_voice(**kwargs)
        
        # Save as WAV
        sf.write(output_path, wavs[0], sr)
        logger.info(f"Speech generated: {output_path}")
        
        # Convert to MP3
        from src.lobes.creative.audio_utils import wav_to_mp3
        final_path = wav_to_mp3(output_path)
        
        return final_path


# Legacy alias for backward compatibility
MediaGenerator = LocalMediaGenerator

