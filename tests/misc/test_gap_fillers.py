import pytest
import re
import os
import json
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from src.voice.synthesizer import AudioSynthesizer
from src.prompts.manager import PromptManager
from src.memory.timeline import Timeline
from src.privacy.scopes import ScopeManager, PrivacyScope
from config import settings

# --- Voice: Synthesizer ---

def test_synthesizer_sanitize():
    synth = AudioSynthesizer()
    text = "Hello #world! This is *bold* and [link](http://test.com) :smile:"
    sanitized = synth._sanitize_text(text)
    
    # regex sub removes #, *, [, ], (, )
    # removes http...
    # should be "Hello world! This is bold and link :smile:" (if emoji logic allows)
    # The code removes # * _ ( ) [ ]
    # It removes http\S+
    
    # http://test.com is removed.
    # [link] -> link
    # (http://test.com) -> removed part of link regex or paren regex?
    # Code: r'[\#\*\_\(\)\[\]]' replaced by empty.
    # Code: r'http\S+' replaced by empty.
    
    assert "bold" in sanitized
    assert "world" in sanitized
    assert "#" not in sanitized
    assert "*" not in sanitized
    assert "http" not in sanitized

@pytest.mark.asyncio
async def test_generate_audio_gap(mocker, tmp_path):
    # Test missing text
    synth = AudioSynthesizer()
    assert await synth.generate_audio("", "out.wav") is None
    
    # Test missing kokoro (simulated)
    synth.kokoro = None
    assert await synth.generate_audio("test", "out.wav") is None

    # Test success flow (mock thread)
    synth.kokoro = MagicMock()
    
    mocker.patch("asyncio.to_thread", new_callable=AsyncMock)
    # First call: create -> (samples, rate)
    # Second call: write
    
    async def side_effect(func, *args, **kwargs):
        if func == synth.kokoro.create:
            return ([1,2,3], 24000)
        return None
    
    # asyncio.to_thread is patched globally?
    # mocker.patch("asyncio.to_thread", side_effect=side_effect) 
    # But side_effect needs to handle different funcs.
    
    # Lets just mock the methods on to_thread
    with patch("asyncio.to_thread", side_effect=side_effect):
        res = await synth.generate_audio("test", "out.wav")
        assert res == "out.wav"

# --- Prompts: Manager ---

def test_prompt_manager_read_file_error(mocker, tmp_path):
    pm = PromptManager()
    # Mock open raising error
    mocker.patch("builtins.open", side_effect=OSError("Read Fail"))
    content = pm._read_file("fake.txt")
    assert content == ""

def test_get_system_prompt_gaps(mocker):
    # Test logging awareness failure
    pm = PromptManager()
    pm._read_file = MagicMock(return_value="template")
    
    # Mock logs existence
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", side_effect=Exception("Access Denied"))
    
    # Should not crash, returns partial
    res = pm.get_system_prompt()
    assert "template" in res

# --- Memory: Timeline ---

def test_timeline_add_event_fail(mocker):
    mocker.patch("os.makedirs")
    tl = Timeline("test.json")
    mocker.patch("builtins.open", side_effect=Exception("Write Fail"))
    # Should log error but not crash
    tl.add_event("type", "desc")
    assert True  # No exception: error handled gracefully

def test_timeline_get_events_corrupt(mocker, tmp_path):
    f = tmp_path / "timeline.jsonl"
    f.write_text('{"good": "json"}\n{corrupt json\n{"good": "json"}', encoding="utf-8")
    
    tl = Timeline(str(f))
    events = tl.get_recent_events()
    # Should skip corrupt line
    assert len(events) == 2

# --- Scopes ---

    # scopes.py is 93% covered already.

# --- Interaction: Reasoning ---
from src.lobes.interaction.reasoning import DeepReasoningAbility

@pytest.mark.asyncio
async def test_deep_reasoning_execute():
    lobe = MagicMock()
    # Mock bot engine
    engine = MagicMock()
    engine.generate_response.return_value = "Deep Thought"
    lobe.cerebrum.bot.engine_manager.get_active_engine.return_value = engine
    lobe.cerebrum.bot.loop.run_in_executor = AsyncMock(return_value="Deep Thought")
    
    reasoning = DeepReasoningAbility(lobe)
    res = await reasoning.execute("Problem")
    
    assert "DEEP THOUGHT" in res
    assert "Deep Thought" in res
    lobe.cerebrum.bot.loop.run_in_executor.assert_awaited()

# --- Voice: Synthesizer Edge Cases ---
from unittest.mock import patch
import sys

def test_synthesizer_import_error(mocker):
    # Simulate kokoro import failure
    with patch.dict(sys.modules, {"kokoro_onnx": None}):
        # Force reload or manually check logic?
        # The module level try/except runs at IMPORT time.
        # Hard to test module-level import error after import.
        # But we can test the __init__ logic if KOKORO_AVAILABLE was False.
        
        # We can modify the global variable in the module
        with patch("src.voice.synthesizer.KOKORO_AVAILABLE", False):
            synth = AudioSynthesizer()
            assert synth.kokoro is None

def test_synthesizer_paths_missing(mocker):
    with patch("src.voice.synthesizer.KOKORO_AVAILABLE", True):
        # Mock os.path.exists to False
        mocker.patch("os.path.exists", return_value=False)
        synth = AudioSynthesizer()
        assert synth.kokoro is None
