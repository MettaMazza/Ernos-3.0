"""Phase 4 polish tests for engine modules at 80-94% coverage.

Covers: engines/trace.py (CognitionTracer), engines/ollama.py, engines/rag_ollama.py
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ═══════════════════════════ CognitionTracer ═══════════════════════════
class TestCognitionTracer:
    def test_save_trace(self, tmp_path):
        from src.engines.trace import CognitionTracer
        bot = MagicMock()
        ct = CognitionTracer(bot)
        # save_trace(step, response, results, request_scope)
        ct.save_trace("analysis", "AI said hello", {"action": "greet"})
        assert True  # Execution completed without error

    def test_generate_fallback(self):
        from src.engines.trace import CognitionTracer
        bot = MagicMock()
        ct = CognitionTracer(bot)
        result = ct.generate_fallback("test query")
        assert isinstance(result, str)


# ═══════════════════════════ OllamaEngine ═══════════════════════════
class TestOllamaEngine:
    def test_basic_generation(self):
        from src.engines.ollama import OllamaEngine
        engine = OllamaEngine.__new__(OllamaEngine)
        engine._client = MagicMock()
        engine._client.generate = MagicMock(return_value={"response": "hello world"})
        engine._model = "test-model"
        # generate_response is sync, uses _client.generate
        result = engine.generate_response("say hi")
        assert "hello" in result

    def test_fallback_on_error(self):
        from src.engines.ollama import OllamaEngine
        engine = OllamaEngine.__new__(OllamaEngine)
        engine._client = MagicMock()
        engine._client.generate = MagicMock(side_effect=Exception("connection refused"))
        engine._model = "test-model"
        # Should return fallback message, not raise
        result = engine.generate_response("test prompt")
        assert isinstance(result, str)
        assert "failure" in result.lower() or "error" in result.lower()


# ═══════════════════════════ VectorEnhancedOllamaEngine ═══════════════════════════
class TestRAGOllamaEngine:
    def test_generate_basic(self):
        from src.engines.rag_ollama import VectorEnhancedOllamaEngine
        engine = VectorEnhancedOllamaEngine.__new__(VectorEnhancedOllamaEngine)
        engine._client = MagicMock()
        engine._client.generate = MagicMock(return_value={"response": "response"})
        engine._model = "test"
        engine.embedder = MagicMock()
        engine.embedder.get_embedding = MagicMock(return_value=[0.1] * 384)
        engine.vector_store = MagicMock()
        engine.vector_store.search = MagicMock(return_value=[])
        result = engine.generate_response("test")
        assert isinstance(result, str)
