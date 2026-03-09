
import pytest
import time
import shutil
from pathlib import Path
from src.core.flux_capacitor import FluxCapacitor, TIER_LIMITS, CYCLE_DURATION

# Test User ID
TEST_USER = 999999

@pytest.fixture
def flux():
    # Setup: Clean user memory
    user_path = Path(f"memory/users/{TEST_USER}")
    if user_path.exists():
        shutil.rmtree(user_path)
    
    fc = FluxCapacitor()
    # Mock _get_path to use a test-safe directory if needed, 
    # but since we clean the standard path above, standard is fine.
    
    yield fc
    
    # Teardown
    if user_path.exists():
        shutil.rmtree(user_path)

def test_initial_state(flux):
    tier = flux.get_tier(TEST_USER)
    assert tier == 0
    
    status = flux.get_status(TEST_USER)
    assert status["used"] == 0
    assert status["limit"] == 20

def test_consume_basic(flux):
    allowed, warning = flux.consume(TEST_USER)
    assert allowed is True
    assert warning is None
    
    status = flux.get_status(TEST_USER)
    assert status["used"] == 1

def test_warning_trigger(flux):
    # Consume until 4 left (16 messages)
    for _ in range(16):
        flux.consume(TEST_USER)
        
    allowed, warning = flux.consume(TEST_USER) # 17th message (3 left)
    
    assert allowed is True
    assert warning is not None
    assert "Low Energy Warning" in warning
    
    # Next message should NOT warn again (warned=True)
    allowed, warning = flux.consume(TEST_USER) # 18th
    assert allowed is True
    assert warning is None

def test_lockout(flux):
    # Consume all 20
    for _ in range(20):
        flux.consume(TEST_USER)
        
    # 21st attempt
    allowed, warning = flux.consume(TEST_USER)
    assert allowed is False
    assert warning is not None
    assert "Energy depleted" in warning

def test_reset_cycle(flux):
    # 1. deplete
    for _ in range(20):
        flux.consume(TEST_USER)
    
    assert flux.get_status(TEST_USER)["used"] == 20
    
    # 2. manually manipulate file to age limit
    data = flux._load(TEST_USER)
    data["last_reset"] = time.time() - (CYCLE_DURATION + 100) # 12h + 100s ago
    flux._save(TEST_USER, data)
    
    # 3. consume again -> Should trigger reset, allow message (count becomes 1)
    allowed, warning = flux.consume(TEST_USER)
    
    assert allowed is True
    status = flux.get_status(TEST_USER)
    assert status["used"] == 1
    assert warning is None # Should not warn immediately on reset

def test_tier_upgrade(flux):
    flux.set_tier(TEST_USER, 1) # Pollinator
    assert flux.get_tier(TEST_USER) == 1
    
    # Verify limit is high
    limit = TIER_LIMITS[1]
    assert limit > 20
    
    status = flux.get_status(TEST_USER)
    assert status["limit"] == limit
