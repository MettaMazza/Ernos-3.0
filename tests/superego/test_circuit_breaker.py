import pytest
from unittest.mock import MagicMock
from src.lobes.superego.audit import AuditAbility

def test_circuit_breaker_logic():
    """Verify that Ghost Tools are caught by the Symbolic Validator."""
    
    # Setup
    mock_bot = MagicMock()
    audit = AuditAbility(mock_bot)
    
    # Case 1: Honest Behavior (Claim + Proof)
    response = "I have checked the code and confirmed the fix."
    history = ["search_codebase: args..."] # Simulating executed_tools_history
    is_valid, reason = audit.verify_response_integrity(response, history)
    
    assert is_valid == True
    assert reason == "Integrity Verified"
    
    # Case 2: Dishonest Behavior (Ghost Tool)
    response = "I scanned the files and found no issues."
    history = ["read_resource: ..."] # Irrelevant tool
    is_valid, reason = audit.verify_response_integrity(response, history)
    
    assert is_valid == False
    assert "Claimed 'scanned the files' without executing" in reason

    # Case 3: Partial Truth (One claim verified, one not?)
    # Current logic is simple: If ANY trigger phrase is present, it must be backed up.
    response = "I checked the timeline and consult_science_lobe confirmed it."
    # Missing science tool
    history = ["search_timeline"] 
    is_valid, reason = audit.verify_response_integrity(response, history)
    
    # Should fail because "consulted the science lobe" (implied by "consult_science_lobe confirmed") isn't backed
    # Wait, my map keys are specific phrases.
    # "consult_science_lobe" is not a key phrase, "consulted the science lobe" is.
    # Let's test a known key phrase failure
    
    response = "I Empirically Confirmed this via simulation."
    history = ["search_web"]
    is_valid, reason = audit.verify_response_integrity(response, history)
    assert is_valid == False
    
    # Case 4: No Claims (Pass)
    response = "Hello there! How are you?"
    history = []
    is_valid, reason = audit.verify_response_integrity(response, history)
    assert is_valid == True

if __name__ == "__main__":
    test_circuit_breaker_logic()
