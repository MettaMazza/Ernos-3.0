#!/usr/bin/env python3
"""
KG Layer Reclassification Script
=================================
One-time migration: Reads all `:Entity` nodes from Neo4j,
uses LLM (via Ernos engine) to classify each into the correct
cognitive layer, and updates the `layer` property in-place.

Also processes quarantine.json entries.

Usage:
    python scripts/reclassify_kg_layers.py [--dry-run]
"""
import sys
import os
import json
import logging
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
from config import settings
from src.memory.types import GraphLayer

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("KG.Reclassify")

VALID_LAYERS = {l.value for l in GraphLayer}

# ─── Layer Classification (rule-based, no LLM needed) ────────────────────────
# Pattern-based classifier: maps relationship types and entity patterns to layers.
# This avoids expensive LLM calls for a one-time migration.

# Predicates that are generic/high-frequency and should NOT dominate classification
GENERIC_PREDICATES = {
    "MEMBER_OF", "DESCRIBED_IN", "RELATES_TO", "MENTIONED_IN", "CONNECTED_TO",
    "CATEGORIZED_AS", "CLASS", "KNOWN_FOR", "HAS", "USES", "WORKS_ON",
    "STUDIES", "PLAYS", "HELPED", "TALKED_ABOUT", "LIKES", "INFLUENCED",
    "CONTRIBUTES_TO",
}

# Domain-specific predicates with high classification confidence
HIGH_CONFIDENCE_PREDICATES = {
    "LOCATED_IN": "spatial", "NEAR": "spatial", "ADJACENT_TO": "spatial",
    "CAPITAL_IS": "spatial", "UNESCO_SITE_IN": "spatial", "HEADQUARTERED_IN": "spatial",
    "SPOKEN_IN": "linguistic", "LANGUAGE_FAMILY": "linguistic", "USES_SCRIPT": "linguistic",
    "WRITTEN_IN": "linguistic",
    "BORN_IN": "social", "AUTHORED": "creative", "WRITTEN_BY": "creative",
    "BY_ARTIST": "aesthetic", "DIRECTED_BY": "creative", "PUBLISHED_BY": "creative",
    "PUBLISHED_ON": "temporal", "OCCURRED_IN": "temporal", "OCCURRED_ON": "temporal",
    "ERA": "temporal", "AWARDED": "social",
    "ATOMIC_NUMBER": "categorical", "SYMBOL": "categorical", "KINGDOM": "ecological",
    "POPULATION": "spatial", "FIELD_OF_STUDY": "epistemic", "OCCUPATION": "social",
    "DEVELOPED_BY": "creative",
    "CAUSES": "causal", "LEADS_TO": "causal", "RESULTS_IN": "causal",
    "TRIGGERED_BY": "causal", "BECAUSE": "causal",
    "IS_A": "categorical", "SUBCLASS_OF": "categorical", "INSTANCE_OF": "categorical",
    "TYPE_OF": "categorical", "BELONGS_TO": "categorical", "CATEGORY": "categorical",
    "FEELS": "emotional", "EVOKES": "emotional", "FEARS": "emotional",
    "LOVES": "emotional", "HATES": "emotional",
    "WANTS": "motivational", "ASPIRES_TO": "motivational", "DESIRES": "motivational",
    "CREATES": "creative", "INSPIRES": "creative", "IMAGINES": "creative",
    "DESIGNS": "creative", "COMPOSES": "creative", "INVENTED": "creative",
    "PREDICTS": "predictive", "EXPECTS": "predictive", "FORECASTS": "predictive",
    "SHOULD": "moral", "MUST_NOT": "moral", "ETHICALLY": "moral", "VIOLATES": "moral",
    "TRADITION_OF": "cultural", "CULTURAL_NORM": "cultural", "CELEBRATES": "cultural",
    "SOURCED_FROM": "epistemic", "VERIFIED_BY": "epistemic", "CITED_BY": "epistemic",
    "RESEMBLES": "analogical", "IS_LIKE": "analogical", "ANALOGOUS_TO": "analogical",
    "TRUSTS": "relational", "DISTRUSTS": "relational", "BONDS_WITH": "relational",
    "EXPERIENCED": "experiential", "VISITED": "experiential", "WITNESSED": "experiential",
    "NEXT_STEP": "procedural", "REQUIRES": "procedural", "FOLLOWED_BY": "procedural",
    "BEFORE": "temporal", "AFTER": "temporal", "DURING": "temporal",
    "STYLES": "aesthetic", "PREFERS_STYLE": "aesthetic", "AESTHETIC_OF": "aesthetic",
    "IDENTIFIES_AS": "self", "VALUES": "self",
    "MEANS": "semantic", "DEFINED_AS": "semantic", "SYNONYM_OF": "semantic",
    "GOVERNS": "system",
}


def classify_relationship(source: str, predicate: str, target: str) -> tuple:
    """Classify a relationship into a cognitive layer. Returns (layer, weight).
    
    High-confidence domain-specific predicates get weight 10.
    Generic/frequent predicates get weight 1.
    Partial matches get weight 3.
    """
    pred_upper = predicate.upper().strip()
    
    # High-confidence direct match
    if pred_upper in HIGH_CONFIDENCE_PREDICATES:
        return (HIGH_CONFIDENCE_PREDICATES[pred_upper], 10)
    
    # Generic predicate — still classify but low weight
    if pred_upper in GENERIC_PREDICATES:
        return ("narrative", 1)
    
    # Partial match on high-confidence predicates
    for key, layer in HIGH_CONFIDENCE_PREDICATES.items():
        if key in pred_upper or pred_upper in key:
            return (layer, 3)
    
    # Entity name pattern match
    entity_patterns = {
        "emotional": ["mood", "feeling", "emotion", "anxiety", "joy", "sadness", "anger", "fear"],
        "motivational": ["goal", "dream", "ambition", "aspiration", "objective"],
        "creative": ["idea", "concept", "design", "art", "music", "poem"],
        "spatial": ["location", "place", "room", "building", "city", "country"],
        "temporal": ["date", "time", "schedule", "deadline", "timeline"],
        "self": ["ernos", "echo", "system", "core", "identity"],
    }
    combined = f"{source} {target}".lower()
    for layer, patterns in entity_patterns.items():
        for pattern in patterns:
            if pattern in combined:
                return (layer, 2)
    
    # Default: narrative with low weight
    return ("narrative", 1)


def classify_node(name: str, properties: dict) -> str:
    """Classify a standalone node into a cognitive layer."""
    name_lower = name.lower()
    
    entity_patterns = {
        "emotional": ["mood", "feeling", "emotion", "anxiety", "joy", "sadness", "anger", "fear"],
        "motivational": ["goal", "dream", "ambition", "aspiration", "objective"],
        "creative": ["idea", "concept", "design", "art", "music", "poem"],
        "spatial": ["location", "place", "room", "building", "city", "country"],
        "temporal": ["date", "time", "schedule", "deadline", "timeline"],
        "self": ["ernos", "echo", "system", "core", "identity"],
    }
    
    for layer, patterns in entity_patterns.items():
        for pattern in patterns:
            if pattern in name_lower:
                return layer
    
    return "narrative"


def reclassify_neo4j(driver, dry_run=False):
    """Read all relationships from Neo4j and reclassify their layers."""
    logger.info("=" * 60)
    logger.info("PHASE 1: Reclassifying Neo4j relationships")
    logger.info("=" * 60)
    
    with driver.session() as session:
        # Get all relationships with their source/target names and current layer
        result = session.run("""
            MATCH (s:Entity)-[r]->(t:Entity)
            RETURN s.name AS source, type(r) AS rel_type, t.name AS target,
                   s.layer AS source_layer, t.layer AS target_layer,
                   id(s) AS source_id, id(t) AS target_id, id(r) AS rel_id
        """)
        
        records = list(result)
        logger.info(f"Found {len(records)} relationships to analyze")
        
        # Count current distribution
        current_layers = {}
        for r in records:
            sl = r["source_layer"] or "narrative"
            current_layers[sl] = current_layers.get(sl, 0) + 1
        logger.info(f"Current layer distribution: {json.dumps(current_layers, indent=2)}")
        
        # Build per-node layer votes from ALL relationships
        node_votes = {}   # node_id -> {layer: count}
        node_names = {}   # node_id -> name
        node_current = {} # node_id -> current layer
        
        for r in records:
            source = r["source"] or ""
            target = r["target"] or ""
            rel_type = r["rel_type"] or ""
            
            new_layer, weight = classify_relationship(source, rel_type, target)
            
            # Vote for source node (weighted)
            sid = r["source_id"]
            node_names[sid] = source
            node_current[sid] = r["source_layer"]
            if sid not in node_votes:
                node_votes[sid] = {}
            node_votes[sid][new_layer] = node_votes[sid].get(new_layer, 0) + weight
            
            # Vote for target node (weighted)
            tid = r["target_id"]
            node_names[tid] = target
            node_current[tid] = r["target_layer"]
            if tid not in node_votes:
                node_votes[tid] = {}
            node_votes[tid][new_layer] = node_votes[tid].get(new_layer, 0) + weight
        
        # Protected nodes: Root:*, Layer:*, Ernos system nodes
        protected_prefixes = ("Root:", "Layer:", "Ernos")
        
        # Determine best layer per node via majority vote
        updates = []
        changes_by_layer = {}  # old_layer -> new_layer -> count
        for node_id, votes in node_votes.items():
            name = node_names.get(node_id, "")
            
            # Skip protected system/architecture nodes
            if any(name.startswith(p) for p in protected_prefixes):
                continue
            
            # Pick the layer with the most votes (exclude 'narrative' as it's the fallback)
            non_narrative = {k: v for k, v in votes.items() if k != "narrative"}
            if non_narrative:
                best_layer = max(non_narrative, key=non_narrative.get)
            else:
                best_layer = "narrative"
            
            current = node_current.get(node_id, "narrative") or "narrative"
            if best_layer != current:
                updates.append((node_id, best_layer))
                key = f"{current} -> {best_layer}"
                changes_by_layer[key] = changes_by_layer.get(key, 0) + 1
        
        logger.info(f"\nReclassification changes breakdown:")
        for change, count in sorted(changes_by_layer.items(), key=lambda x: -x[1]):
            logger.info(f"  {change}: {count} nodes")
        logger.info(f"Total nodes to reclassify: {len(updates)}")
        
        if dry_run:
            logger.info("[DRY RUN] No changes written to Neo4j")
            # Show sample changes
            sample = [(nid, nl) for nid, nl in updates[:20]]
            for nid, nl in sample:
                logger.info(f"  {node_names.get(nid, '?'):40s} {node_current.get(nid, '?'):15s} -> {nl}")
            return len(updates)
        
        # Apply updates in batches
        updated = 0
        batch_size = 100
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            for node_id, new_layer in batch:
                try:
                    session.run(
                        "MATCH (n) WHERE id(n) = $node_id SET n.layer = $layer",
                        node_id=node_id, layer=new_layer
                    )
                    updated += 1
                except Exception as e:
                    logger.warning(f"Failed to update node {node_id}: {e}")
            logger.info(f"  Batch {i//batch_size + 1}: {updated} updated so far...")
        
        logger.info(f"✅ Updated {updated} nodes to new layers")
        return updated


def process_quarantine(driver, dry_run=False):
    """Process quarantine.json entries — fix ownership and re-store valid ones."""
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2: Processing quarantine entries")
    logger.info("=" * 60)
    
    quarantine_path = os.path.join("memory", "quarantine.json")
    if not os.path.exists(quarantine_path):
        logger.warning(f"Quarantine file not found: {quarantine_path}")
        return 0
    
    with open(quarantine_path, "r") as f:
        entries = json.load(f)
    
    logger.info(f"Loaded {len(entries)} quarantine entries")
    
    # Analyze violation types
    violation_types = {}
    for e in entries:
        v = e.get("violation", "unknown")
        # Extract violation type (first word before ":")
        vtype = v.split(":")[0].strip() if ":" in v else v[:30]
        violation_types[vtype] = violation_types.get(vtype, 0) + 1
    
    logger.info(f"Violation breakdown: {json.dumps(violation_types, indent=2)}")
    
    # Process fixable entries
    fixable = []
    unfixable = []
    
    for e in entries:
        violation = e.get("violation", "")
        source = e.get("source", "")
        target = e.get("target", "")
        rel_type = e.get("rel_type", "")
        layer = e.get("layer", "narrative")
        props = e.get("props", {})
        
        # Skip junk entries
        if len(rel_type) > 50 or len(source) < 2 or len(target) < 2:
            unfixable.append(e)
            continue
        
        # Fix ownership violations — assign proper layer + system user_id
        if "no user_id" in violation or "ownership" in violation.lower():
            # Reclassify the layer
            new_layer, _ = classify_relationship(source, rel_type, target)
            
            # Fix user_id: use the one from props if available, else use -1 (system)
            user_id = props.get("user_id")
            if user_id == "CORE" or user_id is None:
                user_id = -1  # System/global node
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                user_id = -1
            
            e["_fix"] = {
                "layer": new_layer,
                "user_id": user_id,
            }
            fixable.append(e)
        else:
            unfixable.append(e)
    
    logger.info(f"Fixable: {len(fixable)}, Unfixable: {len(unfixable)}")
    
    if dry_run:
        logger.info("[DRY RUN] No quarantine entries processed")
        return len(fixable)
    
    # Write fixable entries back to Neo4j
    stored = 0
    with driver.session() as session:
        for e in fixable:
            fix = e["_fix"]
            try:
                # Merge source node
                session.run("""
                    MERGE (s:Entity {name: $source})
                    ON CREATE SET s.layer = $layer, s.user_id = $user_id
                """, source=e["source"], layer=fix["layer"], user_id=fix["user_id"])
                
                # Merge target node
                session.run("""
                    MERGE (t:Entity {name: $target})
                    ON CREATE SET t.layer = $layer, t.user_id = $user_id
                """, target=e["target"], layer=fix["layer"], user_id=fix["user_id"])
                
                # Sanitize rel_type for Neo4j (replace spaces, limit length)
                rel_type = e["rel_type"].replace(" ", "_").replace("-", "_")[:50]
                
                # Create relationship
                session.run(f"""
                    MATCH (s:Entity {{name: $source}})
                    MATCH (t:Entity {{name: $target}})
                    MERGE (s)-[r:`{rel_type}`]->(t)
                    ON CREATE SET r.layer = $layer, r.source = 'quarantine_drain'
                """, source=e["source"], target=e["target"], layer=fix["layer"])
                
                stored += 1
            except Exception as ex:
                logger.debug(f"Failed to store quarantine entry: {ex}")
    
    # Write remaining unfixable entries back to quarantine
    with open(quarantine_path, "w") as f:
        json.dump(unfixable, f, indent=2)
    
    logger.info(f"✅ Drained {stored} quarantine entries into KG")
    logger.info(f"📋 {len(unfixable)} unfixable entries remain in quarantine")
    return stored


def main():
    parser = argparse.ArgumentParser(description="Reclassify KG nodes into 26 cognitive layers")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()
    
    logger.info("🧠 KG Layer Reclassification Script")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    
    # Connect to Neo4j
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        driver.verify_connectivity()
        logger.info(f"Connected to Neo4j at {settings.NEO4J_URI}")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        sys.exit(1)
    
    try:
        # Phase 1: Reclassify existing nodes
        nodes_updated = reclassify_neo4j(driver, dry_run=args.dry_run)
        
        # Phase 2: Drain quarantine
        quarantine_drained = process_quarantine(driver, dry_run=args.dry_run)
        
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Nodes reclassified:    {nodes_updated}")
        logger.info(f"Quarantine drained:    {quarantine_drained}")
        logger.info("Done! Refresh the visualizer to see the new layer distribution.")
        
    finally:
        driver.close()


if __name__ == "__main__":
    main()
