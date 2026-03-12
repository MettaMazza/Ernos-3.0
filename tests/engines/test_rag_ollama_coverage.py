"""
Coverage tests for src/engines/rag_ollama.py.
Targets 36 uncovered lines in VectorEnhancedOllamaEngine.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestVectorEnhancedOllamaEngine:
    def _make_engine(self):
        with patch("ollama.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            from src.engines.rag_ollama import VectorEnhancedOllamaEngine
            engine = VectorEnhancedOllamaEngine("llama3.2")
            engine._client = mock_client
            return engine

    def test_name(self):
        engine = self._make_engine()
        assert "llama3.2" in engine.name

    def test_context_limit_local(self):
        engine = self._make_engine()
        assert engine.context_limit > 0

    def test_context_limit_cloud(self):
        with patch("ollama.Client"):
            from src.engines.rag_ollama import VectorEnhancedOllamaEngine
            with patch("config.settings") as s:
                s.OLLAMA_CLOUD_MODEL = "gpt-4o"
                s.CONTEXT_CHAR_LIMIT_CLOUD = 128000
                engine = VectorEnhancedOllamaEngine("gpt-4o")
                assert engine.context_limit == 128000

    def test_num_predict_local(self):
        engine = self._make_engine()
        assert engine._num_predict > 0

    def test_num_predict_cloud(self):
        with patch("ollama.Client"):
            from src.engines.rag_ollama import VectorEnhancedOllamaEngine
            with patch("config.settings") as s:
                s.OLLAMA_CLOUD_MODEL = "gpt-4o"
                s.OUTPUT_TOKEN_LIMIT_CLOUD = 32768
                engine = VectorEnhancedOllamaEngine("gpt-4o")
                assert engine._num_predict == 32768

    def test_add_knowledge(self):
        engine = self._make_engine()
        engine.embedder = MagicMock()
        engine.embedder.get_embedding.return_value = [0.1, 0.2, 0.3]
        engine.vector_store = MagicMock()
        with patch("src.memory.chunking.chunk_text", return_value=["chunk1"]):
            engine.add_knowledge("test knowledge", {"source": "test"})
        engine.vector_store.add_element.assert_called_once()

    def test_generate_response_basic(self):
        engine = self._make_engine()
        engine.embedder = MagicMock()
        engine.embedder.get_embedding.return_value = [0.1]
        engine.vector_store = MagicMock()
        engine.vector_store.retrieve.return_value = []
        mock_resp = MagicMock()
        mock_resp.response = "Hello!"
        mock_resp.eval_count = 10
        mock_resp.done_reason = "stop"
        engine._client.generate.return_value = mock_resp
        with patch("src.memory.chunking.chunk_text", return_value=["hi"]):
            result = engine.generate_response("Hi there")
        assert result == "Hello!"

    def test_generate_response_with_context(self):
        engine = self._make_engine()
        mock_resp = MagicMock()
        mock_resp.response = "Answer with context"
        mock_resp.eval_count = 20
        mock_resp.done_reason = "stop"
        engine._client.generate.return_value = mock_resp
        result = engine.generate_response("Question?", context="some context")
        assert result == "Answer with context"

    def test_generate_response_with_system_prompt(self):
        engine = self._make_engine()
        mock_resp = MagicMock()
        mock_resp.response = "Pirate response"
        mock_resp.eval_count = 15
        mock_resp.done_reason = "stop"
        engine._client.generate.return_value = mock_resp
        result = engine.generate_response("Hi", context="ctx", system_prompt="You are a pirate")
        assert result == "Pirate response"
        # Verify system was passed
        call_kwargs = engine._client.generate.call_args
        assert call_kwargs[1].get("system") == "You are a pirate" or call_kwargs.kwargs.get("system") == "You are a pirate"

    def test_generate_response_with_images(self):
        engine = self._make_engine()
        mock_resp = MagicMock()
        mock_resp.response = "I see an image"
        mock_resp.eval_count = 12
        mock_resp.done_reason = "stop"
        engine._client.generate.return_value = mock_resp
        result = engine.generate_response("What?", context="ctx", images=[b"img"])
        assert "image" in result.lower()

    def test_generate_response_error(self):
        engine = self._make_engine()
        engine._client.generate.side_effect = Exception("model 'x' not found (status code: 404)")
        engine.embedder = MagicMock()
        engine.embedder.get_embedding.return_value = [0.1]
        engine.vector_store = MagicMock()
        engine.vector_store.retrieve.return_value = []
        with patch("src.memory.chunking.chunk_text", return_value=["hi"]):
            result = engine.generate_response("Hi")
        assert result is None

    def test_generate_response_strict_prompt(self):
        engine = self._make_engine()
        mock_resp = MagicMock()
        mock_resp.response = "Strict result"
        mock_resp.eval_count = 5
        mock_resp.done_reason = "stop"
        engine._client.generate.return_value = mock_resp
        result = engine.generate_response("Do this", context="ctx", strict_prompt=True)
        assert result == "Strict result"

    def test_generate_response_dict_format(self):
        engine = self._make_engine()
        engine._client.generate.return_value = {
            "response": "Dict response",
            "eval_count": 10,
            "done_reason": "stop",
        }
        result = engine.generate_response("Test", context="ctx")
        assert result == "Dict response"

    def test_generate_response_transient_retry(self):
        engine = self._make_engine()
        mock_resp = MagicMock()
        mock_resp.response = "Recovered"
        mock_resp.eval_count = 5
        mock_resp.done_reason = "stop"
        engine._client.generate.side_effect = [
            Exception("500 internal server error"),
            mock_resp,
        ]
        with patch("time.sleep"):
            result = engine.generate_response("Hi", context="ctx")
        assert result == "Recovered"
