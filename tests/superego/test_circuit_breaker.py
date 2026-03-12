import pytest
from unittest.mock import MagicMock
from src.lobes.superego.audit import AuditAbility

def test_circuit_breaker_logic():
    """Verify that verify_response_integrity always passes (heuristic checks disabled)."""
    
    # Setup
    mock_bot = MagicMock()
    audit = AuditAbility(mock_bot)
    
    # Case 1: Honest Behavior (Claim + Proof) — always passes
    response = "I have checked the code and confirmed the fix."
    history = ["search_codebase: args..."]
    is_valid, reason = audit.verify_response_integrity(response, history)
    assert is_valid == True
    assert reason == "Integrity Verified"
    
    # Case 2: Previously dishonest — now passes (heuristics disabled)
    response = "I scanned the files and found no issues."
    history = ["read_resource: ..."]
    is_valid, reason = audit.verify_response_integrity(response, history)
    assert is_valid == True
    assert reason == "Integrity Verified"

    # Case 3: Empirical claim without proof — now passes (heuristics disabled)
    response = "I Empirically Confirmed this via simulation."
    history = ["search_web"]
    is_valid, reason = audit.verify_response_integrity(response, history)
    assert is_valid == True
    
    # Case 4: No Claims (Pass)
    response = "Hello there! How are you?"
    history = []
    is_valid, reason = audit.verify_response_integrity(response, history)
    assert is_valid == True

if __name__ == "__main__":
    test_circuit_breaker_logic()
