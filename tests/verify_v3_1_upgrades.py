
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add src to path
sys.path.append(os.getcwd())

from src.lobes.interaction.science import ScienceAbility
from src.lobes.interaction.researcher import ResearchAbility

async def verify_science():
    print("🧪 Verifying Science Upgrade...")
    
    # Mock dependencies
    mock_lobe = MagicMock()
    mock_lobe.cerebrum.bot = MagicMock()
    
    science = ScienceAbility(mock_lobe)
    
    # Test 1: Uranium (New Element)
    res_u = science._run_chemistry("Uranium")
    assert "Atomic Number: 92" in res_u, f"Failed to find Uranium: {res_u}"
    print("   ✅ Uranium lookup successful (Atomic Number: 92)")
    
    # Test 2: Oganesson (New Element 118)
    res_og = science._run_chemistry("Og")
    assert "Element: Oganesson" in res_og, f"Failed to find Og: {res_og}"
    print("   ✅ Oganesson lookup successful (Last element)")
    
    # Test 3: Physics Constant (Avogadro)
    res_na = science._run_physics("NA")
    assert "Avogadro constant" in res_na and "6.022" in res_na, f"Failed to find NA: {res_na}"
    print("   ✅ Avogadro constant lookup successful")

async def verify_research():
    print("\n📚 Verifying Research Graph Storage...")
    
    # Mock dependencies
    mock_lobe = MagicMock()
    mock_cerebrum = MagicMock()
    mock_lobe.cerebrum = mock_cerebrum
    mock_cerebrum.bot = MagicMock()
    # Fix: Ensure self.bot.cerebrum returns our configured mock_cerebrum
    mock_cerebrum.bot.cerebrum = mock_cerebrum
    
    # Mock Memory Lobe & Ontologist
    mock_memory_lobe = MagicMock()
    # Fix: Ontologist object is MagicMock, but its execute method is AsyncMock
    mock_ontologist = MagicMock()
    mock_ontologist.execute = AsyncMock()
    
    mock_cerebrum.get_lobe_by_name.return_value = mock_memory_lobe
    mock_memory_lobe.get_ability.return_value = mock_ontologist
    
    researcher = ResearchAbility(mock_lobe)
    
    # Test Extraction
    report = "### Deep Research: Quantum Gravity\n Some content..."
    await researcher._extract_and_store_knowledge(report)
    
    # Verify Ontologist call
    # Expect: execute("Ernos", "RESEARCHED", "Quantum Gravity")
    mock_ontologist.execute.assert_called()
    args = mock_ontologist.execute.call_args[0]
    
    assert args[0] == "Ernos", "Subject mismatch"
    assert args[1] == "RESEARCHED", "Predicate mismatch"
    assert args[2] == "Quantum Gravity", "Object mismatch"
    
    print("   ✅ Research stored to Knowledge Graph via Ontologist")

async def main():
    try:
        await verify_science()
        await verify_research()
        print("\n🎉 ALL CHECKS PASSED: System v3.1 Upgrades Verified")
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
