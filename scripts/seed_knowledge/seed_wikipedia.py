"""
Foundation Knowledge Seed: Wikipedia / Wikidata
Extracts structured knowledge from Wikidata SPARQL endpoint.

Usage:
    python -m scripts.seed_knowledge.seed_wikipedia [--limit 5000] [--dry-run]
"""
import logging
import time
import json
import urllib.request
import urllib.parse

logger = logging.getLogger("Seed.Wikipedia")

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "ErnOS-KG-Seed/1.0 (Foundation Knowledge Seeding)"

# Rate limit: 1 request per second per Wikidata policy
RATE_LIMIT_SECONDS = 1.5

PROVENANCE = {
    "source": "wikidata",
    "confidence": 0.95,
    "retrieved": "2026-02-09"
}


def _sparql_query(query: str) -> list:
    """Execute a SPARQL query against Wikidata and return results."""
    url = WIKIDATA_SPARQL + "?" + urllib.parse.urlencode({
        "query": query,
        "format": "json"
    })
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("results", {}).get("bindings", [])
    except Exception as e:
        logger.error(f"SPARQL query failed: {e}")
        return []


# ─── Query Templates ──────────────────────────────────────────

def fetch_world_capitals(limit: int = 300) -> list:
    """Fetch country → capital relationships from Wikidata."""
    query = f"""
    SELECT ?countryLabel ?capitalLabel WHERE {{
      ?country wdt:P31 wd:Q6256 .
      ?country wdt:P36 ?capital .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    LIMIT {limit}
    """
    results = _sparql_query(query)
    facts = []
    for r in results:
        country = r.get("countryLabel", {}).get("value", "")
        capital = r.get("capitalLabel", {}).get("value", "")
        if country and capital and not country.startswith("Q") and not capital.startswith("Q"):
            facts.append({
                "subject": country,
                "predicate": "CAPITAL_IS",
                "object": capital,
                "layer": "spatial",
                "provenance": {**PROVENANCE, "qid": r.get("country", {}).get("value", "")}
            })
    return facts


def fetch_chemical_elements(limit: int = 150) -> list:
    """Fetch chemical elements with symbols and atomic numbers."""
    query = f"""
    SELECT ?elementLabel ?symbol ?atomicNumber WHERE {{
      ?element wdt:P31 wd:Q11344 .
      ?element wdt:P246 ?symbol .
      ?element wdt:P1086 ?atomicNumber .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    LIMIT {limit}
    """
    results = _sparql_query(query)
    facts = []
    for r in results:
        name = r.get("elementLabel", {}).get("value", "")
        symbol = r.get("symbol", {}).get("value", "")
        atomic_num = r.get("atomicNumber", {}).get("value", "")
        if name and not name.startswith("Q"):
            if symbol:
                facts.append({
                    "subject": name, "predicate": "SYMBOL", "object": symbol,
                    "layer": "categorical", "provenance": PROVENANCE
                })
            if atomic_num:
                facts.append({
                    "subject": name, "predicate": "ATOMIC_NUMBER", "object": str(int(float(atomic_num))),
                    "layer": "categorical", "provenance": PROVENANCE
                })
    return facts


def fetch_notable_scientists(limit: int = 200) -> list:
    """Fetch notable scientists with their fields and discoveries."""
    query = f"""
    SELECT ?personLabel ?fieldLabel ?awardLabel WHERE {{
      ?person wdt:P31 wd:Q5 .
      ?person wdt:P106 wd:Q901 .
      ?person wdt:P101 ?field .
      OPTIONAL {{ ?person wdt:P166 ?award . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    LIMIT {limit}
    """
    results = _sparql_query(query)
    facts = []
    seen = set()
    for r in results:
        person = r.get("personLabel", {}).get("value", "")
        field = r.get("fieldLabel", {}).get("value", "")
        if person and field and not person.startswith("Q") and not field.startswith("Q"):
            key = (person, "FIELD_OF_STUDY", field)
            if key not in seen:
                seen.add(key)
                facts.append({
                    "subject": person, "predicate": "FIELD_OF_STUDY", "object": field,
                    "layer": "social", "provenance": PROVENANCE
                })
    return facts


def fetch_world_languages(limit: int = 100) -> list:
    """Fetch languages with their writing systems and regions."""
    query = f"""
    SELECT ?langLabel ?scriptLabel ?regionLabel WHERE {{
      ?lang wdt:P31 wd:Q34770 .
      OPTIONAL {{ ?lang wdt:P282 ?script . }}
      OPTIONAL {{ ?lang wdt:P17 ?region . }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    LIMIT {limit}
    """
    results = _sparql_query(query)
    facts = []
    seen = set()
    for r in results:
        lang = r.get("langLabel", {}).get("value", "")
        script = r.get("scriptLabel", {}).get("value", "")
        region = r.get("regionLabel", {}).get("value", "")
        if lang and not lang.startswith("Q"):
            if script and not script.startswith("Q"):
                key = (lang, "USES_SCRIPT", script)
                if key not in seen:
                    seen.add(key)
                    facts.append({
                        "subject": lang, "predicate": "USES_SCRIPT", "object": script,
                        "layer": "cultural", "provenance": PROVENANCE
                    })
            if region and not region.startswith("Q"):
                key = (lang, "SPOKEN_IN", region)
                if key not in seen:
                    seen.add(key)
                    facts.append({
                        "subject": lang, "predicate": "SPOKEN_IN", "object": region,
                        "layer": "cultural", "provenance": PROVENANCE
                    })
    return facts


def fetch_unesco_sites(limit: int = 200) -> list:
    """Fetch UNESCO World Heritage Sites with locations."""
    query = f"""
    SELECT ?siteLabel ?countryLabel WHERE {{
      ?site wdt:P1435 wd:Q9259 .
      ?site wdt:P17 ?country .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    LIMIT {limit}
    """
    results = _sparql_query(query)
    facts = []
    seen = set()
    for r in results:
        site = r.get("siteLabel", {}).get("value", "")
        country = r.get("countryLabel", {}).get("value", "")
        if site and country and not site.startswith("Q") and not country.startswith("Q"):
            key = (site, "UNESCO_SITE_IN", country)
            if key not in seen:
                seen.add(key)
                facts.append({
                    "subject": site, "predicate": "UNESCO_SITE_IN", "object": country,
                    "layer": "cultural", "provenance": PROVENANCE
                })
    return facts


# ─── Orchestrator ──────────────────────────────────────────────

def get_wikipedia_facts(limit_per_query: int = 200) -> list:
    """
    Run all Wikidata queries and return combined fact list.
    
    Args:
        limit_per_query: Max results per SPARQL query
        
    Returns:
        List of fact dicts ready for bulk_seed()
    """
    all_facts = []
    
    queries = [
        ("World Capitals", fetch_world_capitals),
        ("Chemical Elements", fetch_chemical_elements),
        ("Notable Scientists", fetch_notable_scientists),
        ("World Languages", fetch_world_languages),
        ("UNESCO Sites", fetch_unesco_sites),
    ]
    
    for name, fetcher in queries:
        logger.info(f"Fetching: {name}...")
        try:
            facts = fetcher(limit=limit_per_query)
            all_facts.extend(facts)
            logger.info(f"  → Got {len(facts)} facts from {name}")
        except Exception as e:
            logger.error(f"  → Failed: {name}: {e}")
        
        # Rate limit between queries
        time.sleep(RATE_LIMIT_SECONDS)
    
    logger.info(f"Total Wikipedia facts: {len(all_facts)}")
    return all_facts


# ─── Runner ────────────────────────────────────────────────────

def run_seed(graph, limit: int = 200, dry_run: bool = False):
    """
    Fetch facts from Wikidata and seed into KG.
    
    Args:
        graph: KnowledgeGraph instance
        limit: Max results per query
        dry_run: If True, fetch but don't seed
    """
    facts = get_wikipedia_facts(limit_per_query=limit)
    
    if dry_run:
        print(f"\n[DRY RUN] Would seed {len(facts)} facts")
        # Show sample
        for f in facts[:10]:
            print(f"  {f['subject']} -[{f['predicate']}]-> {f['object']} ({f['layer']})")
        return {"fetched": len(facts), "seeded": 0}
    
    result = graph.bulk_seed(facts)
    return {**result, "fetched": len(facts)}


if __name__ == "__main__":
    import sys
    import argparse
    
    sys.path.insert(0, ".")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    
    parser = argparse.ArgumentParser(description="Seed from Wikidata")
    parser.add_argument("--limit", type=int, default=200, help="Max results per query")
    parser.add_argument("--dry-run", action="store_true", help="Fetch without seeding")
    args = parser.parse_args()
    
    if args.dry_run:
        run_seed(None, limit=args.limit, dry_run=True)
    else:
        from src.memory.graph import KnowledgeGraph
        kg = KnowledgeGraph()
        try:
            result = run_seed(kg, limit=args.limit)
            print(f"\n✅ Wikipedia seed complete: {result}")
        finally:
            kg.close()
