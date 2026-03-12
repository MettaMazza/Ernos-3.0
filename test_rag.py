import logging
from src.engines.rag_ollama import VectorEnhancedOllamaEngine
import pytest
from config import settings

logging.basicConfig(level=logging.INFO)

def test_engine():
    engine = VectorEnhancedOllamaEngine(settings.OLLAMA_CLOUD_MODEL)
    print("Engine initialized.")
    res = engine.generate_response(
        prompt="Search for latest breakthrough in solid state batteries",
        system_prompt="You are a helpful assistant.",
        images=None,
    )
    print(f"Result: {repr(res)}")

if __name__ == "__main__":
    test_engine()
