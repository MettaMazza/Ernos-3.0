import logging
from src.memory.graph import KnowledgeGraph
from src.memory.vector import InMemoryVectorStore # Assuming we can inspect the singleton?
# Actually InMemoryVectorStore is instance-based in Hippocampus. 
# We can't easily inspect the running instance's memory from a script unless it's persisted.

# But Graph is persistent!
logging.basicConfig(level=logging.INFO)

def check_sunny():
    print("--- Checking 'Sunny' in Graph ---")
    graph = KnowledgeGraph()
    try:
        with graph.driver.session() as session:
            # Check Graph
            res = session.run("MATCH (n)-[r]-(m) WHERE m.name CONTAINS 'Sunny' OR n.name CONTAINS 'Sunny' RETURN n, r, m")
            found = list(res)
            if found:
                for record in found:
                    print(f"⚠️ FOUND in GRAPH: {record['n'].get('name')} -[{record['r'].type}]-> {record['m'].get('name')}")
                    print(f"   Scope: {record['r'].get('scope')} (Expected PRIVATE?)")
            else:
                print("✅ 'Sunny' NOT found in Graph.")
                
    except Exception as e:
        print(f"Graph check failed: {e}")
    finally:
        graph.close()

if __name__ == "__main__":
    check_sunny()
