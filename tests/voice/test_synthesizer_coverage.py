import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from src.voice.synthesizer import AudioSynthesizer
from config import settings

@pytest.fixture
def clean_sys_modules():
    # Helper to clean up imports if needed
    yield
    if 'src.voice.synthesizer' in sys.modules:
        del sys.modules['src.voice.synthesizer']

def test_init_no_kokoro_import():
    with patch.dict("sys.modules", {"kokoro_onnx": None}):
        # Force reload or re-import inside the test logic isn't easy if top-level try/except ran.
        # But we can patch the KOKORO_AVAILABLE constant using patch.object if we import the module.
        # Let's import the module first.
        import src.voice.synthesizer
        with patch("src.voice.synthesizer.KOKORO_AVAILABLE", False):
            synth = src.voice.synthesizer.AudioSynthesizer()
            assert synth.kokoro is None

def test_init_paths_missing(mocker):
    import src.voice.synthesizer
    with patch("src.voice.synthesizer.KOKORO_AVAILABLE", True):
        # Case 1: Model Missing
        with patch("os.path.exists", return_value=False):
             synth = src.voice.synthesizer.AudioSynthesizer()
             assert synth.kokoro is None
             
        # Case 2: Voices Missing
        # side_effect: True (Model), False (Voices)
        with patch("os.path.exists", side_effect=[True, False]):
             synth = src.voice.synthesizer.AudioSynthesizer()
             assert synth.kokoro is None

def test_init_exception(mocker):
    import src.voice.synthesizer
    
    # If import failed in module, Kokoro won't exist. We must inject it to patch it.
    if not hasattr(src.voice.synthesizer, 'Kokoro'):
        src.voice.synthesizer.Kokoro = MagicMock()

    with patch("src.voice.synthesizer.KOKORO_AVAILABLE", True):
        with patch("os.path.exists", return_value=True):
             with patch("src.voice.synthesizer.Kokoro", side_effect=Exception("Init Fail")):
                 synth = src.voice.synthesizer.AudioSynthesizer()
                 assert synth.kokoro is None

@pytest.mark.asyncio
async def test_generate_audio_empty_sanitized():
    import src.voice.synthesizer
    synth = src.voice.synthesizer.AudioSynthesizer()
    # Mock text that cleans to empty
    res = await synth.generate_audio("#####", "out.wav")
    assert res is None

@pytest.mark.asyncio
async def test_generate_audio_no_kokoro():
    import src.voice.synthesizer
    synth = src.voice.synthesizer.AudioSynthesizer()
    synth.kokoro = None
    res = await synth.generate_audio("Hello", "out.wav")
    assert res is None

@pytest.mark.asyncio
async def test_generate_audio_exception():
    import src.voice.synthesizer
    synth = src.voice.synthesizer.AudioSynthesizer()
    synth.kokoro = MagicMock()
    
    with patch("asyncio.to_thread", side_effect=Exception("TTS Fail")):
         res = await synth.generate_audio("Hello", "out.wav")
         assert res is None
