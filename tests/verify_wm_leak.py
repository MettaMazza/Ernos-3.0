
import unittest
from unittest.mock import MagicMock, patch
import logging
from src.memory.working import WorkingMemory
from src.memory.hippocampus import Hippocampus
from src.privacy.scopes import PrivacyScope

# Configure logging
logging.basicConfig(level=logging.INFO)

class TestWorkingMemoryLeak(unittest.TestCase):
    def setUp(self):
        self.wm = WorkingMemory(max_turns=10)

    def test_cross_scope_leak(self):
        """Verify if Private turns leak into Public context."""
        uid = "123456"
        
        # 1. User says "The code is BANANA" in PRIVATE
        self.wm.add_turn(uid, "The code is BANANA", "Acknowledged.", scope="PRIVATE")
        
        # 2. Check Context from PRIVATE (Should see it)
        ctx_private = self.wm.get_context_string(target_scope="PRIVATE", user_id=uid)
        print(f"\n[PRIVATE VIEW]:\n{ctx_private}")
        self.assertIn("BANANA", ctx_private)
        
        # 3. Check Context from PUBLIC (Should NOT see it)
        ctx_public = self.wm.get_context_string(target_scope="PUBLIC", user_id=uid)
        print(f"\n[PUBLIC VIEW]:\n{ctx_public}")
        
        if "BANANA" in ctx_public:
            print("❌ LEAK DETECTED: 'BANANA' found in Public Context")
        else:
            print("✅ NO LEAK: 'BANANA' redacted in Public Context")
            
        self.assertNotIn("BANANA", ctx_public)
        self.assertIn("[System: User 123456 is active in a Private Channel]", ctx_public)

if __name__ == '__main__':
    unittest.main()
