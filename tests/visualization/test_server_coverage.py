import pytest
import asyncio
import json
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from src.visualization.server import KGVisualizationServer, HAS_AIOHTTP


class TestVisualizationServerCoverage:
    def setup_method(self):
        self.bot = MagicMock()

    @pytest.mark.asyncio
    @patch("src.visualization.server.HAS_AIOHTTP", False)
    async def test_start_no_aiohttp(self):
        server = KGVisualizationServer(self.bot)
        # Should return early without setting up _app
        await server.start()
        assert server._app is None

    @pytest.mark.asyncio
    @patch("src.visualization.server.web")
    async def test_start_and_stop_success(self, mock_web):
        server = KGVisualizationServer(self.bot)
        mock_runner = AsyncMock()
        mock_web.AppRunner.return_value = mock_runner
        mock_site = AsyncMock()
        mock_web.TCPSite.return_value = mock_site

        await server.start()
        
        assert server._app is not None
        mock_web.Application.assert_called_once()
        mock_runner.setup.assert_awaited_once()
        mock_site.start.assert_awaited_once()

        await server.stop()
        mock_runner.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("src.visualization.server.Path.exists")
    @patch("src.visualization.server.web")
    async def test_serve_frontend_not_found(self, mock_web, mock_exists):
        server = KGVisualizationServer(self.bot)
        mock_exists.return_value = False
        
        mock_response = MagicMock()
        mock_web.Response = MagicMock(return_value=mock_response)
        
        request = MagicMock()
        res = await server._serve_frontend(request)
        
        mock_web.Response.assert_called_once_with(text="index.html not found", status=404)
        assert res == mock_response

    @pytest.mark.asyncio
    @patch("src.visualization.server.data_dir")
    async def test_handle_quarantine_fallback_graph(self, mock_data_dir):
        # When quarantine.json doesn't exist but graph.quarantine does
        server = KGVisualizationServer(self.bot)
        
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_dir = MagicMock()
        mock_dir.__truediv__.return_value = mock_path
        mock_data_dir.return_value = mock_dir
        
        graph = MagicMock()
        graph.quarantine.peek.return_value = [{"entry": 1}, {"entry": 2}]
        server._get_graph = MagicMock(return_value=graph)
        
        request = MagicMock()
        
        # Need to patch hasattr so graph.quarantine works, MagicMock usually handles it
        with patch.object(server, "_json_response") as mock_json:
            res = await server._handle_quarantine(request)
            mock_json.assert_called_once()
            args, _ = mock_json.call_args
            assert args[0]["count"] == 2

    @pytest.mark.asyncio
    async def test_handle_crawler_status_error(self):
        server = KGVisualizationServer(self.bot)
        # Force an ImportError or Exception inside
        server._get_graph = MagicMock(side_effect=Exception("Crawler error"))
        
        request = MagicMock()
        with patch.object(server, "_json_response") as mock_json:
            await server._handle_crawler_status(request)
            mock_json.assert_called_once()
            args, _ = mock_json.call_args
            assert args[0] == {"sources": {}, "stats": {}, "visited_urls": 0, "topic_queue": 0}

    @pytest.mark.asyncio
    @patch("src.visualization.server.asyncio.get_event_loop")
    async def test_handle_crawler_run(self, mock_get_loop):
        server = KGVisualizationServer(self.bot)
        
        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock(return_value={"new": 5})
        mock_get_loop.return_value = mock_loop
        
        request = MagicMock()
        request.query.get.return_value = "source1"
        
        mock_module = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.crawl_cycle = MagicMock(return_value={"new": 5})
        mock_module.get_crawler.return_value = mock_crawler
        
        with patch.dict("sys.modules", {"scripts.continuous_crawler": mock_module}):
            with patch.object(server, "_json_response") as mock_json:
                await server._handle_crawler_run(request)
                mock_json.assert_called_once_with({"new": 5})

    @pytest.mark.asyncio
    async def test_handle_crawler_run_error(self):
        server = KGVisualizationServer(self.bot)
        server._get_graph = MagicMock(side_effect=Exception("Run error"))
        request = MagicMock()
        
        with patch.object(server, "_json_response") as mock_json:
            await server._handle_crawler_run(request)
            mock_json.assert_called_once_with({"error": "Run error", "new": 0})

    def test_get_graph_cognition_hippocampus(self):
        # Need to delete bot.hippocampus and bot.graph to reach cognition
        delattr(self.bot, "hippocampus")
        delattr(self.bot, "graph")
        
        mock_tape_engine = MagicMock()
        mock_hippocampus = MagicMock()
        mock_graph = MagicMock()
        
        mock_hippocampus.graph = mock_graph
        mock_tape_engine.hippocampus = mock_hippocampus
        self.bot.cognition = mock_tape_engine
        
        server = KGVisualizationServer(self.bot)
        res = server._get_graph()
        assert res == mock_graph

    @patch("src.visualization.server.data_dir")
    def test_extract_graph_data(self, mock_data_dir):
        # Mock data_dir to prevent reading real quarantine.json
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_data_dir.return_value = mock_path

        server = KGVisualizationServer(self.bot)
        graph = MagicMock()
        
        # Test full driver logic
        session = MagicMock()
        graph.driver.session.return_value.__enter__.return_value = session
        
        # Mock records
        # Node record
        node1 = MagicMock()
        node1.element_id = "node1"
        node1.items.return_value = [("scope", "PUBLIC"), ("name", "Node 1"), ("layer", "core")]
        
        node2 = MagicMock()
        node2.element_id = "node2"
        # No scope property or layer
        node2.items.return_value = [("user_id", "123")]
        
        # Duplicate node to test seen_nodes filter
        
        record1 = {"n": node1, "lbls": ["Entity"]}
        record2 = {"n": node2, "lbls": ["Entity"]}
        
        # For nodes we have multiple session.run calls
        # 5 scope priorities + 1 CORE + 1 ALL
        # We can just return empty lists for most and our records for one
        def run_side_effect(query, **kwargs):
            if "MATCH (n) WHERE n.scope = $scope" in query:
                if kwargs.get("scope") == "PUBLIC":
                    return [record1, record1] # duplicate to test seen_nodes
                return []
            if "LIMIT 20000" in query:
                return [record2]
            if "MATCH (a)-[r]->(b)" in query:
                return [{"src_id": "node1", "tgt_id": "node2", "rel_type": "KNOWS", "rel_props": {"layer": "sub"}}]
            return []
            
        session.run.side_effect = run_side_effect
        
        nodes, links = server._extract_graph_data(graph)
        
        assert len(nodes) == 2
        assert len(links) == 1
        assert nodes[0]["id"] == "node1"
        assert nodes[1]["id"] == "node2"
        assert links[0]["source"] == "node1"
        assert links[0]["target"] == "node2"

    @patch("src.visualization.server.data_dir")
    def test_extract_graph_data_with_quarantine(self, mock_data_dir):
        server = KGVisualizationServer(self.bot)
        graph = MagicMock()
        
        session = MagicMock()
        graph.driver.session.return_value.__enter__.return_value = session
        session.run.return_value = [] # No normal nodes
        
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = json.dumps([{"source": "A", "target": "B", "layer": "bot"}])
        mock_data_dir.return_value = MagicMock()
        mock_data_dir.return_value.__truediv__.return_value = mock_path
        
        nodes, links = server._extract_graph_data(graph)
        
        assert len(nodes) == 1
        assert len(links) == 0
        assert nodes[0]["quarantined"] is True
        assert "A" in nodes[0]["name"]
        assert "B" in nodes[0]["name"]

    @patch("src.visualization.server.data_dir")
    def test_extract_graph_data_filter(self, mock_data_dir):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_data_dir.return_value = mock_path

        # test scope_filter and user_filter
        server = KGVisualizationServer(self.bot)
        graph = MagicMock()
        
        session = MagicMock()
        graph.driver.session.return_value.__enter__.return_value = session
        
        node1 = MagicMock()
        node1.element_id = "node1"
        node1.items.return_value = [("scope", "PUBLIC"), ("user_id", "user1")]
        
        record1 = {"n": node1, "lbls": ["Entity"]}
        
        def run_side_effect(query, **kwargs):
            if "MATCH (n) WHERE n.scope = $scope RETURN n" in query and kwargs.get("scope") == "PUBLIC":
                return [record1]
            return []
            
        session.run.side_effect = run_side_effect
        
        # Test scope filter mismatch
        nodes, _ = server._extract_graph_data(graph, scope_filter="PRIVATE")
        assert len(nodes) == 0
        
        # Test user_filter mismatch
        nodes, _ = server._extract_graph_data(graph, user_filter="user2")
        assert len(nodes) == 0
        
        # Test match
        nodes, _ = server._extract_graph_data(graph, scope_filter="PUBLIC", user_filter="user1")
        assert len(nodes) == 1

    def test_compute_stats_fallbacks(self):
        server = KGVisualizationServer(self.bot)
        # Trigger exception path in compute_stats
        graph = MagicMock()
        # To trigger exception, have session run raise Exception
        graph.driver.session.side_effect = Exception("DB error")
        
        stats = server._compute_stats(graph)
        assert stats["total_nodes"] == 0
        assert stats["health_score"] is None

    @patch("src.visualization.server.data_dir")
    def test_compute_stats_quarantine_fallback(self, mock_data_dir):
        server = KGVisualizationServer(self.bot)
        graph = MagicMock()
        
        session = MagicMock()
        graph.driver.session.return_value.__enter__.return_value = session
        
        def run_side_effect(query, **kwargs):
            mock_res = MagicMock()
            if "NOT (n)--()" in query:
                mock_res.single.return_value = {"c": 5}
            elif "count(n)" in query:
                mock_res.single.return_value = {"c": 100}
            elif "count(r)" in query:
                mock_res.single.return_value = {"c": 200}
            elif "DISTINCT n.layer" in query:
                mock_res.single.return_value = {"c": 3}
            elif "return count" in query.lower():
                mock_res.single.return_value = {"c": 0}
            else:
                 mock_res.single.return_value = {"c": 100} # default for count
            return mock_res
            
        session.run.side_effect = run_side_effect
        
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_dir = MagicMock()
        mock_dir.__truediv__.return_value = mock_path
        mock_data_dir.return_value = mock_dir
        
        graph.quarantine.peek.return_value = [1, 2, 3, 4, 5]
        
        stats = server._compute_stats(graph)
        assert stats["total_nodes"] == 100
        assert stats["orphaned_nodes"] == 5
        assert stats["quarantine_count"] == 5
        # health = 1.0 - (5/100) - min(5*0.02, 0.3) = 1.0 - 0.05 - 0.1 = 0.85
        assert stats["health_score"] == 0.85
        assert stats["quarantine_count"] == 5
        assert stats["health_score"] == 0.85

    @pytest.mark.asyncio
    @patch("src.visualization.server.data_dir")
    async def test_handle_quarantine_file_success(self, mock_data_dir):
        server = KGVisualizationServer(self.bot)
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = json.dumps([{"source": "X", "target": "Y"}])
        mock_dir = MagicMock()
        mock_dir.__truediv__.return_value = mock_path
        mock_data_dir.return_value = mock_dir
        
        request = MagicMock()
        res = await server._handle_quarantine(request)
        assert res.status == 200
        
        body = json.loads(res.text)
        assert body["count"] == 1
        assert body["entries"][0]["source"] == "X"

    def test_extract_graph_data_no_driver(self):
        server = KGVisualizationServer(self.bot)
        graph = MagicMock()
        graph.driver = None
        nodes, links = server._extract_graph_data(graph)
        assert len(nodes) == 0
        assert len(links) == 0

    @patch("src.visualization.server.data_dir")
    def test_compute_stats_quarantine_json_read(self, mock_data_dir):
        server = KGVisualizationServer(self.bot)
        # Test the branch that reads quarantine.json successfully
        graph = MagicMock()
        session = MagicMock()
        graph.driver.session.return_value.__enter__.return_value = session
        
        def run_side_effect(query, **kwargs):
            mock_res = MagicMock()
            mock_res.single.return_value = {"c": 100}
            return mock_res
        session.run.side_effect = run_side_effect
        
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = json.dumps([{"a": 1}, {"b": 2}])
        mock_dir = MagicMock()
        mock_dir.__truediv__.return_value = mock_path
        mock_data_dir.return_value = mock_dir
        
        stats = server._compute_stats(graph)
        assert stats["quarantine_count"] == 2

    @pytest.mark.asyncio
    @patch("src.visualization.server.Path.exists")
    @patch("src.visualization.server.web")
    async def test_serve_frontend_success(self, mock_web, mock_exists):
        server = KGVisualizationServer(self.bot)
        mock_exists.return_value = True
        
        mock_response = MagicMock()
        mock_web.FileResponse = MagicMock(return_value=mock_response)
        
        request = MagicMock()
        res = await server._serve_frontend(request)
        
        mock_web.FileResponse.assert_called_once()
        assert res == mock_response

    @pytest.mark.asyncio
    async def test_handle_graph_success(self):
        server = KGVisualizationServer(self.bot)
        server._get_graph = MagicMock(return_value=MagicMock())
        server._extract_graph_data = MagicMock(return_value=([{"id": 1}], [{"source": 1, "target": 2}]))
        
        request = MagicMock()
        request.query.get.side_effect = lambda k, default=None: "user1" if k == "user_id" else default
        
        with patch.object(server, "_json_response") as mock_json:
            await server._handle_graph(request)
            mock_json.assert_called_once()
            args, _ = mock_json.call_args
            assert args[0]["nodes"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_handle_graph_empty_and_error(self):
        server = KGVisualizationServer(self.bot)
        server._get_graph = MagicMock(return_value=None)
        
        request = MagicMock()
        with patch.object(server, "_json_response") as mock_json:
            await server._handle_graph(request)
            mock_json.assert_called_once()
            assert mock_json.call_args[0][0]["nodes"] == []
            
        server._get_graph.side_effect = Exception("Graph error")
        with patch.object(server, "_json_response") as mock_json:
            await server._handle_graph(request)
            mock_json.assert_called_once()
            assert mock_json.call_args[0][0]["error"] == "Graph error"

    @pytest.mark.asyncio
    async def test_handle_stats_success(self):
        server = KGVisualizationServer(self.bot)
        server._get_graph = MagicMock(return_value=MagicMock())
        server._compute_stats = MagicMock(return_value={"total_nodes": 100})
        
        request = MagicMock()
        
        with patch.object(server, "_json_response") as mock_json:
            await server._handle_stats(request)
            mock_json.assert_called_once()
            assert mock_json.call_args[0][0]["total_nodes"] == 100

    @pytest.mark.asyncio
    async def test_handle_stats_empty_and_error(self):
        server = KGVisualizationServer(self.bot)
        server._get_graph = MagicMock(return_value=None)
        
        request = MagicMock()
        with patch.object(server, "_json_response") as mock_json:
            await server._handle_stats(request)
            mock_json.assert_called_once()
            assert mock_json.call_args[0][0]["total_nodes"] == 0
            
        server._get_graph.side_effect = Exception("Stats error")
        with patch.object(server, "_json_response") as mock_json:
            await server._handle_stats(request)
            mock_json.assert_called_once()
            assert mock_json.call_args[0][0]["total_nodes"] == 0

    @pytest.mark.asyncio
    async def test_handle_crawler_status_success(self):
        server = KGVisualizationServer(self.bot)
        server._get_graph = MagicMock(return_value=MagicMock())
        
        request = MagicMock()
        mock_module = MagicMock()
        mock_crawler = MagicMock()
        mock_crawler.get_status.return_value = {"visited_urls": 42}
        mock_module.get_crawler.return_value = mock_crawler
        
        with patch.dict("sys.modules", {"scripts.continuous_crawler": mock_module}):
            with patch.object(server, "_json_response") as mock_json:
                await server._handle_crawler_status(request)
                mock_json.assert_called_once()
                assert mock_json.call_args[0][0]["visited_urls"] == 42
