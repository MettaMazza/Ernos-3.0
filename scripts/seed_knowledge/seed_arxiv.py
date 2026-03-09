"""
Foundation Knowledge Seed: arXiv
Extracts key AI/ML/CS/Math/Physics concepts from arXiv API.

Usage:
    python -m scripts.seed_knowledge.seed_arxiv [--limit 100] [--dry-run]
"""
import logging
import time
import json
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse

logger = logging.getLogger("Seed.ArXiv")

ARXIV_API = "http://export.arxiv.org/api/query"
RATE_LIMIT_SECONDS = 3.0  # arXiv requests 3s between API calls

PROVENANCE = {
    "source": "arxiv",
    "confidence": 0.92,
    "retrieved": "2026-02-09"
}

# Focus areas for foundation knowledge
SEARCH_QUERIES = [
    # AI & ML
    ("cat:cs.AI", "artificial_intelligence"),
    ("cat:cs.LG", "machine_learning"),
    ("cat:cs.CL", "natural_language_processing"),
    ("cat:cs.CV", "computer_vision"),
    # Math & Theory
    ("cat:cs.DS", "data_structures"),
    ("cat:math.LO", "mathematical_logic"),
    # Physics
    ("cat:physics.gen-ph", "general_physics"),
    ("cat:quant-ph", "quantum_physics"),
]

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def _fetch_arxiv(query: str, max_results: int = 50, sort_by: str = "relevance") -> list:
    """Fetch papers from arXiv API."""
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": "descending"
    }
    url = ARXIV_API + "?" + urllib.parse.urlencode(params)
    
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "ErnOS-KG-Seed/1.0"
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            xml_data = response.read().decode("utf-8")
            return _parse_arxiv_xml(xml_data)
    except Exception as e:
        logger.error(f"arXiv API error: {e}")
        return []


def _parse_arxiv_xml(xml_data: str) -> list:
    """Parse arXiv Atom XML response into structured entries."""
    entries = []
    try:
        root = ET.fromstring(xml_data)
        for entry in root.findall(f"{ATOM_NS}entry"):
            title = entry.findtext(f"{ATOM_NS}title", "").strip().replace("\n", " ")
            summary = entry.findtext(f"{ATOM_NS}summary", "").strip()[:200]
            arxiv_id = entry.findtext(f"{ATOM_NS}id", "")
            published = entry.findtext(f"{ATOM_NS}published", "")[:10]
            
            authors = []
            for author in entry.findall(f"{ATOM_NS}author"):
                name = author.findtext(f"{ATOM_NS}name", "")
                if name:
                    authors.append(name)
            
            categories = []
            for cat in entry.findall(f"{ATOM_NS}category"):
                term = cat.get("term", "")
                if term:
                    categories.append(term)
            
            if title:
                entries.append({
                    "title": title,
                    "authors": authors,
                    "categories": categories,
                    "summary": summary,
                    "arxiv_id": arxiv_id,
                    "published": published
                })
    except ET.ParseError as e:
        logger.error(f"XML parse error: {e}")
    
    return entries


def _entry_to_facts(entry: dict, field: str) -> list:
    """Convert an arXiv entry into KG facts."""
    facts = []
    title = entry["title"]
    prov = {**PROVENANCE, "arxiv_id": entry.get("arxiv_id", "")}
    
    # Paper → field relationship
    facts.append({
        "subject": title,
        "predicate": "CONTRIBUTES_TO",
        "object": field.replace("_", " ").title(),
        "layer": "epistemic",
        "provenance": prov
    })
    
    # Paper → author relationships (first 3 authors)
    for author in entry.get("authors", [])[:3]:
        facts.append({
            "subject": author,
            "predicate": "AUTHORED",
            "object": title,
            "layer": "social",
            "provenance": prov
        })
    
    # Paper → category relationships
    for cat in entry.get("categories", [])[:2]:
        facts.append({
            "subject": title,
            "predicate": "CATEGORIZED_AS",
            "object": cat,
            "layer": "categorical",
            "provenance": prov
        })
    
    return facts


# ─── Orchestrator ──────────────────────────────────────────────

def get_arxiv_facts(limit_per_query: int = 25) -> list:
    """
    Fetch papers from arXiv and convert to KG facts.
    
    Args:
        limit_per_query: Max papers per category query
        
    Returns:
        List of fact dicts ready for bulk_seed()
    """
    all_facts = []
    seen = set()
    
    for query, field in SEARCH_QUERIES:
        logger.info(f"Fetching arXiv: {field}...")
        try:
            entries = _fetch_arxiv(query, max_results=limit_per_query)
            for entry in entries:
                facts = _entry_to_facts(entry, field)
                for fact in facts:
                    key = (fact["subject"], fact["predicate"], fact["object"])
                    if key not in seen:
                        seen.add(key)
                        all_facts.append(fact)
            
            logger.info(f"  → Got {len(entries)} papers from {field}")
        except Exception as e:
            logger.error(f"  → Failed: {field}: {e}")
        
        # Rate limit between queries
        time.sleep(RATE_LIMIT_SECONDS)
    
    logger.info(f"Total arXiv facts: {len(all_facts)}")
    return all_facts


# ─── Runner ────────────────────────────────────────────────────

def run_seed(graph, limit: int = 25, dry_run: bool = False):
    """Fetch from arXiv and seed into KG."""
    facts = get_arxiv_facts(limit_per_query=limit)
    
    if dry_run:
        print(f"\n[DRY RUN] Would seed {len(facts)} arXiv facts")
        for f in facts[:10]:
            print(f"  {f['subject'][:50]} -[{f['predicate']}]-> {f['object'][:40]} ({f['layer']})")
        return {"fetched": len(facts), "seeded": 0}
    
    result = graph.bulk_seed(facts)
    return {**result, "fetched": len(facts)}


if __name__ == "__main__":
    import sys
    import argparse
    
    sys.path.insert(0, ".")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    
    parser = argparse.ArgumentParser(description="Seed from arXiv")
    parser.add_argument("--limit", type=int, default=25, help="Max papers per category")
    parser.add_argument("--dry-run", action="store_true", help="Fetch without seeding")
    args = parser.parse_args()
    
    if args.dry_run:
        run_seed(None, limit=args.limit, dry_run=True)
    else:
        from src.memory.graph import KnowledgeGraph
        kg = KnowledgeGraph()
        try:
            result = run_seed(kg, limit=args.limit)
            print(f"\n✅ arXiv seed complete: {result}")
        finally:
            kg.close()
