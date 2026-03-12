# Audit Report: `src/engines/` (Cognition & Inference Core)

## Overview
The `src/engines/` directory forms the cognitive core of Ernos. It isolates inference logic (`BaseEngine`, `OllamaEngine`, `SteeringEngine`) from the ReAct loop executor (`CognitionEngine` and its extracted submodules). It defines how prompts are assembled, how context is chunked and retrieved, how fallback retry loops are enforced, and how tools are parsed. It also contains the `evolution_sandbox.py` system for auto-mutating the codebase.

---

## File-by-File Analysis

### 1. Base Engines (`base.py`, `ollama.py`, `rag_ollama.py`, `steering.py`)
**Functionality:** Abstract factory pattern for LLM execution. 
**Key Mechanisms:**
- **`OllamaEngine`:** Direct inference using the `ollama` python client. Supports multimodal `images` arrays.
- **`VectorEnhancedOllamaEngine` (`rag_ollama.py`):** An implementation of the engine that forcibly injects RAG context.
  - **Ad-Hoc RAG:** Contains a massive safety net. If context exceeds the model's `context_limit`, it *dynamically chunk-embeds its own context* and queries it against the prompt to shrink the payload down to 5 chunks, avoiding `HTTP 500` overflow errors.
  - **Context Clearing:** Crucially, it forces `context=[]` into the Ollama client to prevent internal state leakage across turns.
- **`SteeringEngine`:** A stub for `llama_cpp` execution allowing prompt injection at the tensor/control-vector level.
**Quote (rag_ollama.py):**
```python
if total_len > limit:
    logger.warning(f"Input too large ({total_len} > {limit}). Engaging Ad-Hoc RAG Chunking...")
    # ... Creates InMemoryVectorStore() just for this massive prompt to shrink it ...
    relevant_chunks = metrics_store.query(prompt_emb, top_k=5)
```

### 2. Cognition Execution Loop (`cognition*.py`)
**Functionality:** The ReAct (Reasoning + Acting) loop state machine. Previously a massive monolith, it has been appropriately modularized.
**Key Mechanisms:**
- **`cognition.py`:** Holds the `CognitionEngine.process()` entrypoint. Manages a `while True:` loop executing tools and feeding outputs back to the LLM until `__CONTINUE__` is no longer returned by the evaluation layer.
- **`cognition_context.py`:** Generates the massive system prompt block, injecting semantic defenses, root-level constraints, and knowledge retrieval hints.
- **`cognition_tools.py`:** Executes functions requested by the LLM. 
- **`cognition_retry.py`:** Houses `forced_retry_loop()`, engaging when the `Skeptic` or `Superego` lobes block an output. If retries hit exhaustion limits, it gracefully returns a static fallback.
- **`cognition_tracker.py`:** A UI module. Posts and updates Discord embeds in real-time. Equivalent to a "thinking" spinner, displaying emoji labels for tools as they execute (e.g. "🔍 Searching the web").
**Quote (cognition.py):**
```python
def _generate_fallback(self, history):
    """Extracts the last meaningful response if loop fails."""
    # Try to extract actual response text (not tool calls)
    # Look for text between [STEP X ASSISTANT]: and [TOOL: or end
    pattern = r'\[STEP \d+ ASSISTANT\]:\s*(.*?)(?=\[TOOL:|$|\[STEP)'
```

### 3. Parse & Trace (`tool_parser.py`, `trace.py`)
**Functionality:**
- **`tool_parser.py`:** A custom state-machine parser replacing Python's `eval()`. Iterates character by character to extract `key="value"` pairs from LLM generation, securely handling escaped quotes and triple-quoted blocks.
- **`trace.py`:** Handles "Mind Channel" transparency. Broadcasts internal reasoning steps to Discord *unless* the context is `PRIVATE`, in which case a "privacy firewall" blocks it to prevent DM leakage.
**Quote (trace.py):**
```python
# PRIVACY FIREWALL: Block PRIVATE reasoning from public mind channel
if request_scope == "PRIVATE":
    logger.debug(f"Skipping mind broadcast for PRIVATE scope (Step {step})")
    return
```

### 4. Persona Map (`persona_map.py`)
**Functionality:** A static dictionary mapping `GraphLayer` enumerations to exact string prompts injected into the ReAct loop.
**Key Mechanisms:**
- Maps 26 distinct internal identities (e.g., `GraphLayer.NARRATIVE` -> "You are a Storyteller..."). This allows Ernos to dynamically shift cognitive focus based on user intent.

### 5. Evolution Sandbox (`evolution_sandbox.py`)
**Functionality:** The "Darwin-Godel Machine" mutating compiler. Allows Ernos to rewrite its own source code, test it in an isolated `.sandbox/` clone, and merge it if tests pass.
**Key Mechanisms:**
- Clones `src/` and `tests/` to a temporary directory.
- Prevents mutation of core memory data or the Kernel Layer (predator trap prevention).
- Runs `pytest` evaluating Darwinian fitness. If it hangs or fails, the mutation dies.
**Quote:**
```python
def _enforce_security_perimeters(self, file_path: str):
    """
    Darwin-Godel Machine Rule: The organism cannot mutate its memory data or user logs.
    PREDATOR/PREY TRAP PREVENTION: The organism is forbidden from mutating the Core Kernel Layer.
    """
```

---

## Technical Debt & Observations
1.  **Complexity Density:** `CognitionEngine.process()` orchestrates context, execution, retries, parsing, tracking, and trace logging all in a tight `while` loop. Despite file modularization, the coupling remains tight.
2.  **Ad-Hoc RAG Necessity:** The `rag_ollama.py` defensive chunking mechanism is incredibly robust for preventing token exhaustion, demonstrating that the engine frequently deals with massive document dumps hitting the prompt.
3.  **No `eval()` Security Win:** `tool_parser.py` explicitly avoiding Python `eval()` is a massive security victory for safe command extraction from raw LLM output.
