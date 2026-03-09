"""
Continuous Knowledge Crawler
Autonomously discovers and ingests new knowledge into the KG.

Designed to run inside the Autonomy idle loop:
    - Each call to `crawl_cycle()` performs ONE mini-crawl (quick, non-blocking)
    - Cycles through sources: RSS → DDG → Articles → DBpedia
    - Tracks visited URLs and last-crawl times in crawl_state.json
    - Deduplicates against existing KG entities

Can also run standalone:
    python -m scripts.continuous_crawler [--once] [--source=rss|ddg|articles|dbpedia]
"""
import json
import logging
import os
import time
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("Crawler.Continuous")

# Crawl state file — persists across restarts
STATE_DIR = Path(__file__).resolve().parent.parent / "memory"
STATE_FILE = STATE_DIR / "crawl_state.json"


class CrawlState:
    """Persistent crawl state — tracks visited URLs, timing, and topic queue."""
    
    def __init__(self):
        self.visited_urls: set = set()
        self.last_crawl: Dict[str, float] = {}  # source → timestamp
        self.topic_queue: List[str] = []  # discovered topics to explore
        self.stats: Dict[str, int] = {
            "total_facts_ingested": 0,
            "total_crawl_cycles": 0,
            "total_new_entities": 0,
        }
        self._load()
    
    def _load(self):
        """Load state from disk."""
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text())
                self.visited_urls = set(data.get("visited_urls", []))
                self.last_crawl = data.get("last_crawl", {})
                self.topic_queue = data.get("topic_queue", [])
                self.stats = data.get("stats", self.stats)
                logger.info(f"Crawl state loaded: {len(self.visited_urls)} visited URLs, "
                           f"{self.stats['total_facts_ingested']} total facts ingested")
            except Exception as e:
                logger.warning(f"Failed to load crawl state: {e}")
    
    def save(self):
        """Persist state to disk."""
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "visited_urls": list(self.visited_urls)[-5000:],  # Cap at 5000 URLs
                "last_crawl": self.last_crawl,
                "topic_queue": self.topic_queue[:200],  # Cap queue
                "stats": self.stats,
                "last_saved": datetime.datetime.now().isoformat(),
            }
            STATE_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save crawl state: {e}")
    
    def should_crawl(self, source: str, interval_seconds: int) -> bool:
        """Check if enough time has passed since last crawl of this source."""
        last = self.last_crawl.get(source, 0)
        return (time.time() - last) >= interval_seconds
    
    def mark_crawled(self, source: str):
        """Mark a source as just-crawled."""
        self.last_crawl[source] = time.time()
    
    def add_visited(self, url: str):
        """Mark a URL as visited."""
        self.visited_urls.add(url)
    
    def is_visited(self, url: str) -> bool:
        """Check if URL was already visited."""
        return url in self.visited_urls


# ── Crawl Intervals ──────────────────────────────────────────

CRAWL_INTERVALS = {
    "rss": 3600,        # 1 hour — news feeds
    "ddg": 21600,       # 6 hours — topic discovery
    "articles": 86400,  # 24 hours — deep Wikipedia extraction
    "dbpedia": 86400,   # 24 hours — structured data refresh
}


class ContinuousCrawler:
    """
    Autonomous knowledge crawler.
    
    Call `crawl_cycle()` from the autonomy idle loop.
    Each call performs ONE mini-crawl of whichever source is due.
    """
    
    def __init__(self, kg=None):
        """
        Args:
            kg: KnowledgeGraph instance (if None, will connect on first crawl)
        """
        self.kg = kg
        self.state = CrawlState()
        self._source_order = ["rss", "ddg", "articles", "dbpedia"]
        self._current_idx = 0
        logger.info("ContinuousCrawler initialized")
    
    def crawl_cycle(self, force_source: str = None) -> Dict[str, Any]:
        """
        Run ONE crawl cycle. Returns stats dict.
        
        Called from autonomy idle loop — should complete in <60s.
        """
        result = {"source": None, "facts": 0, "new": 0, "skipped": False}
        
        # Determine which source to crawl
        if force_source:
            source = force_source
        else:
            source = self._next_due_source()
        
        if source is None:
            result["skipped"] = True
            logger.debug("Crawler: No sources due for crawl")
            return result
        
        result["source"] = source
        logger.info(f"🕷️ Crawler: Starting {source} cycle")
        
        try:
            facts = self._crawl_source(source)
            result["facts"] = len(facts)
            
            if facts and self.kg:
                # Seed into KG
                seed_result = self.kg.bulk_seed(facts, batch_size=500)
                result["new"] = seed_result.get("seeded", 0)
                self.state.stats["total_new_entities"] += result["new"]
                logger.info(f"Crawler: {source} -> {result['new']} new facts seeded to KG")
            elif facts:
                result["new"] = len(facts)
                logger.info(f"🕷️ Crawler: {source} → {len(facts)} facts (no KG connected, dry)")
            
            # Update state
            self.state.mark_crawled(source)
            self.state.stats["total_facts_ingested"] += result["new"]
            self.state.stats["total_crawl_cycles"] += 1
            self.state.save()
            
        except Exception as e:
            logger.error(f"Crawler {source} error: {e}")
            result["error"] = str(e)
        
        return result
    
    def _next_due_source(self) -> Optional[str]:
        """Find the next source that's due for crawling."""
        for _ in range(len(self._source_order)):
            source = self._source_order[self._current_idx]
            self._current_idx = (self._current_idx + 1) % len(self._source_order)
            
            interval = CRAWL_INTERVALS.get(source, 3600)
            if self.state.should_crawl(source, interval):
                return source
        return None
    
    def _crawl_source(self, source: str) -> list:
        """Execute a single source crawl — returns facts list."""
        from scripts.seed_knowledge.seed_web_crawl import (
            fetch_rss_facts,
            fetch_ddg_discovery_facts,
            fetch_article_facts,
            get_dbpedia_facts,
            DISCOVERY_TOPICS,
            ARTICLE_URLS,
            DBPEDIA_FETCHERS,
        )
        
        if source == "rss":
            return fetch_rss_facts(max_per_feed=10)
        
        elif source == "ddg":
            # Pick a subset of topics not recently searched
            import random
            topics = random.sample(DISCOVERY_TOPICS, min(10, len(DISCOVERY_TOPICS)))
            return fetch_ddg_discovery_facts(topics=topics, max_results=3)
        
        elif source == "articles":
            # Pick articles not yet visited
            import random
            unvisited = [u for u in ARTICLE_URLS if not self.state.is_visited(u)]
            if not unvisited:
                # Static articles exhausted — generate URLs from topic queue
                if self.state.topic_queue:
                    topic = self.state.topic_queue.pop(0)
                    query = topic.replace(' ', '_')
                    unvisited = [f"https://en.wikipedia.org/wiki/{query}"]
                    logger.info(f"Crawler: Static articles exhausted, seeding from topic queue: {topic}")
                else:
                    logger.info("Crawler: All articles visited and topic queue empty")
                    return []
            batch = random.sample(unvisited, min(10, len(unvisited)))
            facts = fetch_article_facts(urls=batch, max_entities_per=30)
            for url in batch:
                self.state.add_visited(url)
            return facts
        
        elif source == "dbpedia":
            # Run 2 random fetchers per cycle (light touch)
            import random
            fetchers = random.sample(DBPEDIA_FETCHERS, min(2, len(DBPEDIA_FETCHERS)))
            all_facts = []
            for fetcher in fetchers:
                try:
                    all_facts.extend(fetcher(limit=200))
                    time.sleep(1.5)
                except Exception as e:
                    logger.warning(f"Crawler DBpedia {fetcher.__name__}: {e}")
            return all_facts
        
        return []
    
    def get_status(self) -> Dict[str, Any]:
        """Get crawler status for display."""
        now = time.time()
        source_status = {}
        for source, interval in CRAWL_INTERVALS.items():
            last = self.state.last_crawl.get(source, 0)
            elapsed = now - last if last else float('inf')
            due_in = max(0, interval - elapsed)
            source_status[source] = {
                "last_crawl": datetime.datetime.fromtimestamp(last).isoformat() if last else "never",
                "due_in_minutes": round(due_in / 60, 1),
                "is_due": elapsed >= interval,
            }
        
        return {
            "sources": source_status,
            "stats": self.state.stats,
            "visited_urls": len(self.state.visited_urls),
            "topic_queue": len(self.state.topic_queue),
        }


# ── Singleton for autonomy integration ───────────────────────

_crawler_instance: Optional[ContinuousCrawler] = None

def get_crawler(kg=None) -> ContinuousCrawler:
    """Get or create the singleton crawler instance."""
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = ContinuousCrawler(kg=kg)
    elif kg is not None and _crawler_instance.kg is None:
        _crawler_instance.kg = kg
    return _crawler_instance


# ── Standalone mode ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys
    
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    
    parser = argparse.ArgumentParser(description="Continuous Knowledge Crawler")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--source", choices=["rss", "ddg", "articles", "dbpedia"],
                       help="Force a specific source")
    parser.add_argument("--status", action="store_true", help="Show crawler status")
    parser.add_argument("--live", action="store_true", help="Connect to Neo4j and seed live")
    args = parser.parse_args()
    
    kg = None
    if args.live:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from src.memory.graph import KnowledgeGraph
        kg = KnowledgeGraph()
    
    crawler = get_crawler(kg=kg)
    
    if args.status:
        import pprint
        pprint.pprint(crawler.get_status())
        sys.exit(0)
    
    if args.once:
        result = crawler.crawl_cycle(force_source=args.source)
        print(f"\nCrawl result: {json.dumps(result, indent=2, default=str)}")
    else:
        # Continuous mode
        print("🕷️ Continuous crawler started. Ctrl+C to stop.")
        try:
            while True:
                result = crawler.crawl_cycle(force_source=args.source)
                if result.get("skipped"):
                    time.sleep(60)  # Check again in 1 minute
                else:
                    print(f"  [{result['source']}] {result.get('new', 0)} facts seeded")
                    time.sleep(10)  # Brief pause between cycles
        except KeyboardInterrupt:
            print("\n🕷️ Crawler stopped. State saved.")
            crawler.state.save()
