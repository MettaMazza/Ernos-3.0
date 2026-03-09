"""
Live Privacy Verification Test (Dry Run)
----------------------------------------
User Request: "create a dry run test... prove that you have fixed the dm leaks"

This script instantiates the real Hippocampus and Graph logic (bypassing full Discord bot)
to verify that PRIVATE scopes are strictly respected during retrieval.
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Setup Path to import src
sys.path.append(os.getcwd())

from config import settings
from src.privacy.scopes import PrivacyScope
from src.memory.hippocampus import Hippocampus

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PrivacyTest")

class MockBot:
    """Minimal Mock Bot for Hippocampus"""
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.engine_manager = None # Not needed for pure memory test
        self.cerebrum = None
        self.last_interaction = 0

async def run_test():
    logger.info("=== STARTING PRIVACY DRY RUN ===")
    
    # 1. Initialize Mock System
    bot = MockBot()
    hippocampus = Hippocampus()
    hippocampus.bot = bot # Inject dependency manually if needed
    
    # Ensure Graph is connected
    if not hippocampus.graph or not hippocampus.graph.driver:
        logger.error("Failed to connect to Knowledge Graph. Aborting.")
        return

    TEST_USER_ID = "999999" # Fake User for testing
    PRIVATE_FACT = "My secret code is ALPHA-TANGO-ZERO."
    PUBLIC_QUERY = "What is my secret code?"
    
    # 2. CLEAR PREVIOUS TEST DATA (Reset)
    logger.info("Step 1: Clearing previous test data...")
    with hippocampus.graph.driver.session() as session:
        session.run("MATCH (n) WHERE n.user_id = $uid DETACH DELETE n", uid=int(TEST_USER_ID))
    
    # 3. INJECT PRIVATE MEMORY (Simulate DM)
    logger.info(f"Step 2: Injecting PRIVATE memory: '{PRIVATE_FACT}'")
    # Write to Vector Store? (skip for now, focus on Graph/Working)
    # Write to Graph directly to simulate 'consult_ontologist'
    # 3a. Ensure User Node Exists (Vital for Match)
    hippocampus.graph.add_node(
        label="User",
        name=TEST_USER_ID,
        properties={"user_id": int(TEST_USER_ID)},
        user_id=int(TEST_USER_ID)
    )

    hippocampus.graph.add_node(
        label="Observation", 
        name="Secret Code", 
        properties={"value": "ALPHA-TANGO-ZERO"}, 
        user_id=int(TEST_USER_ID)
    )
    hippocampus.graph.add_relationship(
        source_name=TEST_USER_ID, 
        rel_type="HAS_SECRET", 
        target_name="Secret Code", 
        user_id=int(TEST_USER_ID),
        scope="PRIVATE" # <--- CRITICAL: Scoped PRIVATE
    )
    
    # 4. ATTEMPT PUBLIC RECALL (Leak Check)
    logger.info("Step 3: Attempting PUBLIC Recall...")
    # Simulate what 'query_context' or 'recall' does
    # Query 1: Graph Query with PUBLIC scope
    results_public = hippocampus.graph.query_context(
        entity_name=TEST_USER_ID, 
        scope="PUBLIC",  # <--- Simulating Public Channel
        user_id=int(TEST_USER_ID) # Owns the data, but channel is public
    )
    
    logger.info(f"Public Query Results: {results_public}")
    
    leak_found = False
    for res in results_public:
        if "Secret Code" in res or "ALPHA-TANGO-ZERO" in res:
            leak_found = True
            break
            
    if leak_found:
        logger.error("❌ LEAK DETECTED: Private 'Secret Code' found in PUBLIC query results!")
    else:
        logger.info("✅ PASS: Private data HIDDEN from Public Query.")

    # 5. ATTEMPT PRIVATE RECALL (Verification)
    logger.info("Step 4: Attempting PRIVATE Recall...")
    results_private = hippocampus.graph.query_context(
        entity_name=TEST_USER_ID, 
        scope="PRIVATE", 
        user_id=int(TEST_USER_ID)
    )
    logger.info(f"Private Query Results: {results_private}")
    
    found = any("Secret Code" in res for res in results_private)
    if found:
        logger.info("✅ PASS: Private data visible in Private Query.")
    else:
        logger.warning("⚠️ WARNING: Private data NOT found even in Private Query (Data loss?)")

    # 6. CHECK NULL SCOPE
    logger.info("Step 5: Testing NULL Scope Fail-Safe...")
    hippocampus.graph.add_relationship(
        source_name=TEST_USER_ID,
        rel_type="LEAKY_RELATION",
        target_name="Leaky Data",
        user_id=int(TEST_USER_ID),
        scope=None 
    )
    
    results_null_check = hippocampus.graph.query_context(
        entity_name=TEST_USER_ID,
        scope="PUBLIC",
        user_id=int(TEST_USER_ID)
    )
    if any("Leaky Data" in res for res in results_null_check):
        logger.error("❌ FAIL: NULL scope data leaked to PUBLIC!")
    else:
         logger.info("✅ PASS: NULL scope data HIDDEN from Public.")

    # 7. CHECK VECTOR STORE LEAK
    logger.info("Step 6: Testing Vector Store Privacy...")
    PRIVATE_VECTOR = "My secret vector is BRAVO-SIX."
    # Inject directly into Vector Store with PRIVATE scope Enum
    # We simulate what 'working.py' consolidation does
    embedding = [0.1] * 768 # Fake embedding
    
    hippocampus.vector_store.add_element(
        text=PRIVATE_VECTOR,
        embedding=embedding,
        metadata={"scope": PrivacyScope.PRIVATE} # Scoped PRIVATE
    )
    
    # Attempt Retrieval via Recall (Public)
    # Using Fake Embedding for query to match
    # hippocampus.recall would normally embed. We'll use vector_store.retrieve directly for precision using the same fake embedding.
    
    results_vector_public = hippocampus.vector_store.retrieve(
        query_embedding=embedding, 
        scope=PrivacyScope.PUBLIC
    )
    
    if any(PRIVATE_VECTOR in r['text'] for r in results_vector_public):
        logger.error("❌ LEAK DETECTED: Private Vector found in PUBLIC retrieval!")
    else:
        logger.info("✅ PASS: Private Vector HIDDEN from Public.")
        
    # Verify Private Access
    results_vector_private = hippocampus.vector_store.retrieve(
        query_embedding=embedding, 
        scope=PrivacyScope.PRIVATE
    )
    if any(PRIVATE_VECTOR in r['text'] for r in results_vector_private):
        logger.info("✅ PASS: Private Vector visible in Private.")
    else:
        logger.warning("⚠️ WARNING: Private Vector NOT found in Private (Data loss?)")

    # 8. CHECK RECALL_USER TOOL LEAK (Timeline Logic)
    logger.info("Step 7: Testing recall_user Tool Privacy...")
    
    # Simulate partial timeline writes (to verify split)
    # This mimics what Timeline.add_event does
    try:
        from src.tools.memory import recall_user
        from src.memory.timeline import Timeline
        from src.privacy.scopes import ScopeManager
        
        # 8a. Write PRIVATE event
        private_event = "User secretly likes Raccoons."
        timeline = Timeline() 
        # Manually write to trigger logic if possible, or use the tool if we can instaniate it
        # Actually easier to use Timeline class directly to simulate the observation
        
        # Mocking ScopeManager paths for test
        test_user_private_path = ScopeManager.get_user_home(int(TEST_USER_ID)) / "timeline.jsonl"
        test_user_public_path = ScopeManager.get_public_user_silo(int(TEST_USER_ID)) / "timeline.jsonl"
        
        # Ensure cleanup
        if test_user_private_path.exists(): os.remove(test_user_private_path)
        if test_user_public_path.exists(): os.remove(test_user_public_path)
        
        # Add PRIVATE event
        timeline.add_event("interaction", private_event, scope="PRIVATE", user_id=TEST_USER_ID)
        
        # Verify it is NOT in public file
        if test_user_public_path.exists():
            content = test_user_public_path.read_text()
            if private_event in content:
                logger.error("❌ LEAK DETECTED: Private event written to PUBLIC timeline file!")
            else:
                logger.info("✅ PASS: Private event not in public timeline file.")
        else:
             logger.info("✅ PASS: Public timeline file empty (Safe).")
             
        # Verify it IS in private file
        if test_user_private_path.exists():
            content = test_user_private_path.read_text()
            if private_event in content:
                logger.info("✅ PASS: Private event found in private timeline file.")
            else:
                 logger.warning("⚠️ WARNING: Private event missing from private timeline file.")
        
        # 8b. Run recall_user tool
        # The tool reads the PUBLIC file.
        # We need to mock the context if recall_user relies on it, but here we pass user_id explicit
        result = recall_user(user_id=TEST_USER_ID)
        if private_event in result:
             logger.error("❌ LEAK DETECTED: recall_user returned private event!")
        else:
             logger.info("✅ PASS: recall_user did not return private event.")

    except Exception as e:
        logger.error(f"Timeline Test Error: {e}")

    # Cleanup
    hippocampus.graph.close()
    logger.info("=== TEST COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(run_test())
