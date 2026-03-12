import logging
from src.memory.graph import KnowledgeGraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Purge")

def purge_et():
    print("--- Purging 'E.T.' from Graph ---")
    graph = KnowledgeGraph()
    try:
        with graph.driver.session() as session:
            # 1. Check existence
            res = session.run("MATCH (n)-[r]-(m) WHERE m.name CONTAINS 'E.T.' RETURN r, m")
            found = list(res)
            if not found:
                print("No 'E.T.' relationships found to purge.")
            else:
                print(f"Found {len(found)} relationships. Deleting...")
                
            # 2. Delete Relationships
            session.run("MATCH (n)-[r]-(m) WHERE m.name CONTAINS 'E.T.' DELETE r")
            print("Relationships deleted.")
            
            # 3. Delete Node if orphan
            session.run("MATCH (n) WHERE n.name CONTAINS 'E.T.' AND NOT (n)--() DELETE n")
            print("Orphan 'E.T.' nodes deleted.")
            
    except Exception as e:
        print(f"Purge failed: {e}")
    finally:
        graph.close()

if __name__ == "__main__":
    purge_et()
