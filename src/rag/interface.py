from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseEmbedder(ABC):
    """Abstract base class for generating embeddings."""
    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        pass

class BaseVectorStore(ABC):
    """Abstract base class for vector storage and retrieval."""
    @abstractmethod
    def add_document(self, text: str, metadata: Dict[str, Any] = None):
        """Add a document to the store."""
        pass

    @abstractmethod
    def query(self, query_embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve relevant documents based on query embedding."""
        pass
