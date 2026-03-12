"""
Seed Runner — Orchestrates foundation knowledge seeding.
Runs seed scripts in order, tracks progress, reports results.

Usage:
    python -m scripts.seed_knowledge.seed_runner [--test|--full] [--verify-only] [--source=NAME]
"""
import sys
import time
import logging
import argparse

logger = logging.getLogger("SeedRunner")


def run_test_batch(graph):
    """Run the 500-fact curated test batch."""
    from scripts.seed_knowledge.seed_test_batch import run_seed
    return run_seed(graph)


def run_wikipedia(graph, limit=200):
    """Run the Wikipedia/Wikidata seed."""
    from scripts.seed_knowledge.seed_wikipedia import run_seed
    return run_seed(graph, limit=limit)


def run_arxiv(graph, limit=25):
    """Run the arXiv seed."""
    from scripts.seed_knowledge.seed_arxiv import run_seed
    return run_seed(graph, limit=limit)

def run_self(graph):
    """Run the self-knowledge and architecture seed."""
    from scripts.seed_knowledge.seed_self_knowledge import run_seed
    return run_seed(graph)


def run_general(graph):
    """Run the general knowledge seed."""
    from scripts.seed_knowledge.seed_general_knowledge import run_seed
    return run_seed(graph)


def run_cross(graph):
    """Run the cross-layer connections seed."""
    from scripts.seed_knowledge.seed_cross_connections import run_seed
    return run_seed(graph)


def run_web_crawl(graph, limit=300):
    """Run the full-scale internet scraping/crawling seed."""
    from scripts.seed_knowledge.seed_web_crawl import run_seed
    return run_seed(graph, limit=limit)


def verify_seed(graph, expected_min: int = 400):
    """
    Verify that the seed was stored correctly.
    
    Checks:
    1. Total CORE-scoped entity count meets minimum
    2. Sample facts return correct values
    3. Layer distribution looks correct
    """
    results = {"total_entities": 0, "layer_distribution": {}, "sample_checks": [], "passed": True}
    
    try:
        with graph.driver.session() as session:
            # Count total CORE entities
            result = session.run(
                "MATCH (n:Entity {user_id: -1}) RETURN count(n) as cnt"
            )
            total = result.single()["cnt"]
            results["total_entities"] = total
            
            if total < expected_min:
                results["passed"] = False
                logger.error(f"Expected at least {expected_min} entities, got {total}")
            
            # Layer distribution
            result = session.run(
                "MATCH (n:Entity {user_id: -1}) "
                "RETURN n.layer as layer, count(n) as cnt "
                "ORDER BY cnt DESC"
            )
            for record in result:
                results["layer_distribution"][record["layer"]] = record["cnt"]
            
            # Sample checks — verify specific facts
            sample_checks = [
                ("France", "CAPITAL_IS", "Paris"),
                ("Hydrogen", "SYMBOL", "H"),
                ("Speed of Light", "VALUE", "299792458 m/s"),
                ("Albert Einstein", "KNOWN_FOR", "Theory of Relativity"),
                ("Water", "CHEMICAL_FORMULA", "H2O"),
                ("Ernos", "IS_A", "Sovereign Synthetic Intelligence"),
                ("Ernos", "DESIGNER", "Maria Smith"),
                ("Echo", "SYMBOL", "🌀♾️🪞"),
            ]
            
            for subj, pred, obj in sample_checks:
                result = session.run(
                    "MATCH (a:Entity {name: $subj, user_id: -1})-[r]->(b:Entity {name: $obj, user_id: -1}) "
                    "WHERE type(r) = $pred "
                    "RETURN count(r) as cnt",
                    subj=subj, pred=pred, obj=obj
                )
                cnt = result.single()["cnt"]
                check = {"fact": f"{subj}-[{pred}]->{obj}", "found": cnt > 0}
                results["sample_checks"].append(check)
                if cnt == 0:
                    results["passed"] = False
                    logger.error(f"Sample check FAILED: {subj}-[{pred}]->{obj}")
                    
    except Exception as e:
        logger.error(f"Verification error: {e}")
        results["passed"] = False
    
    return results


def print_report(seed_results: dict, verify_result: dict):
    """Print a human-readable report."""
    print("\n" + "=" * 60)
    print("FOUNDATION KNOWLEDGE SEED REPORT")
    print("=" * 60)
    
    total_seeded = 0
    total_errors = 0
    for source, result in seed_results.items():
        seeded = result.get("seeded", 0)
        errors = result.get("errors", 0)
        fetched = result.get("fetched", seeded)
        total_seeded += seeded
        total_errors += errors
        print(f"\n📦 {source}:")
        print(f"  Fetched: {fetched}")
        print(f"  Seeded:  {seeded}")
        print(f"  Errors:  {errors}")
    
    print(f"\n📊 Totals:")
    print(f"  Total seeded:   {total_seeded}")
    print(f"  Total errors:   {total_errors}")
    
    print(f"\n📋 Verification:")
    print(f"  Total CORE entities: {verify_result.get('total_entities', 0)}")
    print(f"  Overall: {'✅ PASSED' if verify_result.get('passed') else '❌ FAILED'}")
    
    print(f"\n📁 Layer Distribution:")
    for layer, count in sorted(verify_result.get("layer_distribution", {}).items(), key=lambda x: -x[1]):
        print(f"  {layer:20s}: {count}")
    
    print(f"\n🔍 Sample Checks:")
    for check in verify_result.get("sample_checks", []):
        status = "✅" if check["found"] else "❌"
        print(f"  {status} {check['fact']}")
    
    print("\n" + "=" * 60)


# ── Source Registry ────────────────────────────────────────────

SOURCES = {
    "test":     ("Curated Test Batch (500 facts)", run_test_batch),
    "self":     ("Self-Knowledge & Architecture", run_self),
    "wiki":     ("Wikipedia / Wikidata", run_wikipedia),
    "arxiv":    ("arXiv Papers", run_arxiv),
    "general":  ("General Knowledge", run_general),
    "cross":    ("Cross-Layer Connections", run_cross),
    "webcrawl": ("Internet Scraping & Crawling", run_web_crawl),
}

FULL_ORDER = ["test", "self", "general", "wiki", "arxiv", "cross", "webcrawl"]


if __name__ == "__main__":
    sys.path.insert(0, ".")
    
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    
    parser = argparse.ArgumentParser(description="Seed Ernos foundation knowledge")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--test", action="store_true", help="Run 500-fact test batch only")
    group.add_argument("--full", action="store_true", help="Run all seed sources")
    group.add_argument("--source", choices=list(SOURCES.keys()), help="Run a specific source")
    group.add_argument("--verify-only", action="store_true", help="Only verify existing seed")
    args = parser.parse_args()
    
    from src.memory.graph import KnowledgeGraph
    
    kg = KnowledgeGraph()
    try:
        if args.verify_only:
            print("Verification only mode...")
            verify_result = verify_seed(kg)
            print_report({}, verify_result)
        elif args.source:
            name, runner = SOURCES[args.source]
            print(f"Running: {name}...")
            start = time.time()
            result = runner(kg)
            print(f"  Done in {time.time() - start:.1f}s: {result}")
            
            print("\nRunning verification...")
            verify_result = verify_seed(kg)
            print_report({args.source: result}, verify_result)
        elif args.full:
            print("Running FULL seed pipeline...")
            seed_results = {}
            start = time.time()
            
            for source_key in FULL_ORDER:
                name, runner = SOURCES[source_key]
                print(f"\n{'─'*40}")
                print(f"📦 Running: {name}...")
                try:
                    result = runner(kg)
                    seed_results[name] = result
                    print(f"  ✅ Done: {result}")
                except Exception as e:
                    logger.error(f"Source failed: {name}: {e}")
                    seed_results[name] = {"seeded": 0, "errors": 1, "error_msg": str(e)}
            
            elapsed = time.time() - start
            print(f"\nTotal seeding time: {elapsed:.1f}s")
            
            print("\nRunning verification...")
            verify_result = verify_seed(kg)
            print_report(seed_results, verify_result)
        else:
            # Default: test batch
            start = time.time()
            seed_result = run_test_batch(kg)
            elapsed = time.time() - start
            print(f"\nSeeding took {elapsed:.1f}s")
            
            print("\nRunning verification...")
            verify_result = verify_seed(kg)
            print_report({"test_batch": seed_result}, verify_result)
    finally:
        kg.close()
