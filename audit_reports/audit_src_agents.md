# Comprehensive Codebase Audit: `src/agents/`

**Date:** 2026-02-23
**Module Path:** `src/agents/`
**Purpose:** Multi-agent orchestration system for Ernos providing sub-agent spawning, parallel tool execution, inter-agent communication, result aggregation, execution planning, model routing, and lifecycle management.

## Overview
The `src/agents/` directory is massive and highly sophisticated, enabling Ernos to break complex problems into DAG (Directed Acyclic Graph) sub-tasks, assign them to specialized LLMs, run them in parallel safely, and synthesize the results. This is the core cognitive routing architecture.

## File-by-File Analysis

### 1. `base.py`
*   **Role:** The genetic ancestor for all agents.
*   **Analysis:** Ensures all agents, regardless of specialization, pull from the same "Trinity Stack" of prompts (Kernel, Architecture, Identity) and have unified tool access.
*   **Direct Quote:**
    ```python
    def get_system_prompt(self, **kwargs) -> str:
        """
        Retrieves the Unified System Prompt (Kernel + Architecture + Identity).
        Injects the Trinity of Truth into every agent.
        """
    ```

### 2. `bus.py`
*   **Role:** `AgentBus`
*   **Analysis:** Implements a publish-subscribe message bus utilizing `asyncio.Queue` for inter-agent communication. It supports Publish/Subscribe, Direct messaging, Request/Response, and Fan-out patterns. Every message generates a UUID.
*   **Direct Quote:**
    ```python
    class AgentBus:
        """
        Central message bus for inter-agent communication.
        ...
        - Publish/Subscribe: one-to-many broadcast
        - Direct: one-to-one messaging
        - Request/Response: ask and wait for answer
    ```

### 3. `lifecycle.py`
*   **Role:** Centralized lifecycle management and telemetry.
*   **Analysis:** Acts as a singleton monitoring all agent activity. Tracks spawned vs completed vs failed counts, calculates success rates, monitors concurrent agents, and persists failure events to disk (`memory/core/agent_history.jsonl`) to survive reboots.
*   **Direct Quote:**
    ```python
    @dataclass
    class AgentMetrics:
        """Cumulative metrics for agent system."""
        total_spawned: int = 0
        total_completed: int = 0
        total_failed: int = 0
        ...
    ```

### 4. `parallel_executor.py`
*   **Role:** `ParallelToolExecutor`
*   **Analysis:** Analyzes proposed tool calls to determine if they can be run in parallel (e.g., read-only tools) or must be run sequentially (mutating tools). Uses a heuristic checking if tool names start with `get_`, `search_`, etc.
*   **Direct Quote:**
    ```python
    # Tools that are read-only and always safe to parallelize
    READONLY_TOOLS = {
        "search_web", "browse_site", "browse_interactive",
        ...
    }
    ```

### 5. `aggregator.py`
*   **Role:** `ResultAggregator`
*   **Analysis:** Takes results from multiple parallel agents and fuses them together. Supports multiple strategies: simple concatenation, deduplication (via Jaccard similarity), voting, LLM-based merging, and LLM-based hierarchical clustering.
*   **Direct Quote:**
    ```python
    @classmethod
    async def synthesize(cls, results: list[str], bot=None,
                         strategy: str = "llm_merge", ...)
        """
        Synthesize multiple result strings into a unified response.
        ...
        - concat: Simple concatenation with separators
        - deduplicate: Remove near-duplicate results
        - vote: Most common answer wins (for factual queries)
        ...
    ```

### 6. `planner.py`
*   **Role:** `ExecutionPlanner`
*   **Analysis:** Takes a complex user request and uses an LLM to decompose it into a JSON DAG (Directed Acyclic Graph) of distinct operational stages. Enforces that Stage 1 must involve multiple parallel research tasks.
*   **Direct Quote:**
    ```python
    "CRITICAL RULES:",
    "- You MUST create at least 2 stages",
    "- Stage 1 should gather/research (parallel tasks for different aspects)",
    "- Final stage should synthesize/combine all findings",
    ```

### 7. `preprocessor.py`
*   **Role:** `UnifiedPreProcessor`
*   **Analysis:** Acts as the "First Thought". Before a request reaches the primary agent loop, this module does cognitive triage using an LLM. It outputs RAW JSON assessing intent, complexity, reality-check requirements, required tool count, and potential adversarial input (sycophancy traps). Auto-escalates low credibility inputs.
*   **Direct Quote:**
    ```python
    # Auto-escalate: low credibility forces external verification
    if analysis.get("credibility_score", 1.0) < 0.4:
        analysis["reality_check"] = True
    ```

### 8. `router.py`
*   **Role:** `ModelRouter`
*   **Analysis:** Evaluates task keywords to route the prompt to the most optimized LLM backend. Routes fast tasks to `gemini-2.0-flash`, logic to `deepseek-r1`, and coding to `qwen2.5-coder`.
*   **Direct Quote:**
    ```python
    # Task type classification keywords
    TASK_SIGNATURES = {
        "web_search": ["search", "find", "lookup", "google", "browse", "news"],
        "code_generation": ["code", "implement", "program", "function", "class", "debug", "fix bug"],
    ```

### 9. `spawner.py`
*   **Role:** `AgentSpawner`
*   **Analysis:** The heavyweight orchestration engine. Spawns `SubAgent` instances which possess their own localized ReAct cognition loops. Heavily throttled (MAX_CONCURRENT_AGENTS = 5) specifically to prevent overwhelming local Ollama instances and crashing them. Supports various concurrency strategies.
*   **Direct Quote:**
    ```python
    # How many agents can call the LLM simultaneously.
    # Ollama returns empty responses when overwhelmed (100 concurrent → 70% empty).
    # 5 concurrent keeps Ollama healthy; all agents still run via semaphore queuing.
    MAX_CONCURRENT_AGENTS = 5
    ```

## Conclusion
The agent architecture is robust, utilizing dynamic model routing, semantic pre-processing triage, heuristic-based parallel tool execution, and complex multi-agent map-reduce topologies (`planner` + `spawner` + `aggregator`).

## Status
Audited fully.
