# Audit Report: `scripts/`

## Overview
The `scripts/` directory houses standalone utilities that are not loaded during the normal runtime execution of the Discord bot (with the exception of the crawler, which can be invoked by a daemon). These scripts generally focus on heavy database mutations, initial grounding knowledge ingestion, and developer tooling.

---

## Technical Analysis

### 1. `launch_visualizer.py`
**Functionality:** A standalone HTTP frontend for the Knowledge Graph.
**Key Mechanisms:**
- Bypasses the bot entirely, connecting directly to Neo4j.
- Spins up an `aiohttp` web server on `http://127.0.0.1:8742`.
- Serves the `index.html` from the `visualiser/` directory and exposes a REST API (`/api/graph`, `/api/stats`, `/api/quarantine`) to feed D3.js node data to the frontend.

### 2. `continuous_crawler.py`
**Functionality:** An autonomous knowledge discovery engine.
**Key Mechanisms:**
- Maintains a persistent `memory/crawl_state.json` file.
- Schedules different extraction intervals based on target type (RSS feeds every 1 hour, DuckDuckGo searches every 6 hours, deep Wikipedia/DBpedia ingestion every 24 hours).
- Provides a `crawl_cycle()` method designed to be invoked by the `AgencyDaemon` when the bot is idle, allowing Ernos to "read the internet" while users are asleep.

### 3. `reclassify_kg_layers.py`
**Functionality:** A heavy Neo4j migration script.
**Key Mechanisms:**
- Performs a one-time reclassification of all `:Entity` nodes and relationships in the Knowledge Graph into specific cognitive "layers" (e.g., spatial, motivational, creative, moral) based on their predicates.
- Uses a deterministic dictionary of `HIGH_CONFIDENCE_PREDICATES` (e.g., `LOCATED_IN -> spatial`, `SINNED -> moral`) to avoid massive LLM token costs when migrating tens of thousands of nodes.
- Also includes logic to process and re-parent "quarantined" memories belonging to missing users.

### 4. `seed_knowledge/` (Subdirectory)
**Functionality:** The foundational bootstrapping suite.
**Key Mechanisms:**
- Contains 12 massive ingestion scripts (e.g., `seed_arxiv.py`, `seed_wikipedia.py`, `mass_scrape_prompt.py`).
- Used by developers to inject baseline "world knowledge" into Ernos's empty brain before deploying it, ensuring the bot doesn't start with total amnesia regarding common concepts.

---

## Technical Debt & Observations
1. **Visualizer Coupling:** `launch_visualizer.py` manually reads from `src/visualization/index.html`. In the codebase, we've observed the frontend code is actually inside `visualiser/` (note the 's' spelling). This means the path `Path(__file__).parent.parent / "src" / "visualization" / "index.html"` may actually be broken or referring to a deprecated internal directory instead of the external `visualiser/` root directory.
2. **Crawler State Management:** `continuous_crawler.py` writes directly to a JSON state file. Because the bot's daemons and the standalone visualizer UI both attempt to invoke this crawler, there could be race conditions corrupting `crawl_state.json` if both processes run simultaneously.
