from ..base import BaseAbility
import logging
import os
from src.memory.graph import KnowledgeGraph

logger = logging.getLogger("Lobe.Strategy.Gardener")

class GardenerAbility(BaseAbility):
    """
    The Gardener maintains code health.
    It analyzes structure, suggests refactors, and identifies dead code.
    """
    def __init__(self, lobe):
        super().__init__(lobe)
        self.graph = KnowledgeGraph() # Use the driver wrapper

    async def refine_graph(self) -> str:
        """
        Scans Neo4j for duplicate nodes (e.g., 'Apple' vs 'Apple Inc').
        Uses Levenshtein distance for fuzzy matching.
        Auto-merges high confidence (>0.9) duplicates.
        """
        logger.info("Gardener: Refining Graph...")
        
        results = ["### Graph Refinement Report"]
        duplicates_found = 0
        auto_merged = 0
        manual_review = []
        
        try:
            # 1. Fetch all node names from Neo4j
            with self.graph.driver.session() as session:
                cypher = """
                MATCH (n)
                WHERE n.name IS NOT NULL
                RETURN DISTINCT n.name as name, elementId(n) as id, labels(n) as labels
                ORDER BY n.name
                """
                result = session.run(cypher)
                nodes = [{"name": r["name"], "id": r["id"], "labels": r["labels"]} for r in result]
            
            if not nodes:
                return "Graph is empty - no nodes to refine."
            
            results.append(f"**Scanned**: {len(nodes)} nodes")
            
            # 2. Find potential duplicates using fuzzy matching
            seen_pairs = set()
            for i, node1 in enumerate(nodes):
                for j, node2 in enumerate(nodes):
                    if i >= j:
                        continue
                    if (node1["id"], node2["id"]) in seen_pairs:
                        continue
                    seen_pairs.add((node1["id"], node2["id"]))
                    
                    # Only compare nodes with same labels
                    if set(node1["labels"]) != set(node2["labels"]):
                        continue
                    
                    # Calculate similarity
                    similarity = self._string_similarity(node1["name"], node2["name"])
                    
                    if similarity > 0.8:  # Potential duplicate
                        duplicates_found += 1
                        
                        if similarity > 0.95:
                            # Auto-merge (very high confidence)
                            try:
                                self._merge_nodes(node1["id"], node2["id"])
                                auto_merged += 1
                                logger.info(f"Auto-merged: '{node2['name']}' → '{node1['name']}' (sim={similarity:.2f})")
                            except Exception as e:
                                manual_review.append((node1, node2, similarity))
                                logger.warning(f"Auto-merge failed: {e}")
                        else:
                            # Needs manual review
                            manual_review.append((node1, node2, similarity))
            
            # 3. Build report
            results.append(f"**Duplicates Found**: {duplicates_found}")
            results.append(f"**Auto-Merged**: {auto_merged}")
            
            if manual_review:
                results.append(f"\n⚠️ **Needs Manual Review** ({len(manual_review)}):")
                for n1, n2, sim in manual_review[:10]:  # Limit display
                    results.append(f"- '{n1['name']}' ↔ '{n2['name']}' ({sim:.0%})")
                if len(manual_review) > 10:
                    results.append(f"  ... and {len(manual_review) - 10} more")
            else:
                if duplicates_found == 0:
                    results.append("\n✅ No duplicates detected.")
                else:
                    results.append("\n✅ All duplicates auto-merged.")
            
            return "\n".join(results)
            
        except Exception as e:
            logger.error(f"Graph refinement failed: {e}")
            return f"❌ Graph refinement failed: {e}"

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings using Levenshtein distance."""
        if not s1 or not s2:
            return 0.0
        
        # Normalize strings
        s1 = s1.lower().strip()
        s2 = s2.lower().strip()
        
        if s1 == s2:
            return 1.0
        
        # Calculate Levenshtein distance
        len1, len2 = len(s1), len(s2)
        if len1 < len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1
        
        # Early termination for very different lengths
        if len1 - len2 > max(len1, len2) * 0.3:
            return 0.0
        
        # Use dynamic programming for Levenshtein
        previous_row = range(len2 + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        distance = previous_row[-1]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len)


    def _merge_nodes(self, keep_id: str, merge_id: str):
        """
        Uses Cypher to move relationships and delete the duplicate.
        """
        query = """
        MATCH (k), (m)
        WHERE elementId(k) = $keep_id AND elementId(m) = $merge_id
        CALL apoc.refactor.mergeNodes([k, m]) YIELD node
        RETURN node
        """
        try:
            with self.graph.driver.session() as session:
                # Requires APOC. If not available, we do manual rel move.
                # Fallback Manual Move:
                session.run("""
                MATCH (m)-[r]->(t)
                WHERE elementId(m) = $merge_id
                MATCH (k) WHERE elementId(k) = $keep_id
                MERGE (k)-[:REL {type: type(r)}]->(t)
                DELETE r
                """, keep_id=keep_id, merge_id=merge_id)
                
                session.run("MATCH (m) WHERE elementId(m) = $merge_id DELETE m", merge_id=merge_id)
                
            logger.info(f"Merged node {merge_id} into {keep_id}")
        except Exception as e:
            logger.error(f"Merge Failed: {e}")

    
    async def execute(self, instruction: str) -> str:
        logger.info(f"Gardener executing: {instruction}")
        
        # Simple heuristic analysis for now
        # In the future, this could use AST parsing
        
        report = []
        report.append(f"### Gardener Analysis: {instruction}")
        
        # 1. Count Lines
        total_lines = 0
        total_files = 0
        for root, _, files in os.walk("src"):
            for file in files:
                if file.endswith(".py"):
                    total_files += 1
                    with open(os.path.join(root, file), "r", errors="ignore") as f:
                        total_lines += len(f.readlines())
        
        report.append(f"- **Codebase Scale**: {total_files} files, {total_lines} lines.")
        
        # 2. Check for large files
        report.append("- **Complexity Check**:")
        for root, _, files in os.walk("src"):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    with open(path, "r", errors="ignore") as f:
                        lc = len(f.readlines())
                        if lc > 200:
                            report.append(f"  - ⚠️ {file}: {lc} lines (Consider refactoring)")
                            
        return "\n".join(report)
