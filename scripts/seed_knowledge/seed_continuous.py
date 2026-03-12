"""
Continuous Self-Expanding Knowledge Seed

Runs the seed pipeline indefinitely. After each cycle, it extracts new entities
from the facts it just seeded and uses them to discover fresh sources — making
the pipeline self-sustaining. It never stalls because every scrape generates
new things to scrape.

All facts are seeded with scope='CORE_PUBLIC' — shareable world knowledge
that is readable by PUBLIC, PRIVATE, and CORE scopes.

Discovery chain:
    scrape facts → extract entities → generate new DDG topics, Wikipedia URLs,
    ConceptNet concepts, arXiv queries → scrape those → repeat forever

Usage:
    python -m scripts.seed_knowledge.seed_continuous [--cycle-pause 60] [--once]

Ctrl+C or `touch scripts/seed_knowledge/.stop` to gracefully shut down.
"""
import sys
import os
import signal
import time
import json
import hashlib
import logging
import random
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Set, Any

sys.path.insert(0, ".")

logger = logging.getLogger("Seed.Continuous")

# All seeded facts use CORE_PUBLIC scope — shareable world knowledge.
# Readable by PUBLIC and PRIVATE queries (not locked to CORE_PRIVATE).
SEED_SCOPE = "CORE_PUBLIC"


def _stamp_scope(facts: list) -> list:
    """Stamp every fact with scope=CORE_PUBLIC before seeding."""
    for fact in facts:
        fact["scope"] = SEED_SCOPE
    return facts

# ═══════════════════════════════════════════════════════════════
# State Tracking
# ═══════════════════════════════════════════════════════════════

STATE_FILE = Path(__file__).parent / "seed_state.json"
STOP_FILE  = Path(__file__).parent / ".stop"

# Max items in the discovery queue before we start pruning
MAX_QUEUE_SIZE = 5000


def _fact_hash(fact: dict) -> str:
    """Deterministic hash for a fact dict."""
    key = f"{fact.get('subject','')}__{fact.get('predicate','')}__{fact.get('object','')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


class SeedState:
    """Persistent state for the continuous runner."""

    def __init__(self):
        self.seen_hashes: Set[str] = set()
        self.total_seeded: int = 0
        self.total_cycles: int = 0
        self.last_cycle: str = ""
        # Discovery queues — entities we haven't explored yet
        self.pending_topics: List[str] = []
        self.pending_urls: List[str] = []
        self.pending_concepts: List[str] = []
        self.pending_arxiv_queries: List[str] = []
        self._load()

    def _load(self):
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                self.seen_hashes = set(data.get("seen_hashes", []))
                self.total_seeded = data.get("total_seeded", 0)
                self.total_cycles = data.get("total_cycles", 0)
                self.last_cycle = data.get("last_cycle", "")
                self.pending_topics = data.get("pending_topics", [])
                self.pending_urls = data.get("pending_urls", [])
                self.pending_concepts = data.get("pending_concepts", [])
                self.pending_arxiv_queries = data.get("pending_arxiv_queries", [])
                logger.info(f"Loaded state: {self.total_seeded} seeded, "
                            f"{len(self.seen_hashes)} hashes, "
                            f"{len(self.pending_topics)} pending topics, "
                            f"{len(self.pending_urls)} pending URLs")
            except Exception as e:
                logger.warning(f"State load error, starting fresh: {e}")

    def save(self):
        # Keep hashes manageable — only store last 50k
        hashes_to_save = list(self.seen_hashes)
        if len(hashes_to_save) > 50000:
            hashes_to_save = hashes_to_save[-50000:]

        data = {
            "seen_hashes": hashes_to_save,
            "total_seeded": self.total_seeded,
            "total_cycles": self.total_cycles,
            "last_cycle": self.last_cycle,
            "pending_topics": self.pending_topics[:MAX_QUEUE_SIZE],
            "pending_urls": self.pending_urls[:MAX_QUEUE_SIZE],
            "pending_concepts": self.pending_concepts[:MAX_QUEUE_SIZE],
            "pending_arxiv_queries": self.pending_arxiv_queries[:MAX_QUEUE_SIZE],
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))

    def dedup(self, facts: list) -> list:
        """Return only facts we haven't seen before."""
        new_facts = []
        for fact in facts:
            h = _fact_hash(fact)
            if h not in self.seen_hashes:
                self.seen_hashes.add(h)
                new_facts.append(fact)
        return new_facts

    def add_pending(self, topics=None, urls=None, concepts=None, arxiv_queries=None):
        """Add newly discovered sources to the queues (deduped)."""
        if topics:
            existing = set(self.pending_topics)
            for t in topics:
                if t not in existing:
                    self.pending_topics.append(t)
                    existing.add(t)
        if urls:
            existing = set(self.pending_urls)
            for u in urls:
                if u not in existing:
                    self.pending_urls.append(u)
                    existing.add(u)
        if concepts:
            existing = set(self.pending_concepts)
            for c in concepts:
                if c not in existing:
                    self.pending_concepts.append(c)
                    existing.add(c)
        if arxiv_queries:
            existing = set(self.pending_arxiv_queries)
            for q in arxiv_queries:
                if q not in existing:
                    self.pending_arxiv_queries.append(q)
                    existing.add(q)

    def pop_topics(self, n: int = 30) -> list:
        """Pop N topics from the discovery queue."""
        batch, self.pending_topics = self.pending_topics[:n], self.pending_topics[n:]
        return batch

    def pop_urls(self, n: int = 30) -> list:
        batch, self.pending_urls = self.pending_urls[:n], self.pending_urls[n:]
        return batch

    def pop_concepts(self, n: int = 20) -> list:
        batch, self.pending_concepts = self.pending_concepts[:n], self.pending_concepts[n:]
        return batch

    def pop_arxiv_queries(self, n: int = 5) -> list:
        batch, self.pending_arxiv_queries = self.pending_arxiv_queries[:n], self.pending_arxiv_queries[n:]
        return batch


# ═══════════════════════════════════════════════════════════════
# Discovery Engine — Extracts new sources from seeded facts
# ═══════════════════════════════════════════════════════════════

# Diverse seed topics to bootstrap discovery if queues are empty
BOOTSTRAP_DOMAINS = [
    # Sciences
    "quantum field theory", "epigenetics", "astrobiology", "materials science",
    "fluid dynamics", "organic chemistry", "molecular biology", "geophysics",
    "astrophysics", "cosmology", "paleontology", "marine biology",
    "ecology", "microbiology", "pharmacology", "bioinformatics",
    # Technology
    "distributed systems", "compiler design", "operating system kernel",
    "computer graphics", "signal processing", "control theory",
    "information retrieval", "formal verification", "type theory",
    "network protocols", "embedded systems", "FPGA design",
    # Mathematics
    "algebraic geometry", "functional analysis", "combinatorics",
    "measure theory", "dynamical systems", "knot theory",
    "representation theory", "stochastic processes", "optimization theory",
    # Humanities
    "cognitive linguistics", "historical sociology", "cultural anthropology",
    "comparative religion", "philosophy of mathematics", "aesthetics",
    "political philosophy", "philosophy of language", "hermeneutics",
    # History & Geography
    "Byzantine Empire", "Mesoamerican civilizations", "Viking Age",
    "Mughal Empire", "Tang Dynasty", "Inca Empire",
    "Hanseatic League", "Phoenician civilization", "Indus Valley civilization",
    # Engineering
    "structural engineering", "biomedical engineering", "chemical engineering",
    "environmental engineering", "nuclear engineering", "ocean engineering",
    # Arts
    "art history movements", "music theory harmony", "cinematography techniques",
    "architectural styles history", "literary theory", "performance art",
    # Social Sciences
    "behavioral economics", "game theory applications", "urban planning",
    "demographic transition", "political economy", "international relations",
    # Medicine
    "immunology", "pathology", "radiology", "endocrinology",
    "hematology", "gastroenterology", "ophthalmology",
    # Interdisciplinary
    "systems biology", "computational neuroscience", "quantum chemistry",
    "astrochemistry", "econophysics", "sociobiology", "psycholinguistics",
    "bioethics", "environmental economics", "digital humanities",
]


def _entity_to_wikipedia_url(entity: str) -> str:
    """Convert an entity name to a likely Wikipedia URL."""
    slug = entity.strip().replace(" ", "_")
    return f"https://en.wikipedia.org/wiki/{slug}"


def _entity_to_search_topic(entity: str, context: str = "") -> str:
    """Convert an entity into a DuckDuckGo-style search topic."""
    # Add some diversity to the search
    modifiers = [
        "", "history of", "applications of", "theory of",
        "significance of", "impact of", "developments in",
    ]
    modifier = random.choice(modifiers)
    if modifier:
        return f"{modifier} {entity}"
    return entity


def _entity_to_arxiv_query(entity: str) -> str:
    """Convert entity to arXiv search query."""
    slug = entity.strip().lower().replace(" ", "+")
    return f"all:{slug}"


def discover_from_facts(facts: list) -> Dict[str, list]:
    """
    Extract new sources from freshly seeded facts.

    Takes the subjects/objects of new facts and generates:
    - New DDG search topics
    - New Wikipedia article URLs
    - New ConceptNet concepts
    - New arXiv search queries

    This is what makes the pipeline self-sustaining.
    """
    new_topics = []
    new_urls = []
    new_concepts = []
    new_arxiv = []
    seen_entities = set()

    for fact in facts:
        for entity in [fact.get("subject", ""), fact.get("object", "")]:
            entity = entity.strip()
            if not entity or len(entity) < 3 or len(entity) > 80:
                continue
            if entity in seen_entities:
                continue
            seen_entities.add(entity)

            # Skip pure numbers, dates, formulas
            if entity.replace(".", "").replace("-", "").isdigit():
                continue
            if entity.startswith("http"):
                continue

            # Generate diverse search topics from entities
            new_topics.append(_entity_to_search_topic(entity))

            # Turn well-formed entities into Wikipedia URLs
            words = entity.split()
            if 1 <= len(words) <= 5 and entity[0].isupper():
                new_urls.append(_entity_to_wikipedia_url(entity))

            # Single words or short phrases → ConceptNet concepts
            if len(words) <= 3 and entity.isascii():
                new_concepts.append(entity.lower())

            # Academic-sounding entities → arXiv queries
            layer = fact.get("layer", "")
            if layer in ("epistemic", "procedural", "predictive", "symbolic"):
                new_arxiv.append(_entity_to_arxiv_query(entity))

    # Shuffle for diversity across cycles
    random.shuffle(new_topics)
    random.shuffle(new_urls)
    random.shuffle(new_concepts)
    random.shuffle(new_arxiv)

    return {
        "topics": new_topics,
        "urls": new_urls,
        "concepts": new_concepts,
        "arxiv_queries": new_arxiv,
    }


# ═══════════════════════════════════════════════════════════════
# Cycle Runner
# ═══════════════════════════════════════════════════════════════

_shutdown_requested = False

def _handle_signal(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    logger.info(f"Shutdown signal received ({signum}), finishing current cycle...")


def run_cycle(graph, state: SeedState, cycle_num: int) -> Dict[str, Any]:
    """
    Run one cycle of the continuous seed pipeline.

    Each cycle:
    1. Run existing seed sources (wiki, arxiv, webcrawl) with DYNAMIC inputs
    2. Seed the new facts
    3. Extract entities from those facts → generate new sources
    4. Queue them for the next cycle
    """
    cycle_stats = {"fetched": 0, "seeded": 0, "discovered": 0, "errors": 0}
    all_new_facts = []

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.info(f"\n{'═'*60}")
    logger.info(f"CYCLE {cycle_num} — {now}")
    logger.info(f"Queues: {len(state.pending_topics)} topics, "
                f"{len(state.pending_urls)} URLs, "
                f"{len(state.pending_concepts)} concepts, "
                f"{len(state.pending_arxiv_queries)} arXiv queries")
    logger.info(f"{'═'*60}")

    # ── Phase 1: Run static sources on first cycle only ──────
    if cycle_num == 1:
        logger.info("── Phase 1: Static foundation sources (first cycle) ──")
        try:
            from scripts.seed_knowledge.seed_test_batch import run_seed as run_test
            result = run_test(graph)
            cycle_stats["seeded"] += result.get("seeded", 0)
            logger.info(f"  Test batch: {result}")
        except Exception as e:
            logger.error(f"  Test batch error: {e}")
            cycle_stats["errors"] += 1

        try:
            from scripts.seed_knowledge.seed_self_knowledge import run_seed as run_self
            result = run_self(graph)
            cycle_stats["seeded"] += result.get("seeded", 0)
            logger.info(f"  Self-knowledge: {result}")
        except Exception as e:
            logger.error(f"  Self-knowledge error: {e}")
            cycle_stats["errors"] += 1

        try:
            from scripts.seed_knowledge.seed_general_knowledge import run_seed as run_general
            result = run_general(graph)
            cycle_stats["seeded"] += result.get("seeded", 0)
            logger.info(f"  General knowledge: {result}")
        except Exception as e:
            logger.error(f"  General knowledge error: {e}")
            cycle_stats["errors"] += 1

        try:
            from scripts.seed_knowledge.seed_cross_connections import run_seed as run_cross
            result = run_cross(graph)
            cycle_stats["seeded"] += result.get("seeded", 0)
            logger.info(f"  Cross-connections: {result}")
        except Exception as e:
            logger.error(f"  Cross-connections error: {e}")
            cycle_stats["errors"] += 1

    # ── Phase 2: Dynamic web sources ─────────────────────────
    logger.info("── Phase 2: Dynamic web sources ──")

    # 2a. Wikipedia / Wikidata — always runs with varying limit
    if not _shutdown_requested:
        try:
            from scripts.seed_knowledge.seed_wikipedia import get_wikipedia_facts
            limit = random.randint(100, 300)
            facts = _stamp_scope(get_wikipedia_facts(limit_per_query=limit))
            new_facts = state.dedup(facts)
            if new_facts:
                result = graph.bulk_seed(new_facts)
                cycle_stats["seeded"] += result.get("seeded", 0)
                all_new_facts.extend(new_facts)
            logger.info(f"  Wikipedia: {len(facts)} fetched, {len(new_facts)} new")
        except Exception as e:
            logger.error(f"  Wikipedia error: {e}")
            cycle_stats["errors"] += 1

    # 2b. arXiv — use pending queries if available, else default categories
    if not _shutdown_requested:
        try:
            from scripts.seed_knowledge.seed_arxiv import _fetch_arxiv, _entry_to_facts, SEARCH_QUERIES
            arxiv_facts = []
            queries = state.pop_arxiv_queries(5)
            # Always include some default categories too
            default_queries = random.sample(SEARCH_QUERIES, min(3, len(SEARCH_QUERIES)))

            for query, field in default_queries:
                try:
                    logger.info(f"  arXiv: fetching {field}...")
                    entries = _fetch_arxiv(query, max_results=random.randint(10, 50))
                    for entry in entries:
                        arxiv_facts.extend(_entry_to_facts(entry, field))
                    logger.info(f"  arXiv: {len(entries)} papers from {field}")
                    time.sleep(3.0)
                except Exception as e:
                    logger.warning(f"  arXiv {field}: {e}")

            # Discovered queries
            for query_str in queries:
                try:
                    logger.info(f"  arXiv: discovered query '{query_str[:40]}'...")
                    entries = _fetch_arxiv(query_str, max_results=20)
                    for entry in entries:
                        arxiv_facts.extend(_entry_to_facts(entry, "discovered"))
                    logger.info(f"  arXiv: {len(entries)} papers from '{query_str[:30]}'")
                    time.sleep(3.0)
                except Exception as e:
                    logger.warning(f"  arXiv discovered '{query_str[:30]}': {e}")

            new_facts = state.dedup(_stamp_scope(arxiv_facts))
            if new_facts:
                result = graph.bulk_seed(new_facts)
                cycle_stats["seeded"] += result.get("seeded", 0)
                all_new_facts.extend(new_facts)
            logger.info(f"  arXiv: {len(arxiv_facts)} fetched, {len(new_facts)} new")
        except Exception as e:
            logger.error(f"  arXiv error: {e}")
            cycle_stats["errors"] += 1

    # 2c. DBpedia — random subset of fetchers each cycle so it stays diverse
    if not _shutdown_requested:
        try:
            from scripts.seed_knowledge.seed_web_crawl import DBPEDIA_FETCHERS, RATE_LIMIT
            # Pick 5 random fetchers each cycle
            fetchers = random.sample(DBPEDIA_FETCHERS, min(5, len(DBPEDIA_FETCHERS)))
            dbpedia_facts = []
            for fetcher in fetchers:
                try:
                    limit = random.randint(50, 200)  # Reduced from 200-800 to avoid SPARQL timeouts
                    logger.info(f"  DBpedia: {fetcher.__name__} (limit={limit})...")
                    dbpedia_facts.extend(fetcher(limit))
                    logger.info(f"  DBpedia: {fetcher.__name__} done ({len(dbpedia_facts)} total so far)")
                    time.sleep(RATE_LIMIT)
                except Exception as e:
                    logger.warning(f"  DBpedia {fetcher.__name__}: {e}")
                if _shutdown_requested:
                    break

            new_facts = state.dedup(_stamp_scope(dbpedia_facts))
            if new_facts:
                result = graph.bulk_seed(new_facts)
                cycle_stats["seeded"] += result.get("seeded", 0)
                all_new_facts.extend(new_facts)
            logger.info(f"  DBpedia: {len(dbpedia_facts)} fetched, {len(new_facts)} new")
        except Exception as e:
            logger.error(f"  DBpedia error: {e}")
            cycle_stats["errors"] += 1

    # 2d. ConceptNet — use pending concepts if available, else defaults
    if not _shutdown_requested:
        try:
            from scripts.seed_knowledge.seed_web_crawl import (
                fetch_conceptnet_edges, SEED_CONCEPTS
            )
            concepts = state.pop_concepts(20)
            if not concepts:
                concepts = random.sample(SEED_CONCEPTS, min(15, len(SEED_CONCEPTS)))

            cn_facts = _stamp_scope(fetch_conceptnet_edges(concepts, limit_per=30))
            new_facts = state.dedup(cn_facts)
            if new_facts:
                result = graph.bulk_seed(new_facts)
                cycle_stats["seeded"] += result.get("seeded", 0)
                all_new_facts.extend(new_facts)
            logger.info(f"  ConceptNet: {len(cn_facts)} fetched, {len(new_facts)} new")
        except Exception as e:
            logger.error(f"  ConceptNet error: {e}")
            cycle_stats["errors"] += 1

    # 2e. DuckDuckGo Discovery — use pending topics if available
    if not _shutdown_requested:
        try:
            from scripts.seed_knowledge.seed_web_crawl import fetch_ddg_discovery_facts
            topics = state.pop_topics(30)
            if not topics:
                topics = random.sample(BOOTSTRAP_DOMAINS, min(20, len(BOOTSTRAP_DOMAINS)))

            ddg_facts = _stamp_scope(fetch_ddg_discovery_facts(topics=topics, max_results=5))
            new_facts = state.dedup(ddg_facts)
            if new_facts:
                result = graph.bulk_seed(new_facts)
                cycle_stats["seeded"] += result.get("seeded", 0)
                all_new_facts.extend(new_facts)
            logger.info(f"  DDG Discovery: {len(ddg_facts)} fetched, {len(new_facts)} new")
        except Exception as e:
            logger.error(f"  DDG error: {e}")
            cycle_stats["errors"] += 1

    # 2f. RSS Feeds — always runs (content changes daily)
    if not _shutdown_requested:
        try:
            from scripts.seed_knowledge.seed_web_crawl import fetch_rss_facts
            rss_facts = _stamp_scope(fetch_rss_facts(max_per_feed=20))
            new_facts = state.dedup(rss_facts)
            if new_facts:
                result = graph.bulk_seed(new_facts)
                cycle_stats["seeded"] += result.get("seeded", 0)
                all_new_facts.extend(new_facts)
            logger.info(f"  RSS: {len(rss_facts)} fetched, {len(new_facts)} new")
        except Exception as e:
            logger.error(f"  RSS error: {e}")
            cycle_stats["errors"] += 1

    # 2g. Article Scraping — use pending URLs if available
    if not _shutdown_requested:
        try:
            from scripts.seed_knowledge.seed_web_crawl import fetch_article_facts
            urls = state.pop_urls(30)
            if urls:
                article_facts = _stamp_scope(fetch_article_facts(urls=urls, max_entities_per=30))
                new_facts = state.dedup(article_facts)
                if new_facts:
                    result = graph.bulk_seed(new_facts)
                    cycle_stats["seeded"] += result.get("seeded", 0)
                    all_new_facts.extend(new_facts)
                logger.info(f"  Articles: {len(article_facts)} fetched, {len(new_facts)} new")
        except Exception as e:
            logger.error(f"  Articles error: {e}")
            cycle_stats["errors"] += 1

    # ── Phase 3: Discovery — mine new facts for new sources ──
    logger.info("── Phase 3: Discovery — extracting new sources ──")
    if all_new_facts:
        discovered = discover_from_facts(all_new_facts)
        state.add_pending(
            topics=discovered["topics"],
            urls=discovered["urls"],
            concepts=discovered["concepts"],
            arxiv_queries=discovered["arxiv_queries"],
        )
        total_discovered = sum(len(v) for v in discovered.values())
        cycle_stats["discovered"] = total_discovered
        logger.info(f"  Discovered {total_discovered} new sources: "
                    f"{len(discovered['topics'])} topics, "
                    f"{len(discovered['urls'])} URLs, "
                    f"{len(discovered['concepts'])} concepts, "
                    f"{len(discovered['arxiv_queries'])} arXiv queries")
    else:
        # Nothing new this cycle — replenish from bootstrap domains
        logger.info("  No new facts — replenishing queues from bootstrap domains")
        bootstrap_batch = random.sample(BOOTSTRAP_DOMAINS, min(30, len(BOOTSTRAP_DOMAINS)))
        state.add_pending(
            topics=bootstrap_batch,
            urls=[_entity_to_wikipedia_url(e) for e in bootstrap_batch[:15]],
            concepts=[e.lower().split()[0] for e in bootstrap_batch[:20]],
        )

    # ── Save state ───────────────────────────────────────────
    cycle_stats["fetched"] = len(all_new_facts) + cycle_stats.get("seeded", 0)
    state.total_seeded += cycle_stats["seeded"]
    state.total_cycles += 1
    state.last_cycle = now
    state.save()

    logger.info(f"\n📊 Cycle {cycle_num} complete: "
                f"seeded={cycle_stats['seeded']}, "
                f"discovered={cycle_stats['discovered']}, "
                f"errors={cycle_stats['errors']}")
    logger.info(f"📈 Running totals: {state.total_seeded} facts seeded over "
                f"{state.total_cycles} cycles")
    logger.info(f"📋 Queues: {len(state.pending_topics)} topics, "
                f"{len(state.pending_urls)} URLs, "
                f"{len(state.pending_concepts)} concepts, "
                f"{len(state.pending_arxiv_queries)} arXiv queries")

    return cycle_stats


# ═══════════════════════════════════════════════════════════════
# Main Loop
# ═══════════════════════════════════════════════════════════════

def main():
    global _shutdown_requested

    parser = argparse.ArgumentParser(description="Continuous self-expanding knowledge seeder")
    parser.add_argument("--cycle-pause", type=int, default=60,
                        help="Seconds to pause between cycles (default: 60)")
    parser.add_argument("--once", action="store_true",
                        help="Run a single cycle then exit")
    parser.add_argument("--reset", action="store_true",
                        help="Clear state file and start fresh")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    # Wire up graceful shutdown
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Clear stop file if it exists from a previous run
    if STOP_FILE.exists():
        STOP_FILE.unlink()

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        logger.info("State file cleared")

    state = SeedState()

    # Connect to KG
    from src.memory.graph import KnowledgeGraph
    kg = KnowledgeGraph()

    try:
        cycle_num = state.total_cycles + 1

        logger.info(f"\n{'▓'*60}")
        logger.info(f"  CONTINUOUS KNOWLEDGE SEED — STARTING")
        logger.info(f"  Cycle pause: {args.cycle_pause}s | Mode: {'single' if args.once else 'continuous'}")
        logger.info(f"  Previous: {state.total_seeded} facts over {state.total_cycles} cycles")
        logger.info(f"{'▓'*60}\n")

        while not _shutdown_requested:
            # Check for .stop file
            if STOP_FILE.exists():
                logger.info("Stop file detected, shutting down...")
                STOP_FILE.unlink()
                break

            try:
                run_cycle(kg, state, cycle_num)
            except Exception as e:
                logger.error(f"Cycle {cycle_num} crashed: {e}")
                # Save state even on crash
                state.save()

            cycle_num += 1

            if args.once:
                logger.info("Single cycle mode — exiting")
                break

            # Pause between cycles
            logger.info(f"\n⏸️  Pausing {args.cycle_pause}s before next cycle...")
            for _ in range(args.cycle_pause):
                if _shutdown_requested or STOP_FILE.exists():
                    break
                time.sleep(1)

    finally:
        kg.close()
        state.save()
        logger.info(f"\n{'▓'*60}")
        logger.info(f"  SHUTDOWN COMPLETE")
        logger.info(f"  Total: {state.total_seeded} facts seeded over {state.total_cycles} cycles")
        logger.info(f"  Queues remaining: {len(state.pending_topics)} topics, "
                    f"{len(state.pending_urls)} URLs")
        logger.info(f"{'▓'*60}")


if __name__ == "__main__":
    main()
