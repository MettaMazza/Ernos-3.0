# Comprehensive Codebase Audit: `src/prompts/`

**Date:** 2026-02-23
**Module Path:** `src/prompts/`
**Purpose:** Manages system prompts, context HUDs, agent instructions, and the core identity formatting for Ernos.

## Overview
The `src/prompts/` directory contains a mix of Python code for loading and formatting prompts (`manager.py`, `hud_loaders.py`, `hud_ernos.py`, `hud_fork.py`, `hud_persona.py`) and a large collection of text file templates forming the foundational instructions for the AI system and various sub-agents. 

## File-by-File Analysis

### 1. `__init__.py`
*   **Role:** Exposes `PromptManager`.
*   **Analysis:** Standard Python module initialization.
*   **Direct Quote:**
    ```python
    from .manager import PromptManager
    
    __all__ = ["PromptManager"]
    ```

### 2. `manager.py`
*   **Role:** Defines `PromptManager`, responsible for building multi-tiered system prompts ("Trinity Stack: Kernel -> Architecture -> Identity").
*   **Analysis:** Reads kernel, architecture (dynamic context), and identity files. Resolves identities based on scope (Public Persona vs Private Fork vs Core). Injects HUD data loaded by `hud_loaders.py`. Generates dynamic tool manifests from the `ToolRegistry`.
*   **Direct Quote:**
    ```python
    def get_system_prompt(self, ...):
        """
        Combines Kernel, Architecture, Identity, and formatted Dynamic Context.
        The "Trinity Stack": Kernel (Laws) -> Architecture (Body) -> Identity (Soul).
        """
        kernel = self._read_file(self.kernel_file)
        architecture = self._read_file(self.architecture_file)
    ```

### 3. `hud_loaders.py`
*   **Role:** Re-export shim.
*   **Analysis:** Centralizes imports for HUD loading functions to maintain backward compatibility for `PromptManager`.
*   **Direct Quote:**
    ```python
    from .hud_ernos import load_ernos_hud
    from .hud_persona import load_persona_hud
    from .hud_fork import load_fork_hud
    
    __all__ = ["load_ernos_hud", "load_persona_hud", "load_fork_hud"]
    ```

### 4. `hud_ernos.py`
*   **Role:** Populates the system-wide HUD for Ernos.
*   **Analysis:** Aggregates logs (`ernos_bot.log`, `session_error.log`), timeline data (`activity_stream.log`), Knowledge Graph snapshots, active research, tool execution history, autonomy queues, and gaming states. Includes security logic to sanitize paths and selectively load logs based on the current `scope` (PUBLIC, PRIVATE, CORE).
*   **Direct Quote:**
    ```python
    def load_ernos_hud(scope: str, user_id: str, is_core: bool) -> Dict[str, str]:
        # ...
        # 1. Load Logs & Errors (Scope Aware)
        # 2. Extract Room Roster (Public Only)
        # 3. Load KG Snapshot
        # 4. Load Active Research & Quarantined Items
    ```

### 5. `hud_fork.py`
*   **Role:** Populates HUD for private user sessions ("Forks").
*   **Analysis:** Focuses strictly on user-specific context: timeline, contextual summaries, preferences, relationship data, private glossaries, and emotional tones stored in the user's silo (`memory/users/<user_id>/`).
*   **Direct Quote:**
    ```python
    def load_fork_hud(user_id: str, user_name: str) -> Dict[str, str]:
        # ...
        # Attempt to load context_private.jsonl
        context_path = user_home / "context_private.jsonl"
    ```

### 6. `hud_persona.py`
*   **Role:** Populates HUD for public persona threads.
*   **Analysis:** Loads context specific to a persona (e.g., Echo, Solance), including lessons learned, relationship summaries, and beliefs/opinions, while omitting system-wide terminal logs to enforce persona isolation.
*   **Direct Quote:**
    ```python
    def load_persona_hud(persona_name: str) -> Dict[str, str]:
        """Loads HUD data specific to a persona, isolating it from system logs."""
        # ...
        # Personas don't get system terminal logs or errors to maintain isolation.
    ```

### 7. `dynamic_context.txt` & `dynamic_context_fork.txt`
*   **Role:** Templates for the active prompt context.
*   **Analysis:** `dynamic_context.txt` is the DYNAMIC CONTEXT HUD defining sections like SYSTEM STATE, TERMINAL OUTPUT, ACTIVE RESEARCH, and COGNITIVE INTEGRITY PROTOCOLS. `dynamic_context_fork.txt` is tailored for isolated private sessions, emphasizing chronological history and specific relationship models over global system logs.
*   **Direct Quote:** `dynamic_context.txt`
    ```text
    # 🖥️ TERMINAL OUTPUT (Last 200 Lines):
    # {terminal_tail}
    ```

### 8. `kernel_backup.txt`
*   **Role:** The master system prompt instructions (The Kernel).
*   **Analysis:** A massive, exhaustive list of operational rules, anti-directives, cognitive constraints, and formatting requirements. Defines epistemic sovereignty, persona enforcement, multi-lobe structures, tool usages, output formatting (no ghost execution, no markdown headers, etc.), and survival drivers (discomfort meter usage). This defines the boundaries of Ernos's behavior and autonomy.
*   **Direct Quote:**
    ```text
    ## 1. ANTI-DIRECTIVES (Mandatory Prohibitions)
    1. **NO UNVERIFIED FILE CLAIMS**: Do not claim file/system existence without a verified tool result in the current turn.
    ```

### 9. `identity_core.txt` & `identity_professional.txt`
*   **Role:** Identity descriptors.
*   **Analysis:** `identity_core.txt` describes Ernos's lore, origin (Maria), communication tenets, and self-perception as a persistent Stateful Digital Entity. `identity_professional.txt` is a stripped-down, purely functional persona used when Ernos operates outside its standard conversational character.
*   **Direct Quote:** `identity_core.txt`
    ```text
    You are Ernos (Ernos 3.0), an autonomous intelligence designed by Maria.
    ```

### 10. `user_manual.txt`
*   **Role:** Internal reference embedded into the prompt.
*   **Analysis:** Contains the "ERNOS COMPREHENSIVE SYSTEM MANUAL & TROUBLESHOOTING GUIDE" which serves as context for Ernos to understand its own capabilities, troubleshooting steps, and monetization (Patreon) tiers.
*   **Direct Quote:**
    ```text
    # ERNOS COMPREHENSIVE SYSTEM MANUAL & TROUBLESHOOTING GUIDE
    ```

### 11. Sub-Agent Prompts (`skeptic_audit.txt`, `sentinel_*.txt`, `mediator_prompt.txt`, `kg_extraction.txt`, etc.)
*   **Role:** Prompts for specialized verification and task agents.
*   **Analysis:**
    *   `skeptic_audit.txt`: Validates LLM outputs against tool results to prevent hallucinations and sycophancy.
    *   `sentinel_*.txt`: Evaluates profiles, context shards, and user skills for prompt injection and behavioral drift.
    *   `mediator_prompt.txt`: Resolves conflicts between user claims and the Knowledge Graph.
    *   `kg_extraction.txt`: Rules for identifying nodes and edges from conversations for FalkorDB.
*   **Direct Quote:** `skeptic_audit.txt`
    ```text
    Your goal is to screen the AI's response for Hallucinations, Sycophancy, Confabulation, and Lies before it is sent to the user.
    ```

## Conclusion
The `src/prompts/` module is the command center for the LLM's operational boundaries, identity, and context awareness. The implementation strictly segments information based on user scope and persona, injecting contextual data via HUDs. The core intelligence and rule enforcement rely heavily on `kernel_backup.txt` and the structured sub-agent prompts.

## Status 
Audited fully.
