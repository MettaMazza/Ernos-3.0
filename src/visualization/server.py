"""
KG Visualization API Server — v3.3 Mycelium Network.

Serves the graph data and health metrics to the 3D visualizer frontend.
Runs on localhost:8742 by default.

Architecture:
    - Reads from the Neo4j KnowledgeGraph (read-only)
    - Exposes /api/graph, /api/stats, /api/quarantine endpoints
    - Serves the index.html frontend
    - CORS allowed for local development only
"""
import asyncio
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("Visualization.Server")

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    logger.warning("aiohttp not installed — KG Visualizer server unavailable. pip install aiohttp")


class KGVisualizationServer:
    """
    Lightweight HTTP server for the 3D Knowledge Graph Visualizer.

    Usage:
        server = KGVisualizationServer(bot)
        await server.start()  # non-blocking; runs in background
        ...
        await server.stop()
    """

    def __init__(self, bot, host: str = "127.0.0.1", port: int = 8742):
        self.bot = bot
        self.host = host
        self.port = port
        self._app = None
        self._runner = None
        self._site = None
        self._static_dir = Path(__file__).parent / "index.html"

    async def start(self):
        if not HAS_AIOHTTP:
            logger.error("Cannot start KG Visualizer — aiohttp not installed")
            return

        self._app = web.Application()
        self._app.router.add_get("/", self._serve_frontend)
        self._app.router.add_get("/api/graph", self._handle_graph)
        self._app.router.add_get("/api/stats", self._handle_stats)
        self._app.router.add_get("/api/quarantine", self._handle_quarantine)
        self._app.router.add_get("/api/crawler/status", self._handle_crawler_status)
        self._app.router.add_post("/api/crawler/run", self._handle_crawler_run)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info(f"KG Visualizer running at http://{self.host}:{self.port}")

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
            logger.info("KG Visualizer server stopped")

    # ─── Routes ──────────────────────────────────────────────────

    async def _serve_frontend(self, request):
        html_path = Path(__file__).parent / "index.html"
        if not html_path.exists():
            return web.Response(text="index.html not found", status=404)
        return web.FileResponse(html_path)

    async def _handle_graph(self, request):
        """Return all nodes and links from the KG as JSON."""
        try:
            graph = self._get_graph()
            if not graph:
                return self._json_response({"nodes": [], "links": []})

            scope_filter = request.query.get("scope", None)
            user_filter = request.query.get("user_id", None)

            nodes, links = self._extract_graph_data(graph, scope_filter, user_filter)
            return self._json_response({"nodes": nodes, "links": links})

        except Exception as e:
            logger.error(f"Graph API error: {e}")
            return self._json_response({"error": str(e), "nodes": [], "links": []})

    async def _handle_stats(self, request):
        """Return KG health metrics."""
        try:
            graph = self._get_graph()
            if not graph:
                return self._json_response(self._empty_stats())

            stats = self._compute_stats(graph)
            return self._json_response(stats)

        except Exception as e:
            logger.error(f"Stats API error: {e}")
            return self._json_response(self._empty_stats())

    async def _handle_quarantine(self, request):
        """Return quarantine queue contents from the actual file."""
        try:
            q_path = Path("memory/quarantine.json")
            if q_path.exists():
                q_data = json.loads(q_path.read_text())
                return self._json_response({
                    "count": len(q_data),
                    "entries": q_data[:20]
                })
            
            # Fallback to graph object
            graph = self._get_graph()
            if graph and hasattr(graph, 'quarantine'):
                entries = graph.quarantine.peek(n=50)
                return self._json_response({
                    "count": len(entries),
                    "entries": entries[:20]
                })
            
            return self._json_response({"count": 0, "entries": []})
        except Exception as e:
            logger.error(f"Quarantine API error: {e}")
            return self._json_response({"count": 0, "entries": []})

    async def _handle_crawler_status(self, request):
        """Return crawler status for the frontend UI."""
        try:
            from scripts.continuous_crawler import get_crawler
            graph = self._get_graph()
            crawler = get_crawler(kg=graph)
            status = crawler.get_status()
            return self._json_response(status)
        except Exception as e:
            logger.error(f"Crawler status API error: {e}")
            return self._json_response({
                "sources": {}, "stats": {}, "visited_urls": 0, "topic_queue": 0
            })

    async def _handle_crawler_run(self, request):
        """Run a crawler cycle (optionally for a specific source)."""
        try:
            from scripts.continuous_crawler import get_crawler
            source = request.query.get("source", None)
            graph = self._get_graph()
            crawler = get_crawler(kg=graph)
            # Run in executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, crawler.crawl_cycle, source)
            return self._json_response(result)
        except Exception as e:
            logger.error(f"Crawler run API error: {e}")
            return self._json_response({"error": str(e), "new": 0})

    # ─── Data Extraction ─────────────────────────────────────────

    def _get_graph(self):
        """Get the KnowledgeGraph instance from the bot."""
        try:
            # Try the hippocampus path first
            if hasattr(self.bot, 'hippocampus') and hasattr(self.bot.hippocampus, 'graph'):
                return self.bot.hippocampus.graph
            # Try direct graph attribute
            if hasattr(self.bot, 'graph'):
                return self.bot.graph
            # Try via cognitive system
            if hasattr(self.bot, 'cognition') and hasattr(self.bot.cognition, 'hippocampus'):
                return self.bot.cognition.hippocampus.graph
        except Exception as e:
            logger.debug(f"Suppressed: {e}")
        return None

    def _extract_graph_data(self, graph, scope_filter=None, user_filter=None):
        """
        Pull nodes and edges from Neo4j into JSON-friendly format.

        IMPORTANT: Nodes are stored as :Entity with layer as a PROPERTY,
        not as a Neo4j label. We query generically and read the layer property.
        """
        nodes = []
        links = []

        try:
            if not hasattr(graph, 'driver') or not graph.driver:
                return nodes, links

            seen_nodes = set()
            node_id_map = {}  # Map element_id -> our node id for link matching

            with graph.driver.session() as session:
                # Query nodes by scope — fetch ALL non-CORE scopes first to ensure
                # they aren't drowned out by the 15K+ CORE nodes
                all_records = []
                for priority_scope in ("PUBLIC", "PRIVATE", "LINEAGE"):
                    r = session.run(
                        "MATCH (n) WHERE n.scope = $scope RETURN n, labels(n) as lbls",
                        scope=priority_scope
                    )
                    all_records.extend(list(r))
                # Then CORE and untagged nodes (capped)
                r = session.run(
                    "MATCH (n) WHERE n.scope IS NULL OR n.scope = 'CORE' "
                    "RETURN n, labels(n) as lbls LIMIT 20000"
                )
                all_records.extend(list(r))

                result = all_records
                for record in result:
                    node = record["n"]
                    lbls = record["lbls"]
                    node_id = str(node.element_id) if hasattr(node, 'element_id') else str(node.id)

                    if node_id in seen_nodes:
                        continue
                    seen_nodes.add(node_id)

                    props = dict(node.items())
                    node_scope = props.get("scope", "UNKNOWN")
                    node_uid = props.get("user_id")
                    # Layer is stored as a property, not as a Neo4j label
                    node_layer = props.get("layer", "system")
                    if isinstance(node_layer, str):
                        node_layer = node_layer.lower()

                    # Apply filters
                    if scope_filter and node_scope != scope_filter:
                        continue
                    if user_filter and str(node_uid) != str(user_filter):
                        continue

                    node_entry = {
                        "id": node_id,
                        "name": props.get("name", props.get("label", node_id)),
                        "layer": node_layer,
                        "scope": node_scope,
                        "user_id": node_uid,
                        "quarantined": False
                    }
                    nodes.append(node_entry)
                    node_id_map[node_id] = node_entry

                # Query ALL relationships
                result = session.run(
                    "MATCH (a)-[r]->(b) "
                    "RETURN elementId(a) as src_id, elementId(b) as tgt_id, "
                    "type(r) as rel_type, properties(r) as rel_props "
                    "LIMIT 50000"
                )
                for record in result:
                    src_id = str(record["src_id"])
                    tgt_id = str(record["tgt_id"])
                    if src_id in seen_nodes and tgt_id in seen_nodes:
                        links.append({
                            "source": src_id,
                            "target": tgt_id,
                            "type": record["rel_type"],
                            "layer": (record["rel_props"] or {}).get("layer", "system")
                        })

        except Exception as e:
            logger.error(f"Graph extraction failed: {e}")

        # Add quarantined entries as ghost nodes
        try:
            q_path = Path("memory/quarantine.json")
            if q_path.exists():
                import json as _json
                q_entries = _json.loads(q_path.read_text())[:20]
                for i, entry in enumerate(q_entries):
                    q_id = f"quarantine_{i}"
                    nodes.append({
                        "id": q_id,
                        "name": f"\u26a0 {entry.get('source', '?')} \u2192 {entry.get('target', '?')}",
                        "layer": entry.get("layer", "system").lower(),
                        "scope": entry.get("props", {}).get("scope", "UNKNOWN"),
                        "user_id": None,
                        "quarantined": True
                    })
        except Exception as e:
            logger.debug(f"Suppressed: {e}")

        return nodes, links

    def _compute_stats(self, graph):
        """Compute health metrics for the KG."""
        stats = self._empty_stats()

        try:
            if hasattr(graph, 'driver') and graph.driver:
                with graph.driver.session() as session:
                    # Total nodes
                    result = session.run("MATCH (n) RETURN count(n) as c")
                    stats["total_nodes"] = result.single()["c"]

                    # Total edges
                    result = session.run("MATCH ()-[r]->() RETURN count(r) as c")
                    stats["total_edges"] = result.single()["c"]

                    # Active layers — count distinct layer PROPERTY values
                    result = session.run(
                        "MATCH (n) WHERE n.layer IS NOT NULL "
                        "RETURN count(DISTINCT n.layer) as c"
                    )
                    stats["active_layers"] = result.single()["c"]

                    # Orphaned nodes (no relationships)
                    result = session.run(
                        "MATCH (n) WHERE NOT (n)--() RETURN count(n) as c"
                    )
                    stats["orphaned_nodes"] = result.single()["c"]

            # Quarantine count — read from actual file, not stale cache
            try:
                q_path = Path("memory/quarantine.json")
                if q_path.exists():
                    import json as _json
                    q_data = _json.loads(q_path.read_text())
                    stats["quarantine_count"] = len(q_data)
                elif hasattr(graph, 'quarantine'):
                    stats["quarantine_count"] = len(graph.quarantine.peek(n=100))
            except Exception as e:
                logger.debug(f"Quarantine stats read failed: {e}")

            # Health score: 1.0 = perfect, lower = more issues
            total = stats["total_nodes"]
            if total > 0:
                orphan_ratio = stats["orphaned_nodes"] / total
                quarantine_penalty = min(stats["quarantine_count"] * 0.02, 0.3)
                stats["health_score"] = round(max(0.0, 1.0 - orphan_ratio - quarantine_penalty), 2)

        except Exception as e:
            logger.error(f"Stats computation failed: {e}")

        return stats

    def _empty_stats(self):
        return {
            "total_nodes": 0,
            "total_edges": 0,
            "active_layers": 0,
            "orphaned_nodes": 0,
            "quarantine_count": 0,
            "health_score": None
        }

    def _json_response(self, data):
        return web.Response(
            text=json.dumps(data, default=str),
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
