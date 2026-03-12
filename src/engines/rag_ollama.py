from .base import BaseEngine
from src.memory.vector import OllamaEmbedder, InMemoryVectorStore, BaseVectorStore
from .ollama import DormantAPIError
import logging
import ollama

logger = logging.getLogger("RAGOllama")

class VectorEnhancedOllamaEngine(BaseEngine):
    """
    RAG Engine that also respects system prompts.
    """
    def __init__(self, model_name: str, embedding_model: str = "nomic-embed-text", base_url: str = None):
        self._model = model_name
        self._client = ollama.Client(host=base_url) if base_url else ollama.Client()
        
        # Initialize RAG components
        self.embedder = OllamaEmbedder(model_name=embedding_model, base_url=base_url)
        self.vector_store = InMemoryVectorStore() 

    @property
    def name(self) -> str:
        return f"Ollama (Vector-Enhanced: {self._model})"

    @property
    def context_limit(self) -> int:
        from config import settings
        if self._model == settings.OLLAMA_CLOUD_MODEL:
            return settings.CONTEXT_CHAR_LIMIT_CLOUD
        return settings.CONTEXT_CHAR_LIMIT_LOCAL

    @property
    def _num_predict(self) -> int:
        """Max output tokens. Higher for cloud models, conservative for local."""
        from config import settings
        if self._model == settings.OLLAMA_CLOUD_MODEL:
            return getattr(settings, 'OUTPUT_TOKEN_LIMIT_CLOUD', 32768)
        return getattr(settings, 'OUTPUT_TOKEN_LIMIT_LOCAL', 8192)

    def add_knowledge(self, text: str, metadata: dict = None):
        # Chunk to prevent HTTP 500 without losing data
        from src.memory.chunking import chunk_text
        chunks = chunk_text(text)
        
        # Embed and store each chunk
        for chunk in chunks:
            embedding = self.embedder.get_embedding(chunk)
            if embedding:
                self.vector_store.add_element(chunk, embedding, metadata)
            logger.info(f"Added knowledge to vector store: {text[:30]}...")

    def generate_response(self, prompt: str, context: any = None, system_prompt: str = None, images: list[bytes] = None, strict_prompt: bool = False, caller: str = None) -> str:
        # 1. Determine Context
        # If context is provided (e.g. from Hippocampus), use it.
        # Otherwise, fall back to internal legacy RAG.
        context_str = ""
        
        if context and isinstance(context, str):
            context_str = context
            logger.info("Using external Hippocampus context.")
        else:
            # Legacy Internal RAG
            from src.privacy.scopes import PrivacyScope
            from src.memory.chunking import chunk_text
            # For queries, use first chunk only (most relevant)
            chunks = chunk_text(prompt)
            query_embedding = self.embedder.get_embedding(chunks[0])
            # Use OPEN scope for fallback (safe default)
            retrieved_docs = self.vector_store.retrieve(query_embedding, scope=PrivacyScope.OPEN, top_k=3) if query_embedding else []
            context_str = "\n".join([d['text'] for d in retrieved_docs])
        
        # 2. Augment Prompt with Context
        full_prompt = prompt
        if context_str:
            full_prompt = (
                f"Use the following context to answer the user's question.\n"
                f"Related Knowledge:\n{context_str}\n\n"
                f"Question: {prompt}\n"
                f"Answer:"
            )
            logger.info(f"Context injected: {len(context_str)} chars")
        
        # 3. Safety Check: Context Limit Management
        # If input is too large, use Ad-Hoc RAG (Chunk -> Embed -> Retrieve) instead of naive truncation.
        limit = self.context_limit
        if strict_prompt:
            limit = max(limit, 200000)
            logger.info(f"Strict prompt enabled. Bypassing Ad-Hoc RAG. New limit: {limit}")
        
        total_len = len(full_prompt) + (len(system_prompt) if system_prompt else 0)
        
        if total_len > limit:
            logger.warning(f"Input too large ({total_len} > {limit}). Engaging Ad-Hoc RAG Chunking...")
            
            # If we have a massive context, let's refine it
            if context_str and len(context_str) > (limit * 0.5):
                logger.info("Refining massive context via Ad-Hoc Vector Search...")
                from src.memory.chunking import chunk_text
                
                # 1. Create Temporary Vector Store
                metrics_store = InMemoryVectorStore()
                chunks = chunk_text(context_str)
                
                # 2. Embed Chunks (Batch process if possible, but loop for now)
                for chunk in chunks:
                    emb = self.embedder.get_embedding(chunk)
                    if emb:
                        metrics_store.add_element(chunk, emb, {})
                
                # 3. Retrieve relevant chunks for the *Prompt*
                prompt_emb = self.embedder.get_embedding(prompt)
                if prompt_emb:
                    # Retrieve top 5 or enough to fill 50% of context
                    relevant_chunks = metrics_store.query(prompt_emb, top_k=5)
                    # Reconstruct Context
                    new_context = "\n...\n".join([r['text'] for r in relevant_chunks])
                    
                    logger.info(f"Context reduced from {len(context_str)} to {len(new_context)} chars via RAG.")
                    context_str = new_context
                    
                    # 4. Rebuild Full Prompt with optimized context
                    full_prompt = (
                        f"Use the following context to answer the user's question.\n"
                        f"Related Knowledge:\n{context_str}\n\n"
                        f"Question: {prompt}\n"
                        f"Answer:"
                    )

            # Final Safety Truncation (if still too big after RAG, or if prompt itself was huge)
            total_len = len(full_prompt) + (len(system_prompt) if system_prompt else 0)
            if total_len > limit:
                 logger.warning("Input still too large after RAG. Applying safety truncation.")
                 sys_len = len(system_prompt) if system_prompt else 0
                 available = max(limit - sys_len - 5000, 5000)
                 full_prompt = full_prompt[:available] + "... [TRUNCATED]"

        # DEBUG: Dump full prompt to file to check for leaks
        try:
            with open("memory/debug_prompt_last.txt", "w", encoding="utf-8") as f:
                f.write(f"SYSTEM:\n{system_prompt}\n\nCONTEXT:\n{context_str}\n\nFULL PROMPT:\n{full_prompt}")
        except Exception as e:
            logger.warning(f"Suppressed {type(e).__name__}: {e}")

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = self._client.generate(
                    model=self._model, 
                    prompt=full_prompt,
                    system=system_prompt, # Injected here
                    images=images, # Multimodal support
                    context=[], # EXPLICITLY CLEAR CONTEXT to prevent leakage across turns
                    options={
                        "num_predict": self._num_predict,
                    }
                )
                # Extract text from response — handles both object and dict formats,
                # and thinking models that populate `thinking` instead of `response`.
                is_obj = not isinstance(response, dict)
                if is_obj:
                    result = response.response or getattr(response, 'thinking', '') or ''
                    eval_count = getattr(response, 'eval_count', '?')
                    done_reason = getattr(response, 'done_reason', '?')
                else:
                    result = response.get('response') or response.get('thinking', '') or ''
                    eval_count = response.get('eval_count', '?')
                    done_reason = response.get('done_reason', '?')

                prefix = f"[{caller}] " if caller else ""
                logger.info(f"{prefix}Ollama generate result: len={len(result)}, prompt_len={len(full_prompt)}, "
                            f"model={self._model}, eval_count={eval_count}, "
                            f"done_reason={done_reason}")
                if not result:
                    keys = dir(response) if is_obj else list(response.keys())
                    logger.warning(f"Ollama returned empty response. Full response keys/attrs: {keys}")
                return result
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate limit" in err_str.lower() or "too many requests" in err_str.lower():
                    logger.warning(f"Ollama cloud API rate limit hit (429): {e}")
                    raise DormantAPIError("Ollama cloud API rate limit reached.") from e
                is_transient = any(code in err_str for code in ["500", "502", "503", "timed out"])
                if is_transient and attempt < max_retries:
                    logger.warning(f"Ollama RAG transient error (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in 1s...")
                    import time
                    time.sleep(1)
                    continue
                # LOG THE NON-TRANSIENT ERROR SO WE CAN SEE IT!
                logger.error(f"Ollama Engine API Error: {e}")
                return None
        
        return None
