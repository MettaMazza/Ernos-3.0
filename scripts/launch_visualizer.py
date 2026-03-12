"""
Standalone KG Visualizer Launcher — No bot required.
Connects directly to Neo4j and serves the 3D visualization.

Usage: python scripts/launch_visualizer.py
Then open http://localhost:8742
"""
import sys, os, json, asyncio, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("Visualizer.Standalone")

HTML_PATH = Path(__file__).parent.parent / "src" / "visualization" / "index.html"
HOST = "127.0.0.1"
PORT = 8742


def get_graph():
    from src.memory.graph import KnowledgeGraph
    return KnowledgeGraph()


def extract_data(graph, scope_filter=None):
    nodes, links = [], []
    seen = set()
    node_id_map = {}

    with graph.driver.session() as session:
        result = session.run("MATCH (n) RETURN n, labels(n) as lbls LIMIT 50000")
        for record in result:
            node = record["n"]
            nid = str(node.element_id) if hasattr(node, 'element_id') else str(node.id)
            if nid in seen:
                continue
            seen.add(nid)
            props = dict(node.items())
            scope = props.get("scope", "PRIVATE")
            if scope_filter and scope != scope_filter:
                continue
            layer = props.get("layer", "system")
            if isinstance(layer, str):
                layer = layer.lower()
            entry = {
                "id": nid,
                "name": props.get("name", props.get("label", nid)),
                "layer": layer,
                "scope": scope,
                "user_id": props.get("user_id"),
                "quarantined": False,
                "immutable": props.get("immutable", False)
            }
            nodes.append(entry)
            node_id_map[nid] = entry

        result = session.run(
            "MATCH (a)-[r]->(b) "
            "RETURN elementId(a) as src_id, elementId(b) as tgt_id, "
            "type(r) as rel_type, properties(r) as rel_props LIMIT 100000"
        )
        for record in result:
            src = str(record["src_id"])
            tgt = str(record["tgt_id"])
            if src in seen and tgt in seen:
                links.append({
                    "source": src,
                    "target": tgt,
                    "type": record["rel_type"],
                    "layer": (record["rel_props"] or {}).get("layer", "system")
                })

    # Quarantine ghost nodes
    q_path = Path("memory/quarantine.json")
    if q_path.exists():
        try:
            entries = json.loads(q_path.read_text())[:20]
            for i, e in enumerate(entries):
                nodes.append({
                    "id": f"quarantine_{i}",
                    "name": f"⚠ {e.get('source','?')} → {e.get('target','?')}",
                    "layer": e.get("layer", "system").lower(),
                    "scope": "QUARANTINE",
                    "user_id": None,
                    "quarantined": True
                })
        except Exception:
            pass

    return nodes, links


def compute_stats(graph):
    stats = {
        "total_nodes": 0, "total_edges": 0, "active_layers": 0,
        "orphaned_nodes": 0, "quarantine_count": 0, "health_score": None
    }
    with graph.driver.session() as session:
        stats["total_nodes"] = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
        stats["total_edges"] = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
        stats["active_layers"] = session.run(
            "MATCH (n) WHERE n.layer IS NOT NULL RETURN count(DISTINCT n.layer) as c"
        ).single()["c"]
        stats["orphaned_nodes"] = session.run(
            "MATCH (n) WHERE NOT (n)--() RETURN count(n) as c"
        ).single()["c"]

    # Quarantine count
    q_path = Path("memory/quarantine.json")
    if q_path.exists():
        try:
            stats["quarantine_count"] = len(json.loads(q_path.read_text()))
        except Exception:
            pass

    # Health score
    total = stats["total_nodes"]
    if total > 0:
        orphan_ratio = stats["orphaned_nodes"] / total
        q_penalty = min(stats["quarantine_count"] * 0.02, 0.3)
        stats["health_score"] = round(max(0.0, 1.0 - orphan_ratio - q_penalty), 2)

    return stats


# ── Routes ─────────────────────────────────────────────────────

kg = None

async def handle_index(request):
    if not HTML_PATH.exists():
        return web.Response(text="index.html not found", status=404)
    return web.FileResponse(HTML_PATH)

async def handle_graph(request):
    scope = request.query.get("scope", None)
    nodes, links = extract_data(kg, scope_filter=scope)
    return web.json_response({"nodes": nodes, "links": links})

async def handle_stats(request):
    stats = compute_stats(kg)
    return web.json_response(stats)

async def handle_quarantine(request):
    q_path = Path("memory/quarantine.json")
    if q_path.exists():
        entries = json.loads(q_path.read_text())
        return web.json_response({"count": len(entries), "entries": entries[:20]})
    return web.json_response({"count": 0, "entries": []})


# ── Crawler API ────────────────────────────────────────────────

async def handle_crawler_status(request):
    """Get crawler status for the UI panel."""
    try:
        from scripts.continuous_crawler import get_crawler
        crawler = get_crawler(kg=kg)
        status = crawler.get_status()
        return web.json_response(status)
    except Exception as e:
        return web.json_response({"error": str(e), "stats": {}, "sources": {}})


async def handle_crawler_run(request):
    """Trigger a crawl cycle from the UI."""
    try:
        source = request.query.get("source", None)
        from scripts.continuous_crawler import get_crawler
        crawler = get_crawler(kg=kg)
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, crawler.crawl_cycle, source)
        return web.json_response(result, default=str)
    except Exception as e:
        return web.json_response({"error": str(e), "facts": 0, "new": 0})


async def main():
    global kg
    kg = get_graph()
    
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/graph", handle_graph)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_get("/api/quarantine", handle_quarantine)
    app.router.add_get("/api/crawler/status", handle_crawler_status)
    app.router.add_post("/api/crawler/run", handle_crawler_run)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    
    print(f"\n{'='*50}")
    print(f"  🧠 KG Visualizer running at:")
    print(f"  http://{HOST}:{PORT}")
    print(f"  http://{HOST}:{PORT}?scope=CORE  (foundation only)")
    print(f"{'='*50}\n")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await runner.cleanup()
        kg.close()


if __name__ == "__main__":
    asyncio.run(main())
