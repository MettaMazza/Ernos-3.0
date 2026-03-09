
import unittest
from unittest.mock import MagicMock
from src.memory.working import WorkingMemory, Turn
from src.memory.graph import KnowledgeGraph
from src.privacy.scopes import PrivacyScope

class TestLeakRepro(unittest.TestCase):
    def test_working_memory_redaction(self):
        print("\n[TEST] Working Memory Redaction...")
        wm = WorkingMemory()
        
        # Add Private Turn
        wm.add_turn("User1", "My secret is Venus", "Ok secret kept", scope="PRIVATE")
        
        # Get Context for Public
        context = wm.get_context_string(target_scope="PUBLIC", user_id="User1")
        
        print(f"Context (Public): {context}")
        
        if "Venus" in context:
            print("❌ LEAK DETECTED in WorkingMemory!")
            self.fail("Working Memory leaked private content")
        else:
            print("✅ Working Memory Redaction Successful")
            
    def test_graph_scoping(self):
        print("\n[TEST] Graph Scoping...")
        # Mock Graph
        graph = MagicMock()
        
        # Let's verify Ontologist Logic passes the scope
        from src.lobes.memory.ontologist import OntologistAbility
        import asyncio
        
        ability = OntologistAbility(MagicMock()) # lobe
        
        # Call execute with request_scope="PRIVATE"
        # We need to mock globals.bot.hippocampus.graph
        from src.bot import globals
        mock_bot = MagicMock()
        mock_graph = MagicMock()
        mock_bot.hippocampus.graph = mock_graph
        globals.bot = mock_bot
        globals.active_message.set(MagicMock()) # Just to pass checks
        
        asyncio.run(ability.execute("User", "LIKES", "Venus", request_scope="PRIVATE", user_id=123))
        
        # Verify graph.add_relationship called with scope='PRIVATE'
        mock_graph.add_relationship.assert_called()
        call_args = mock_graph.add_relationship.call_args
        kwargs = call_args.kwargs
        props = kwargs.get('props', {})
        
        print(f"Ontologist Kwargs: {kwargs}")
        
        # Check if scope was passed directly OR in props
        passed_scope = kwargs.get('scope') or props.get('scope')
        
        if passed_scope != 'PRIVATE':
             print("❌ LEAK DETECTED in Ontologist (Did not pass scope)")
             self.fail("Ontologist failed to pass PRIVATE scope")
        else:
             print("✅ Ontologist passed PRIVATE scope")

if __name__ == "__main__":
    unittest.main()
