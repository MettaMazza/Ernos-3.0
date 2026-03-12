"""
Tests — KG Visualization Server & Tool (v3.3)

Tests the visualization server routes, data extraction,
and the manage_kg_visualizer tool.
"""
import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestKGServerDataExtraction(unittest.TestCase):
    """Test data extraction methods of the server (no real Neo4j needed)."""

    def _make_server(self):
        from src.visualization.server import KGVisualizationServer
        bot = MagicMock()
        bot.hippocampus = MagicMock()
        bot.hippocampus.graph = MagicMock()
        return KGVisualizationServer(bot), bot

    def test_get_graph_from_hippocampus(self):
        server, bot = self._make_server()
        graph = server._get_graph()
        self.assertIsNotNone(graph)

    def test_get_graph_returns_none_when_missing(self):
        from src.visualization.server import KGVisualizationServer
        bot = MagicMock(spec=[])  # no attributes
        server = KGVisualizationServer(bot)
        self.assertIsNone(server._get_graph())

    def test_empty_stats(self):
        server, _ = self._make_server()
        stats = server._empty_stats()
        self.assertEqual(stats["total_nodes"], 0)
        self.assertEqual(stats["total_edges"], 0)
        self.assertIsNone(stats["health_score"])

    def test_json_response_cors(self):
        server, _ = self._make_server()
        resp = server._json_response({"test": True})
        self.assertEqual(resp.content_type, "application/json")
        self.assertIn("Access-Control-Allow-Origin", resp.headers)


class TestVisualizationTool(unittest.TestCase):
    """Test the manage_kg_visualizer tool."""

    @patch('socket.socket')
    def test_status_when_not_running(self, mock_socket_cls):
        # Make _port_in_use return False (port not bound)
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_sock.connect_ex.return_value = 1  # Connection refused = not in use
        mock_socket_cls.return_value = mock_sock
        import src.tools.visualization_tools as vt
        vt._server_instance = None
        result = _run(vt.manage_kg_visualizer(action="status"))
        self.assertIn("not running", result)

    def test_stop_when_not_running(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = None
        result = _run(vt.manage_kg_visualizer(action="stop"))
        self.assertIn("not running", result)

    @patch('socket.socket')
    def test_start_without_bot(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_sock.connect_ex.return_value = 1  # Connection refused = not in use
        mock_socket_cls.return_value = mock_sock
        import src.tools.visualization_tools as vt
        vt._server_instance = None
        result = _run(vt.manage_kg_visualizer(action="start"))
        self.assertIn("❌", result)

    def test_unknown_action(self):
        import src.tools.visualization_tools as vt
        result = _run(vt.manage_kg_visualizer(action="explode"))
        self.assertIn("Unknown action", result)

    def test_already_running(self):
        import src.tools.visualization_tools as vt
        vt._server_instance = MagicMock()
        result = _run(vt.manage_kg_visualizer(action="start"))
        self.assertIn("already running", result)
        vt._server_instance = None  # reset


class TestFrontendExists(unittest.TestCase):
    """Verify the frontend file exists and has expected content."""

    def test_index_html_exists(self):
        html = Path(__file__).parent.parent / "src" / "visualization" / "index.html"
        self.assertTrue(html.exists(), "index.html should exist")

    def test_index_html_has_3d_graph(self):
        html = Path(__file__).parent.parent / "src" / "visualization" / "index.html"
        content = html.read_text()
        self.assertIn("3d-force-graph", content)
        self.assertIn("/api/graph", content)
        self.assertIn("LAYER_COLORS", content)

    def test_index_html_has_layer_legend(self):
        html = Path(__file__).parent.parent / "src" / "visualization" / "index.html"
        content = html.read_text()
        self.assertIn("narrative", content)
        self.assertIn("epistemic", content)
        self.assertIn("quarantine", content.lower())


if __name__ == "__main__":
    unittest.main()
