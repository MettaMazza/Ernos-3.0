# Audit Report: `src/memory/` Core Components

## Overview
The `src/memory/` subsystem is the most complex component of Ernos 3.0, mapping a multi-tiered architecture (Stream, Tape, Vector, Graph, Timeline) representing the AI's cognitive state.

## 1. `hippocampus.py`
- **Function**: The Central Nervous System. Orchestrates retrieval and storage across all memory tiers.
- **Key Logic**:
  - `observe()`: Ingests a new interaction, calculates a `salience_score`, pushes data to the `ContextStream` and `TapeMachine`, appends to the `Timeline`, queues the interaction for the `KGConsolidator`, and writes the raw turn to disk (e.g., `context_private.jsonl`).
  - `recall()`: Central retrieval function. Gathers context chunks across the Vector DB and Neo4j KG. Modifies response based on active `PersonaSession` and specific `PrivacyScope` boundaries.
  - **Reconciliation**: Actively detects LLM-driven conflicts between Vector and Graph data using `CrossTierReconciler`, triggering asynchronous `_background_invalidate` to self-heal vector hallucinations.
- **Quote**:
  ```python
              # ===== RESULTS-LEVEL SCOPE GATE (DEFENSE IN DEPTH) =====
              # Even if the graph query incorrectly returns PRIVATE data in PUBLIC scope
              # strip it here before it reaches the LLM.
              if scope.name == "PUBLIC" and graph_context:
                  # ...
  ```

## 2. `tape_machine.py`
- **Function**: Tier 1b "Cognitive Tape" — A Turing-machine style 3D spatial memory structure primarily used by the autonomous BFF loop.
- **Key Logic**:
  - Organizes `Cell` objects by `(X, Y, Z)` coordinates.
  - Exposes operators to the LLM (`op_seek`, `op_move`, `op_scan`, `op_read`, `op_write`, `op_delete`), enabling the agent to manually navigate its own state space.
  - Supports Darwinian Evolution: allows the LLM to call `op_edit_code` to mutate the Python source codebase directly, or `op_fork_tape` to trigger Sandbox cloning.
- **Quote**:
  ```python
      def op_edit_code(self, file_path: str, target: str, replacement: str) -> None:
          # Security Boundary: Restrict to src/ directory and user memory
          if not any(allowed in file_path for allowed in ["src/", "tests/", "memory/users/"]):
              raise TapeFaultError(f"EDIT_CODE Blocked: Path '{file_path}' is outside the mutable organism boundaries...")
  ```

## 3. `stream.py` & `working.py`
- **Function**: Tier 1a "Unified History". `stream.py` (`ContextStream`) is the modern replacement for the legacy `working.py`.
- **Key Logic**:
  - Maintains a discrete rolling window (last 50 turns).
  - Crucially, it tracks a concurrent `StateVector` representing the synthesized "Now" (a moving summary asynchronously updated by the LLM every turn).
  - Scope isolation is fiercely preserved: individual user DMs are scoped to vectors like `PRIVATE:12345` to prevent the LLM from conceptually blurring two private conversations.

## 4. `types.py`
- **Function**: Defines the structural layers (Enums) of the Neo4j Knowledge Graph.
- **Key Logic**:
  - Contains the 26 core cognitive layers (e.g. `NARRATIVE`, `CAUSAL`, `SYMBOLIC`, `EPISTEMIC`).
  - Instantiates a `DynamicLayerRegistry`, permitting Ernos to autonomously register new layers in the database if it determines the 26 built-in schemas are insufficient to model a user's world.
