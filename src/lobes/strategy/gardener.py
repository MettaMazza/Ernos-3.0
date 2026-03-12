from ..base import BaseAbility
import logging
import json
import os
import asyncio
from src.memory.graph import KnowledgeGraph

logger = logging.getLogger("Lobe.Strategy.Gardener")

class GardenerAbility(BaseAbility):
    """
    The Gardener maintains KG health and code health.
    
    Capabilities:
        - refine_graph(): Deduplicate near-identical nodes via Levenshtein
        - connect_graph(): Discover and create missing relationships between under-connected nodes
        - execute(): Code health analysis (file counts, large file detection)
    """
    def __init__(self, lobe):
        super().__init__(lobe)
        self.graph = KnowledgeGraph()  # Use the driver wrapper

    # ═══════════════════════════════════════════════════════════════
    #  KG CONNECTOR — Relationship Discovery & Creation
    # ═══════════════════════════════════════════════════════════════

    async def connect_graph(self, max_candidates: int = 50) -> str:
        """
        Scans the KG for under-connected or isolated nodes and uses the LLM
        to discover missing relationships. Each proposed connection is routed
        through OntologistAbility for validation, contradiction checking,
        and confidence scoring before storage.

        Pipeline:
            1. Cypher scan for low-connectivity nodes
            2. Candidate pair selection (shared neighbors, same layer, semantic proximity)
            3. LLM-based relationship inference
            4. OntologistAbility validation + storage
        """
        logger.info("Gardener: Starting KG connection discovery...")

        results = ["### KG Connection Discovery Report"]
        new_connections = 0
        candidates_evaluated = 0

        try:
            # ── Phase 1: Graph Scan ──────────────────────────────
            with self.graph.driver.session() as session:
                cypher = """
                MATCH (n)
                WHERE n.name IS NOT NULL
                  AND NOT n.name STARTS WITH 'Root:'
                  AND NOT n.name STARTS WITH 'Layer:'
                OPTIONAL MATCH (n)-[r]-(m)
                WITH n, 
                     collect(DISTINCT m.name) AS neighbors,
                     count(r) AS degree,
                     labels(n) AS node_labels,
                     n.layer AS node_layer
                WHERE degree <= 2
                RETURN n.name AS name, 
                       node_labels AS labels, 
                       node_layer AS layer,
                       neighbors,
                       degree
                ORDER BY degree ASC
                LIMIT 200
                """
                result = session.run(cypher)
                low_connectivity = [
                    {
                        "name": r["name"],
                        "labels": r["labels"],
                        "layer": r["layer"],
                        "neighbors": [n for n in r["neighbors"] if n],
                        "degree": r["degree"],
                    }
                    for r in result
                ]

            if not low_connectivity:
                return "✅ Graph is well-connected — no isolated or under-connected nodes found."

            results.append(f"**Scanned**: {len(low_connectivity)} low-connectivity nodes (degree ≤ 2)")

            # ── Phase 2: Candidate Pair Selection ────────────────
            candidates = self._select_candidate_pairs(low_connectivity, max_candidates)

            if not candidates:
                results.append("✅ No viable candidate pairs found for connection.")
                return "\n".join(results)

            results.append(f"**Candidate Pairs**: {len(candidates)}")

            # ── Phase 3: LLM Relationship Inference ──────────────
            from src.bot import globals

            engine = (
                globals.bot.engine_manager.get_active_engine()
                if globals.bot else None
            )
            if not engine:
                results.append("⚠️ No active LLM engine — cannot infer relationships.")
                return "\n".join(results)

            # Process in batches of 10
            proposed_triples = []
            for batch_start in range(0, len(candidates), 10):
                batch = candidates[batch_start:batch_start + 10]
                batch_triples = await self._infer_relationships(engine, batch)
                proposed_triples.extend(batch_triples)
                candidates_evaluated += len(batch)

            results.append(f"**Proposed Connections**: {len(proposed_triples)}")

            if not proposed_triples:
                results.append("✅ LLM found no meaningful new connections.")
                return "\n".join(results)

            # ── Phase 4: Validated Storage ───────────────────────
            ontologist = self._get_ontologist()
            if not ontologist:
                results.append("⚠️ OntologistAbility not available — cannot store connections.")
                return "\n".join(results)

            for triple in proposed_triples[:max_candidates]:
                subject = triple.get("subject", "").strip()
                predicate = triple.get("predicate", "").strip().upper().replace(" ", "_").replace("-", "_")
                obj = triple.get("object", "").strip()

                if not subject or not obj or not predicate:
                    continue

                try:
                    result = await ontologist.execute(
                        subject, predicate, obj,
                        request_scope="CORE",
                        user_id="CORE",
                        source_url="gardener:connect_graph"
                    )
                    if result and "Learned" in str(result):
                        new_connections += 1
                        logger.info(f"  KG connected: {subject} -[{predicate}]-> {obj}")
                except Exception as e:
                    logger.debug(f"  Connection rejected: {subject} -[{predicate}]-> {obj}: {e}")

            # ── Report ───────────────────────────────────────────
            results.append(f"\n**New Connections Stored**: {new_connections}")
            results.append(f"**Candidates Evaluated**: {candidates_evaluated}")

            if new_connections > 0:
                results.append(f"\n🔗 Successfully wired {new_connections} new relationships into the KG.")
            else:
                results.append("\n✅ Graph reviewed — no new connections warranted after validation.")

            return "\n".join(results)

        except Exception as e:
            logger.error(f"KG connection discovery failed: {e}")
            return f"❌ Connection discovery failed: {e}"

    def _select_candidate_pairs(self, nodes: list, max_pairs: int) -> list:
        """
        Select promising node pairs for relationship discovery.

        Heuristics (in priority order):
            1. Shared neighbor — nodes that both connect to the same third node
            2. Same layer — nodes in the same cognitive layer are topically related
            3. Semantic proximity — node names share significant word overlap
        """
        pairs = []
        seen = set()

        # Index neighbors for fast shared-neighbor lookup
        neighbor_to_nodes = {}
        for node in nodes:
            for nb in node["neighbors"]:
                neighbor_to_nodes.setdefault(nb, []).append(node)

        # Strategy 1: Shared neighbors
        for nb, connected_nodes in neighbor_to_nodes.items():
            if len(connected_nodes) < 2:
                continue
            for i, n1 in enumerate(connected_nodes):
                for n2 in connected_nodes[i + 1:]:
                    pair_key = tuple(sorted([n1["name"], n2["name"]]))
                    if pair_key in seen or n1["name"] == n2["name"]:
                        continue
                    seen.add(pair_key)
                    pairs.append({
                        "node_a": n1,
                        "node_b": n2,
                        "reason": f"shared_neighbor:{nb}",
                    })

        # Strategy 2: Same layer (only if we need more candidates)
        if len(pairs) < max_pairs:
            layer_groups = {}
            for node in nodes:
                if node["layer"]:
                    layer_groups.setdefault(node["layer"], []).append(node)

            for layer, group in layer_groups.items():
                if len(group) < 2:
                    continue
                for i, n1 in enumerate(group):
                    for n2 in group[i + 1:]:
                        pair_key = tuple(sorted([n1["name"], n2["name"]]))
                        if pair_key in seen or n1["name"] == n2["name"]:
                            continue
                        seen.add(pair_key)
                        pairs.append({
                            "node_a": n1,
                            "node_b": n2,
                            "reason": f"same_layer:{layer}",
                        })
                        if len(pairs) >= max_pairs:
                            break
                    if len(pairs) >= max_pairs:
                        break
                if len(pairs) >= max_pairs:
                    break

        # Strategy 3: Semantic word overlap (fallback)
        if len(pairs) < max_pairs:
            for i, n1 in enumerate(nodes):
                words1 = set(n1["name"].lower().split())
                for n2 in nodes[i + 1:]:
                    pair_key = tuple(sorted([n1["name"], n2["name"]]))
                    if pair_key in seen or n1["name"] == n2["name"]:
                        continue
                    words2 = set(n2["name"].lower().split())
                    overlap = words1 & words2 - {"the", "a", "an", "of", "in", "to", "and", "or"}
                    if overlap:
                        seen.add(pair_key)
                        pairs.append({
                            "node_a": n1,
                            "node_b": n2,
                            "reason": f"word_overlap:{','.join(overlap)}",
                        })
                        if len(pairs) >= max_pairs:
                            break
                if len(pairs) >= max_pairs:
                    break

        return pairs[:max_pairs]

    async def _infer_relationships(self, engine, candidate_batch: list) -> list:
        """
        Send a batch of candidate pairs to the LLM for relationship inference.
        Returns a list of proposed triples.
        """
        # Build the batch prompt
        pair_descriptions = []
        for idx, pair in enumerate(candidate_batch, 1):
            a = pair["node_a"]
            b = pair["node_b"]
            a_ctx = f"neighbors: {', '.join(a['neighbors'][:5])}" if a["neighbors"] else "isolated"
            b_ctx = f"neighbors: {', '.join(b['neighbors'][:5])}" if b["neighbors"] else "isolated"
            pair_descriptions.append(
                f"{idx}. \"{a['name']}\" ({a_ctx}) ↔ \"{b['name']}\" ({b_ctx}) "
                f"[hint: {pair['reason']}]"
            )

        prompt = (
            "You are a Knowledge Graph maintenance agent. "
            "Analyze these pairs of KG nodes and determine what relationship (if any) "
            "connects them. ONLY propose connections that are factually accurate and meaningful.\n\n"
            "NODE PAIRS:\n" + "\n".join(pair_descriptions) + "\n\n"
            "RULES:\n"
            "- Only propose a connection if there is a real, verifiable relationship\n"
            "- Skip pairs that have no meaningful connection\n"
            "- Predicates should be relationship types like: RELATED_TO, IS_A, PART_OF, "
            "HAS_PROPERTY, DEVELOPED_BY, USED_FOR, CAUSES, ENABLES, SUBSET_OF, "
            "PRECEDED_BY, ASSOCIATED_WITH, etc.\n"
            "- Subjects and objects must be concise entity names (not sentences)\n"
            "- Be conservative — false connections are worse than missing ones\n\n"
            "OUTPUT: Return ONLY a JSON array of objects with 'subject', 'predicate', 'object' keys.\n"
            "If NO pair has a meaningful connection, return an empty array: []\n\n"
            "JSON ARRAY:"
        )

        try:
            from src.bot import globals
            loop = globals.bot.loop if globals.bot else asyncio.get_event_loop()
            raw = await loop.run_in_executor(None, engine.generate_response, prompt)

            if not raw:
                return []

            return _parse_connection_response(raw)

        except Exception as e:
            logger.warning(f"LLM inference failed for batch: {e}")
            return []

    def _get_ontologist(self):
        """Get OntologistAbility through the Cerebrum lobe system."""
        try:
            from src.bot import globals
            if not (globals.bot and globals.bot.cerebrum):
                return None
            memory_lobe = globals.bot.cerebrum.get_lobe_by_name("MemoryLobe")
            if not memory_lobe:
                return None
            return memory_lobe.get_ability("OntologistAbility")
        except Exception:
            return None

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
                        if lc > 1000:
                            report.append(f"  - ⚠️ {file}: {lc} lines (Consider refactoring)")
                            
        return "\n".join(report)


# ═══════════════════════════════════════════════════════════════
#  Module-level utility
# ═══════════════════════════════════════════════════════════════

def _parse_connection_response(raw: str) -> list:
    """
    Parse LLM JSON response into a list of triple dicts.
    Handles common LLM output quirks: code fences, preamble text, etc.
    """
    import re

    if not raw:
        return []

    # Strip markdown code fences
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # Try to find JSON array in the response
    bracket_start = cleaned.find("[")
    bracket_end = cleaned.rfind("]")

    if bracket_start == -1 or bracket_end == -1 or bracket_end <= bracket_start:
        return []

    json_str = cleaned[bracket_start:bracket_end + 1]

    try:
        parsed = json.loads(json_str)
        if isinstance(parsed, list):
            # Validate each item has the required keys
            valid = []
            for item in parsed:
                if isinstance(item, dict) and "subject" in item and "object" in item:
                    valid.append(item)
            return valid
        return []
    except (json.JSONDecodeError, ValueError):
        return []
