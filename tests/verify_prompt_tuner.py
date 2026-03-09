
import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
import json

# Add project root to path
sys.path.append(os.getcwd())

# Mock psutil to avoid dependency error in performance.py
sys.modules["psutil"] = MagicMock()
# Mock neo4j for KnowledgeGraph dependency
sys.modules["neo4j"] = MagicMock()

from src.lobes.strategy.prompt_tuner import PromptTunerAbility
from src.lobes.base import BaseLobe

# Mock classes to simulate environment
class MockBot:
    def __init__(self):
        self.cerebrum = MagicMock()
        self.cerebrum.bot = self

class MockLobe(BaseLobe):
    def _register_abilities(self):
        pass

async def test_prompt_tuner_flow():
    print("🧪 Starting PromptTuner Integration Test...")
    
    # Setup
    bot = MockBot()
    lobe = MockLobe(bot.cerebrum)
    
    # Initialize Ability
    tuner = PromptTunerAbility(lobe)
    
    # Mock file operations to prevent actual file writes during test
    tuner._save_state = MagicMock()
    
    # 1. Test Proposal
    print("\n1️⃣  Testing Proposal Creation...")
    proposal = tuner.propose_modification(
        prompt_file="test_prompt.txt",
        section="TEST_SECTION",
        current_text="Old text",
        proposed_text="New text",
        rationale="Testing self-update"
    )
    
    print(f"   Shape: {proposal.keys()}")
    assert proposal["status"] == "pending"
    assert proposal["proposed_text"] == "New text"
    pid = proposal["id"]
    print(f"✅ Proposal Created: {pid}")
    
    # 2. Test Get Pending
    print("\n2️⃣  Testing Get Pending...")
    pending = tuner.get_pending()
    assert len(pending) == 1
    assert pending[0]["id"] == pid
    print(f"✅ Pending list correct (Count: {len(pending)})")
    
    # 3. Test Approval
    print("\n3️⃣  Testing Approval...")
    # Mock _apply_modification since we don't want to write real files
    tuner._apply_modification = MagicMock(return_value=True)
    
    success = tuner.approve_modification(pid, "admin_user_1")
    
    assert success is True
    assert tuner._proposals[0]["status"] == "approved"
    tuner._apply_modification.assert_called_once()
    print("✅ Approval successful and apply triggered")
    
    # 4. Test Rejection
    print("\n4️⃣  Testing Rejection...")
    # Create another proposal
    prop2 = tuner.propose_modification("f2", "s2", "c2", "p2", "r2")
    pid2 = prop2["id"]
    
    success = tuner.reject_modification(pid2, "Bad idea")
    
    assert success is True
    assert tuner._proposals[1]["status"] == "rejected"
    print("✅ Rejection successful")

    print("\n🎉 All PromptTuner logic checks passed!")

if __name__ == "__main__":
    asyncio.run(test_prompt_tuner_flow())
