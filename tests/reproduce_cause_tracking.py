import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock heavy dependencies BEFORE importing src
from unittest.mock import MagicMock
MOCKED_MODULES = ['psutil', 'neo4j', 'discord', 'discord.ext', 'discord.ext.commands', 'aiohttp']
for m in MOCKED_MODULES:
    sys.modules[m] = MagicMock()

from src.lobes.strategy.prompt_tuner import PromptTunerAbility
from src.tools.lobe_tools import check_prompt_status

async def test_cause_tracking():
    print("Testing Cause Tracking...")
    
    # Mock Bot and Cerebrum
    mock_bot = MagicMock()
    mock_cerebrum = MagicMock()
    mock_bot.cerebrum = mock_cerebrum
    
    # Setup Tuner
    tuner = PromptTunerAbility(mock_cerebrum)
    # Mock the _proposals list since we don't want to read/write real files for a quick test
    tuner._proposals = []
    
    # Inject into globals for the tool to find
    from src.bot import globals
    globals.bot = mock_bot
    mock_cerebrum.get_lobe.return_value.get_ability.return_value = tuner
    
    # 1. Propose an update with a Cause
    print("1. Proposing update with cause='Unit Test Trigger'...")
    proposal = tuner.propose_modification(
        prompt_file="test_identity.txt",
        section="Test Section",
        current_text="Old Text",
        proposed_text="New Text",
        rationale="Testing rationale field",
        operation="replace",
        cause="Unit Test Trigger"  # <--- The new field
    )
    
    print(f"   Proposal Created: {proposal['id']}")
    print(f"   Stored Cause: {proposal.get('cause')}")
    
    if proposal.get('cause') != "Unit Test Trigger":
        print("❌ FAILED: Cause not stored correctly.")
        return

    # 2. Verify check_prompt_status output
    print("\n2. Verifying check_prompt_status output...")
    # The tool reads from tuner.get_recent_proposals
    status_report = await check_prompt_status(limit=1)
    
    print("\n--- Tool Output ---")
    print(status_report)
    print("-------------------")
    
    if "cause: *Unit Test Trigger*" in status_report:
        print("\n✅ SUCCESS: Cause field found in status report.")
    else:
        print("\n❌ FAILED: Cause field NOT found in report.")

if __name__ == "__main__":
    asyncio.run(test_cause_tracking())
