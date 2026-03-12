"""
RAG Core — Re-exports from canonical memory.vector module.

The OllamaEmbedder and InMemoryVectorStore live in src/memory/vector.py
as the single source of truth. This module re-exports them for backward
compatibility with existing imports from src.rag.
"""
from src.memory.vector import OllamaEmbedder, InMemoryVectorStore, BaseEmbedder, BaseVectorStore

__all__ = ["OllamaEmbedder", "InMemoryVectorStore", "BaseEmbedder", "BaseVectorStore"]
