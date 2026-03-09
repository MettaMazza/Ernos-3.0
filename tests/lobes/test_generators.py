import pytest
import sys
import importlib
from unittest.mock import MagicMock, patch

# Define Mocks
mock_torch = MagicMock()
mock_torch.backends.mps.is_available.return_value = True
mock_torch.cuda.is_available.return_value = False
mock_torch.bfloat16 = "bfloat16"
mock_torch.float16 = "float16" # Add this mock
mock_torch.float32 = "float32"
# Important: Map attributes so generated mocks behave consistently
mock_torch.Generator.return_value = MagicMock()

mock_diffusers = MagicMock()
mock_FluxPipeline = MagicMock()
mock_LTXPipeline = MagicMock()
mock_export = MagicMock()

mock_diffusers.FluxPipeline = mock_FluxPipeline
mock_diffusers.LTXPipeline = mock_LTXPipeline
mock_diffusers.utils.export_to_video = mock_export

@pytest.fixture
def media_generator_cls():
    """
    Patches sys.modules and returns the MediaGenerator class
    reloaded in the mocked environment.
    """
    with patch.dict("sys.modules", {"torch": mock_torch, "diffusers": mock_diffusers, "diffusers.utils": mock_diffusers.utils}):
        # Remove from sys.modules if present to force reload
        if "src.lobes.creative.generators" in sys.modules:
            del sys.modules["src.lobes.creative.generators"]
            
        import src.lobes.creative.generators
        importlib.reload(src.lobes.creative.generators)
        
        # Reset singleton state
        cls = src.lobes.creative.generators.MediaGenerator
        cls._instance = None
        cls._flux_pipe = None
        cls._ltx_pipe = None
        
        yield cls

def test_singleton(media_generator_cls):
    g1 = media_generator_cls()
    g2 = media_generator_cls()
    assert g1 is g2

def test_device_detection_mps(media_generator_cls):
    mock_torch.backends.mps.is_available.return_value = True
    g = media_generator_cls()
    assert g.device == "mps"
    assert g.dtype == "float16"

def test_get_flux_pipe(media_generator_cls):
    mock_FluxPipeline.from_pretrained.reset_mock()
    mock_FluxPipeline.from_pretrained.return_value = MagicMock()
    
    g = media_generator_cls()
    pipe = g.get_flux_pipe()
    
    mock_FluxPipeline.from_pretrained.assert_called_once()
    assert pipe is mock_FluxPipeline.from_pretrained.return_value

def test_get_ltx_pipe(media_generator_cls):
    mock_LTXPipeline.from_pretrained.reset_mock()
    g = media_generator_cls()
    pipe = g.get_ltx_pipe()
    mock_LTXPipeline.from_pretrained.assert_called_once()

def test_generate_image(media_generator_cls):
    g = media_generator_cls()
    
    mock_pipe = mock_FluxPipeline.from_pretrained.return_value
    mock_image = MagicMock()
    mock_pipe.return_value.images = [mock_image]
    
    res = g.generate_image("prompt", "/tmp/out.png")
    assert res == "/tmp/out.png"
    mock_image.save.assert_called_with("/tmp/out.png")

def test_generate_video(media_generator_cls):
    g = media_generator_cls()
    
    # Mock pipe behavior
    mock_pipe = mock_LTXPipeline.from_pretrained.return_value
    mock_pipe.return_value.frames = [MagicMock()]
    
    res = g.generate_video("prompt", "/tmp/out.mp4")
    assert res == "/tmp/out.mp4"
    mock_export.assert_called()

def test_get_flux_pipe_error(media_generator_cls):
    mock_FluxPipeline.from_pretrained.side_effect = Exception("Flux Load Error")
    g = media_generator_cls()
    
    with pytest.raises(Exception):
        g.get_flux_pipe()
    mock_FluxPipeline.from_pretrained.side_effect = None

def test_get_ltx_pipe_error(media_generator_cls):
    mock_LTXPipeline.from_pretrained.side_effect = Exception("LTX Load Error")
    g = media_generator_cls()
    
    with pytest.raises(Exception):
        g.get_ltx_pipe()
    mock_LTXPipeline.from_pretrained.side_effect = None

def test_get_ltx_pipe_import_error(media_generator_cls):
    # Simulate LTXVideoPipeline missing from diffusers
    # We create a mock that raises ImportError on access or simply lacks the attribute
    # "from diffusers import LTXVideoPipeline" -> getattr(diffusers, "LTXVideoPipeline")
    
    # We must patch sys.modules["diffusers"] with a mock that raises AttributeError or ImportError
    # But checking getattr usually raises AttributeError, which Python translates to ImportError for "from" imports?
    # No, usually "ImportError: cannot import name..."
    
    # Let's try deleting the attribute from the mock_diffusers temporarily
    orig = mock_diffusers.LTXPipeline
    del mock_diffusers.LTXPipeline
    
    g = media_generator_cls()
    try:
        with pytest.raises(ImportError, match="LTXPipeline not found"):
             g.get_ltx_pipe()
    finally:
        # Restore
        mock_diffusers.LTXPipeline = orig
