# Audit Report: `src/memory/` Vector & Epistemic Engines

## Overview
This report covers Tier 2 Vector Memory (Semantic Search) and the `MechIntuition` Epistemic Engine responsible for source provenance.

## 1. `vector.py` & `chroma_store.py`
- **Function**: Tier 2 Semantic Memory. Provides high-dimensional text embeddings and retrieval. `chroma_store.py` is the persistent production backend; `vector.py` provides an `InMemoryVectorStore` fallback.
- **Key Logic**:
  - `OllamaEmbedder`: Generates embeddings. If text exceeds 4000 chars, it automatically chunks the text and averages the resulting vectors to prevent HTTP 500 errors from the Ollama API.
  - **Privacy Enforcement (`retrieve`)**: 
    1. Fetches candidate documents.
    2. Runs `ScopeManager.check_access` to ensure the requested scope (e.g. `PUBLIC`) is allowed to see the document's scope (e.g. `PRIVATE`).
    3. If the document is `PRIVATE`, it strictly verifies that the `user_id` matches the document's `user_ids` metadata.
  - **Invalidation**: Supports soft-deletion (`invalidate_by_content` / `invalidate_by_id`) which flags vectors when the `CrossTierReconciler` detects a hallucination or contradiction.

## 2. `epistemic.py`
- **Function**: "MechIntuition". Provides self-awareness of *where* Ernos's knowledge comes from.
- **Key Logic**:
  - `EpistemicContext`: Tags all retrieved context with traceable markers before it hits the prompt (e.g., `[SRC:VS:user_1]`, `[SRC:KG:User_123->likes->dogs]`).
  - `introspect_claim`: An advanced tool that searches all 4 memory tiers (KG, Vector, Working, Lessons) for explicit evidence supporting or contradicting a given claim.
- **Quote**:
  ```python
      # Architecture Guide Compliance:
      # - This function RETRIEVES data, it does NOT classify.
      # - The LLM receives the evidence and makes the epistemic judgment.
  ```

## 3. `chunking.py`
- **Function**: Minor utility script.
- **Key Logic**: Safely splits strings > 8192 characters into chunks with a 200-character overlap to prevent token limit crashes during embedding.
