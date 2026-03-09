from .base import BaseEngine
from src.rag import OllamaEmbedder, InMemoryVectorStore
import logging
import os

logger = logging.getLogger("LlamaSteering")

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

class SteeringEngine(BaseEngine):
    """
    RAG + Steering Engine (Llama.cpp).
    """
    def __init__(self, model_path: str, control_vector_path: str = None, 
                 embedding_model: str = "nomic-embed-text", base_url: str = None, 
                 n_ctx: int = 2048):
        self._model_path = model_path
        self._control_vector_path = control_vector_path
        self._llm = None
        self._n_ctx = n_ctx
        
        self.embedder = OllamaEmbedder(model_name=embedding_model, base_url=base_url)
        self.vector_store = InMemoryVectorStore()
        
        if not Llama:
             logger.critical("llama-cpp-python is not installed! Steering engine disabled.")

    @property
    def name(self) -> str:
        return f"Llama Steering + RAG ({os.path.basename(self._model_path)})"

    @property
    def context_limit(self) -> int:
        from config import settings
        return settings.CONTEXT_CHAR_LIMIT_LOCAL

    def add_knowledge(self, text: str, metadata: dict = None):
        from src.memory.chunking import chunk_text
        chunks = chunk_text(text)
        
        for chunk in chunks:
            embedding = self.embedder.get_embedding(chunk)
            if embedding:
                self.vector_store.add_document(chunk, embedding, metadata)

    def _ensure_loaded(self):
        if self._llm: return
        if not os.path.exists(self._model_path):
             logger.error(f"Model not found: {self._model_path}")
             return

        logger.info(f"Loading model for steering: {self._model_path}")
        try:
            kwargs = { "model_path": self._model_path, "n_ctx": self._n_ctx, "verbose": False }
            self._llm = Llama(**kwargs)
        except Exception as e:
            logger.error(f"Failed: {e}")
            self._llm = None

    def generate_response(self, prompt: str, context: any = None, system_prompt: str = None, images: list[bytes] = None) -> str:
        self._ensure_loaded()
        if not self._llm: return "Error: Steering Model not loaded."

        if images:
            logger.info(f"Steering engine received {len(images)} image(s) — forwarding to llama.cpp")

        # 1. RAG Retrieval
        from src.memory.chunking import chunk_text
        chunks = chunk_text(prompt)
        query_embedding = self.embedder.get_embedding(chunks[0])
        retrieved_docs = self.vector_store.query(query_embedding, top_k=3) if query_embedding else []
        context_str = "\n".join([d['text'] for d in retrieved_docs])
        
        # 2. Construct Full Prompt with System + Context
        # Structure:
        # [System Prompt]
        # [Context]
        # [User Query]
        
        final_prompt = ""
        if system_prompt:
            final_prompt += f"{system_prompt}\n\n"
            
        if context_str:
            final_prompt += (
                f"Context data:\n{context_str}\n\n"
                f"Question: {prompt}\nAnswer:"
            )
        else:
            final_prompt += f"Question: {prompt}\nAnswer:"

        # 3. Generate
        output = self._llm(
            final_prompt,
            max_tokens=512,
            stop=["User:", "\n\n", "Question:"],
            echo=False
        )
        return output['choices'][0]['text'].strip()
