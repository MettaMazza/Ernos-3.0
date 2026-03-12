import os
import shutil
import logging
import sys

# Add src to path to import settings
sys.path.append(os.getcwd())

try:
    from config import settings
    from neo4j import GraphDatabase
except ImportError:
    print("CRITICAL: Missing dependencies. Run `pip install -r requirements.txt`")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CycleReset")

TARGET_DIRS = [
    "memory/users",
    "memory/core",
    "memory/public",
    "memory/system"
]

TARGET_FILES = [
    "ernos_bot.log",
    "session.log"
]

def wipe_structure():
    print(">>> PHASE 1: FILE SYSTEM WIPE")
    for d in TARGET_DIRS:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                logger.info(f"Deleted Directory: {d}")
            except Exception as e:
                logger.error(f"Failed to delete {d}: {e}")
        
    for f in TARGET_FILES:
        if os.path.exists(f):
            try:
                os.remove(f)
                logger.info(f"Deleted File: {f}")
            except Exception as e:
                logger.error(f"Failed to delete {f}: {e}")

    # Recreate empty structure
    print(">>> PHASE 2: STRUCTURE REBUILD")
    os.makedirs("memory/users", exist_ok=True)
    os.makedirs("memory/core", exist_ok=True)
    os.makedirs("memory/public", exist_ok=True)
    logger.info("Memory structure retained.")

def wipe_graph():
    print(">>> PHASE 3: KNOWLEDGE GRAPH WIPE (NEO4J)")
    uri = settings.NEO4J_URI
    user = settings.NEO4J_USER
    password = settings.NEO4J_PASSWORD
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # COUNT first
            count = session.run("MATCH (n) RETURN count(n) as c").single()['c']
            print(f"Nodes identified for destruction: {count}")
            
            if count > 0:
                session.run("MATCH (n) DETACH DELETE n")
                logger.info("Neo4j Graph CLEARED.")
            else:
                logger.info("Neo4j Graph already empty.")
        driver.close()
    except Exception as e:
        logger.error(f"Neo4j Wipe Failed: {e}")

def main():
    print("!"*60)
    print("WARNING: ERNOS 3.0 CYCLE RESET PROTOCOL")
    print("This will PERMANENTLY DELETE all memory, logs, and graph data.")
    print("!"*60)
    confirm = input("Type 'TABULA RASA' to confirm: ")
    
    if confirm == "TABULA RASA":
        # PRE-RESET: Export user contexts to DMs (rate limited)
        print(">>> PHASE 0: USER CONTEXT PRESERVATION")
        try:
            import asyncio
            from src.backup.manager import BackupManager
            backup_mgr = BackupManager()
            # Note: This is synchronous context, so we create a new loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            backed_up = loop.run_until_complete(backup_mgr.export_all_users_on_reset())
            loop.close()
            print(f"User contexts backed up: {backed_up} users")
        except Exception as e:
            logger.warning(f"Pre-reset backup skipped: {e}")
        
        wipe_structure()
        wipe_graph()
        print("\nCYCLE RESET COMPLETE. System is clean.")
    else:
        print("Reset Aborted.")

if __name__ == "__main__":
    main()
