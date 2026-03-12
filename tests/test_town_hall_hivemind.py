"""
Test: Town Hall Hive-Mind Integration

Verifies that Town Hall personas route through the full CognitionEngine pipeline
instead of making raw LLM calls. Tests:
1. CognitionEngine.process() is called (not raw engine.generate_response)
2. Persona identity is correctly injected (no Ernos identity leak)
3. request_scope is PUBLIC
4. user_id is "persona:<name>"
5. Superego identity check is skipped for persona user_ids
"""
import pytest
import asyncio
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# --- Test 1: Town Hall routes through CognitionEngine ---

@pytest.mark.asyncio
async def test_town_hall_uses_cognition_engine():
    """Town Hall must call CognitionEngine.process(), not raw LLM."""
    from src.daemons.town_hall import TownHallDaemon, PersonaAgent
    
    # Setup mock bot 
    bot = MagicMock()
    bot.tape_engine = AsyncMock()
    bot.cognition.process = AsyncMock(return_value=("Hello from persona!", [], []))
    bot.cognition.process = AsyncMock(return_value=("Hello from persona!", [], []))
    
    mock_engine = MagicMock()
    mock_engine.__class__.__name__ = "TestEngine"
    bot.engine_manager.get_active_engine.return_value = mock_engine
    
    daemon = TownHallDaemon(bot)
    daemon._topic = "What is consciousness?"
    
    # Create a test persona
    speaker = PersonaAgent("test-hivemind-agent")
    # Write a character file
    persona_file = speaker._home / "persona.txt"
    persona_file.write_text("I am TestBot, a curious thinker.")
    
    try:
        # Mock PromptManager to avoid file dependencies
        with patch("src.prompts.manager.PromptManager") as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_system_prompt.return_value = "SYSTEM PROMPT"
            MockPM.return_value = mock_pm_instance
            
            response = await daemon._generate_persona_response(speaker)
        
        # MUST have called CognitionEngine.process
        bot.cognition.process.assert_called_once()
        
        # MUST NOT have called raw engine.generate_response
        mock_engine.generate_response.assert_not_called()
        
        assert response == "Hello from persona!"
    finally:
        if speaker._home.exists():
            shutil.rmtree(speaker._home)


# --- Test 2: Persona identity is injected, Ernos identity is NOT ---

@pytest.mark.asyncio 
async def test_town_hall_injects_persona_identity():
    """Town Hall must inject persona's identity, not Ernos's."""
    from src.daemons.town_hall import TownHallDaemon, PersonaAgent
    
    bot = MagicMock()
    bot.tape_engine = AsyncMock()
    bot.cognition.process = AsyncMock(return_value=("Response", [], []))
    bot.cognition.process = AsyncMock(return_value=("Response", [], []))
    
    mock_engine = MagicMock()
    mock_engine.__class__.__name__ = "TestEngine"
    bot.engine_manager.get_active_engine.return_value = mock_engine
    
    daemon = TownHallDaemon(bot)
    daemon._topic = "Test topic"
    
    speaker = PersonaAgent("identity-test-persona")
    persona_file = speaker._home / "persona.txt"
    persona_file.write_text("I am IdentityTestBot, unique and distinct.")
    
    try:
        with patch("src.prompts.manager.PromptManager") as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_system_prompt.return_value = "KERNEL + ARCH"
            MockPM.return_value = mock_pm_instance
            
            await daemon._generate_persona_response(speaker)
        
        # Check that identity_core_file was overridden to persona's file
        assert mock_pm_instance.identity_core_file != "src/prompts/identity_core.txt", \
            "identity_core_file should be overridden to persona's file"
        
        # Check that identity file was blanked
        assert mock_pm_instance.identity_file == "", \
            "Legacy identity_file should be blanked to prevent leaks"
    finally:
        if speaker._home.exists():
            shutil.rmtree(speaker._home)


# --- Test 3: Correct scope and user_id ---

@pytest.mark.asyncio
async def test_town_hall_scope_and_user_id():
    """Town Hall must pass request_scope=PUBLIC and user_id=persona:<name>."""
    from src.daemons.town_hall import TownHallDaemon, PersonaAgent
    
    bot = MagicMock()
    bot.tape_engine = AsyncMock()
    bot.cognition.process = AsyncMock(return_value=("Response", [], []))
    bot.cognition.process = AsyncMock(return_value=("Response", [], []))
    
    mock_engine = MagicMock()
    mock_engine.__class__.__name__ = "TestEngine"
    bot.engine_manager.get_active_engine.return_value = mock_engine
    
    daemon = TownHallDaemon(bot)
    daemon._topic = "Test topic"
    
    speaker = PersonaAgent("scope-test-bot")
    persona_file = speaker._home / "persona.txt"
    persona_file.write_text("I am ScopeTestBot.")
    
    try:
        with patch("src.prompts.manager.PromptManager") as MockPM:
            mock_pm_instance = MagicMock()
            mock_pm_instance.get_system_prompt.return_value = "SYSTEM"
            MockPM.return_value = mock_pm_instance
            
            await daemon._generate_persona_response(speaker)
        
        # Verify CognitionEngine was called with correct scope params
        call_kwargs = bot.cognition.process.call_args[1]
        
        assert call_kwargs["request_scope"] == "PUBLIC", \
            f"Expected PUBLIC scope, got {call_kwargs['request_scope']}"
        
        assert call_kwargs["user_id"] == "persona:scope-test-bot", \
            f"Expected persona:scope-test-bot, got {call_kwargs['user_id']}"
        
        assert call_kwargs["skip_defenses"] == False, \
            "Skeptic audit should NOT be skipped for personas"
    finally:
        if speaker._home.exists():
            shutil.rmtree(speaker._home)


# --- Test 4: Superego receives persona identity (not bypassed) ---

def test_superego_receives_persona_identity():
    """IdentityAbility must accept persona_identity and build audit accordingly."""
    from src.lobes.superego.identity import IdentityAbility
    
    ability = IdentityAbility.__new__(IdentityAbility)
    
    # Verify it accepts persona_identity parameter
    import inspect
    sig = inspect.signature(ability.execute)
    assert "persona_identity" in sig.parameters, \
        "IdentityAbility.execute must accept persona_identity parameter"
    
    # Verify default is None (backward-compatible for Ernos)
    assert sig.parameters["persona_identity"].default is None, \
        "persona_identity should default to None for backward compatibility"


def test_superego_persona_agnostic_not_bypassed():
    """CognitionEngine must NOT bypass Superego for persona:* user_ids."""
    # Read the cognition.py source to verify no bypass logic remains
    from pathlib import Path
    source = Path("src/engines/cognition.py").read_text()
    
    assert "skip_identity" not in source, \
        "skip_identity bypass logic should be removed — Superego is persona-agnostic now"


# --- Test 5: Fallback works when CognitionEngine is unavailable ---

@pytest.mark.asyncio
async def test_town_hall_fallback_when_no_cognition():
    """Town Hall must fall back to raw LLM when CognitionEngine is None."""
    from src.daemons.town_hall import TownHallDaemon, PersonaAgent
    
    bot = MagicMock()
    bot.tape_engine = None  # No cognition engine
    bot.loop = asyncio.get_event_loop()
    
    mock_engine = MagicMock()
    mock_engine.generate_response.return_value = "Fallback response"
    bot.engine_manager.get_active_engine.return_value = mock_engine
    
    daemon = TownHallDaemon(bot)
    daemon._topic = "Fallback test"
    
    speaker = PersonaAgent("fallback-test-bot")
    persona_file = speaker._home / "persona.txt"
    persona_file.write_text("I am FallbackBot.")
    
    try:
        response = await daemon._generate_persona_response(speaker)
        
        assert response == "Fallback response"
        # Should have used raw engine, not cognition
        mock_engine.generate_response.assert_called_once()
    finally:
        if speaker._home.exists():
            shutil.rmtree(speaker._home)
